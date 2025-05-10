#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from flask import Flask, render_template, request, redirect, url_for, flash, session, make_response, jsonify, abort, send_from_directory
import subprocess
import os
from dotenv import load_dotenv
import psutil # For network statistics
import time
import logging
import threading
from wifi.wifi_routes import wifi_bp
from vpn.vpn_routes import vpn_bp
from hostapd.hostapd_routes import hostapd_bp
from wireguard.wireguard_routes import wireguard_bp
from security.security_routes import security_bp
from adblock.adblock_routes import adblock_bp
from werkzeug.middleware.proxy_fix import ProxyFix
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps

# Asegurar que estamos en el directorio correcto
APP_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(APP_DIR)

# Estado global para saber si hay una actualización en curso
global_adblock_update_status = {'updating': False, 'last_result': None, 'last_error': None}

# Global state for network statistics
last_net_io = {}
last_stats_time = {}

logging.Formatter.converter = time.localtime
from hostberry_config import HostBerryConfig
import time
from werkzeug.utils import secure_filename
import re
from flask_babel import Babel, gettext as _
from flask_talisman import Talisman

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
from wtforms import BooleanField, SelectField, StringField, PasswordField, HiddenField
from wtforms.validators import DataRequired

# --- Formulario de Login ---
class LoginForm(FlaskForm):
    username = StringField('Usuario', validators=[DataRequired()])
    password = PasswordField('Contraseña', validators=[DataRequired()])
    csrf_token = HiddenField()

import logging
import logging.config
import os
import secrets
import json
from cryptography.fernet import Fernet
from base64 import b64encode, b64decode
import time

# Configuración de logging para toda la app y Flask
import os
LOG_PATH = '/opt/hostberry/logs/hostberry.log'
os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)

logging_config = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'detailed': {
            'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            'datefmt': '%Y-%m-%d %H:%M:%S'
        },
    },
    'handlers': {
        'file': {
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': LOG_PATH,
            'maxBytes': 10*1024*1024,  # 10MB
            'backupCount': 5,
            'formatter': 'detailed',
            'encoding': 'utf8',
        },
    },
    'root': {
        'handlers': ['file'],
        'level': 'DEBUG',
    },
    'loggers': {
        'werkzeug': {
            'handlers': ['file'],
            'level': 'INFO',
            'propagate': False
        },
        'flask.app': {
            'handlers': ['file'],
            'level': 'DEBUG',
            'propagate': False
        },
    }
}
logging.config.dictConfig(logging_config)
logger = logging.getLogger(__name__)
app_logger = logger
app_logger.info('Sistema de logging configurado correctamente')

# Initialize environment and logging
app_logger.info('Iniciando proceso de inicialización de la aplicación')

start_time = time.time()

