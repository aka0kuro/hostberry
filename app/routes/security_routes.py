from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, current_app as app
from flask_babel import _
from flask_wtf import FlaskForm
from wtforms import BooleanField, SelectField
import subprocess
import os
import json
import datetime
import pytz
from app.config import save_config

# Blueprint
security_bp = Blueprint('security', __name__)

# --- Formulario de Configuración de Seguridad ---
class SecurityConfigForm(FlaskForm):
    enable_firewall = BooleanField('Enable Firewall')
    block_icmp = SelectField('ICMP Protection', choices=[('1', 'Block Ping Requests'), ('0', 'Allow Ping Requests')])
    timezone = SelectField('Timezone')
    time_format = SelectField('Time Format')

# --- Rutas de Seguridad ---
@security_bp.route('/security_config', methods=['GET', 'POST'])
def security_config():
    form = SecurityConfigForm()
    if request.method == 'POST':
        try:
            firewall_enabled = 'enable_firewall' in request.form
            block_icmp = request.form.get('block_icmp') == '1'
            timezone = request.form.get('timezone')
            time_format = request.form.get('time_format')

            save_config('FIREWALL_ENABLED', firewall_enabled)
            save_config('BLOCK_ICMP', block_icmp)
            save_config('TIMEZONE', timezone)
            save_config('TIME_FORMAT', time_format)

            flash(_('Configuración guardada correctamente'), 'success')
            return redirect(url_for('security.security_config'))
        except Exception as e:
            flash(_('Error al procesar el formulario: %(error)s', error=str(e)), 'danger')
    
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
        config=app.config,
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

@security_bp.route('/security/logs')
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

@security_bp.route('/security/save', methods=['POST'])
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
