#!/usr/bin/env python3
from flask import Flask, render_template, request, redirect, url_for, flash, session, make_response, jsonify, abort
import subprocess
import os
from dotenv import load_dotenv
import time
import logging
import threading

# Estado global para saber si hay una actualización en curso
global_adblock_update_status = {'updating': False, 'last_result': None, 'last_error': None}

logging.Formatter.converter = time.localtime
from hostberry_config import HostBerryConfig
import time
from werkzeug.utils import secure_filename
import re
from flask_babel import Babel, gettext as _
import logging
from logging.handlers import RotatingFileHandler
import psutil
import datetime
import pytz
import subprocess
import socket
from collections import deque
from flask_wtf.csrf import CSRFProtect
from flask_wtf import FlaskForm
from wtforms import BooleanField, SelectField
import logging
import logging.config
import os
import secrets
import json
from cryptography.fernet import Fernet
from base64 import b64encode, b64decode

# Initialize environment and logging
if not os.path.exists('.env'):
    with open('.env', 'w') as f:
        secret_key = secrets.token_hex(32)
        f.write(f"FLASK_SECRET_KEY={secret_key}\n")

load_dotenv()

secret_key = os.getenv('FLASK_SECRET_KEY')
if not secret_key or len(secret_key) < 32:
    secret_key = secrets.token_hex(32)
    with open('.env', 'a') as f:
        f.write(f"FLASK_SECRET_KEY={secret_key}\n")

app = Flask(__name__)
app.config['SECRET_KEY'] = secret_key
csrf = CSRFProtect(app)

# Configure secure session settings
app.config.update(
    SESSION_COOKIE_SECURE=False,  # Cambia a True en producción con HTTPS
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE='Lax',
    PERMANENT_SESSION_LIFETIME=86400,
    BABEL_DEFAULT_LOCALE='es',
    BABEL_TRANSLATION_DIRECTORIES='translations',
    BABEL_SUPPORTED_LOCALES=['en', 'es'],
    SESSION_COOKIE_DOMAIN=None,
    SESSION_COOKIE_PATH=None,
    WTF_CSRF_ENABLED=True,
    WTF_CSRF_CHECK_DEFAULT=True,
    WTF_CSRF_HEADERS=['X-CSRFToken'],
    WTF_CSRF_TIME_LIMIT=3600
)

# Configuración avanzada de logging
log_dir = 'logs'
if not os.path.exists(log_dir):
    os.makedirs(log_dir)

# Configuración detallada
logging_config = {
    'version': 1,
    'formatters': {
        'detailed': {
            'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            'datefmt': '%Y-%m-%d %H:%M:%S'
        },
    },
    'handlers': {
        'file': {
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': f'{log_dir}/hostberry.log',
            'maxBytes': 1000000,
            'backupCount': 5,
            'formatter': 'detailed',
            'level': 'DEBUG'
        },
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'detailed',
            'level': 'INFO'
        }
    },
    'root': {
        'handlers': ['file', 'console'],
        'level': 'DEBUG'
    }
}

logging.config.dictConfig(logging_config)
logger = logging.getLogger(__name__)
logger.info('Sistema de logging configurado correctamente')

# Initialize Babel
babel = Babel(app)

# Version-agnostic locale selector
try:
    # Flask-Babel 2.x style
    @babel.localeselector
    def get_locale():
        pass
except AttributeError:
    try:
        # Flask-Babel 1.x style
        @babel.localeselector
        def get_locale():
            pass
    except AttributeError:
        # Fallback implementation
        def get_locale():
            return app.config['BABEL_DEFAULT_LOCALE']

# Actual implementation
def get_locale():
    try:
        # First check session (set by /set_language route)
        if 'language' in session:
            return session['language']
            
        # Fall back to browser preference
        browser_lang = request.accept_languages.best_match(app.config['BABEL_SUPPORTED_LOCALES'])
        if browser_lang:
            return browser_lang
            
        # Finally use default locale
        return app.config['BABEL_DEFAULT_LOCALE']
    except Exception as e:
        app.logger.error(f"Locale selection error: {str(e)}")
        return app.config['BABEL_DEFAULT_LOCALE']

def get_logs():
    """Read and parse application logs from the last 24 hours"""
    log_file = 'logs/hostberry.log'  # Use relative path to match logging config
    logs = []
    try:
        # Calculate cutoff time (24 hours ago)
        cutoff_time = datetime.datetime.now() - datetime.timedelta(hours=24)
        
        with open(log_file, 'r') as f:
            for line in f.readlines()[-100:]:  # Check last 100 lines for recent entries
                line = line.strip()
                if line:
                    # Parse timestamp and message
                    parts = line.split(' ', 3)  # Split into timestamp, level, logger, message
                    if len(parts) >= 4:
                        try:
                            log_time = datetime.datetime.strptime(parts[0] + ' ' + parts[1], 
                                                               '%Y-%m-%d %H:%M:%S,%f')
                            if log_time > cutoff_time:
                                logs.append({
                                    'timestamp': ' '.join(parts[:2]),
                                    'message': parts[3]
                                })
                        except ValueError:
                            # Fallback for lines with invalid timestamps
                            logs.append({
                                'timestamp': '',
                                'message': line
                            })
                    else:
                        logs.append({
                            'timestamp': '',
                            'message': line
                        })
    except FileNotFoundError:
        pass
    return list(reversed(logs))  # Show newest first

@app.context_processor
def inject_get_locale():
    return dict(get_locale=get_locale)

@app.route('/set_language/<lang>')
def set_language(lang):
    if lang in ['en', 'es']:
        session['language'] = lang
        # Force client-side refresh by adding cache-control headers
        response = redirect(request.args.get('next') or request.referrer or url_for('index'))
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response.headers['Pragma'] = 'no-cache'
        return response

@app.route('/check_lang')
def check_lang():
    return {
        'current_lang': get_locale(),
        'session': dict(session),
        'babel_config': app.config['BABEL_SUPPORTED_LOCALES']
    }

VPN_CONF_PATH = '/etc/openvpn/client.conf'

# === Seguridad: IP Whitelist y bloqueo por intentos fallidos ===
from functools import wraps
from collections import defaultdict

FAILED_ATTEMPTS = defaultdict(int)
BLOCKED_IPS = set()

@app.before_request
def restrict_ip_whitelist():
    config = get_config().get_current_config()
    ip_whitelist = config.get('IP_WHITELIST', '').strip()
    if ip_whitelist:
        allowed_ips = [ip.strip() for ip in ip_whitelist.split(',') if ip.strip()]
        if request.remote_addr not in allowed_ips:
            return render_template('blocked.html', reason=_('Your IP is not allowed.')), 403

@app.before_request
def block_on_failed_attempts():
    config = get_config().get_current_config()
    max_attempts = int(config.get('FAILED_ATTEMPTS_LIMIT', 5))
    ip = request.remote_addr
    if ip in BLOCKED_IPS:
        return render_template('blocked.html', reason=_('Too many failed attempts.')), 403
    if request.endpoint == 'security_config' and request.method == 'POST':
        if 'ssh_port' in request.form:
            ssh_port = request.form.get('ssh_port')
            try:
                port = int(ssh_port)
                if port < 1 or port > 65535:
                    raise ValueError
            except Exception:
                FAILED_ATTEMPTS[ip] += 1
                if FAILED_ATTEMPTS[ip] >= max_attempts:
                    BLOCKED_IPS.add(ip)
                flash(_('Invalid SSH port. Attempt counted as failed.'), 'danger')
                return redirect(url_for('security_config'))

@app.route('/blocked')
def blocked():
    reason = request.args.get('reason', _('Access denied.'))
    return render_template('blocked.html', reason=reason), 403

# Inicialización al inicio del archivo
config = HostBerryConfig()

def get_config():
    global config
    return config

def get_system_stats(force_refresh=False):
    """Obtener estadísticas del sistema"""
    stats = {}
    try:
        # CPU
        stats['cpu_usage'] = round(psutil.cpu_percent(), 1)
        
        # Temperatura
        stats['cpu_temp'] = get_cpu_temp()
        
        # Memoria
        mem = psutil.virtual_memory()
        stats['memory_usage'] = round(mem.percent, 1)
        
        # Red (KB/s)
        net = psutil.net_io_counters()
        stats['network_sent'] = round(net.bytes_sent / 1024, 1)
        stats['network_recv'] = round(net.bytes_recv / 1024, 1)
        
    except Exception as e:
        print(f"Error getting system stats: {e}")
    
    return stats

def get_network_interface():
    """Obtener la interfaz de red activa"""
    try:
        result = subprocess.run(['ip', 'route', 'show', 'default'], capture_output=True, text=True)
        interface = result.stdout.split('dev ')[1].split(' ')[0] if result.returncode == 0 else 'eth0'
        return interface
    except:
        return 'eth0'

