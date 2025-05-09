from flask import render_template, jsonify, request, current_app as app, session, redirect, url_for, flash
import subprocess
import os
import logging
import json
from datetime import datetime
from werkzeug.utils import secure_filename
from . import wireguard_bp  # Importar el blueprint desde el módulo actual

# --- Seguridad subida archivos ---
ALLOWED_EXTENSIONS = {'.conf'}
MAX_FILE_SIZE = 256 * 1024  # 256 KB

def allowed_file(filename):
    return '.' in filename and os.path.splitext(filename)[1].lower() in ALLOWED_EXTENSIONS

def login_required(f):
    from functools import wraps
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('logged_in'):
            flash('Debes iniciar sesión para acceder a esta sección.', 'warning')
            return redirect(url_for('login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function

@wireguard_bp.route('/wireguard')
def wireguard_page():
    """Página principal de configuración de WireGuard"""
    try:
        # Verificar si WireGuard está instalado
        wg_installed = subprocess.run(['which', 'wg'], capture_output=True).returncode == 0
        
        # Obtener estado del servicio
        wg_status = subprocess.run(['systemctl', 'is-active', 'wg-quick@wg0'], 
                                 capture_output=True, 
                                 text=True)
        is_running = wg_status.returncode == 0
        
        # Obtener configuración actual
        config = None
        if os.path.exists('/etc/wireguard/wg0.conf'):
            with open('/etc/wireguard/wg0.conf', 'r') as f:
                config = f.read()
                
        # Obtener información de la interfaz
        interface_info = {}
        if is_running:
            try:
                wg_show = subprocess.run(['wg', 'show'], 
                                       capture_output=True, 
                                       text=True)
                if wg_show.returncode == 0:
                    interface_info['raw_output'] = wg_show.stdout
            except Exception as e:
                app.logger.error(f"Error al obtener información de la interfaz: {str(e)}")
        
        return render_template(
            'wireguard.html',
            wg_installed=wg_installed,
            is_running=is_running,
            config=config,
            interface_info=interface_info
        )
    except Exception as e:
        app.logger.error(f"Error en wireguard_page: {str(e)}")
        return render_template('wireguard.html', 
                             wg_installed=False, 
                             is_running=False, 
                             config=None, 
                             error=str(e))

@wireguard_bp.route('/wireguard/config', methods=['POST'])
@login_required
def wireguard_config():
    """Guardar la configuración de WireGuard"""
    try:
        # Soporte para subida de archivo
        if 'wg_file' in request.files:
            file = request.files['wg_file']
            if file.filename == '':
                return jsonify({'success': False, 'error': 'Nombre de archivo vacío'}), 400
            filename = secure_filename(file.filename)
            ext = os.path.splitext(filename)[1].lower()
            if ext not in ALLOWED_EXTENSIONS:
                return jsonify({'success': False, 'error': 'Extensión no permitida'}), 400
            file.seek(0, os.SEEK_END)
            size = file.tell()
            file.seek(0)
            if size > MAX_FILE_SIZE:
                return jsonify({'success': False, 'error': 'Archivo demasiado grande (máx 256KB)'}), 400
            config = file.read().decode('utf-8', errors='ignore')
        else:
            config = request.form.get('config', '')

        if not config:
            return jsonify({'success': False, 'error': 'No config provided'}), 400
            
        # Validar la configuración antes de guardar
        if not validate_wireguard_config(config):
            return jsonify({'success': False, 'error': 'Configuración inválida'}), 400
            
        # Hacer backup de la configuración actual
        if os.path.exists('/etc/wireguard/wg0.conf'):
            backup_path = f'/etc/wireguard/wg0.conf.bak.{datetime.now().strftime("%Y%m%d_%H%M%S")}'
            os.rename('/etc/wireguard/wg0.conf', backup_path)
            
        # Guardar nueva configuración
        with open('/etc/wireguard/wg0.conf', 'w') as f:
            f.write(config)
            
        return jsonify({'success': True, 'message': 'Configuración guardada'})
    except Exception as e:
        app.logger.error(f"Error en wireguard_config: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@wireguard_bp.route('/wireguard/toggle', methods=['POST'])
def wireguard_toggle():
    """Iniciar o detener el servicio WireGuard"""
    try:
        action = request.form.get('action', '')
        if action not in ['start', 'stop']:
            return jsonify({'success': False, 'error': 'Acción inválida'}), 400
            
        subprocess.run(['systemctl', action, 'wg-quick@wg0'], check=True)
        return jsonify({'success': True, 'message': f'WireGuard {action} ejecutado'})
    except subprocess.CalledProcessError as e:
        app.logger.error(f"Error al {action} WireGuard: {str(e)}")
        return jsonify({'success': False, 'error': f'Error al {action} WireGuard'}), 500
    except Exception as e:
        app.logger.error(f"Error en wireguard_toggle: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@wireguard_bp.route('/wireguard/status')
def wireguard_status():
    """Obtener el estado actual de WireGuard"""
    try:
        status = subprocess.run(['systemctl', 'is-active', 'wg-quick@wg0'], 
                              capture_output=True, 
                              text=True)
        is_running = status.returncode == 0
        
        # Obtener información detallada si está corriendo
        interface_info = {}
        if is_running:
            wg_show = subprocess.run(['wg', 'show'], 
                                   capture_output=True, 
                                   text=True)
            if wg_show.returncode == 0:
                interface_info['raw_output'] = wg_show.stdout
                
        return jsonify({
            'success': True, 
            'running': is_running, 
            'status': status.stdout.strip(),
            'interface_info': interface_info
        })
    except Exception as e:
        app.logger.error(f"Error en wireguard_status: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@wireguard_bp.route('/wireguard/check_installation')
def check_wireguard_installation():
    """Verificar si WireGuard está instalado"""
    try:
        result = subprocess.run(['which', 'wg'], capture_output=True)
        is_installed = result.returncode == 0
        
        if is_installed:
            version = subprocess.run(['wg', '--version'], 
                                  capture_output=True, 
                                  text=True).stdout.strip()
        else:
            version = None
            
        return jsonify({
            'success': True,
            'installed': is_installed,
            'version': version
        })
    except Exception as e:
        app.logger.error(f"Error en check_wireguard_installation: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@wireguard_bp.route('/wireguard/generate_keys', methods=['POST'])
def generate_wireguard_keys():
    """Generar un nuevo par de claves para WireGuard"""
    try:
        # Generar clave privada
        private_key = subprocess.run(['wg', 'genkey'], 
                                   capture_output=True, 
                                   text=True).stdout.strip()
        
        # Generar clave pública
        public_key = subprocess.run(['wg', 'pubkey'], 
                                  input=private_key.encode(), 
                                  capture_output=True, 
                                  text=True).stdout.strip()
        
        return jsonify({
            'success': True,
            'private_key': private_key,
            'public_key': public_key
        })
    except Exception as e:
        app.logger.error(f"Error en generate_wireguard_keys: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

def validate_wireguard_config(config):
    """Validar la configuración de WireGuard"""
    try:
        # Verificar secciones básicas
        if '[Interface]' not in config:
            return False
            
        # Verificar claves requeridas
        required_keys = ['PrivateKey']
        for key in required_keys:
            if key not in config:
                return False
                
        # Verificar formato de direcciones IP
        import re
        ip_pattern = r'^(\d{1,3}\.){3}\d{1,3}/\d{1,2}$'
        for line in config.split('\n'):
            if 'Address' in line:
                ip = line.split('=')[1].strip()
                if not re.match(ip_pattern, ip):
                    return False
                    
        return True
    except Exception as e:
        app.logger.error(f"Error en validate_wireguard_config: {str(e)}")
        return False 