try:
    # Asegurar que el archivo .env existe y tiene la clave secreta
    env_path = os.path.join(APP_DIR, '.env')
    secret_key = None

    if not os.path.exists(env_path):
        app_logger.info('Creando archivo .env con nueva clave secreta')
        secret_key = secrets.token_hex(32)
        try:
            with open(env_path, 'w') as f:
                f.write(f"FLASK_SECRET_KEY={secret_key}\n")
            app_logger.info('Archivo .env creado correctamente.')
        except Exception as e:
            error_msg = f"No se pudo crear el archivo .env en {env_path}: {e}"
            print(error_msg)
            app_logger.error(error_msg)
            raise RuntimeError(error_msg)
    else:
        # Leer la clave existente
        try:
            with open(env_path, 'r') as f:
                for line in f:
                    if line.startswith('FLASK_SECRET_KEY='):
                        secret_key = line.strip().split('=')[1]
                        break
        except Exception as e:
            app_logger.error(f"Error al leer .env: {e}")
            secret_key = None

    # Si no hay clave válida, generar una nueva
    if not secret_key or len(secret_key) < 32:
        app_logger.info('Generando nueva clave secreta')
        secret_key = secrets.token_hex(32)
        try:
            with open(env_path, 'a') as f:
                f.write(f"FLASK_SECRET_KEY={secret_key}\n")
            app_logger.info('Clave secreta añadida a .env correctamente.')
        except Exception as e:
            error_msg = f"No se pudo escribir en el archivo .env: {e}"
            print(error_msg)
            app_logger.error(error_msg)
            raise RuntimeError(error_msg)

    app_logger.debug('Cargando variables de entorno')
    load_dotenv(env_path)

    # Crear instancia de Flask con rutas absolutas
    app = Flask(__name__,
                instance_path=os.path.join(APP_DIR, 'instance'),
                static_folder=os.path.join(APP_DIR, 'static'),
                template_folder=os.path.join(APP_DIR, 'templates'))
    app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)
    
    # Configuraciones de seguridad
    app.config.update(
        SESSION_COOKIE_SECURE=False,
        REMEMBER_COOKIE_SECURE=False,
        SESSION_COOKIE_HTTPONLY=True,
        REMEMBER_COOKIE_HTTPONLY=True,
        SECRET_KEY=secret_key,
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
        WTF_CSRF_TIME_LIMIT=3600,
        MAX_CONTENT_LENGTH=16 * 1024 * 1024  # 16MB max-limit
    )

    # Inicializar CSRF
    csrf = CSRFProtect()
    csrf.init_app(app)

    # --- Autenticación básica ---
    USERS = {
        'admin': generate_password_hash('admin123')
    }

    def is_default_password(username, password):
        return username == 'admin' and password == 'admin123'

    # Control de intentos fallidos de login
    FAILED_LOGIN_ATTEMPTS = {}
    LOGIN_BLOCKED = {}
    LOGIN_BLOCK_LIMIT = 5
    BLOCK_TIME_SECONDS = 900  # 15 minutos

    def login_required(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not session.get('logged_in'):
                return redirect(url_for('login'))
            return f(*args, **kwargs)
        return decorated_function

    @app.route('/login', methods=['GET', 'POST'])
    def login():
        error = None
        if request.method == 'POST':
            username = request.form.get('username')
            password = request.form.get('password')
            
            # Verificar si el usuario está bloqueado
            if username in LOGIN_BLOCKED:
                if time.time() < LOGIN_BLOCKED[username]:
                    remaining_time = int((LOGIN_BLOCKED[username] - time.time()) / 60)
                    error = f'Usuario bloqueado. Intente nuevamente en {remaining_time} minutos.'
                else:
                    del LOGIN_BLOCKED[username]
                    FAILED_LOGIN_ATTEMPTS[username] = 0
            
            if not error and username in USERS and check_password_hash(USERS[username], password):
                session['logged_in'] = True
                session['username'] = username
                
                # Forzar cambio de contraseña por defecto
                if is_default_password(username, password):
                    session['force_change_password'] = True
                    flash('¡Debes cambiar la contraseña por defecto!', 'warning')
                    return redirect(url_for('change_password'))
                
                FAILED_LOGIN_ATTEMPTS[username] = 0
                flash('Inicio de sesión exitoso.', 'success')
                return redirect(url_for('index'))
            else:
                if username in USERS:
                    FAILED_LOGIN_ATTEMPTS[username] = FAILED_LOGIN_ATTEMPTS.get(username, 0) + 1
                    if FAILED_LOGIN_ATTEMPTS[username] >= LOGIN_BLOCK_LIMIT:
                        LOGIN_BLOCKED[username] = time.time() + BLOCK_TIME_SECONDS
                        error = 'Demasiados intentos fallidos. Usuario bloqueado temporalmente.'
                    else:
                        error = 'Usuario o contraseña incorrectos.'
                else:
                    error = 'Usuario o contraseña incorrectos.'
        
        # Advertencia si la contraseña por defecto sigue activa
        default_pwd_active = check_password_hash(USERS.get('admin',''), 'admin123')
        return render_template('login.html', error=error, default_pwd_active=default_pwd_active)

    @app.route('/logout')
    def logout():
        session.clear()
        flash('Sesión cerrada.', 'info')
        return redirect(url_for('login'))

    @app.route('/change_password', methods=['GET', 'POST'])
    @login_required
    def change_password():
        if request.method == 'POST':
            new_password = request.form.get('new_password')
            confirm_password = request.form.get('confirm_password')
            
            if not new_password or len(new_password) < 8:
                flash('La nueva contraseña debe tener al menos 8 caracteres.', 'danger')
            elif new_password != confirm_password:
                flash('Las contraseñas no coinciden.', 'danger')
            elif is_default_password(session['username'], new_password):
                flash('No puedes usar la contraseña por defecto.', 'danger')
            else:
                USERS[session['username']] = generate_password_hash(new_password)
                session.pop('force_change_password', None)
                flash('Contraseña cambiada con éxito.', 'success')
                return redirect(url_for('index'))
        
        return render_template('change_password.html', force_change=True)

    @app.route('/')
    @login_required
    def index():
        """
        Página principal con estadísticas del sistema
        """
        import time
        start_time = time.time()
        try:
            # Debug logging
            app.logger.debug(f"Index route called")
            
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
            app.logger.info(f"[PERF] index route duration: {time.time() - start_time:.3f}s")
            return response
        except Exception as e:
            app.logger.error(f"Error in index route: {str(e)}")
            flash(_('Error loading system information'), 'danger')
            return render_template('error.html', error=str(e)), 500

except Exception as e:
    app_logger.error(f'Error durante la inicialización: {e}', exc_info=True)
    raise

finally:
    end_time = time.time()
    app_logger.info(f'Tiempo de inicialización: {end_time - start_time:.2f} segundos')

# Registrar blueprints WiFi, VPN, AdBlock, hostapd, WireGuard y Security
app_logger.info('Registrando blueprints de la aplicación')
try:
    start_blueprint_time = time.time()
    app.register_blueprint(wifi_bp)
    app.register_blueprint(vpn_bp)
    app.register_blueprint(adblock_bp)
    app.register_blueprint(hostapd_bp)
    app.register_blueprint(wireguard_bp)
    app.register_blueprint(security_bp)
    end_blueprint_time = time.time()
    app_logger.info(f'Tiempo de registro de blueprints: {end_blueprint_time - start_blueprint_time:.2f} segundos')
except Exception as e:
    app_logger.error(f'Error al registrar blueprints: {e}', exc_info=True)
    raise

# Configuración avanzada de seguridad HTTP (Flask-Talisman)
# Reglas menos restrictivas para HTTPS
Talisman(app, content_security_policy={
    'default-src': ['*', 'data:', 'blob:', 'https:'],
    'img-src': ['*', 'data:', 'blob:', 'https:'],
    'script-src': ['*', 'data:', 'https:', "'unsafe-inline'", "'unsafe-eval'"],
    'style-src': ['*', 'data:', 'https:', "'unsafe-inline'"],
    'connect-src': ['*', 'https:'],
    'font-src': ['*', 'data:', 'https:'],
    'frame-src': ['*', 'https:'],
}, force_https=False)  # Desactivar redirección HTTPS forzada

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
from apsta_routes import apsta_bp
app.register_blueprint(apsta_bp)

@app.context_processor
def inject_logged_in():
    from flask import session
    return {'logged_in': session.get('logged_in', False)}

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

# Variables globales de seguridad
FAILED_ATTEMPTS = defaultdict(int)
BLOCKED_IPS = set()

# Importar y compartir las variables con el módulo security
from security.security_routes import FAILED_ATTEMPTS, BLOCKED_IPS

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
app_logger.info('Inicializando configuración de HostBerry')
try:
    start_config_time = time.time()
    config = HostBerryConfig()
    end_config_time = time.time()
    app_logger.info(f'Tiempo de inicialización de configuración: {end_config_time - start_config_time:.2f} segundos')
except Exception as e:
    app_logger.error(f'Error al inicializar configuración: {e}', exc_info=True)
    raise

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
    except Exception:
        return None

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
@login_required
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
@login_required
def security_logs():
    try:
        # Obtener IPs bloqueadas
        blocked_ips = list(BLOCKED_IPS)
        
        # Obtener intentos fallidos
        failed_attempts = []
        for ip, attempts in FAILED_ATTEMPTS.items():
            if attempts > 0:
                failed_attempts.append({
                    'ip': ip,
                    'attempts': attempts,
                    'blocked': ip in BLOCKED_IPS
                })
        
        # Obtener logs de seguridad del sistema
        security_logs = []
        try:
            with open('/var/log/auth.log', 'r') as f:
                for line in f.readlines()[-100:]:  # Últimas 100 líneas
                    if 'Failed password' in line or 'Invalid user' in line or 'Connection closed' in line:
                        security_logs.append({
                            'timestamp': line.split(' ')[0:3],
                            'message': line.strip()
                        })
        except Exception as e:
            app.logger.error(f"Error reading auth.log: {e}")
        
        # Obtener estadísticas de iptables
        try:
            iptables_rules = subprocess.check_output(['iptables', '-L', '-n', '-v'], text=True)
            blocked_count = iptables_rules.count('DROP')
        except Exception as e:
            app.logger.error(f"Error getting iptables stats: {e}")
            blocked_count = 0
        
        return render_template('security_logs.html', 
                             blocked_ips=blocked_ips,
                             failed_attempts=failed_attempts,
                             security_logs=security_logs,
                             blocked_count=blocked_count)
    except Exception as e:
        app.logger.error(f"Error retrieving security logs: {str(e)}")
        flash(_('Error al obtener los logs de seguridad'), 'danger')
        return render_template('security_logs.html', 
                             blocked_ips=[],
                             failed_attempts=[],
                             security_logs=[],
                             blocked_count=0)

@app.route('/security/save', methods=['POST'])
@login_required
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
        # Logging adicional para diagnóstico
        app.logger.info(f'Iniciando apply_config con datos: {request.get_json()}')
        config_data = request.get_json()
        results = {}
        
        # Define script paths
        # Usar rutas relativas desde el directorio de la aplicación
        base_scripts_path = os.path.join(os.path.dirname(__file__), 'scripts')
        scripts = {
            'network': os.path.join(base_scripts_path, 'network.sh'),
            'security': os.path.join(base_scripts_path, 'security.sh'),
            'monitoring': os.path.join(base_scripts_path, 'monitoring.sh')
        }
        
        for feature, script_path in scripts.items():
            app.logger.info(f'Procesando feature: {feature}, script_path: {script_path}')
            if config_data.get(f'apply_{feature}', False):
                if os.path.exists(script_path):
                    try:
                        app.logger.info(f'Ejecutando script: {script_path}')
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
                        app.logger.info(f'Script {script_path} ejecutado con éxito')
                    except subprocess.CalledProcessError as e:
                        app.logger.error(f'Error ejecutando script {script_path}: {e.stderr}')
                        results[feature] = {
                            'success': False,
                            'error': e.stderr
                        }
                else:
                    app.logger.error(f'Script no encontrado: {script_path}')
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

@app.route('/network-stats')
def network_stats():
    global last_net_io, last_stats_time
    current_time = time.time()

    total_upload_bps = 0
    total_download_bps = 0

    try:
        current_net_io = psutil.net_io_counters(pernic=True)

        for interface, io_stats in current_net_io.items():
            if interface == 'lo':  # Skip loopback interface
                continue

            if interface in last_net_io and interface in last_stats_time:
                time_delta = current_time - last_stats_time[interface]
                if time_delta > 0:
                    bytes_sent_delta = io_stats.bytes_sent - last_net_io[interface].bytes_sent
                    bytes_recv_delta = io_stats.bytes_recv - last_net_io[interface].bytes_recv

                    total_upload_bps += (bytes_sent_delta / time_delta)
                    total_download_bps += (bytes_recv_delta / time_delta)
            
            # Update last known stats for this interface
            last_net_io[interface] = io_stats
            last_stats_time[interface] = current_time
        
        # Convert Bps to KBps for the response
        upload_kbps = (total_upload_bps / 1024) if total_upload_bps > 0 else 0
        download_kbps = (total_download_bps / 1024) if total_download_bps > 0 else 0
        
        return jsonify({'upload': round(upload_kbps, 2), 'download': round(download_kbps, 2)})

    except Exception as e:
        app.logger.error(f"Error in /network-stats: {str(e)}")
        return jsonify({'upload': 0, 'download': 0, 'error': str(e)}), 500

@app.route('/status')
def status():
    import time
    start_time = time.time()
    # Obtener estadísticas del sistema
    stats = get_system_stats(force_refresh=True)
    network_interface = get_network_interface()
    local_ip = get_ip_address()
    # Intentar obtener el SSID del WiFi
    try:
        ssid = subprocess.run(['iwgetid', '-r'], capture_output=True, text=True)
        wifi_ssid = ssid.stdout.strip() if ssid.returncode == 0 else ''
    except Exception:
        wifi_ssid = ''
    # Intentar obtener el estado de hostapd
    try:
        hostapd_status = subprocess.run(['systemctl', 'is-active', 'hostapd'], capture_output=True, text=True)
        hostapd_status_str = hostapd_status.stdout.strip() if hostapd_status.returncode == 0 else 'unknown'
    except Exception:
        hostapd_status_str = 'unknown'
    app.logger.info(f"[PERF] status route duration: {time.time() - start_time:.3f}s")
    return jsonify({
        'stats': stats,
        'network_interface': network_interface,
        'local_ip': local_ip,
        'wifi_ssid': wifi_ssid,
        'hostapd_status': hostapd_status_str
    })

# --- Manejador global de errores para respuestas JSON ---
from flask import jsonify

@app.errorhandler(Exception)
def handle_exception(e):
    app.logger.error(f"Excepción no controlada: {e}")
    return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/init-session')
def init_session():
    session['init'] = True
    return jsonify({'ok': True})

if __name__ == '__main__':
    # Solo para desarrollo local. En producción usar Gunicorn.
    import socket
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(('8.8.8.8', 80))
        local_ip = s.getsockname()[0]
        s.close()
    except Exception:
        local_ip = 'localhost'
    print(f"\n[INFO] Accede a la app desde otros dispositivos en: http://{local_ip}:5000\n")

    # Asegura que el directorio de logs tenga permisos correctos
    import os
    log_dir = 'logs'
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
    try:
        import pwd
        os.chown(log_dir, pwd.getpwnam('www-data').pw_uid, pwd.getpwnam('www-data').pw_gid)
    except Exception:
        pass  # Ignora si no se puede cambiar el propietario

    # IMPORTANTE: Para producción usa Gunicorn y configura debug=False
    app.run(host='0.0.0.0', port=5000, debug=True)  # Activamos debug para desarrollo