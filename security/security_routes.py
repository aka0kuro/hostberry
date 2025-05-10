from flask import render_template, jsonify, request, current_app as app, redirect, url_for, flash, session
import subprocess
import os
import logging
import json
from datetime import datetime
import pytz
from collections import defaultdict
from functools import wraps
from flask_wtf import FlaskForm
from wtforms import BooleanField, SelectField
from . import security_bp  # Importar el blueprint desde el módulo actual

# Estado global para el control de intentos fallidos
FAILED_ATTEMPTS = defaultdict(int)
BLOCKED_IPS = set()

class SecurityConfigForm(FlaskForm):
    enable_firewall = BooleanField('Enable Firewall')
    block_icmp = SelectField('ICMP Protection', 
                           choices=[('1', 'Block Ping Requests'), 
                                  ('0', 'Allow Ping Requests')])
    timezone = SelectField('Timezone')
    time_format = SelectField('Time Format')

def get_config():
    """Obtener la configuración actual"""
    from hostberry_config import HostBerryConfig
    return HostBerryConfig()

@security_bp.before_request
def restrict_ip_whitelist():
    """Verificar IP contra whitelist"""
    config = get_config().get_current_config()
    ip_whitelist = config.get('IP_WHITELIST', '').strip()
    if ip_whitelist:
        allowed_ips = [ip.strip() for ip in ip_whitelist.split(',') if ip.strip()]
        if request.remote_addr not in allowed_ips:
            return render_template('blocked.html', 
                                 reason='Your IP is not allowed.'), 403

@security_bp.before_request
def block_on_failed_attempts():
    """Bloquear IPs con demasiados intentos fallidos"""
    config = get_config().get_current_config()
    max_attempts = int(config.get('FAILED_ATTEMPTS_LIMIT', 5))
    ip = request.remote_addr
    
    if ip in BLOCKED_IPS:
        return render_template('blocked.html', 
                             reason='Too many failed attempts.'), 403
        
    if request.endpoint == 'security.security_config' and request.method == 'POST':
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
                flash('Invalid SSH port. Attempt counted as failed.', 'danger')
                return redirect(url_for('security.security_config'))

@security_bp.route('/blocked')
def blocked():
    """Página de bloqueo"""
    reason = request.args.get('reason', 'Access denied.')
    return render_template('blocked.html', reason=reason), 403

@security_bp.route('/security_config', methods=['GET', 'POST'])
def security_config():
    """Configuración de seguridad"""
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
                    
            success = get_config().update_config({
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
                flash('Configuración guardada correctamente', 'success')
                return redirect(url_for('security.security_config'))
            else:
                flash('Error al guardar la configuración', 'danger')
        except Exception as e:
            flash(f'Error al procesar el formulario: {str(e)}', 'danger')
    
    current_config = get_config().get_current_config()
    
    # Obtener estado actual de seguridad
    try:
        rules_count = int(subprocess.check_output(['iptables', '-L', '-n', '--line-numbers'])
                         .decode().count('\n')) - 2
        blocked_ips = int(subprocess.check_output(['iptables', '-L', 'INPUT', '-n', '-v'])
                         .decode().count('DROP'))
        last_attack = None  # Esto vendría del análisis de logs en una implementación real
    except Exception as e:
        app.logger.error(f"Error obteniendo estado de seguridad: {str(e)}")
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
            'last_check': datetime.utcnow()
        },
        timezones=pytz.all_timezones,
        time_formats=['%Y-%m-%d %H:%M', '%d/%m/%Y %H:%M', '%m/%d/%Y %I:%M %p'],
        pytz=pytz
    )

