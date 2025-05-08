from flask import Blueprint, request, jsonify, render_template, flash, redirect, url_for, current_app as app
import os
import subprocess
import time
import re
from . import vpn_bp  # Importar el blueprint desde el módulo actual
from .vpn_utils import configure_vpn_routing, restore_original_routing

@vpn_bp.route('/vpn', methods=['GET'])
def vpn_page():
    """Renderiza la página de configuración de VPN"""
    return render_template('vpn.html')

@vpn_bp.route('/api/vpn/config', methods=['POST'])
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
                'dhcp-option DNS 8.8.8.8': "Añadida configuración de DNS 8.8.8.8.",
                'dhcp-option DNS 8.8.4.4': "Añadida configuración de DNS 8.8.4.4.",
                'script-security 2': "Añadida configuración script-security 2.",
                'up /etc/openvpn/update-resolv-conf': "Añadida configuración up script para DNS.",
                'down /etc/openvpn/update-resolv-conf': "Añadida configuración down script para DNS."
            }

            # Eliminar route-nopull si está presente
            if 'route-nopull' in config_content:
                config_content = config_content.replace('route-nopull', '')
                app.logger.info("Eliminada opción route-nopull del archivo de configuración.")

            # Añadir directivas necesarias si no están presentes
            for directive, log_message in common_directives.items():
                if directive.split()[0] not in config_content:
                    config_content += f'{directive}\n'
                    app.logger.info(log_message)

            # Guardar los cambios en el archivo de configuración
            if config_content.strip() != '\n'.join(original_lines).strip():
                with open(config_path, 'w') as f:
                    f.write(config_content)
                app.logger.info(f"Archivo de configuración OpenVPN '{config_path}' actualizado.")
        except Exception as e:
            app.logger.error(f"Error al guardar archivo de configuración: {str(e)}")
            return jsonify({
                'success': False, 
                'error': f'Error al guardar archivo de configuración: {str(e)}'
            }), 500

        try:
            # Verificar si el servicio OpenVPN está instalado
            subprocess.run(['which', 'openvpn'], check=True, capture_output=True)
        except subprocess.CalledProcessError:
            return jsonify({'success': False, 'error': 'OpenVPN no está instalado'}), 500

        # Verificar estado actual
        try:
            result = subprocess.run(['systemctl', 'is-active', 'openvpn'], capture_output=True, text=True)
            is_active = result.returncode == 0
        except subprocess.CalledProcessError:
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
                app.logger.info("Rutas originales restauradas correctamente")
            else:
                app.logger.warning("No se pudieron restaurar las rutas originales")

        # Iniciar VPN con nueva configuración
        try:
            subprocess.run(['systemctl', 'start', 'openvpn'], check=True)
            app.logger.info("Servicio OpenVPN iniciado correctamente")
            return jsonify({'success': True, 'message': 'Configuración VPN actualizada y servicio iniciado'})
        except subprocess.CalledProcessError as e:
            app.logger.error(f"Error al iniciar OpenVPN: {str(e)}")
            return jsonify({'success': False, 'error': 'Error al iniciar el servicio OpenVPN'}), 500

    except Exception as e:
        app.logger.error(f"Error general en vpn_config_api: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@vpn_bp.route('/api/vpn/status', methods=['GET'])
def vpn_status_api():
    try:
        # Verifica si el servicio openvpn está activo
        status = subprocess.run(['systemctl', 'is-active', 'openvpn'], capture_output=True, text=True)
        is_active = status.returncode == 0
        # Obtener IP pública y VPN (puedes mejorar esto según tu lógica)
        public_ip = subprocess.getoutput("curl -s ifconfig.me") if is_active else '-'
        vpn_ip = subprocess.getoutput("ip addr show tun0 | grep 'inet ' | awk '{print $2}' | cut -d'/' -f1") if is_active else '-'
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
        app.logger.error(f'Error al obtener estado VPN: {str(e)}')
        return jsonify({'error': str(e)}), 500

@vpn_bp.route('/api/vpn/toggle', methods=['POST'])
def toggle_vpn():
    try:
        status = subprocess.run(['systemctl', 'is-active', 'openvpn'], capture_output=True, text=True)
        if status.returncode == 0:
            # Está activo, detener
            subprocess.run(['systemctl', 'stop', 'openvpn'], check=True)
            msg = 'VPN detenida correctamente'
        else:
            # No está activo, iniciar
            subprocess.run(['systemctl', 'start', 'openvpn'], check=True)
            msg = 'VPN iniciada correctamente'
        return jsonify({'success': True, 'message': msg})
    except Exception as e:
        app.logger.error(f'Error al alternar VPN: {str(e)}')
        return jsonify({'success': False, 'error': str(e)}), 500

@vpn_bp.route('/api/vpn/killswitch', methods=['POST'])
def toggle_killswitch():
    try:
        data = request.get_json()
        enabled = data.get('enabled', False)
        vpn_status = subprocess.run(['systemctl', 'is-active', 'openvpn'], capture_output=True, text=True)
        is_vpn_active = vpn_status.returncode == 0
        killswitch_flag = '/etc/openvpn/killswitch_enabled'
        if enabled:
            if not is_vpn_active:
                return jsonify({'success': False, 'error': 'No se puede activar el Kill Switch: la VPN no está conectada'}), 400
            # Habilitar reglas de firewall para bloquear tráfico fuera de tun0
            subprocess.run(['iptables', '-I', 'OUTPUT', '!', '-o', 'tun0', '-m', 'conntrack', '!', '--ctstate', 'RELATED,ESTABLISHED', '-j', 'DROP'], check=True)
            with open(killswitch_flag, 'w') as f:
                f.write('1')
            app.logger.info("Kill Switch activado correctamente")
            return jsonify({'success': True, 'message': 'Kill Switch activado'})
        else:
            # Eliminar reglas de firewall
            subprocess.run(['iptables', '-D', 'OUTPUT', '!', '-o', 'tun0', '-m', 'conntrack', '!', '--ctstate', 'RELATED,ESTABLISHED', '-j', 'DROP'], check=False)
            if os.path.exists(killswitch_flag):
                os.remove(killswitch_flag)
            app.logger.info("Kill Switch desactivado correctamente")
            return jsonify({'success': True, 'message': 'Kill Switch desactivado'})
    except Exception as e:
        app.logger.error(f'Error en Kill Switch: {str(e)}')
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
