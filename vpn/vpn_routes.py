from flask import Blueprint, request, jsonify, render_template, flash, redirect, url_for, current_app as app, session
import os
import subprocess
import time
import re
import logging
from werkzeug.utils import secure_filename
from . import vpn_bp
from .vpn_utils import vpn_utils

logger = logging.getLogger(__name__)

# --- Seguridad subida archivos ---
ALLOWED_EXTENSIONS = {'.ovpn', '.conf'}
MAX_FILE_SIZE = 512 * 1024  # 512 KB

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

@vpn_bp.route('/vpn', methods=['GET'])
def vpn_page():
    """Renderiza la página de configuración de VPN"""
    try:
        # Verificar si OpenVPN está instalado
        subprocess.run(['which', 'openvpn'], check=True, capture_output=True)
        openvpn_installed = True
    except subprocess.CalledProcessError:
        openvpn_installed = False
        
    return render_template('vpn.html', openvpn_installed=openvpn_installed)

@vpn_bp.route('/api/vpn/config', methods=['POST'])
@login_required
def vpn_config_api():
    """API para configurar la VPN"""
    try:
        # Verificar permisos sudo
        if not vpn_utils.verify_sudo():
            return jsonify({
                'success': False,
                'error': 'Se requieren permisos de administrador para configurar la VPN'
            }), 403

        # Verificar si se proporcionó un archivo
        if 'vpn_file' not in request.files:
            return jsonify({'success': False, 'error': 'No se proporcionó archivo de configuración'}), 400

        file = request.files['vpn_file']
        if file.filename == '':
            return jsonify({'success': False, 'error': 'Nombre de archivo vacío'}), 400

        # Validar extensión y tamaño
        filename = secure_filename(file.filename)
        ext = os.path.splitext(filename)[1].lower()
        if ext not in ALLOWED_EXTENSIONS:
            return jsonify({'success': False, 'error': 'Extensión de archivo no permitida'}), 400
        file.seek(0, os.SEEK_END)
        size = file.tell()
        file.seek(0)
        if size > MAX_FILE_SIZE:
            return jsonify({'success': False, 'error': 'Archivo demasiado grande (máx 512KB)'}), 400

        # Obtener y validar credenciales
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        
        if not username or not password:
            return jsonify({
                'success': False,
                'error': 'Usuario y contraseña son requeridos'
            }), 400

        # Guardar credenciales
        success, message = vpn_utils.save_credentials(username, password)
        if not success:
            return jsonify({
                'success': False,
                'error': f'Error guardando credenciales: {message}'
            }), 500

        # Crear directorio si no existe
        vpn_dir = '/etc/openvpn'
        if not os.path.exists(vpn_dir):
            os.makedirs(vpn_dir, mode=0o755)

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
            
            # Verificar integridad del archivo
            is_valid, message = vpn_utils.verify_config_file(config_path)
            if not is_valid:
                return jsonify({
                    'success': False,
                    'error': f'Archivo de configuración inválido: {message}'
                }), 400
            
            # Establecer permisos seguros
            os.chmod(config_path, 0o644)
            
            logger.info(f"Archivo de configuración guardado correctamente en {config_path}")
        except Exception as e:
            logger.error(f"Error al guardar archivo de configuración: {str(e)}")
            return jsonify({
                'success': False, 
                'error': f'Error al guardar archivo de configuración: {str(e)}'
            }), 500

        # Verificar y actualizar configuración
        try:
            with open(config_path, 'r') as f:
                config_content = f.read()

            # Eliminar todas las líneas auth-user-pass existentes
            config_lines = config_content.splitlines()
            original_lines = list(config_lines)
            
            # Asegurar que auth-user-pass apunte al archivo correcto
            auth_file_path = '/etc/openvpn/auth.txt'
            auth_line_found = False
            new_config_lines = []
            for line in config_lines:
                if re.match(r'^\s*auth-user-pass(\s|$)', line):
                    if os.path.exists(auth_file_path):
                        new_config_lines.append(f'auth-user-pass {auth_file_path}')
                        auth_line_found = True
                else:
                    new_config_lines.append(line)

            if not auth_line_found and os.path.exists(auth_file_path):
                new_config_lines.append(f'auth-user-pass {auth_file_path}')

            config_content = '\n'.join(new_config_lines) + '\n'

            # Añadir directivas de seguridad
            security_directives = {
                'dhcp-option DNS 8.8.8.8': "Configuración DNS primario",
                'dhcp-option DNS 8.8.4.4': "Configuración DNS secundario",
                'script-security 2': "Seguridad de scripts",
                'up /etc/openvpn/update-resolv-conf': "Script de actualización DNS",
                'down /etc/openvpn/update-resolv-conf': "Script de limpieza DNS",
                'auth-nocache': "No cachear credenciales",
                'verify-x509-name': "Verificación de certificados",
                'remote-cert-tls': "Verificación TLS",
                'cipher AES-256-GCM': "Cifrado fuerte",
                'auth SHA256': "Hash seguro"
            }

            # Eliminar directivas inseguras
            if 'route-nopull' in config_content:
                config_content = config_content.replace('route-nopull', '')
                logger.info("Eliminada opción route-nopull")

            # Añadir directivas de seguridad si no están presentes
            for directive, description in security_directives.items():
                if directive.split()[0] not in config_content:
                    config_content += f'{directive}\n'
                    logger.info(f"Añadida {description}")

            # Guardar configuración actualizada
            if config_content.strip() != '\n'.join(original_lines).strip():
                with open(config_path, 'w') as f:
                    f.write(config_content)
                logger.info("Configuración OpenVPN actualizada")

        except Exception as e:
            logger.error(f"Error actualizando configuración: {str(e)}")
            return jsonify({
                'success': False, 
                'error': f'Error actualizando configuración: {str(e)}'
            }), 500

        # Verificar estado actual y reiniciar servicio
        try:
            # Detener VPN si está activa
            subprocess.run(['systemctl', 'stop', 'openvpn'], check=True)
            time.sleep(2)  # Esperar a que se detenga completamente

            # Restaurar rutas originales
            vpn_utils.restore_original_routing()

            # Iniciar VPN con nueva configuración
            subprocess.run(['systemctl', 'start', 'openvpn'], check=True)
            logger.info("Servicio OpenVPN reiniciado correctamente")

            return jsonify({
                'success': True,
                'message': 'Configuración VPN actualizada y servicio reiniciado'
            })

        except subprocess.CalledProcessError as e:
            logger.error(f"Error reiniciando OpenVPN: {str(e)}")
            return jsonify({
                'success': False,
                'error': 'Error reiniciando el servicio OpenVPN'
            }), 500

    except Exception as e:
        logger.error(f"Error general en vpn_config_api: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@vpn_bp.route('/api/vpn/status', methods=['GET'])
def vpn_status_api():
    """API para obtener el estado de la VPN"""
    try:
        # Verificar estado del servicio
        status = subprocess.run(['systemctl', 'is-active', 'openvpn'], capture_output=True, text=True)
        is_active = status.returncode == 0

        # Obtener información de conexión
        public_ip = vpn_utils.get_public_ip()
        vpn_ip = '-'
        if is_active:
            try:
                vpn_ip = subprocess.getoutput("ip addr show tun0 | grep 'inet ' | awk '{print $2}' | cut -d'/' -f1")
            except Exception as e:
                logger.warning(f"Error obteniendo IP VPN: {str(e)}")

        # Verificar configuración
        config_file = '/etc/openvpn/client.conf' if os.path.exists('/etc/openvpn/client.conf') else None
        killswitch_enabled = os.path.exists('/etc/openvpn/killswitch_enabled')

        return jsonify({
            'status': 'Conectado' if is_active else 'Desconectado',
            'public_ip': public_ip,
            'vpn_ip': vpn_ip,
            'config_file': config_file,
            'killswitch_enabled': killswitch_enabled
        })

    except Exception as e:
        logger.error(f'Error obteniendo estado VPN: {str(e)}')
        return jsonify({'error': str(e)}), 500

@vpn_bp.route('/api/vpn/toggle', methods=['POST'])
def toggle_vpn():
    """API para activar/desactivar la VPN"""
    try:
        if not vpn_utils.verify_sudo():
            return jsonify({
                'success': False,
                'error': 'Se requieren permisos de administrador'
            }), 403

        status = subprocess.run(['systemctl', 'is-active', 'openvpn'], capture_output=True, text=True)
        if status.returncode == 0:
            # Desactivar VPN
            subprocess.run(['systemctl', 'stop', 'openvpn'], check=True)
            vpn_utils.restore_original_routing()
            return jsonify({'success': True, 'message': 'VPN desactivada'})
        else:
            # Activar VPN
            subprocess.run(['systemctl', 'start', 'openvpn'], check=True)
            time.sleep(2)  # Esperar a que se inicie
            vpn_utils.configure_vpn_routing()
            return jsonify({'success': True, 'message': 'VPN activada'})

    except Exception as e:
        logger.error(f'Error en toggle_vpn: {str(e)}')
        return jsonify({'success': False, 'error': str(e)}), 500

@vpn_bp.route('/api/vpn/killswitch', methods=['POST'])
def toggle_killswitch():
    """API para activar/desactivar el kill switch"""
    try:
        if not vpn_utils.verify_sudo():
            return jsonify({
                'success': False,
                'error': 'Se requieren permisos de administrador'
            }), 403

        killswitch_enabled = os.path.exists('/etc/openvpn/killswitch_enabled')
        
        if killswitch_enabled:
            # Desactivar kill switch
            vpn_utils.restore_original_routing()
            return jsonify({'success': True, 'message': 'Kill switch desactivado'})
        else:
            # Activar kill switch
            vpn_utils.configure_vpn_routing()
            return jsonify({'success': True, 'message': 'Kill switch activado'})

    except Exception as e:
        logger.error(f'Error en toggle_killswitch: {str(e)}')
        return jsonify({'success': False, 'error': str(e)}), 500

def setup_initial_iptables_rules():
    """Configura las reglas iniciales de iptables para permitir tráfico esencial."""
    try:
        app.logger.info("Configurando reglas iniciales de iptables...")
        # Permitir tráfico local
        subprocess.run(['iptables', '-A', 'INPUT', '-i', 'lo', '-j', 'ACCEPT'], check=True)
        subprocess.run(['iptables', '-A', 'OUTPUT', '-o', 'lo', '-j', 'ACCEPT'], check=True)
        
        # Permitir tráfico de todas las interfaces VPN (tun+)
        subprocess.run(['iptables', '-A', 'INPUT', '-i', 'tun+', '-j', 'ACCEPT'], check=True)
        subprocess.run(['iptables', '-A', 'OUTPUT', '-o', 'tun+', '-j', 'ACCEPT'], check=True)
        
        # Permitir tráfico necesario para mantener la conexión VPN (ej. OpenVPN en UDP 1194)
        # Asegúrate de que el puerto coincida con tu configuración VPN
        subprocess.run(['iptables', '-A', 'INPUT', '-p', 'udp', '--dport', '1194', '-j', 'ACCEPT'], check=True)
        subprocess.run(['iptables', '-A', 'OUTPUT', '-p', 'udp', '--sport', '1194', '-j', 'ACCEPT'], check=True)
        
        # Permitir tráfico DNS (necesario para que la VPN resuelva nombres de host)
        # Esto es un ejemplo, ajusta los puertos si usas un DNS diferente o DoH/DoT.
        subprocess.run(['iptables', '-A', 'OUTPUT', '-p', 'udp', '--dport', '53', '-j', 'ACCEPT'], check=True)
        subprocess.run(['iptables', '-A', 'OUTPUT', '-p', 'tcp', '--dport', '53', '-j', 'ACCEPT'], check=True)
        subprocess.run(['iptables', '-A', 'INPUT', '-p', 'udp', '--sport', '53', '-j', 'ACCEPT'], check=True)
        subprocess.run(['iptables', '-A', 'INPUT', '-p', 'tcp', '--sport', '53', '-j', 'ACCEPT'], check=True)

        app.logger.info("Reglas iniciales de iptables configuradas exitosamente.")
        return True
    except subprocess.CalledProcessError as e:
        app.logger.error(f"Error configurando reglas de iptables: {e}")
        return False
    except Exception as e:
        app.logger.error(f"Error inesperado en setup_initial_iptables_rules: {e}")
        return False
