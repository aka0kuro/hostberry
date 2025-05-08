from flask import render_template, jsonify, request, current_app as app
import subprocess
import os
import logging
from . import hostapd_bp  # Importar el blueprint desde el módulo actual

@hostapd_bp.route('/hostapd')
def hostapd_page():
    """Página principal de configuración de hostapd"""
    try:
        hostapd_installed = subprocess.run(['which', 'hostapd'], capture_output=True).returncode == 0
        hostapd_status = subprocess.run(['systemctl', 'is-active', 'hostapd'], capture_output=True, text=True)
        is_running = hostapd_status.returncode == 0
        config = None
        
        if os.path.exists('/etc/hostapd/hostapd.conf'):
            with open('/etc/hostapd/hostapd.conf', 'r') as f:
                config = f.read()
                
        return render_template(
            'hostapd.html',
            hostapd_installed=hostapd_installed,
            is_running=is_running,
            config=config
        )
    except Exception as e:
        app.logger.error(f"Error en hostapd_page: {str(e)}")
        return render_template('hostapd.html', 
                             hostapd_installed=False, 
                             is_running=False, 
                             config=None, 
                             error=str(e))

@hostapd_bp.route('/hostapd/config', methods=['POST'])
def hostapd_config():
    """Guardar la configuración de hostapd"""
    try:
        config = request.form.get('config', '')
        if not config:
            return jsonify({'success': False, 'error': 'No config provided'}), 400
            
        with open('/etc/hostapd/hostapd.conf', 'w') as f:
            f.write(config)
            
        return jsonify({'success': True, 'message': 'Configuración guardada'})
    except Exception as e:
        app.logger.error(f"Error en hostapd_config: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@hostapd_bp.route('/hostapd/toggle', methods=['POST'])
def hostapd_toggle():
    """Iniciar o detener el servicio hostapd"""
    try:
        action = request.form.get('action', '')
        if action not in ['start', 'stop']:
            return jsonify({'success': False, 'error': 'Acción inválida'}), 400
            
        subprocess.run(['systemctl', action, 'hostapd'], check=True)
        return jsonify({'success': True, 'message': f'hostapd {action} ejecutado'})
    except subprocess.CalledProcessError as e:
        app.logger.error(f"Error al {action} hostapd: {str(e)}")
        return jsonify({'success': False, 'error': f'Error al {action} hostapd'}), 500
    except Exception as e:
        app.logger.error(f"Error en hostapd_toggle: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@hostapd_bp.route('/hostapd/status')
def hostapd_status():
    """Obtener el estado actual de hostapd"""
    try:
        status = subprocess.run(['systemctl', 'is-active', 'hostapd'], 
                              capture_output=True, 
                              text=True)
        is_running = status.returncode == 0
        return jsonify({
            'success': True, 
            'running': is_running, 
            'status': status.stdout.strip()
        })
    except Exception as e:
        app.logger.error(f"Error en hostapd_status: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@hostapd_bp.route('/hostapd/check_installation')
def check_hostapd_installation():
    """Verificar si hostapd está instalado"""
    try:
        result = subprocess.run(['which', 'hostapd'], capture_output=True)
        is_installed = result.returncode == 0
        
        if is_installed:
            version = subprocess.run(['hostapd', '-v'], 
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
        app.logger.error(f"Error en check_hostapd_installation: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500 