@security_bp.route('/security/logs')
def security_logs():
    """Página de logs de seguridad"""
    try:
        # Obtener IPs bloqueadas de iptables
        blocked_ips = []
        try:
            # Obtener reglas de iptables con números de línea y detalles
            iptables_output = subprocess.check_output(['iptables', '-L', 'INPUT', '-n', '-v', '--line-numbers'], text=True)
            
            # Procesar la salida línea por línea
            for line in iptables_output.split('\n'):
                if 'DROP' in line:
                    # Extraer IP de la línea
                    parts = line.split()
                    # Buscar la IP en la línea (está después de 'DROP')
                    drop_index = line.find('DROP')
                    if drop_index != -1:
                        # Obtener la parte después de DROP
                        after_drop = line[drop_index:].split()
                        if len(after_drop) > 1:
                            # La IP suele estar después de 'DROP'
                            ip = after_drop[1]
                            if ip not in blocked_ips and ip != '0.0.0.0/0' and ip != 'anywhere':
                                blocked_ips.append(ip)
                                app.logger.debug(f"Found blocked IP: {ip} in line: {line}")
        except Exception as e:
            app.logger.error(f"Error getting blocked IPs from iptables: {e}")
        
        # Obtener intentos fallidos
        failed_attempts = []
        for ip, attempts in FAILED_ATTEMPTS.items():
            if attempts > 0:
                failed_attempts.append({
                    'ip': ip,
                    'attempts': attempts,
                    'blocked': ip in blocked_ips
                })
        
        # Obtener logs de seguridad del sistema
        security_logs = []
        log_files = [
            '/var/log/auth.log',
            '/var/log/syslog',
            '/var/log/iptables.log'
        ]
        
        for log_file in log_files:
            if os.path.exists(log_file):
                try:
                    with open(log_file, 'r') as f:
                        for line in f.readlines()[-100:]:  # Últimas 100 líneas
                            if any(keyword in line.lower() for keyword in 
                                  ['failed', 'error', 'warning', 'blocked', 'attack']):
                                security_logs.append({
                                    'timestamp': line[:19],
                                    'message': line[20:].strip()
                                })
                except Exception as e:
                    app.logger.error(f"Error reading {log_file}: {e}")
        
        # Obtener estadísticas de iptables
        try:
            iptables_rules = subprocess.check_output(['iptables', '-L', 'INPUT', '-n', '-v'], text=True)
            blocked_count = len(blocked_ips)  # Usar el número real de IPs bloqueadas
        except Exception as e:
            app.logger.error(f"Error getting iptables stats: {e}")
            blocked_count = 0
        
        app.logger.info(f"Blocked IPs: {blocked_ips}")  # Log para debugging
        app.logger.info(f"Blocked count: {blocked_count}")  # Log para debugging
        
        return render_template('security_logs.html', 
                             blocked_ips=blocked_ips,
                             failed_attempts=failed_attempts,
                             security_logs=security_logs,
                             blocked_count=blocked_count)
    except Exception as e:
        app.logger.error(f"Error retrieving security logs: {str(e)}")
        flash('Error al obtener los logs de seguridad', 'danger')
        return render_template('security_logs.html', 
                             blocked_ips=[],
                             failed_attempts=[],
                             security_logs=[],
                             blocked_count=0)

@security_bp.route('/security/save', methods=['POST'])
def save_security_settings():
    """Guardar configuración de seguridad"""
    try:
        # Obtener datos del formulario
        settings = {
            'SESSION_COOKIE_SECURE': request.form.get('cookie_secure') == 'true',
            'SESSION_COOKIE_HTTPONLY': request.form.get('cookie_httponly') == 'true',
            'SESSION_COOKIE_SAMESITE': request.form.get('cookie_samesite', 'Lax'),
            'PERMANENT_SESSION_LIFETIME': int(request.form.get('session_lifetime', 86400))
        }
        
        # Actualizar configuración en tiempo de ejecución
        for key, value in settings.items():
            app.config[key] = value
            
        # Guardar en archivo de configuración persistente
        config_path = os.path.join(os.path.dirname(__file__), 'config.json')
        with open(config_path, 'w') as f:
            json.dump(settings, f, indent=4)
            
        # Actualizar archivo .env con timestamp
        with open('.env', 'a') as f:
            f.write(f'\n# Security settings updated at {datetime.now()}\n')
            
        flash('Security settings saved successfully', 'success')
        return jsonify({'success': True})
        
    except Exception as e:
        app.logger.error(f'Error saving security settings: {str(e)}')
        flash('Failed to save security settings', 'danger')
        return jsonify({'success': False, 'error': str(e)}), 500

@security_bp.route('/security/check_firewall')
def check_firewall_status():
    """Verificar estado del firewall"""
    try:
        # Verificar si iptables está activo
        iptables_status = subprocess.run(['iptables', '-L'], 
                                       capture_output=True, 
                                       text=True)
        
        # Contar reglas
        rules_count = iptables_status.stdout.count('\n') - 2
        
        # Verificar si hay reglas de bloqueo
        blocked_count = iptables_status.stdout.count('DROP')
        
        return jsonify({
            'success': True,
            'active': rules_count > 0,
            'rules_count': rules_count,
            'blocked_count': blocked_count
        })
    except Exception as e:
        app.logger.error(f"Error checking firewall status: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@security_bp.route('/security/unblock/<ip>', methods=['POST'])
def unblock_ip(ip):
    """Desbloquear una IP específica"""
    try:
        # Eliminar la regla de iptables para la IP
        subprocess.run(['iptables', '-D', 'INPUT', '-s', ip, '-j', 'DROP'], check=True)
        app.logger.info(f"IP {ip} desbloqueada exitosamente")
        return jsonify({'success': True})
    except Exception as e:
        app.logger.error(f"Error al desbloquear IP {ip}: {e}")
        return jsonify({'success': False, 'error': str(e)}) 