#!/usr/bin/env python3
from flask import Flask, render_template, request, redirect, url_for, flash, session, make_response, jsonify, abort
import subprocess
import os
from dotenv import load_dotenv
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
app.secret_key = secret_key

# Configure secure session settings
app.config.update(
    SESSION_COOKIE_SECURE=True,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE='Lax',
    PERMANENT_SESSION_LIFETIME=86400,
    BABEL_DEFAULT_LOCALE='es',
    BABEL_TRANSLATION_DIRECTORIES='translations',
    BABEL_SUPPORTED_LOCALES=['en', 'es'],
    SESSION_COOKIE_DOMAIN=None,
    SESSION_COOKIE_PATH=None
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
            'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
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
    """Read and parse application logs"""
    log_file = 'logs/hostberry.log'
    logs = []
    try:
        with open(log_file, 'r') as f:
            for line in f.readlines()[-50:]:  # Get last 50 lines
                line = line.strip()
                if line:
                    # Parse timestamp and message
                    parts = line.split(' ', 2)  # Split into timestamp, level, message
                    if len(parts) >= 3:
                        logs.append({
                            'timestamp': ' '.join(parts[:2]),
                            'message': parts[2]
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
        result = subprocess.run(['iwgetid', '-r'], capture_output=True, text=True)
        return result.stdout.strip() if result.returncode == 0 else None
    except:
        return None

def is_wifi_connected():
    """Verificar si está conectado a WiFi"""
    try:
        result = subprocess.run(['iwconfig'], capture_output=True, text=True)
        return 'ESSID:' in result.stdout
    except:
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
        
        log_file = '/opt/hostberry/logs/hostberry.log'
        log_lines = []
        logs_available = False
        
        try:
            if os.path.isfile(log_file):
                with open(log_file, 'r') as f:
                    log_lines = f.readlines()[-100:]  # Get last 100 lines
                    log_lines.reverse()
                logs_available = True
        except IOError:
            pass
        
        response = make_response(render_template(
            'index.html',
            title=_('Index'),
            stats=stats,
            logs_available=logs_available,
            log_lines=log_lines,
            current_lang=get_locale()
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
    
    if form.validate_on_submit():
        try:
            success = config.update_config({
                'FIREWALL_ENABLED': form.enable_firewall.data,
                'BLOCK_ICMP': form.block_icmp.data == '1',
                'TIMEZONE': form.timezone.data,
                'TIME_FORMAT': form.time_format.data
            })
            
            if success:
                flash(_('Configuración guardada correctamente'), 'success')
                # Recargar configuración inmediatamente
                current_config = config.get_current_config()
            else:
                flash(_('Error al guardar la configuración'), 'danger')
        except Exception as e:
            flash(_('Error crítico: %(error)s', error=str(e)), 'danger')
    
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

@app.route('/vpn', methods=['GET', 'POST'])
def vpn_config():
    if request.method == 'POST':
        new_config = {
            'VPN_ENABLED': request.form.get('vpn_enabled') == 'on',
            'VPN_PROVIDER': request.form.get('vpn_provider'),
            'VPN_COUNTRY': request.form.get('vpn_country')
        }
        config.update_config(new_config)
        flash(_('VPN configuration updated successfully!'), 'success')
        return redirect(url_for('vpn_config'))
    
    current_config = config.get_current_config()
    return render_template('vpn.html', 
        config=current_config,
        vpn_providers=['OpenVPN', 'WireGuard', 'IPSec'],
        vpn_countries=['US', 'UK', 'DE', 'FR', 'JP'],
        vpn_status={
            'connected': False,
            'ip_address': None,
            'location': None
        }
    )

@app.route('/vpn/toggle', methods=['POST'])
def vpn_toggle():
    try:
        # Toggle VPN connection logic here
        flash(_('VPN connection toggled successfully'), 'success')
    except Exception as e:
        app.logger.error(f"VPN toggle error: {e}")
        flash(_('Error toggling VPN connection'), 'danger')
    return redirect(url_for('vpn_config'))

@app.route('/adblock', methods=['GET', 'POST'])
def adblock_config():
    if request.method == 'POST':
        try:
            adblock_enabled = request.form.get('adblock_enabled') == 'on'
            config.update_config({'ADBLOCK_ENABLED': adblock_enabled})
            
            if adblock_enabled:
                script_path = '/usr/local/bin/adblock.sh'
                if os.path.exists(script_path):
                    result = subprocess.run(
                        [script_path],
                        check=True,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True
                    )
                    if result.returncode == 0:
                        flash(_('AdBlock enabled and lists updated!'), 'success')
                    else:
                        flash(_('AdBlock enabled but update failed: %(error)s', error=result.stderr), 'warning')
                else:
                    flash(_('Required script not found at %(path)s', path=script_path), 'warning')
                    # Fallback behavior here
            else:
                script_path = '/usr/local/bin/adblock.sh'
                if os.path.exists(script_path):
                    result = subprocess.run(
                        [script_path, '--disable'],
                        check=True,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True
                    )
                    flash(_('AdBlock disabled'), 'success')
                else:
                    flash(_('Required script not found at %(path)s', path=script_path), 'warning')
                    # Fallback behavior here
                
        except subprocess.CalledProcessError as e:
            flash(_('Script execution failed: %(error)s', error=e.stderr), 'danger')
        except Exception as e:
            flash(_('Error configuring AdBlock: %(error)s', error=str(e)), 'danger')
        
        return redirect(url_for('adblock_config'))
    
    current_config = config.get_current_config()
    adblock_status = current_config.get('ADBLOCK_ENABLED', False)
    
    # Verificar si hay listas actualizadas
    last_updated = None
    try:
        with open('/etc/hostberry/adblock/last_updated', 'r') as f:
            last_updated = f.read().strip()
    except:
        pass
    
    return render_template(
        'adblock.html',
        config=current_config,
        adblock_status=adblock_status,
        last_updated=last_updated
    )

@app.route('/adblock/update', methods=['POST'])
def adblock_update():
    try:
        script_path = '/usr/local/bin/adblock_update.sh'
        if os.path.exists(script_path):
            result = subprocess.run(
                [script_path],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            if result.returncode == 0:
                flash(_('AdBlock lists updated successfully!'), 'success')
            else:
                flash(_('Error updating AdBlock lists: ') + result.stderr, 'danger')
        else:
            flash(_('Required script not found at %(path)s', path=script_path), 'warning')
            # Fallback behavior here
            
    except subprocess.CalledProcessError as e:
        flash(_('Script execution failed: %(error)s', error=e.stderr), 'danger')
    except Exception as e:
        app.logger.error(f"AdBlock update error: {str(e)}")
        flash(_('Error updating AdBlock lists'), 'danger')
    
    return redirect(url_for('adblock_config'))

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

@app.route('/api/wifi/scan', methods=['GET'])
def wifi_scan():
    try:
        # 1. Verificar estado WiFi
        status = subprocess.run(['nmcli', 'radio', 'wifi'], capture_output=True, text=True)
        if 'disabled' in status.stdout.lower():
            return jsonify({'success': False, 'error': 'WiFi radio is disabled'}), 400
            
        # 2. Escanear redes
        result = subprocess.run(
            ['nmcli', '-t', '-f', 'SSID,SIGNAL,SECURITY,BSSID', 'device', 'wifi', 'list'],
            capture_output=True,
            text=True,
            timeout=30
        )
        
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
        
        return jsonify({'success': True, 'networks': networks})
        
    except subprocess.TimeoutExpired:
        return jsonify({'success': False, 'error': 'Scan timeout'}), 408
    except Exception as e:
        app.logger.error(f'WiFi scan error: {str(e)}')
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/wifi/connect', methods=['POST'])
def wifi_connect():
    try:
        data = request.get_json()
        if not data or not data.get('ssid'):
            return jsonify({'success': False, 'error': 'SSID is required'}), 400
            
        # Sanitización y validación
        ssid = re.sub(r'[^\w \-]', '', data['ssid']).strip()
        password = data.get('password', '')
        
        if not ssid:
            return jsonify({'success': False, 'error': 'Invalid SSID format'}), 400
            
        # Construir comando seguro
        cmd = ['nmcli', 'device', 'wifi', 'connect', ssid]
        if password:
            if len(password) < 8:
                return jsonify({'success': False, 'error': 'Password must be at least 8 characters'}), 400
            cmd.extend(['password', password])
            
        # Ejecutar conexión
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=60
        )
        
        if result.returncode == 0:
            return jsonify({'success': True, 'message': 'Connected successfully'})
        else:
            error_msg = result.stderr.split('\n')[0] if result.stderr else 'Connection failed'
            return jsonify({'success': False, 'error': error_msg}), 400
            
    except subprocess.TimeoutExpired:
        return jsonify({'success': False, 'error': 'Connection timeout'}), 408
    except Exception as e:
        app.logger.error(f'WiFi connection error: {str(e)}')
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/wifi/status', methods=['GET'])
def wifi_status():
    try:
        # Obtener estado completo
        radio = subprocess.run(['nmcli', 'radio', 'wifi'], capture_output=True, text=True)
        rfkill = subprocess.run(['rfkill', 'list', 'wifi'], capture_output=True, text=True)
        
        return jsonify({
            'enabled': 'enabled' in radio.stdout.lower(),
            'soft_blocked': 'Soft blocked: yes' in rfkill.stdout,
            'hard_blocked': 'Hard blocked: yes' in rfkill.stdout
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/wifi/enable', methods=['POST'])
def enable_wifi():
    try:
        # Desbloquear y activar WiFi
        subprocess.run(['rfkill', 'unblock', 'wifi'], check=True)
        subprocess.run(['nmcli', 'radio', 'wifi', 'on'], check=True)
        time.sleep(2)  # Esperar activación
        
        return jsonify({'success': True})
    except subprocess.CalledProcessError as e:
        return jsonify({
            'success': False, 
            'error': str(e),
            'stderr': e.stderr.decode() if e.stderr else None
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

@app.route('/wifi_scan')
def wifi_scan_page():
    try:
        # Verificar estado WiFi
        status = subprocess.run(['nmcli', 'radio', 'wifi'], capture_output=True, text=True)
        wifi_enabled = 'enabled' in status.stdout.lower()
        
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
        
        return render_template('wifi_scan.html', 
                             wifi_enabled=wifi_enabled,
                             current_connection=current_conn)
    except Exception as e:
        app.logger.error(f'Error loading WiFi page: {str(e)}')
        return render_template('wifi_scan.html', error=str(e))

def read_lines_filter(filename):
    try:
        with open(filename, 'r') as f:
            return f.readlines()
    except IOError:
        return []

def file_exists(filename):
    return os.path.isfile(filename)

app.jinja_env.tests['file_exists'] = file_exists
app.jinja_env.filters['read_lines'] = read_lines_filter

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)