def get_ip_address():
    """Obtener la dirección IP"""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(('8.8.8.8', 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except:
        return '127.0.0.1'

def get_wifi_ssid():
    """Obtener el SSID de la red WiFi"""
    try:
        # Primero verificar si wlan0 existe y está activa
        result = subprocess.run(['ip', 'link', 'show', 'wlan0'], capture_output=True, text=True)
        if result.returncode != 0 or 'state DOWN' in result.stdout:
            return None
            
        # Obtener SSID actual
        result = subprocess.run(['nmcli', '-t', '-f', 'NAME,TYPE,DEVICE', 'connection', 'show', '--active'], 
                              capture_output=True, text=True)
        if result.returncode == 0:
            for line in result.stdout.splitlines():
                if 'wifi' in line.lower():
                    return line.split(':')[0]
        return None
    except Exception as e:
        app.logger.error(f"Error getting WiFi SSID: {str(e)}")
        return None

def is_wifi_connected():
    """Verificar si está conectado a WiFi"""
    try:
        # Primero verificar si wlan0 existe y está activa
        result = subprocess.run(['ip', 'link', 'show', 'wlan0'], capture_output=True, text=True)
        if result.returncode != 0 or 'state DOWN' in result.stdout:
            return False
            
        # Verificar conexión actual
        result = subprocess.run(['nmcli', '-t', '-f', 'NAME,TYPE,DEVICE', 'connection', 'show', '--active'], 
                              capture_output=True, text=True)
        if result.returncode == 0:
            for line in result.stdout.splitlines():
                if 'wifi' in line.lower():
                    return True
        return False
    except Exception as e:
        app.logger.error(f"Error checking WiFi connection: {str(e)}")
        return False

def get_cpu_temp():
    """Obtener temperatura del CPU"""
    try:
        # Primero intentar con psutil
        temps = psutil.sensors_temperatures()
        if 'cpu_thermal' in temps:
            return round(temps['cpu_thermal'][0].current, 1)
            
        # Alternativa para Raspberry Pi
        with open('/sys/class/thermal/thermal_zone0/temp', 'r') as f:
            return round(float(f.read()) / 1000, 1)
    except:
        return None

@app.route('/')
def index():
    """
    Página principal con estadísticas del sistema
    """
    try:
        # Debug logging
        app.logger.debug(f"Index route called. Session: {dict(session)}, Args: {dict(request.args)}")
        
        # Check if language was just changed
        lang_changed = request.args.get('lang_changed', False)
        
        stats = get_system_stats()
        
        log_file = 'logs/hostberry.log'
        log_lines = []
        logs_available = False
        
        try:
            if os.path.isfile(log_file):
                with open(log_file, 'r') as f:
                    raw_lines = f.readlines()[-100:]
                    logs = []
                    for line in reversed(raw_lines):
                        line = line.strip()
                        if line:
                            # Parse timestamp and message
                            parts = line.split(' ', 2)
                            if len(parts) >= 3:
                                logs.append({'timestamp': ' '.join(parts[:2]), 'message': parts[2]})
                            else:
                                logs.append({'timestamp': '', 'message': line})
                logs_available = True
        except IOError:
            pass
        
        current_config = config.get_current_config()
        # Obtener información de red
        try:
            interface = subprocess.check_output(['hostname', '-I'], text=True).strip().split()[0]
        except Exception:
            interface = 'Desconocido'
        try:
            ip_addr = subprocess.check_output(['hostname', '-I'], text=True).strip().split()[0]
        except Exception:
            ip_addr = 'Desconocida'
        try:
            ssid = subprocess.check_output(['iwgetid', '-r'], text=True).strip()
        except Exception:
            ssid = ''
        try:
            hostapd_status = subprocess.check_output(['systemctl', 'is-active', 'hostapd'], text=True).strip()
        except Exception:
            hostapd_status = 'unknown'

        response = make_response(render_template(
            'index.html',
            title=_('Index'),
            stats=stats,
            logs=logs,
            current_lang=get_locale(),
            logs_available=logs_available,
            adblock_enabled=current_config.get('ADBLOCK_ENABLED', False),
            vpn_enabled=current_config.get('VPN_ENABLED', False),
            firewall_enabled=current_config.get('FIREWALL_ENABLED', False),
            network_interface=interface,
            local_ip=ip_addr,
            wifi_ssid=ssid,
            hostapd_status=hostapd_status
        ))
        
        # Add cache control headers to prevent caching
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
        return response
    except Exception as e:
        app.logger.error(f"Error in index route: {str(e)}")
        flash(_('Error loading system information'), 'danger')
        
        # For now, just return the error page without redirect
        return render_template('error.html', error=str(e)), 500

@app.route('/network', methods=['GET', 'POST'])
def network_config():
    if request.method == 'POST':
        new_config = {
            'NETWORK_INTERFACE': request.form.get('interface'),
            'IP_ADDRESS': request.form.get('ip_address')
        }
        config.update_config(new_config)
        flash(_('Network configuration updated successfully!'), 'success')
        return redirect(url_for('network_config'))
    
    # Get current network status
    try:
        interface = subprocess.check_output(['hostname', '-I'], text=True).strip().split()[0]
        speed_test = subprocess.check_output(['speedtest-cli', '--simple'], text=True)
        upload = re.search(r'Upload: (\d+\.\d+)', speed_test).group(1)
        download = re.search(r'Download: (\d+\.\d+)', speed_test).group(1)
    except Exception as e:
        interface = 'Unknown'
        upload = '0'
        download = '0'
    
    return render_template(
        'network.html',
        config=config.get_current_config(),
        network_interfaces=['eth0', 'wlan0', 'tun0'],
        network_status={
            'interface': interface,
            'ip_address': interface,
            'upload': upload,
            'download': download
        }
    )

class SecurityConfigForm(FlaskForm):
    enable_firewall = BooleanField('Enable Firewall')
    block_icmp = SelectField('ICMP Protection', choices=[('1', 'Block Ping Requests'), ('0', 'Allow Ping Requests')])
    timezone = SelectField('Timezone')
    time_format = SelectField('Time Format')

@app.route('/security_config', methods=['GET', 'POST'])
def security_config():
    global config
    form = SecurityConfigForm()
    
    if request.method == 'POST':
        try:
            firewall_enabled = 'enable_firewall' in request.form
            block_icmp = request.form.get('block_icmp') == '1'
            timezone = request.form.get('timezone')
            time_format = request.form.get('time_format')
            # Cambiar zona horaria del sistema si es válida
            if timezone in pytz.all_timezones:
                try:
                    subprocess.run(['timedatectl', 'set-timezone', timezone], check=True)
                    app.logger.info(f'Zona horaria del sistema cambiada a {timezone}')
                except Exception as e:
                    app.logger.error(f'Error al cambiar la zona horaria del sistema: {e}')
            success = config.update_config({
                'FIREWALL_ENABLED': firewall_enabled,
                'BLOCK_ICMP': block_icmp,
                'TIMEZONE': timezone,
                'TIME_FORMAT': time_format
            })
            # Actualizar el formato de logs en caliente
            for handler in logging.getLogger().handlers:
                if hasattr(handler, 'formatter') and handler.formatter:
                    handler.formatter.datefmt = time_format
            if success:
                flash(_('Configuración guardada correctamente'), 'success')
                return redirect(url_for('security_config'))
            else:
                flash(_('Error al guardar la configuración'), 'danger')
        except Exception as e:
            flash(_('Error al procesar el formulario: %(error)s', error=str(e)), 'danger')
    
    current_config = config.get_current_config()
    # Get current security status
    try:
        rules_count = int(subprocess.check_output(['iptables', '-L', '-n', '--line-numbers']).decode().count('\n')) - 2
        blocked_ips = int(subprocess.check_output(['iptables', '-L', 'INPUT', '-n', '-v']).decode().count('DROP'))
        last_attack = None  # This would come from log parsing in a real implementation
    except Exception as e:
        rules_count = 0
        blocked_ips = 0
        last_attack = None
    
    return render_template(
        'security.html',
        form=form,
        config=current_config,
        security_status={
            'rules_count': rules_count,
            'blocked_ips': blocked_ips,
            'last_attack': last_attack,
            'last_check': datetime.datetime.utcnow()
        },
        timezones=pytz.all_timezones,
        time_formats=['%Y-%m-%d %H:%M', '%d/%m/%Y %H:%M', '%m/%d/%Y %I:%M %p'],
        pytz=pytz
    )

@app.route('/security/logs')
def security_logs():
    try:
        # Sample log data - replace with actual log retrieval
        logs = [
            {"timestamp": "2025-05-03 10:30", "ip": "192.168.1.100", "action": "Blocked", "reason": "Port scan detected"},
            {"timestamp": "2025-05-03 09:15", "ip": "10.0.0.5", "action": "Allowed", "reason": "Normal traffic"}
        ]
        return render_template('security_logs.html', logs=logs)
    except Exception as e:
        app.logger.error(f"Error retrieving security logs: {str(e)}")
        return render_template('security_logs.html', logs=[])

@app.route('/security/save', methods=['POST'])
def save_security_settings():
    try:
        # Get form data
        settings = {
            'SESSION_COOKIE_SECURE': request.form.get('cookie_secure') == 'true',
            'SESSION_COOKIE_HTTPONLY': request.form.get('cookie_httponly') == 'true',
            'SESSION_COOKIE_SAMESITE': request.form.get('cookie_samesite', 'Lax'),
            'PERMANENT_SESSION_LIFETIME': int(request.form.get('session_lifetime', 86400))
        }
        
        # Update runtime configuration
        for key, value in settings.items():
            app.config[key] = value
            
        # Save to persistent config file
        config_path = os.path.join(os.path.dirname(__file__), 'config.json')
        with open(config_path, 'w') as f:
            json.dump(settings, f, indent=4)
            
        # Update .env file with timestamp
        with open('.env', 'a') as f:
            f.write(f'\n# Security settings updated at {datetime.datetime.now()}\n')
            
        flash(_('Security settings saved successfully'), 'success')
        return jsonify({'success': True})
        
    except Exception as e:
        app.logger.error(f'Error saving security settings: {str(e)}')
        flash(_('Failed to save security settings'), 'danger')
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/monitoring', methods=['GET', 'POST'])
def monitoring_config():
    if request.method == 'POST':
        new_config = {
            'MONITORING_ENABLED': request.form.get('enable_monitoring') == 'on',
            'MONITORING_INTERVAL': request.form.get('update_interval')
        }
        config.update_config(new_config)
        flash(_('Monitoring configuration updated successfully!'), 'success')
        return redirect(url_for('monitoring_config'))
    
    # Get current system stats
    try:
        cpu = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory().percent
        disk = psutil.disk_usage('/').percent
        uptime = datetime.datetime.now() - datetime.datetime.fromtimestamp(psutil.boot_time())
        uptime_str = str(uptime).split('.')[0]  # Remove microseconds
    except Exception as e:
        cpu = 0
        memory = 0
        disk = 0
        uptime_str = 'Unknown'
    
    return render_template(
        'monitoring.html',
        config=config.get_current_config(),
        monitoring_stats={
            'cpu': cpu,
            'memory': memory,
            'disk': disk,
            'uptime': uptime_str
        }
    )

@app.route('/api/monitoring/stats')
def monitoring_stats_api():
    try:
        # Uptime
        uptime = int(time.time() - psutil.boot_time())

        # CPU Stats
        cpu_usage = psutil.cpu_percent(interval=1)
        cpu_temp = get_cpu_temp()
        cpu_cores = psutil.cpu_count()
        cpu_freq = psutil.cpu_freq().current if hasattr(psutil.cpu_freq(), 'current') else 0

        # Memory Stats
        memory = psutil.virtual_memory()
        mem_total = round(memory.total / (1024**3), 2)
        mem_used = round(memory.used / (1024**3), 2)
        mem_free = round(memory.free / (1024**3), 2)
        mem_usage = memory.percent

        # Disk Stats
        disk = psutil.disk_usage('/')
        disk_total = round(disk.total / (1024**3), 2)
        disk_used = round(disk.used / (1024**3), 2)
        disk_free = round(disk.free / (1024**3), 2)
        disk_usage = disk.percent

        # Network Stats
        net_io = psutil.net_io_counters()
        net_interface = get_network_interface()
        net_ip = get_ip_address()
        
        # Calculate network speed (bytes per second)
        net_upload = round(net_io.bytes_sent / 1024, 2)
        net_download = round(net_io.bytes_recv / 1024, 2)

        return jsonify({
            'uptime': uptime,
            'cpu': {
                'usage': cpu_usage,
                'temperature': cpu_temp,
                'cores': cpu_cores,
                'frequency': round(cpu_freq, 2)
            },
            'memory': {
                'total': f"{mem_total} GB",
                'used': f"{mem_used} GB",
                'free': f"{mem_free} GB",
                'usage': mem_usage
            },
            'disk': {
                'total': f"{disk_total} GB",
                'used': f"{disk_used} GB",
                'free': f"{disk_free} GB",
                'usage': disk_usage
            },
            'network': {
                'ip': net_ip,
                'interface': net_interface,
                'upload': f"{net_upload} KB/s",
                'download': f"{net_download} KB/s"
            }
        })
    except Exception as e:
        app.logger.error(f"Error getting monitoring stats: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/apply', methods=['POST'])
def apply_config():
    try:
        config_data = request.get_json()
        results = {}
        
        # Define script paths
        scripts = {
            'network': '/home/blag0rag/Desktop/hostberry/scripts/network.sh',
            'security': '/home/blag0rag/Desktop/hostberry/scripts/security.sh',
            'monitoring': '/home/blag0rag/Desktop/hostberry/scripts/monitoring.sh'
        }
        
        for feature, script_path in scripts.items():
            if config_data.get(f'apply_{feature}', False):
                if os.path.exists(script_path):
                    try:
                        result = subprocess.run(
                            [script_path],
                            check=True,
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE,
                            text=True
                        )
                        results[feature] = {
                            'success': True,
                            'output': result.stdout
                        }
                    except subprocess.CalledProcessError as e:
                        results[feature] = {
                            'success': False,
                            'error': e.stderr
                        }
                else:
                    results[feature] = {
                        'success': False,
                        'error': f'Script not found at {script_path}'
                    }
                    
        return jsonify({
            'status': 'success',
            'results': results
        })
        
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

def configure_vpn_routing():
    """Configura el enrutamiento para que todo el tráfico pase por la VPN"""
    try:
        # Obtener la interfaz de red principal
        route_cmd = subprocess.run(['ip', 'route', 'show', 'default'], capture_output=True, text=True)
        if route_cmd.returncode != 0 or not route_cmd.stdout.strip():
            app.logger.error(f"Error ejecutando 'ip route show default': {route_cmd.stderr}")
            raise Exception("No se pudo obtener la ruta por defecto")

        # Buscar gateway e interfaz de manera robusta
        default_gateway = None
        default_interface = None
        for line in route_cmd.stdout.strip().split('\n'):
            parts = line.split()
            if 'via' in parts and 'dev' in parts:
                try:
                    default_gateway = parts[parts.index('via') + 1]
                    default_interface = parts[parts.index('dev') + 1]
                    break
                except Exception as e:
                    app.logger.error(f"Error parseando línea de ruta: {line} - {e}")
        if not default_gateway or not default_interface:
            app.logger.error(f"No se pudo encontrar gateway o interfaz en la ruta: {route_cmd.stdout}")
            raise Exception("Formato de ruta por defecto inválido")
        
        app.logger.info(f"Gateway por defecto: {default_gateway}, Interfaz: {default_interface}")
        
        # Guardar la configuración original
        with open('/etc/hostberry/original_routes.txt', 'w') as f:
            f.write(f"GATEWAY={default_gateway}\n")
            f.write(f"INTERFACE={default_interface}\n")
        
        # Verificar que tun0 existe y está UP antes de modificar rutas
        tun_status = subprocess.run(['ip', 'link', 'show', 'tun0'], capture_output=True, text=True)
        if tun_status.returncode != 0 or 'state DOWN' in tun_status.stdout:
            app.logger.error(f"tun0 no existe o está DOWN: {tun_status.stdout}")
            raise Exception("La interfaz tun0 no está activa. Verifica la conexión OpenVPN.")
        
        # Eliminar la ruta por defecto actual
        subprocess.run(['ip', 'route', 'del', 'default'], check=True)
        
        # Añadir ruta por defecto a través de tun0
        subprocess.run(['ip', 'route', 'add', 'default', 'dev', 'tun0'], check=True)
        
        # Mantener ruta al servidor VPN a través de la interfaz original
        subprocess.run(['ip', 'route', 'add', default_gateway, 'dev', default_interface], check=True)
        
        # Configurar iptables para el kill switch
        # Limpiar reglas existentes
        subprocess.run(['iptables', '-F'], check=True)
        subprocess.run(['iptables', '-X'], check=True)
        
        # Permitir tráfico local
        subprocess.run(['iptables', '-A', 'INPUT', '-i', 'lo', '-j', 'ACCEPT'], check=True)
        subprocess.run(['iptables', '-A', 'OUTPUT', '-o', 'lo', '-j', 'ACCEPT'], check=True)
        
        # Permitir tráfico en la interfaz VPN
        subprocess.run(['iptables', '-A', 'INPUT', '-i', 'tun+', '-j', 'ACCEPT'], check=True)
        subprocess.run(['iptables', '-A', 'OUTPUT', '-o', 'tun+', '-j', 'ACCEPT'], check=True)
        
        # Permitir tráfico DNS
        subprocess.run(['iptables', '-A', 'OUTPUT', '-p', 'udp', '--dport', '53', '-j', 'ACCEPT'], check=True)
        subprocess.run(['iptables', '-A', 'INPUT', '-p', 'udp', '--sport', '53', '-j', 'ACCEPT'], check=True)
        
        # Permitir tráfico establecido y relacionado
        subprocess.run(['iptables', '-A', 'INPUT', '-m', 'state', '--state', 'ESTABLISHED,RELATED', '-j', 'ACCEPT'], check=True)
        subprocess.run(['iptables', '-A', 'OUTPUT', '-m', 'state', '--state', 'ESTABLISHED,RELATED', '-j', 'ACCEPT'], check=True)
        
        # Permitir tráfico hacia el servidor VPN a través de la interfaz original
        subprocess.run(['iptables', '-A', 'OUTPUT', '-o', default_interface, '-d', default_gateway, '-j', 'ACCEPT'], check=True)
        
        # Bloquear todo el demás tráfico
        subprocess.run(['iptables', '-P', 'INPUT', 'DROP'], check=True)
        subprocess.run(['iptables', '-P', 'OUTPUT', 'DROP'], check=True)
        subprocess.run(['iptables', '-P', 'FORWARD', 'DROP'], check=True)
        
        # Habilitar el reenvío de IP
        with open('/proc/sys/net/ipv4/ip_forward', 'w') as f:
            f.write('1\n')
        
        # Configurar reglas de NAT
        subprocess.run(['iptables', '-t', 'nat', '-A', 'POSTROUTING', '-o', 'tun0', '-j', 'MASQUERADE'], check=True)
        
        app.logger.info("Configuración de enrutamiento VPN completada")
        return True
        
    except Exception as e:
        app.logger.error(f"Error configurando enrutamiento VPN: {str(e)}")
        return False

def restore_original_routing():
    """Restaura la configuración de red original"""
    try:
        # Intentar desactivar la interfaz tun0 primero
        tun0_down_result = subprocess.run(['ip', 'link', 'set', 'tun0', 'down'], check=False, capture_output=True, text=True)
        if tun0_down_result.returncode == 0:
            app.logger.info("Interfaz tun0 desactivada correctamente.")
        else:
            # No es necesariamente un error crítico si tun0 no existe o no se puede bajar, así que solo lo registramos.
            app.logger.warning(f"No se pudo desactivar la interfaz tun0 o ya estaba desactivada. Salida: {tun0_down_result.stderr or tun0_down_result.stdout}")

        # Leer la configuración original
        if not os.path.exists('/etc/hostberry/original_routes.txt'):
            raise Exception("No se encontró la configuración original")
            
        original_config = {}
        with open('/etc/hostberry/original_routes.txt', 'r') as f:
            for line in f:
                key, value = line.strip().split('=')
                original_config[key] = value
        
        # Eliminar la ruta por defecto actual
        subprocess.run(['ip', 'route', 'del', 'default'], check=False)
        
        # Restaurar la ruta original
        subprocess.run([
            'ip', 'route', 'add', 'default',
            'via', original_config['GATEWAY'],
            'dev', original_config['INTERFACE']
        ], check=True)
        
        # Limpiar reglas de iptables
        subprocess.run(['iptables', '-F'], check=True)
        subprocess.run(['iptables', '-X'], check=True)
        subprocess.run(['iptables', '-t', 'nat', '-F'], check=True)
        
        # Restaurar políticas por defecto
        subprocess.run(['iptables', '-P', 'INPUT', 'ACCEPT'], check=True)
        subprocess.run(['iptables', '-P', 'OUTPUT', 'ACCEPT'], check=True)
        subprocess.run(['iptables', '-P', 'FORWARD', 'ACCEPT'], check=True)
        
        # Deshabilitar el reenvío de IP
        with open('/proc/sys/net/ipv4/ip_forward', 'w') as f:
            f.write('0\n')
        
        app.logger.info("Configuración de red original restaurada")
        return True
        
    except Exception as e:
        app.logger.error(f"Error restaurando configuración original: {str(e)}")
        return False

# Modificar la función vpn_config existente para incluir la configuración de enrutamiento
@app.route('/api/vpn/config', methods=['POST'])
def vpn_config_api():
    try:
        # Verificar si se proporcionó un archivo
        if 'vpn_file' not in request.files:
            return jsonify({'success': False, 'error': 'No se proporcionó archivo de configuración'}), 400

        file = request.files['vpn_file']
        if not file or not file.filename:
            return jsonify({'success': False, 'error': 'No se seleccionó archivo'}), 400

        # Verificar extensión del archivo
        if not file.filename.endswith(('.ovpn', '.conf')):
            return jsonify({'success': False, 'error': 'Tipo de archivo inválido. Use .ovpn o .conf'}), 400

        # Crear directorio si no existe
        vpn_dir = '/etc/openvpn'
        if not os.path.exists(vpn_dir):
            os.makedirs(vpn_dir, mode=0o755)

        # Guardar credenciales
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        
        if username and password:
            auth_file = os.path.join(vpn_dir, 'auth.txt')
            try:
                # Verificar permisos del directorio
                if not os.access(vpn_dir, os.W_OK):
                    return jsonify({
                        'success': False, 
                        'error': f'No se tienen permisos de escritura en {vpn_dir}'
                    }), 500

                # Guardar credenciales
                with open(auth_file, 'w') as f:
                    f.write(f"{username}\n{password}\n")
                
                # Verificar que se guardaron correctamente
                if not os.path.exists(auth_file):
                    return jsonify({
                        'success': False, 
                        'error': f'Error al guardar credenciales en {auth_file}'
                    }), 500
                
                # Establecer permisos
                os.chmod(auth_file, 0o600)
                
                # Verificar permisos
                if oct(os.stat(auth_file).st_mode)[-3:] != '600':
                    return jsonify({
                        'success': False, 
                        'error': f'No se pudieron establecer los permisos correctos en {auth_file}'
                    }), 500
                
                app.logger.info(f"Credenciales guardadas correctamente en {auth_file}")
            except Exception as e:
                app.logger.error(f"Error al guardar credenciales: {str(e)}")
                return jsonify({
                    'success': False, 
                    'error': f'Error al guardar credenciales: {str(e)}'
                }), 500

        # Guardar archivo de configuración
        config_path = os.path.join(vpn_dir, 'client.conf')
        try:
            # Verificar permisos del directorio
            if not os.access(vpn_dir, os.W_OK):
                return jsonify({
                    'success': False, 
                    'error': f'No se tienen permisos de escritura en {vpn_dir}'
                }), 500

            file.save(config_path)
            
            # Verificar que se guardó correctamente
            if not os.path.exists(config_path):
                return jsonify({
                    'success': False, 
                    'error': f'Error al guardar el archivo de configuración en {config_path}'
                }), 500
            
            # Establecer permisos
            os.chmod(config_path, 0o644)
            
            # Verificar permisos
            if oct(os.stat(config_path).st_mode)[-3:] != '644':
                return jsonify({
                    'success': False, 
                    'error': f'No se pudieron establecer los permisos correctos en {config_path}'
                }), 500
            
            app.logger.info(f"Archivo de configuración guardado correctamente en {config_path}")
        except Exception as e:
            app.logger.error(f"Error al guardar archivo de configuración: {str(e)}")
            return jsonify({
                'success': False, 
                'error': f'Error al guardar archivo de configuración: {str(e)}'
            }), 500

        # Verificar y actualizar configuración
        try:
            with open(config_path, 'r') as f:
                config_content = f.read()

            # Eliminar todas las líneas auth-user-pass existentes (para evitar duplicados o errores)
            import re
            config_lines = config_content.splitlines()
            original_lines = list(config_lines) # Copia para comparar si hay cambios
            
            # Asegurar que auth-user-pass apunte a /etc/openvpn/auth.txt si existe
            auth_file_path = '/etc/openvpn/auth.txt'
            auth_line_found = False
            new_config_lines = []
            for line in config_lines:
                if re.match(r'^\s*auth-user-pass(\s|$)', line):
                    if os.path.exists(auth_file_path):
                        new_config_lines.append(f'auth-user-pass {auth_file_path}')
                        auth_line_found = True
                    # Si auth.txt no existe, eliminamos la línea para evitar errores de OpenVPN
                    # y se registrará un warning.
                else:
                    new_config_lines.append(line)

            if not auth_line_found and os.path.exists(auth_file_path):
                new_config_lines.append(f'auth-user-pass {auth_file_path}')
            elif not os.path.exists(auth_file_path):
                app.logger.warning(f"El archivo de credenciales {auth_file_path} no existe. " 
                                   f"La directiva 'auth-user-pass' no se añadirá o se eliminará si existía.")

            config_content = '\n'.join(new_config_lines) + '\n'

            # Añadir directivas comunes si no existen
            common_directives = {
                # 'redirect-gateway def1': "Añadida configuración de enrutamiento redirect-gateway.",
                'dhcp-option DNS 8.8.8.8': "Añadida configuración de DNS 8.8.8.8.",
                'dhcp-option DNS 8.8.4.4': "Añadida configuración de DNS 8.8.4.4.",
                # 'block-ipv6': "Añadida configuración para bloquear IPv6.",
                'script-security 2': "Añadida configuración script-security 2.",
                'up /etc/openvpn/update-resolv-conf': "Añadida configuración up script para DNS.",
                'down /etc/openvpn/update-resolv-conf': "Añadida configuración down script para DNS."
            }

            # No añadiremos redirect-gateway def1 ni block-ipv6 automáticamente
            # para dar más control al usuario sobre su configuración original.
            # Solo nos aseguramos de los scripts de DNS y script-security.

            # Eliminar route-nopull si está presente, ya que interfiere con redirect-gateway
            if 'route-nopull' in config_content:
                config_content = config_content.replace('route-nopull', '')
                app.logger.info("Eliminada opción route-nopull del archivo de configuración.")

            # Añadir directivas necesarias si no están presentes
            for directive, log_message in common_directives.items():
                if directive.split()[0] not in config_content: # Comprobar por la directiva base
                    config_content += f'{directive}\n'
                    app.logger.info(log_message)

            # Guardar los cambios en el archivo de configuración
            if config_content.strip() != '\n'.join(original_lines).strip():
                with open(config_path, 'w') as f:
                    f.write(config_content)
                app.logger.info(f"Archivo de configuración OpenVPN '{config_path}' actualizado.")
        except Exception as e:
            app.logger.error(f"Error al actualizar configuración OpenVPN: {str(e)}")
            return jsonify({
                'success': False,
                'error': f'Error al actualizar configuración OpenVPN: {str(e)}'
            }), 500

        # Verificar si el servicio OpenVPN está instalado
        try:
            subprocess.run(['which', 'openvpn'], check=True, capture_output=True)
        except subprocess.CalledProcessError:
            return jsonify({'success': False, 'error': 'OpenVPN no está instalado'}), 500

        # Verificar estado actual
        try:
            result = subprocess.run(['systemctl', 'is-active', 'openvpn'], capture_output=True, text=True)
            is_active = result.returncode == 0
        except Exception as e:
            app.logger.warning(f"Error checking OpenVPN status with systemctl: {e}")
            is_active = False

        if is_active:
            # Detener VPN y restaurar configuración original
            subprocess.run(['systemctl', 'stop', 'openvpn'], check=True)
            # Esperar a que tun0 desaparezca (máx 10s)
            for _ in range(20):
                tun_status = subprocess.run(['ip', 'link', 'show', 'tun0'], capture_output=True, text=True)
                if tun_status.returncode != 0:
                    break  # tun0 ya no existe
                time.sleep(0.5)
            # Restaurar rutas aunque tun0 no exista
            if restore_original_routing():
                return jsonify({'success': True, 'message': 'VPN desconectada y configuración original restaurada'})
            else:
                return jsonify({'success': False, 'error': 'Error restaurando la configuración original'}), 500
        else:
            # Iniciar VPN y esperar a que tun0 esté UP (máx 15s)
            subprocess.run(['systemctl', 'start', 'openvpn'], check=True)
            tun_up = False
            for _ in range(30):
                tun_status = subprocess.run(['ip', 'link', 'show', 'tun0'], capture_output=True, text=True)
                if tun_status.returncode == 0 and 'state UP' in tun_status.stdout:
                    tun_up = True
                    break
                time.sleep(0.5)
            if not tun_up:
                app.logger.error('tun0 no está UP tras iniciar OpenVPN')
                return jsonify({'success': False, 'error': 'OpenVPN no conectó correctamente: tun0 no está UP'}), 500
            if configure_vpn_routing():
                return jsonify({'success': True, 'message': 'VPN conectada y enrutamiento configurado'})
            else:
                return jsonify({'success': False, 'error': 'Error configurando el enrutamiento VPN'}), 500
                
    except Exception as e:
        app.logger.error(f"Error en toggle_vpn: {str(e)}")
        return jsonify({'success': False, 'error': f'Error interno en toggle_vpn: {str(e)}'}), 500

@app.route('/api/vpn/status')
def vpn_status():
    try:
        # Obtener IP pública por defecto
        public_ip = None
        try:
            result = subprocess.run(['curl', '-s', 'https://api.ipify.org'], capture_output=True, text=True)
            if result.returncode == 0 and result.stdout.strip():
                public_ip = result.stdout.strip()
        except:
            pass

        # Verificar si OpenVPN está ejecutándose
        result = subprocess.run(['systemctl', 'is-active', 'openvpn'], capture_output=True, text=True)
        is_active = result.returncode == 0

        # Obtener IP VPN si está conectado
        vpn_ip = None
        config_file = None
        if is_active:
            try:
                # Obtener el archivo de configuración usado
                config_file = '/etc/openvpn/client.conf'
                if not os.path.exists(config_file):
                    config_file = None

                # Intentar obtener la IP de la VPN de múltiples formas
                # 1. Usar ip addr show tun0
                result = subprocess.run(['ip', 'addr', 'show', 'tun0'], capture_output=True, text=True)
                if result.returncode == 0:
                    ip_match = re.search(r'inet (\d+\.\d+\.\d+\.\d+)', result.stdout)
                    if ip_match:
                        vpn_ip = ip_match.group(1)
                
                # 2. Si no se encontró IP, intentar con ip route
                if not vpn_ip:
                    result = subprocess.run(['ip', 'route', 'show', 'default'], capture_output=True, text=True)
                    if result.returncode == 0:
                        # Buscar la ruta que usa tun0
                        for line in result.stdout.splitlines():
                            if 'tun0' in line:
                                ip_match = re.search(r'via (\d+\.\d+\.\d+\.\d+)', line)
                                if ip_match:
                                    vpn_ip = ip_match.group(1)
                                    break
                
                # 3. Si aún no se encontró IP, intentar con curl a través de tun0
                if not vpn_ip:
                    try:
                        # Usar curl con la interfaz tun0 específicamente
                        result = subprocess.run(['curl', '--interface', 'tun0', '-s', 'https://api.ipify.org'], 
                                             capture_output=True, text=True)
                        if result.returncode == 0 and result.stdout.strip():
                            vpn_ip = result.stdout.strip()
                    except:
                        pass
                
                # 4. Si aún no se encontró IP, intentar con ifconfig
                if not vpn_ip:
                    try:
                        result = subprocess.run(['ifconfig', 'tun0'], capture_output=True, text=True)
                        if result.returncode == 0:
                            ip_match = re.search(r'inet (\d+\.\d+\.\d+\.\d+)', result.stdout)
                            if ip_match:
                                vpn_ip = ip_match.group(1)
                    except:
                        pass
                
                # 5. Si aún no se encontró IP, verificar el log de OpenVPN
                if not vpn_ip:
                    log_file = '/etc/openvpn/openvpn.log'
                    if os.path.exists(log_file):
                        with open(log_file, 'r') as f:
                            log_content = f.read()
                            ip_match = re.search(r'ifconfig.*?(\d+\.\d+\.\d+\.\d+)', log_content)
                            if ip_match:
                                vpn_ip = ip_match.group(1)
                
                # 6. Si aún no se encontró IP, verificar el estado de la conexión
                if not vpn_ip:
                    try:
                        result = subprocess.run(['openvpn', '--status', '/etc/openvpn/openvpn.log', '10'], 
                                             capture_output=True, text=True)
                        if result.returncode == 0:
                            ip_match = re.search(r'ifconfig.*?(\d+\.\d+\.\d+\.\d+)', result.stdout)
                            if ip_match:
                                vpn_ip = ip_match.group(1)
                    except:
                        pass
                
                # Si después de todos los intentos no se encontró la IP, verificar si la interfaz existe
                if not vpn_ip:
                    result = subprocess.run(['ip', 'link', 'show', 'tun0'], capture_output=True, text=True)
                    if result.returncode != 0:
                        app.logger.warning("La interfaz tun0 no existe")
                    elif 'state DOWN' in result.stdout:
                        app.logger.warning("La interfaz tun0 está en estado DOWN")
                    else:
                        app.logger.warning("No se pudo obtener la IP de la VPN a pesar de que la interfaz existe y está UP")
            except Exception as e:
                app.logger.error(f"Error al obtener IP VPN: {str(e)}")

        # Verificar estado del Kill Switch
        killswitch_enabled = False
        try:
            result = subprocess.run(['iptables', '-L', 'INPUT', '-n'], capture_output=True, text=True)
            if result.returncode == 0:
                # Si hay reglas de DROP en INPUT y OUTPUT, el Kill Switch está activo
                input_drop = 'DROP' in result.stdout
                result = subprocess.run(['iptables', '-L', 'OUTPUT', '-n'], capture_output=True, text=True)
                output_drop = 'DROP' in result.stdout
                killswitch_enabled = input_drop and output_drop
        except:
            pass

        return jsonify({
            'status': 'Conectado' if is_active else 'Desconectado',
            'public_ip': public_ip or '-',
            'vpn_ip': vpn_ip or '-',
            'config_file': config_file or '-',
            'killswitch_enabled': killswitch_enabled
        })
    except Exception as e:
        app.logger.error(f"Error al obtener estado VPN: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/vpn', methods=['GET', 'POST'])
def vpn_page():
    return render_template('vpn.html')

@app.route('/vpn/toggle', methods=['POST'])
def toggle_vpn_connection():
    try:
        # Toggle VPN connection logic here
        flash(_('VPN connection toggled successfully'), 'success')
    except Exception as e:
        app.logger.error(f"VPN toggle error: {e}")
        flash(_('Error toggling VPN connection'), 'danger')
    return redirect(url_for('vpn_page'))


@app.route('/adblock', methods=['GET', 'POST'])
def adblock_config():
    global global_adblock_update_status
    if request.method == 'POST':
        current_config = config.get_current_config()
        new_config = {
            'ADBLOCK_ENABLED': request.form.get('adblock_enabled') == 'on',
            'ADBLOCK_UPDATE_FREQUENCY': request.form.get('update_frequency', 'weekly')
        }
        if request.form.get('action') == 'update_lists':
            selected_lists = request.form.getlist('selected_lists')
            new_config['ADBLOCK_LISTS'] = selected_lists
            new_config['ADBLOCK_ENABLED'] = current_config.get('ADBLOCK_ENABLED', False)
            if config.update_config(new_config):
                script_path = '/usr/local/bin/adblock.sh'
                if os.path.exists(script_path):
                    def run_adblock_update():
                        global global_adblock_update_status
                        global_adblock_update_status['updating'] = True
                        global_adblock_update_status['last_error'] = None
                        try:
                            subprocess.run(['sed', '-i', '/# AdBlock Start/,/# AdBlock End/d', '/etc/hosts'], check=True)
                            result = subprocess.run([script_path, '--lists'] + selected_lists, capture_output=True, text=True)
                            global_adblock_update_status['last_result'] = result.stdout
                            if result.returncode != 0:
                                global_adblock_update_status['last_error'] = result.stderr
                        except Exception as e:
                            global_adblock_update_status['last_error'] = str(e)
                        global_adblock_update_status['updating'] = False
                    threading.Thread(target=run_adblock_update, daemon=True).start()
                    flash('Block lists update started in background. Please refresh statistics after a while.', 'info')
                else:
                    flash('AdBlock script not found', 'danger')
            else:
                flash('Error updating configuration', 'danger')
        else:
            if 'ADBLOCK_LISTS' not in current_config:
                new_config['ADBLOCK_LISTS'] = config.DEFAULT_CONFIG['ADBLOCK_LISTS']
            else:
                new_config['ADBLOCK_LISTS'] = current_config['ADBLOCK_LISTS']
            if config.update_config(new_config):
                # Si se desactiva AdBlock, ejecuta el script de limpieza
                if not new_config['ADBLOCK_ENABLED']:
                    script_path = '/usr/local/bin/adblock.sh'
                    if os.path.exists(script_path):
                        def run_adblock_disable():
                            try:
                                subprocess.run([script_path, '--disable'], check=True)
                            except Exception as e:
                                app.logger.error(f"Error disabling AdBlock: {str(e)}")
                        threading.Thread(target=run_adblock_disable, daemon=True).start()
                        flash('AdBlock desactivado. Las listas han sido eliminadas del hosts.', 'info')
                    else:
                        flash('AdBlock script not found', 'danger')
                else:
                    # Si se activa AdBlock, vuelve a aplicar las listas seleccionadas
                    script_path = '/usr/local/bin/adblock.sh'
                    selected_lists = new_config.get('ADBLOCK_LISTS', [])
                    if os.path.exists(script_path) and new_config['ADBLOCK_ENABLED'] and selected_lists:
                        def run_adblock_enable():
                            try:
                                subprocess.run(['sed', '-i', '/# AdBlock Start/,/# AdBlock End/d', '/etc/hosts'], check=True)
                                subprocess.run([script_path, '--lists'] + selected_lists, check=True)
                            except Exception as e:
                                app.logger.error(f"Error enabling AdBlock: {str(e)}")
                        threading.Thread(target=run_adblock_enable, daemon=True).start()
                        flash('AdBlock activado. Las listas seleccionadas han sido aplicadas.', 'info')
                    else:
                        flash('Configuration updated successfully', 'success')
            else:
                flash('Error updating configuration', 'danger')
        return redirect(url_for('adblock_config'))
    
    # Obtener estadísticas SIEMPRE tras cada GET o POST
    def recalculate_adblock_stats():
        stats = {'domains_blocked': 0, 'rules_active': 0, 'lists_active': 0}
        try:
            with open('/etc/hosts', 'r') as f:
                hosts_content = f.read()
                rules_count = sum(1 for line in hosts_content.splitlines() if line.strip().startswith('0.0.0.0'))
                stats['domains_blocked'] = rules_count
                stats['rules_active'] = rules_count
            # Añadir número de listas activas
            current_config = config.get_current_config()
            stats['lists_active'] = len(current_config.get('ADBLOCK_LISTS', []))
            stats_file = '/etc/hostberry/adblock/stats.json'
            os.makedirs(os.path.dirname(stats_file), exist_ok=True)
            with open(stats_file, 'w') as f:
                json.dump(stats, f)
            app.logger.info(f"AdBlock stats: {stats}")
        except Exception as e:
            app.logger.error(f"Error reading/updating AdBlock stats: {str(e)}")
        return stats
    stats = recalculate_adblock_stats()
    # Leer última actualización
    last_updated = None
    try:
        last_updated_file = '/etc/hostberry/adblock/last_updated'
        if os.path.exists(last_updated_file):
            with open(last_updated_file, 'r') as f:
                last_updated = f.read().strip()
    except Exception as e:
        app.logger.error(f"Error reading last update time: {str(e)}")
    
    # Obtener configuración actual
    current_config = config.get_current_config()
    
    # Asegurarse de que ADBLOCK_LISTS existe en la configuración
    if 'ADBLOCK_LISTS' not in current_config:
        current_config['ADBLOCK_LISTS'] = config.DEFAULT_CONFIG['ADBLOCK_LISTS']
    
    # Obtener las listas seleccionadas actualmente
    selected_lists = current_config.get('ADBLOCK_LISTS', [])
    
    # Asegurarse de que todas las listas por defecto estén presentes en la configuración
    all_lists = list(set(config.DEFAULT_CONFIG['ADBLOCK_LISTS']))
    current_config['ADBLOCK_LISTS'] = all_lists
    
    return render_template('adblock.html',
                         config=current_config,
                         stats=stats,
                         last_updated=last_updated,
                         update_frequency=current_config.get('ADBLOCK_UPDATE_FREQUENCY', 'weekly'),
                         selected_lists=selected_lists)

@app.route('/adblock/update', methods=['POST'])
def adblock_update():
    global global_adblock_update_status
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': 'No data provided'}), 400
        current_config = config.get_current_config()
        if data.get('action') == 'update_lists':
            selected_lists = data.get('lists', [])
            if not selected_lists:
                return jsonify({'success': False, 'error': 'No lists selected'}), 400
            new_config = {'ADBLOCK_LISTS': selected_lists}
            if 'ADBLOCK_ENABLED' in current_config:
                new_config['ADBLOCK_ENABLED'] = current_config['ADBLOCK_ENABLED']
            if config.update_config(new_config):
                script_path = '/usr/local/bin/adblock.sh'
                if os.path.exists(script_path):
                    def run_adblock_update_api():
                        global global_adblock_update_status
                        global_adblock_update_status['updating'] = True
                        global_adblock_update_status['last_error'] = None
                        try:
                            with open('/etc/hosts', 'r') as f:
                                hosts_content = f.readlines()
                            filtered_content = [line for line in hosts_content if not line.startswith('0.0.0.0')]
                            with open('/etc/hosts', 'w') as f:
                                f.writelines(filtered_content)
                            result = subprocess.run([script_path, '--lists'] + selected_lists, capture_output=True, text=True)
                            global_adblock_update_status['last_result'] = result.stdout
                            if result.returncode != 0:
                                global_adblock_update_status['last_error'] = result.stderr
                        except Exception as e:
                            global_adblock_update_status['last_error'] = str(e)
                        global_adblock_update_status['updating'] = False
                    threading.Thread(target=run_adblock_update_api, daemon=True).start()
                    return jsonify({'success': True, 'message': 'Update started in background'})
                else:
                    return jsonify({'success': False, 'error': f'Script not found at {script_path}'}), 404
            else:
                return jsonify({'success': False, 'error': 'Failed to update configuration'}), 500
        script_path = '/usr/local/bin/adblock.sh'
        if os.path.exists(script_path):
            current_config = config.get_current_config()
            block_lists = current_config.get('ADBLOCK_LISTS', [])
            def run_adblock_update_normal():
                global global_adblock_update_status
                global_adblock_update_status['updating'] = True
                global_adblock_update_status['last_error'] = None
                try:
                    result = subprocess.run([script_path, '--lists'] + block_lists, capture_output=True, text=True)
                    global_adblock_update_status['last_result'] = result.stdout
                    if result.returncode != 0:
                        global_adblock_update_status['last_error'] = result.stderr
                except Exception as e:
                    global_adblock_update_status['last_error'] = str(e)
                global_adblock_update_status['updating'] = False
            threading.Thread(target=run_adblock_update_normal, daemon=True).start()
            return jsonify({'success': True, 'message': 'Update started in background'})
        else:
            return jsonify({'success': False, 'error': f'Script not found at {script_path}'}), 404
    except Exception as e:
        app.logger.error(f"AdBlock update error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500
    except Exception as e:
        app.logger.error(f"AdBlock update error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/wireguard', methods=['GET', 'POST'])
def wireguard_config():
    status = None
    ip = None
    peers = []
    interface_active = False

    if request.method == 'POST':
        action = request.form.get('action')
        try:
            if action == 'up':
                subprocess.run(
                    ["sudo", "wg-quick", "up", "wg0"],
                    check=True,
                    capture_output=True,
                    text=True
                )
                flash(_('WireGuard interface activated'), 'success')
            elif action == 'down':
                subprocess.run(
                    ["sudo", "wg-quick", "down", "wg0"],
                    check=True,
                    capture_output=True,
                    text=True
                )
                flash(_('WireGuard interface deactivated'), 'success')
            elif 'wg_file' in request.files:
                file = request.files['wg_file']
                if file and file.filename.endswith('.conf'):
                    config_path = '/etc/wireguard/wg0.conf'
                    file.save(config_path)
                    flash(_('WireGuard configuration saved'), 'success')
        except subprocess.CalledProcessError as e:
            flash(_('Error: %(error)s', error=e.stderr), 'danger')
        except Exception as e:
            flash(_('Unexpected error: %(error)s', error=str(e)), 'danger')

    # Obtener estado actual
    try:
        status_output = subprocess.check_output(
            ["sudo", "wg", "show", "wg0"],
            text=True
        )
        status = status_output
        interface_active = True
        
        # Obtener dirección IP
        ip_output = subprocess.check_output(
            ["ip", "addr", "show", "wg0"],
            text=True
        )
        ip_match = re.search(r'inet (\d+\.\d+\.\d+\.\d+)', ip_output)
        if ip_match:
            ip = ip_match.group(1)
            
        # Parsear información de peers
        peer_pattern = r'peer: (.+?)\n.*?endpoint: (.+?)\n.*?allowed ips: (.+?)\n.*?transfer: (.+?)\n'
        peers = []
        for match in re.finditer(peer_pattern, status_output, re.DOTALL):
            peers.append({
                'pubkey': match.group(1),
                'endpoint': match.group(2),
                'allowed_ips': match.group(3),
                'transfer': match.group(4)
            })
            
    except subprocess.CalledProcessError:
        interface_active = False
    except Exception as e:
        flash(_('Error getting WireGuard status: %(error)s', error=str(e)), 'warning')

    return render_template(
        'wireguard.html',
        status=status,
        ip=ip,
        peers=peers,
        interface_active=interface_active,
        config=config.get_current_config()
    )

@app.route('/network-stats')
def network_stats():
    """Endpoint para obtener estadísticas de red en tiempo real"""
    try:
        net = psutil.net_io_counters()
        return jsonify({
            'upload': (net.bytes_sent - getattr(network_stats, 'last_sent', 0)) / 1024,
            'download': (net.bytes_recv - getattr(network_stats, 'last_recv', 0)) / 1024
        })
    finally:
        network_stats.last_sent = net.bytes_sent
        network_stats.last_recv = net.bytes_recv

def ensure_wifi_interface():
    """Ensure WiFi interface is properly configured"""
    try:
        # Check if wlan0 exists
        result = subprocess.run(['ip', 'link', 'show', 'wlan0'], capture_output=True, text=True)
        if result.returncode != 0:
            app.logger.error("wlan0 interface not found")
            return False

        # Enable WiFi radio
        subprocess.run(['nmcli', 'radio', 'wifi', 'on'], check=True)
        
        # Bring interface up
        subprocess.run(['ip', 'link', 'set', 'wlan0', 'up'], check=True)
        
        # Restart NetworkManager if needed
        nm_status = subprocess.run(['systemctl', 'is-active', 'NetworkManager'], capture_output=True, text=True)
        if nm_status.returncode != 0:
            subprocess.run(['systemctl', 'restart', 'NetworkManager'], check=True)
            time.sleep(2)  # Wait for NetworkManager to restart
            
        return True
    except Exception as e:
        app.logger.error(f"Error ensuring WiFi interface: {str(e)}")
        return False

@app.route('/api/wifi/status')
def wifi_status():
    """Endpoint para obtener el estado actual del WiFi"""
    try:
        # Ensure WiFi interface is properly configured
        if not ensure_wifi_interface():
            app.logger.error("Failed to configure WiFi interface")
            return jsonify({
                'success': False,
                'error': 'Failed to configure WiFi interface'
            })

        # Verificar si la interfaz WiFi está habilitada
        wifi_enabled = False
        try:
            result = subprocess.run(['nmcli', 'radio', 'wifi'], capture_output=True, text=True)
            wifi_enabled = 'enabled' in result.stdout.lower()
            if not wifi_enabled:
                # Try to enable WiFi
                try:
                    subprocess.run(['nmcli', 'radio', 'wifi', 'on'], check=True)
                    time.sleep(2)  # Wait for WiFi to enable
                    wifi_enabled = True
                except subprocess.CalledProcessError as e:
                    app.logger.error(f"Error enabling WiFi radio: {str(e)}")
                    return jsonify({
                        'success': False,
                        'error': f'Error enabling WiFi radio: {str(e)}'
                    })
        except Exception as e:
            app.logger.error(f"Error checking WiFi radio status: {str(e)}")
            return jsonify({
                'success': False,
                'error': f'Error checking WiFi radio status: {str(e)}'
            })

        # Verificar si wlan0 existe y está activa
        interface_active = False
        try:
            result = subprocess.run(['ip', 'link', 'show', 'wlan0'], capture_output=True, text=True)
            interface_active = result.returncode == 0 and 'state UP' in result.stdout
            if not interface_active:
                # Try to bring interface up
                try:
                    subprocess.run(['ip', 'link', 'set', 'wlan0', 'up'], check=True)
                    time.sleep(1)  # Wait for interface to come up
                    interface_active = True
                except subprocess.CalledProcessError as e:
                    app.logger.error(f"Error bringing up wlan0: {str(e)}")
                    return jsonify({
                        'success': False,
                        'error': f'Error bringing up wlan0: {str(e)}'
                    })
        except Exception as e:
            app.logger.error(f"Error checking wlan0 status: {str(e)}")
            return jsonify({
                'success': False,
                'error': f'Error checking wlan0 status: {str(e)}'
            })

        # Obtener conexión actual
        current_connection = None
        connection_info = None
        try:
            # First try to get connection using nmcli
            result = subprocess.run(['nmcli', '-t', '-f', 'NAME,TYPE,DEVICE', 'connection', 'show', '--active'], 
                                  capture_output=True, text=True)
            if result.returncode == 0:
                for line in result.stdout.splitlines():
                    if 'wifi' in line.lower():
                        current_connection = line.split(':')[0]
                        # Get signal strength if connected
                        try:
                            signal_result = subprocess.run(['nmcli', '-f', 'SIGNAL', 'device', 'wifi', 'list', 'ifname', 'wlan0'], 
                                                         capture_output=True, text=True)
                            if signal_result.returncode == 0:
                                for signal_line in signal_result.stdout.splitlines():
                                    if current_connection in signal_line:
                                        signal = signal_line.split()[0]
                                        connection_info = {'signal': signal}
                                        break
                        except Exception as e:
                            app.logger.error(f"Error getting signal strength: {str(e)}")
                        break

            # If nmcli fails, try alternative method using iwconfig
            if not current_connection:
                try:
                    iw_result = subprocess.run(['iwconfig', 'wlan0'], capture_output=True, text=True)
                    if iw_result.returncode == 0 and 'ESSID:' in iw_result.stdout:
                        # Extract SSID from iwconfig output
                        ssid_match = re.search(r'ESSID:"([^"]+)"', iw_result.stdout)
                        if ssid_match:
                            current_connection = ssid_match.group(1)
                except Exception as e:
                    app.logger.error(f"Error getting connection from iwconfig: {str(e)}")

        except Exception as e:
            app.logger.error(f"Error getting current connection: {str(e)}")
            # Don't return error here, continue with other checks

        # Obtener SSID actual
        current_ssid = get_wifi_ssid()
        if current_ssid and not current_connection:
            current_connection = current_ssid

        # Obtener dirección IP
        ip_address = None
        try:
            result = subprocess.run(['ip', 'addr', 'show', 'wlan0'], capture_output=True, text=True)
            if result.returncode == 0:
                ip_match = re.search(r'inet (\d+\.\d+\.\d+\.\d+)', result.stdout)
                if ip_match:
                    ip_address = ip_match.group(1)
        except Exception as e:
            app.logger.error(f"Error getting IP address: {str(e)}")

        # If we have an IP address but no connection name, try to get it from the SSID
        if ip_address and not current_connection:
            current_connection = current_ssid

        return jsonify({
            'success': True,
            'enabled': wifi_enabled,
            'interface_active': interface_active,
            'current_connection': current_connection,
            'current_ssid': current_ssid,
            'ip_address': ip_address,
            'connection_info': connection_info
        })
    except Exception as e:
        app.logger.error(f"Error in wifi_status: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        })

@app.route('/api/wifi/scan', methods=['GET'])
def wifi_scan():
    try:
        app.logger.info('Iniciando escaneo WiFi...')
        
        # Ensure WiFi interface is properly configured
        if not ensure_wifi_interface():
            return jsonify({
                'success': False,
                'error': 'Failed to configure WiFi interface'
            })
        
        # 1. Verificar estado WiFi
        status = subprocess.run(['nmcli', 'radio', 'wifi'], capture_output=True, text=True)
        app.logger.debug(f'Estado WiFi: {status.stdout}')
        
        if 'disabled' in status.stdout.lower():
            # Intentar habilitar WiFi
            subprocess.run(['nmcli', 'radio', 'wifi', 'on'], check=True)
            time.sleep(2)  # Esperar a que se active
            
        # 1.5. Forzar escaneo
        subprocess.run(['nmcli', 'device', 'wifi', 'rescan'], check=True)
        time.sleep(2)  # Esperar a que termine el escaneo
        
        # 2. Escanear redes
        result = subprocess.run(
            ['nmcli', '-t', '-f', 'SSID,SIGNAL,SECURITY,BSSID', 'device', 'wifi', 'list'],
            capture_output=True,
            text=True,
            timeout=30
        )
        app.logger.debug(f'Resultado nmcli: {result.stdout}')
        
        if result.returncode != 0:
            raise Exception(result.stderr or 'Failed to scan networks')
        
        # 3. Procesar resultados
        networks = []
        for line in result.stdout.splitlines():
            if line and line.count(':') >= 3:
                parts = line.split(':')
                networks.append({
                    'ssid': parts[0] if parts[0] else 'Hidden Network',
                    'signal': f'{min(100, int(parts[1]))}%',
                    'security': parts[2] if parts[2] else 'Open',
                    'bssid': parts[3]
                })
        
        app.logger.info(f'Encontradas {len(networks)} redes WiFi')
        return jsonify({'success': True, 'networks': networks})
        
    except subprocess.TimeoutExpired:
        app.logger.error('Timeout al escanear WiFi')
        return jsonify({'success': False, 'error': 'Scan timeout'}), 408
    except Exception as e:
        app.logger.error(f'Error en wifi_scan: {str(e)}')
        return jsonify({'success': False, 'error': str(e)}), 500

def get_wifi_credentials_path():
    """Obtiene la ruta del archivo de credenciales WiFi"""
    config_dir = os.path.join(os.path.expanduser('~'), '.hostberry')
    if not os.path.exists(config_dir):
        os.makedirs(config_dir, mode=0o700)
    return os.path.join(config_dir, 'wifi_credentials.json')

def get_encryption_key():
    """Obtiene o genera la clave de encriptación"""
    key_file = os.path.join(os.path.expanduser('~'), '.hostberry', '.wifi_key')
    if os.path.exists(key_file):
        with open(key_file, 'rb') as f:
            return f.read()
    else:
        key = Fernet.generate_key()
        os.makedirs(os.path.dirname(key_file), mode=0o700, exist_ok=True)
        with open(key_file, 'wb') as f:
            f.write(key)
        return key

def save_wifi_credentials(ssid, password):
    """Guarda las credenciales WiFi de forma segura"""
    try:
        credentials_file = get_wifi_credentials_path()
        key = get_encryption_key()
        f = Fernet(key)
        
        # Cargar credenciales existentes
        if os.path.exists(credentials_file):
            with open(credentials_file, 'rb') as file:
                encrypted_data = file.read()
                decrypted_data = f.decrypt(encrypted_data)
                credentials = json.loads(decrypted_data)
        else:
            credentials = {}
        
        # Actualizar credenciales
        credentials[ssid] = password
        
        # Guardar credenciales encriptadas
        encrypted_data = f.encrypt(json.dumps(credentials).encode())
        with open(credentials_file, 'wb') as file:
            file.write(encrypted_data)
        
        # Establecer permisos seguros
        os.chmod(credentials_file, 0o600)
        return True
    except Exception as e:
        app.logger.error(f'Error al guardar credenciales WiFi: {str(e)}')
        return False

def get_wifi_credentials(ssid):
    """Recupera las credenciales WiFi almacenadas"""
    try:
        credentials_file = get_wifi_credentials_path()
        if not os.path.exists(credentials_file):
            return None
            
        key = get_encryption_key()
        f = Fernet(key)
        
        with open(credentials_file, 'rb') as file:
            encrypted_data = file.read()
            decrypted_data = f.decrypt(encrypted_data)
            credentials = json.loads(decrypted_data)
            
        return credentials.get(ssid)
    except Exception as e:
        app.logger.error(f'Error al recuperar credenciales WiFi: {str(e)}')
        return None

@app.route('/api/wifi/check_credentials', methods=['GET', 'POST'])
def check_wifi_credentials():
    try:
        if request.method == 'POST':
            if not request.is_json:
                return jsonify({
                    'success': False,
                    'error': 'Content-Type debe ser application/json'
                }), 400

            data = request.get_json()
        else:  # GET request
            data = request.args

        ssid = data.get('ssid', '').strip()

        if not ssid:
            return jsonify({
                'success': False,
                'error': 'El SSID es requerido'
            }), 400

        # Verificar si hay credenciales guardadas
        password = get_wifi_credentials(ssid)
        
        if password:
            app.logger.info(f'Credenciales encontradas para {ssid}')
            return jsonify({
                'success': True,
                'has_credentials': True,
                'password': password
            })
        else:
            app.logger.info(f'No hay credenciales guardadas para {ssid}')
            return jsonify({
                'success': True,
                'has_credentials': False
            })

    except Exception as e:
        app.logger.error(f'Error al verificar credenciales WiFi: {str(e)}')
        return jsonify({
            'success': False,
            'error': f'Error al verificar credenciales: {str(e)}'
        }), 500

def auto_connect_last_wifi():
    """Intenta reconectar a la última red WiFi guardada al inicio del sistema."""
    try:
        # Verificar si hay una conexión activa
        if is_wifi_connected():
            app.logger.info("Ya hay una conexión WiFi activa")
            return

        # Obtener la última red guardada
        last_network = get_last_connected_network()
        if not last_network:
            app.logger.info("No hay red guardada para reconectar")
            return

        # Verificar si hay credenciales guardadas
        credentials = get_wifi_credentials(last_network['ssid'])
        if not credentials:
            app.logger.info(f"No hay credenciales guardadas para {last_network['ssid']}")
            return

        # Intentar la conexión
        app.logger.info(f"Intentando reconectar a {last_network['ssid']}")
        if last_network['security'] == 'Open':
            subprocess.check_call(['nmcli', 'device', 'wifi', 'connect', last_network['ssid']])
        else:
            subprocess.check_call(['nmcli', 'device', 'wifi', 'connect', last_network['ssid'], 'password', credentials['password']])
        
        app.logger.info(f"Reconexión exitosa a {last_network['ssid']}")
    except Exception as e:
        app.logger.error(f"Error en reconexión automática: {str(e)}")

def get_last_connected_network():
    """Obtiene la información de la última red conectada."""
    try:
        with open('/etc/hostberry/last_wifi.json', 'r') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return None

def save_last_connected_network(ssid, security):
    """Guarda la información de la última red conectada."""
    try:
        os.makedirs('/etc/hostberry', exist_ok=True)
        with open('/etc/hostberry/last_wifi.json', 'w') as f:
            json.dump({
                'ssid': ssid,
                'security': security,
                'timestamp': datetime.now().isoformat()
            }, f)
    except Exception as e:
        app.logger.error(f"Error guardando última red: {str(e)}")

# Endpoint para crear la interfaz virtual wlan_ap0
@app.route('/api/hostapd/create_wlan_ap0', methods=['POST'])
def create_wlan_ap0_endpoint():
    try:
        # Check if interface exists
        result = subprocess.run(['ip', 'link', 'show', 'wlan_ap0'], 
                              capture_output=True, text=True)
        exists = result.returncode == 0
        
        if exists:
            # Check if interface is up
            is_up = 'state UP' in result.stdout
            
            # If interface exists and is down, bring it up
            if not is_up:
                subprocess.run(['ip', 'link', 'set', 'wlan_ap0', 'up'], check=True)
                return jsonify({
                    'success': True,
                    'message': 'Interface wlan_ap0 brought up successfully',
                    'action': 'up'
                })
            else:
                # If interface exists and is up, delete it
                subprocess.run(['iw', 'dev', 'wlan_ap0', 'del'], check=True)
                return jsonify({
                    'success': True,
                    'message': 'Interface wlan_ap0 deleted successfully',
                    'action': 'delete'
                })
        else:
            # Create virtual interface
            if create_virtual_interface():
                return jsonify({
                    'success': True,
                    'message': 'Virtual interface wlan_ap0 created successfully',
                    'action': 'create'
                })
            else:
                return jsonify({
                    'success': False,
                    'error': 'Failed to create virtual interface'
                })
    except subprocess.CalledProcessError as e:
        return jsonify({
            'success': False,
            'error': f'Command failed: {e.cmd}\nOutput: {e.output}'
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        })

# Modificar la función wifi_connect para guardar la última red
@app.route('/api/wifi/connect', methods=['GET', 'POST'])
def wifi_connect():
    try:
        if request.method == 'POST':
            data = request.get_json()
            ssid = data.get('ssid')
            password = data.get('password')
            security = data.get('security', 'Open')
            save_credentials = data.get('save_credentials', False)

            if not ssid:
                return jsonify({'success': False, 'error': 'No SSID provided'})

            # Guardar la última red conectada
            save_last_connected_network(ssid, security)

            # Resto del código existente...
            if not ssid:
                app.logger.error('SSID no proporcionado')
                return jsonify({
                    'success': False,
                    'error': 'El SSID es requerido'
                }), 400

            # Normalizar tipo de seguridad
            security = security.upper()
            if security not in ['OPEN', 'WPA', 'WPA2', 'WPA3', 'WEP']:
                security = 'WPA2'  # Por defecto asumimos WPA2 para redes protegidas

            if security != 'OPEN' and not password:
                # Intentar recuperar contraseña guardada
                saved_password = get_wifi_credentials(ssid)
                if saved_password:
                    password = saved_password
                else:
                    app.logger.error('Contraseña faltante para red protegida')
                    return jsonify({
                        'success': False,
                        'error': 'La contraseña es requerida para redes protegidas'
                    }), 400

            # Intentar conectar usando nmcli
            try:
                # Primero intentamos eliminar cualquier conexión existente con el mismo SSID
                subprocess.run(['nmcli', 'connection', 'delete', ssid], 
                             capture_output=True, 
                             check=False)
                
                # Crear nueva conexión
                if security == 'OPEN':
                    cmd = ['nmcli', 'device', 'wifi', 'connect', ssid]
                else:
                    # Para redes protegidas, primero eliminamos cualquier conexión existente
                    subprocess.run(['nmcli', 'connection', 'delete', ssid], 
                                 capture_output=True, 
                                 check=False)
                    
                    # Guardar credenciales si se solicitó
                    if save_credentials and security != 'OPEN':
                        if save_wifi_credentials(ssid, password):
                            app.logger.info(f'Credenciales guardadas para {ssid}')
                        else:
                            app.logger.warning(f'No se pudieron guardar las credenciales para {ssid}')
                    
                    # Creamos una nueva conexión con los parámetros de seguridad
                    if security in ['WPA', 'WPA2', 'WPA3']:
                        cmd = [
                            'nmcli', 'connection', 'add',
                            'type', 'wifi',
                            'con-name', ssid,
                            'ifname', 'wlan0',
                            'ssid', ssid,
                            'wifi-sec.key-mgmt', 'wpa-psk',
                            'wifi-sec.psk', password,
                            'connection.autoconnect', 'yes'  # Habilitar autoconexión
                        ]
                    elif security == 'WEP':
                        cmd = [
                            'nmcli', 'connection', 'add',
                            'type', 'wifi',
                            'con-name', ssid,
                            'ifname', 'wlan0',
                            'ssid', ssid,
                            'wifi-sec.key-mgmt', 'none',
                            'wifi-sec.auth-alg', 'open',
                            'wifi-sec.wep-key-type', 'key',
                            'wifi-sec.wep-key0', password,
                            'connection.autoconnect', 'yes'  # Habilitar autoconexión
                        ]
                    
                    # Ejecutamos el comando de creación
                    app.logger.info(f'Ejecutando comando de creación: {" ".join(cmd)}')
                    result = subprocess.run(cmd, capture_output=True, text=True)
                    
                    if result.returncode == 0:
                        # Si la creación fue exitosa, activamos la conexión
                        cmd = ['nmcli', 'connection', 'up', ssid]
                    else:
                        error_msg = result.stderr.strip() or 'Error desconocido al crear la conexión'
                        app.logger.error(f'Error al crear conexión WiFi: {error_msg}')
                        return jsonify({
                            'success': False,
                            'error': f'Error al crear conexión: {error_msg}'
                        }), 400
                
                app.logger.info(f'Ejecutando comando: {" ".join(cmd)}')
                result = subprocess.run(cmd, capture_output=True, text=True)
                
                if result.returncode == 0:
                    app.logger.info(f'Conexión exitosa a {ssid}')
                    return jsonify({
                        'success': True,
                        'message': f'Conectado exitosamente a {ssid}'
                    })
                else:
                    error_msg = result.stderr.strip() or 'Error desconocido al conectar'
                    app.logger.error(f'Error al conectar a WiFi: {error_msg}')
                    return jsonify({
                        'success': False,
                        'error': f'Error al conectar: {error_msg}'
                    }), 400
                    
            except subprocess.CalledProcessError as e:
                app.logger.error(f'Error en comando nmcli: {str(e)}')
                return jsonify({
                    'success': False,
                    'error': f'Error en comando nmcli: {str(e)}'
                }), 500

    except Exception as e:
        app.logger.error(f'Error en wifi_connect: {str(e)}', exc_info=True)
        return jsonify({
            'success': False,
            'error': f'Error en la conexión: {str(e)}'
        }), 500

@app.route('/api/wifi/disconnect', methods=['GET', 'POST'])
def wifi_disconnect():
    try:
        if request.method == 'POST':
            if not request.is_json:
                return jsonify({
                    'success': False,
                    'error': 'Content-Type debe ser application/json'
                }), 400

            data = request.get_json()
        else:  # GET request
            data = request.args

        ssid = data.get('ssid', '').strip()

        if not ssid:
            return jsonify({
                'success': False,
                'error': 'El SSID es requerido'
            }), 400

        # Desconectar usando nmcli
        try:
            # Primero intentamos desconectar la conexión activa
            subprocess.run(['nmcli', 'device', 'disconnect', 'wlan0'], 
                         capture_output=True, 
                         check=False)
            
            # Luego eliminamos la configuración de la red
            subprocess.run(['nmcli', 'connection', 'delete', ssid], 
                         capture_output=True, 
                         check=False)
            
            app.logger.info(f'Desconectado exitosamente de {ssid}')
            return jsonify({
                'success': True,
                'message': f'Desconectado exitosamente de {ssid}'
            })
            
        except subprocess.CalledProcessError as e:
            error_msg = e.stderr.strip() or 'Error desconocido al desconectar'
            app.logger.error(f'Error al desconectar de WiFi: {error_msg}')
            return jsonify({
                'success': False,
                'error': f'Error al desconectar: {error_msg}'
            }), 400

    except Exception as e:
        app.logger.error(f'Error en wifi_disconnect: {str(e)}')
        return jsonify({
            'success': False,
            'error': f'Error en la desconexión: {str(e)}'
        }), 500

@app.route('/connect', methods=['POST'])
def connect():
    data = request.get_json()
    ssid = data.get('ssid')
    password = data.get('password')

    if not ssid or not password:
        return jsonify({'message': 'SSID and password are required.'}), 400

    try:
        subprocess.check_call(['nmcli', 'dev', 'wifi', 'connect', ssid, 'password', password])
        return jsonify({'message': 'Connected successfully!'})
    except subprocess.CalledProcessError as e:
        return jsonify({'message': f'Failed to connect: {str(e)}'}), 400


@app.route('/enable_wifi', methods=['POST'])
def enable_wifi():
    import subprocess
    import logging
    try:
        logging.info('[Enable WiFi] Ejecutando rfkill unblock wifi...')
        subprocess.run(['rfkill', 'unblock', 'wifi'], check=True)
        logging.info('[Enable WiFi] Ejecutando nmcli radio wifi on...')
        subprocess.run(['nmcli', 'radio', 'wifi', 'on'], check=True)
        return '', 200
    except subprocess.CalledProcessError as e:
        logging.error(f'[Enable WiFi] Error: {e}')
        return '', 500

# Función utilitaria para saber si la interfaz wifi está bloqueada

def is_wifi_blocked_or_disabled():
    # subprocess is imported globally
    # logging is imported globally and app.logger is available
    try:
        # Verifica rfkill
        result = subprocess.run(['rfkill', 'list', 'wifi'], capture_output=True, text=True, check=True)
        output = result.stdout.lower()
        blocked = (
            'soft blocked: yes' in output or
            'hard blocked: yes' in output or
            'blocked: yes' in output
        )
        # Verifica nmcli
        nmcli_result = subprocess.run(['nmcli', 'radio', 'wifi'], capture_output=True, text=True, check=True)
        wifi_status = nmcli_result.stdout.strip().lower()
        disabled = ('disable' in wifi_status) # Note: 'disabled' in English, 'desactivado' in Spanish
        return blocked or disabled
    except FileNotFoundError as e:
        app.logger.error(f"[is_wifi_blocked_or_disabled] Command not found: {e}. Ensure 'rfkill' and 'nmcli' are installed and in PATH.")
        raise # Re-raise the exception
    except subprocess.CalledProcessError as e:
        app.logger.error(f"[is_wifi_blocked_or_disabled] Error executing command: {e}. stderr: {e.stderr}")
        raise # Re-raise the exception
    except Exception as e:
        app.logger.error(f'[is_wifi_blocked_or_disabled] Unexpected error checking rfkill/nmcli: {str(e)}')
        raise # Re-raise the exception

@app.route('/wifi_scan')
def wifi_scan_page():
    """
    Renderiza la página de escaneo WiFi. Nunca debe retornar JSON, solo HTML.
    """
    try:
        # Verificar estado WiFi
        status = subprocess.run(['nmcli', 'radio', 'wifi'], capture_output=True, text=True)
        wifi_enabled = 'enabled' in status.stdout.lower()
        app.logger.debug(f'[WiFi Page] Estado WiFi: {status.stdout.strip()}')
        wifi_blocked = is_wifi_blocked_or_disabled()

        # Obtener conexión actual
        current_conn = None
        conn_result = subprocess.run(
            ['nmcli', '-t', '-f', 'NAME,TYPE,DEVICE', 'connection', 'show', '--active'],
            capture_output=True,
            text=True
        )
        if conn_result.returncode == 0:
            for line in conn_result.stdout.splitlines():
                if 'wifi' in line.lower():
                    current_conn = line.split(':')[0]
                    break
        app.logger.debug(f'[WiFi Page] Conexión actual: {current_conn}')

        app.logger.debug(f'[WiFi Page] wifi_blocked: {wifi_blocked} | wifi_enabled: {wifi_enabled}')
        return render_template(
            'wifi_scan.html',
            wifi_blocked=wifi_blocked,
            wifi_enabled=wifi_enabled,
            current_connection=current_conn
        )
    except Exception as e:
        app.logger.error(f'[WiFi Page] Error cargando página WiFi: {str(e)}')
        wifi_blocked = False
        # Nunca retornar JSON aquí
        app.logger.debug(f'[WiFi Page] wifi_blocked (except): {wifi_blocked}')
        return render_template('wifi_scan.html', wifi_blocked=wifi_blocked, wifi_enabled=False, current_connection=None, error=str(e))

@app.route('/hostapd')
def hostapd_page():
    """
    Renderiza la página de configuración del punto de acceso WiFi.
    """
    try:
        # Verificar si hostapd está instalado
        hostapd_installed = subprocess.run(['which', 'hostapd'], capture_output=True).returncode == 0
        
        # Verificar estado actual de hostapd
        hostapd_service_active = subprocess.run(['systemctl', 'is-active', 'hostapd'], capture_output=True, text=True).returncode == 0
        is_running = False
        if hostapd_service_active:
            try:
                iw_status = subprocess.run(['iw', 'dev', 'wlan_ap0', 'info'], capture_output=True, text=True, check=True)
                if 'type AP' in iw_status.stdout:
                    is_running = True
                else:
                    app.logger.info("[Hostapd Page] wlan_ap0 found but not in AP mode.")
            except subprocess.CalledProcessError as e:
                app.logger.error(f"[Hostapd Page] Error checking iw dev wlan_ap0 info: {e.stderr}")
            except FileNotFoundError:
                app.logger.error("[Hostapd Page] 'iw' command not found. Cannot verify wlan_ap0 AP status.")
        else:
            app.logger.info("[Hostapd Page] hostapd service is not active.")
        
        # Obtener configuración actual si existe
        current_config = {}
        if os.path.exists('/etc/hostapd/hostapd.conf'):
            with open('/etc/hostapd/hostapd.conf', 'r') as f:
                for line in f:
                    if '=' in line:
                        key, value = line.strip().split('=', 1)
                        current_config[key] = value
        
        # Detectar interfaces WiFi disponibles (wlan0, wlan1, wlan_ap0)
        interfaces = []
        for iface in ['wlan0', 'wlan1', 'wlan_ap0']:
            result = subprocess.run(['ip', 'link', 'show', iface], capture_output=True)
            if result.returncode == 0:
                interfaces.append(iface)
        # Pasar la interfaz configurada actual
        current_config['interface'] = current_config.get('interface', 'wlan_ap0')
        return render_template(
            'hostapd.html',
            hostapd_installed=hostapd_installed,
            is_running=is_running,
            current_config=current_config,
            interfaces=interfaces
        )
    except Exception as e:
        app.logger.error(f'Error cargando página hostapd: {str(e)}')
        return render_template('hostapd.html', error=str(e))

def create_virtual_interface():
    """Create virtual interface for AP mode"""
    try:
        # Create udev rule for virtual interface
        udev_rule = """SUBSYSTEM=="ieee80211", ACTION=="add|change", KERNEL=="phy0", \
RUN+="/sbin/iw phy phy0 interface add wlan_ap0 type __ap", \
RUN+="/bin/ip link set wlan_ap0 address 99:88:77:66:55:44"
"""
        with open('/etc/udev/rules.d/70-persistent-net.rules', 'w') as f:
            f.write(udev_rule)
        
        # Reload udev rules
        subprocess.run(['udevadm', 'control', '--reload-rules'], check=True)
        subprocess.run(['udevadm', 'trigger'], check=True)
        
        # Wait for interface to be created
        for _ in range(10):  # Try for 10 seconds
            if subprocess.run(['ip', 'link', 'show', 'wlan_ap0'], 
                            capture_output=True).returncode == 0:
                return True
            time.sleep(1)
        return False
    except Exception as e:
        app.logger.error(f"Error creating virtual interface: {str(e)}")
        return False

def configure_hostapd(ssid, password, channel, hw_mode, country_code, interface):
    """Configure hostapd"""
    try:
        config = f"""interface={interface}
driver=nl80211
ssid={ssid}
hw_mode={hw_mode}
channel={channel}
country_code={country_code}
auth_algs=1
wpa=2
wpa_passphrase={password}
wpa_key_mgmt=WPA-PSK
wpa_pairwise=CCMP
rsn_pairwise=CCMP
"""
        with open('/etc/hostapd/hostapd.conf', 'w') as f:
            f.write(config)
        return True
    except Exception as e:
        app.logger.error(f"Error configuring hostapd: {str(e)}")
        return False

def configure_dhcp(start_ip, end_ip):
    """Configure DHCP server"""
    try:
        # Configure dhcpd.conf
        dhcp_config = f"""subnet 192.168.90.0 netmask 255.255.255.0 {{
    range {start_ip} {end_ip};
    option subnet-mask 255.255.255.0;
    option routers 192.168.90.1;
    option domain-name-servers 8.8.8.8, 8.8.4.4;
    option time-offset 0;
    option broadcast-address 192.168.90.255;
}}"""
        with open('/etc/dhcp/dhcpd.conf', 'w') as f:
            f.write(dhcp_config)

        # Configure isc-dhcp-server
        with open('/etc/default/isc-dhcp-server', 'w') as f:
            f.write('INTERFACESv4="wlan_ap0"\n')
        
        return True
    except Exception as e:
        app.logger.error(f"Error configuring DHCP: {str(e)}")
        return False

def configure_network_passthrough():
    """Configure network passthrough"""
    try:
        # Enable IP forwarding
        with open('/proc/sys/net/ipv4/ip_forward', 'w') as f:
            f.write('1\n')
        
        # Configure NAT for both interfaces
        subprocess.run(['iptables', '-t', 'nat', '-A', 'POSTROUTING', 
                       '-o', 'wlan0', '-j', 'MASQUERADE'], check=True)
        subprocess.run(['iptables', '-t', 'nat', '-A', 'POSTROUTING', 
                       '-o', 'eth0', '-j', 'MASQUERADE'], check=True)
        
        # Allow forwarding between interfaces
        subprocess.run(['iptables', '-A', 'FORWARD', '-i', 'wlan_ap0', '-o', 'wlan0', '-j', 'ACCEPT'], check=True)
        subprocess.run(['iptables', '-A', 'FORWARD', '-i', 'wlan0', '-o', 'wlan_ap0', '-m', 'state', '--state', 'ESTABLISHED,RELATED', '-j', 'ACCEPT'], check=True)
        
        return True
    except Exception as e:
        app.logger.error(f"Error configuring network passthrough: {str(e)}")
        return False

@app.route('/api/hostapd/interface_status')
def hostapd_interface_status():
    try:
        # Check if interface exists
        result = subprocess.run(['ip', 'link', 'show', 'wlan_ap0'], 
                              capture_output=True, text=True)
        exists = result.returncode == 0
        
        if exists:
            # Check if interface is up
            is_up = 'state UP' in result.stdout
            
            # Check if interface has IP
            ip_result = subprocess.run(['ip', 'addr', 'show', 'wlan_ap0'], 
                                     capture_output=True, text=True)
            has_ip = 'inet ' in ip_result.stdout
        else:
            is_up = False
            has_ip = False

        return jsonify({
            'success': True,
            'exists': exists,
            'is_up': is_up,
            'has_ip': has_ip
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        })

@app.route('/api/hostapd/config', methods=['POST'])
def hostapd_config():
    try:
        data = request.get_json()
        interface = data.get('interface', 'wlan_ap0')
        # Guardar la interfaz en la config actual (si usas un sistema de config persistente, aquí deberías actualizarlo)
        # current_config['interface'] = interface  # Si tienes un objeto config global, actualízalo aquí
        # Crear interfaz virtual solo si se selecciona wlan_ap0
        if interface == 'wlan_ap0':
            if not create_virtual_interface():
                return jsonify({
                    'success': False,
                    'error': 'Failed to create virtual interface'
                })
        # Configurar hostapd con la interfaz seleccionada
        if not configure_hostapd(
            data.get('ssid'),
            data.get('password'),
            data.get('channel'),
            data.get('hw_mode'),
            data.get('country_code'),
            interface
        ):
            return jsonify({
                'success': False,
                'error': 'Failed to configure hostapd'
            })

        # Configure DHCP
        if not configure_dhcp(data.get('dhcp_start'), data.get('dhcp_end')):
            return jsonify({
                'success': False,
                'error': 'Failed to configure DHCP'
            })

        # Configure network passthrough if enabled
        if data.get('enable_passthrough'):
            if not configure_network_passthrough():
                return jsonify({
                    'success': False,
                    'error': 'Failed to configure network passthrough'
                })

        # Set static IP for AP interface
        try:
            link_show_result = subprocess.run(['ip', 'link', 'show', 'wlan_ap0'], capture_output=True, text=True)
            app.logger.info(f"[Hostapd Config] 'ip link show wlan_ap0' before add: stdout: {link_show_result.stdout}, stderr: {link_show_result.stderr}, rc: {link_show_result.returncode}")
        except Exception as log_e:
            app.logger.error(f"[Hostapd Config] Error logging 'ip link show wlan_ap0': {log_e}")

        # Enhanced logging for 'ip addr add'
        ip_addr_add_cmd = ['ip', 'addr', 'add', '192.168.90.1/24', 'dev', 'wlan_ap0']
        try:
            app.logger.info(f"[Hostapd Config] Attempting to run: {' '.join(ip_addr_add_cmd)}")
            # Using check=False here to manually inspect result and error
            ip_addr_result = subprocess.run(ip_addr_add_cmd, capture_output=True, text=True, check=False)
            if ip_addr_result.returncode == 0:
                app.logger.info(f"[Hostapd Config] 'ip addr add' SUCCEEDED. Stdout: {ip_addr_result.stdout or '[empty]'}, Stderr: {ip_addr_result.stderr or '[empty]'}")
            else:
                # This case should ideally not be reached if check=True is used later or if we raise an error
                app.logger.error(f"[Hostapd Config] 'ip addr add' FAILED with rc={ip_addr_result.returncode}. Stdout: {ip_addr_result.stdout or '[empty]'}, Stderr: {ip_addr_result.stderr or '[empty]'}")
                # We'll let the existing outer try/except handle the JSON response for failure
                # Forcing a CalledProcessError to be caught by the main handler
                raise subprocess.CalledProcessError(returncode=ip_addr_result.returncode, cmd=ip_addr_add_cmd, output=ip_addr_result.stdout, stderr=ip_addr_result.stderr)
        except subprocess.CalledProcessError as e:
            # Log specifics here. The outer handler will form the JSON response.
            stderr_info = e.stderr if hasattr(e, 'stderr') and e.stderr else (e.output if hasattr(e, 'output') and e.output else 'N/A')
            app.logger.error(f"[Hostapd Config] 'ip addr add' EXCEPTION. Command: {' '.join(e.cmd)}. Stderr/Output: {stderr_info}")
            raise # Re-raise

        subprocess.run(['ip', 'link', 'set', 'wlan_ap0', 'up'], check=True)

        # Restart services
        subprocess.run(['systemctl', 'restart', 'isc-dhcp-server'], check=True)
        subprocess.run(['systemctl', 'restart', 'hostapd'], check=True)

        return jsonify({
            'success': True,
            'message': 'Access Point configured and started successfully'
        })
    except subprocess.CalledProcessError as e:
        return jsonify({
            'success': False,
            'error': f'Command failed: {e.cmd}\nOutput: {e.output}'
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        })

def restore_network_connectivity():
    """Restore network connectivity after AP mode"""
    try:
        # Stop hostapd and DHCP server
        subprocess.run(['systemctl', 'stop', 'hostapd'], check=False)
        subprocess.run(['systemctl', 'stop', 'isc-dhcp-server'], check=False)

        # Detect which interface was used for AP
        ap_interface = 'wlan_ap0'
        if os.path.exists('/etc/hostapd/hostapd.conf'):
            with open('/etc/hostapd/hostapd.conf') as f:
                for line in f:
                    if line.startswith('interface='):
                        ap_interface = line.split('=', 1)[1].strip()
                        break

        # Only remove virtual interface if it was used
        if ap_interface == 'wlan_ap0':
            # Remove virtual interface without affecting physical interfaces
            subprocess.run(['iw', 'dev', 'wlan_ap0', 'del'], check=False)
        # Do NOT bring down physical interfaces (wlan0/wlan1)

        # Clear iptables rules
        subprocess.run(['iptables', '-F'], check=False)
        subprocess.run(['iptables', '-t', 'nat', '-F'], check=False)

        # Disable IP forwarding
        with open('/proc/sys/net/ipv4/ip_forward', 'w') as f:
            f.write('0\n')

        return True
    except Exception as e:
        app.logger.error(f"Error restoring network: {str(e)}")
        return False

@app.route('/api/hostapd/toggle', methods=['POST'])
def hostapd_toggle():
    try:
        # Leer la interfaz configurada actual desde el hostapd.conf
        interface = 'wlan_ap0'
        if os.path.exists('/etc/hostapd/hostapd.conf'):
            with open('/etc/hostapd/hostapd.conf') as f:
                for line in f:
                    if line.startswith('interface='):
                        interface = line.split('=', 1)[1].strip()
                        break
        # Check current status
        status = subprocess.run(['systemctl', 'is-active', 'hostapd'], 
                              capture_output=True, text=True)
        is_running = status.returncode == 0

        if is_running:
            # Stop AP and restore network
            if restore_network_connectivity():
                message = 'Access Point stopped and network restored successfully'
            else:
                message = 'Access Point stopped but network restoration failed'
        else:
            # Start AP
            try:
                # Crear interfaz virtual solo si corresponde
                if interface == 'wlan_ap0':
                    if not create_virtual_interface():
                        return jsonify({
                            'success': False,
                            'error': 'Failed to create virtual interface'
                        })
                # Set static IP for AP interface
                subprocess.run(['ip', 'addr', 'add', '192.168.90.1/24', 'dev', interface], check=True)
                subprocess.run(['ip', 'link', 'set', interface, 'up'], check=True)
                # Start services
                subprocess.run(['systemctl', 'start', 'isc-dhcp-server'], check=True)
                subprocess.run(['systemctl', 'start', 'hostapd'], check=True)
                message = 'Access Point started successfully'
            except Exception as e:
                # If AP start fails, restore network
                restore_network_connectivity()
                return jsonify({
                    'success': False,
                    'error': f'Failed to start AP: {str(e)}'
                })
        return jsonify({
            'success': True,
            'message': message
        })
    except Exception as e:
        # If anything fails, try to restore network
        restore_network_connectivity()
        return jsonify({
            'success': False,
            'error': str(e)
        })

@app.route('/api/network/restore', methods=['POST'])
def restore_network():
    """Endpoint to restore network connectivity"""
    try:
        if restore_network_connectivity():
            return jsonify({
                'success': True,
                'message': 'Network connectivity restored successfully'
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Failed to restore network connectivity'
            })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        })

@app.route('/api/hostapd/status')
def hostapd_status():
    try:
        # Get AP status
        status = subprocess.run(['systemctl', 'is-active', 'hostapd'], 
                              capture_output=True, text=True)
        is_running = status.returncode == 0
        
        # Get connected clients
        clients = []
        if is_running:
            client_result = subprocess.run(['hostapd_cli', 'all_sta'], 
                                         capture_output=True, text=True)
            for line in client_result.stdout.splitlines():
                if '=' in line:
                    key, value = line.split('=')
                    if key == 'addr':
                        clients.append({
                            'mac': value,
                            'signal': 'N/A',
                            'tx_rate': 'N/A',
                            'rx_rate': 'N/A'
                        })

        # Get channel information
        channel = None
        if is_running:
            channel_result = subprocess.run(['hostapd_cli', 'get_config'], 
                                          capture_output=True, text=True)
            for line in channel_result.stdout.splitlines():
                if line.startswith('channel='):
                    channel = line.split('=')[1]

        return jsonify({
            'success': True,
            'status': 'running' if is_running else 'stopped',
            'clients': clients,
            'channel': channel
        })
    except subprocess.CalledProcessError as e:
        return jsonify({
            'success': False,
            'error': f'Command failed: {e.cmd}\nOutput: {e.output}'
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        })

@app.route('/api/vpn/killswitch', methods=['POST'])
def toggle_killswitch():
    try:
        data = request.get_json()
        enabled = data.get('enabled', False)
        
        # Verificar si la VPN está conectada
        vpn_status = subprocess.run(['systemctl', 'is-active', 'openvpn'], capture_output=True, text=True)
        is_vpn_active = vpn_status.returncode == 0
        
        if enabled:
            if not is_vpn_active:
                return jsonify({
                    'success': False, 
                    'error': 'No se puede activar el Kill Switch: la VPN no está conectada'
                }), 400
                
            # Crear reglas de iptables para bloquear todo el tráfico excepto la VPN
            try:
                # Limpiar reglas existentes
                subprocess.run(['iptables', '-F'], check=True)
                subprocess.run(['iptables', '-X'], check=True)
                
                # Permitir tráfico local
                subprocess.run(['iptables', '-A', 'INPUT', '-i', 'lo', '-j', 'ACCEPT'], check=True)
                subprocess.run(['iptables', '-A', 'OUTPUT', '-o', 'lo', '-j', 'ACCEPT'], check=True)
                
                # Permitir tráfico de todas las interfaces VPN
                subprocess.run(['iptables', '-A', 'INPUT', '-i', 'tun+', '-j', 'ACCEPT'], check=True)
                subprocess.run(['iptables', '-A', 'OUTPUT', '-o', 'tun+', '-j', 'ACCEPT'], check=True)
                
                # Permitir tráfico necesario para mantener la conexión VPN
                subprocess.run(['iptables', '-A', 'INPUT', '-p', 'udp', '--dport', '1194', '-j', 'ACCEPT'], check=True)
                subprocess.run(['iptables', '-A', 'OUTPUT', '-p', 'udp', '--sport', '1194', '-j', 'ACCEPT'], check=True)
                
                # Permitir tráfico DNS necesario para la VPN
                subprocess.run(['iptables', '-A', 'INPUT', '-p', 'udp', '--dport', '53', '-j', 'ACCEPT'], check=True)
                subprocess.run(['iptables', '-A', 'OUTPUT', '-p', 'udp', '--dport', '53', '-j', 'ACCEPT'], check=True)
                
                # Permitir tráfico ICMP (ping) necesario para mantener la conexión
                subprocess.run(['iptables', '-A', 'INPUT', '-p', 'icmp', '-j', 'ACCEPT'], check=True)
                subprocess.run(['iptables', '-A', 'OUTPUT', '-p', 'icmp', '-j', 'ACCEPT'], check=True)
                
                # Permitir tráfico DHCP necesario para la red
                subprocess.run(['iptables', '-A', 'INPUT', '-p', 'udp', '--sport', '67', '--dport', '68', '-j', 'ACCEPT'], check=True)
                subprocess.run(['iptables', '-A', 'OUTPUT', '-p', 'udp', '--sport', '68', '--dport', '67', '-j', 'ACCEPT'], check=True)
                
                # Bloquear todo el tráfico que no sea de la VPN
                subprocess.run(['iptables', '-A', 'INPUT', '-j', 'DROP'], check=True)
                subprocess.run(['iptables', '-A', 'OUTPUT', '-j', 'DROP'], check=True)
                
                app.logger.info("Kill Switch activado correctamente")
                return jsonify({'success': True, 'message': 'Kill Switch activado'})
            except subprocess.CalledProcessError as e:
                app.logger.error(f"Error al activar Kill Switch: {str(e)}")
                return jsonify({'success': False, 'error': f'Error al activar Kill Switch: {str(e)}'}), 500
        else:
            # Limpiar reglas de iptables
            try:
                subprocess.run(['iptables', '-F'], check=True)
                subprocess.run(['iptables', '-X'], check=True)
                
                # Restaurar reglas por defecto
                subprocess.run(['iptables', '-P', 'INPUT', 'ACCEPT'], check=True)
                subprocess.run(['iptables', '-P', 'OUTPUT', 'ACCEPT'], check=True)
                subprocess.run(['iptables', '-P', 'FORWARD', 'ACCEPT'], check=True)
                
                app.logger.info("Kill Switch desactivado correctamente")
                return jsonify({'success': True, 'message': 'Kill Switch desactivado'})
            except subprocess.CalledProcessError as e:
                app.logger.error(f"Error al desactivar Kill Switch: {str(e)}")
                return jsonify({'success': False, 'error': f'Error al desactivar Kill Switch: {str(e)}'}), 500
                
    except Exception as e:
        app.logger.error(f"Error en Kill Switch: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/adblock/logs')
def adblock_logs():
    try:
        log_file = '/etc/hostberry/adblock/realtime.log'
        if os.path.exists(log_file):
            with open(log_file, 'r') as f:
                lines = f.readlines()
                last_lines = lines[-100:] if len(lines) > 100 else lines
                
                logs = []
                for line in last_lines:
                    if 'Blocked:' in line:
                        timestamp = line[1:20]  # [YYYY-MM-DD HH:MM:SS]
                        domain = line.split('Blocked: ')[1].strip()
                        logs.append({
                            'timestamp': timestamp,
                            'domain': domain
                        })
                
                return jsonify({'logs': logs})
    except Exception as e:
        app.logger.error(f"Error reading AdBlock logs: {str(e)}")
    
    return jsonify({'logs': []})

@app.route('/adblock/update_status')
def adblock_update_status():
    global global_adblock_update_status
    return jsonify(global_adblock_update_status)

@app.route('/adblock/realtime_log')
def adblock_realtime_log():
    logfile = '/etc/hostberry/adblock/realtime.log'
    domains = []
    try:
        with open(logfile, 'r') as f:
            lines = f.readlines()
            for line in lines[-20:]:
                if 'Blocked:' in line:
                    # Formato: [YYYY-MM-DD HH:MM:SS] Blocked: domain.com
                    parts = line.strip().split('Blocked:')
                    if len(parts) == 2:
                        dt_part = parts[0].strip().lstrip('[').rstrip(']')
                        domain = parts[1].strip()
                        domains.append({'domain': domain, 'datetime': dt_part})
    except Exception:
        pass
    return jsonify({'domains': domains[::-1]})

if __name__ == '__main__':
    # Intentar reconexión automática al inicio
    auto_connect_last_wifi()
    
    # Iniciar la aplicación
    app.run(host='0.0.0.0', port=5000, debug=True)