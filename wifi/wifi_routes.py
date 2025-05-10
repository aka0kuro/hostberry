from flask import Blueprint, request, jsonify, render_template, current_app as app
import os
from hostberry_config import HostBerryConfig
from .wifi_security import wifi_security
from .wifi_connection import wifi_connection
from .wifi_utils import wifi_utils

wifi_bp = Blueprint('wifi', __name__)

@wifi_bp.route('/api/wifi/connect', methods=['GET', 'POST'])
@csrf.exempt
def wifi_connect():
    """Conecta a una red WiFi y SIEMPRE genera el archivo wpa_supplicant.conf aunque la conexión falle."""
    try:
        if request.method == 'POST':
            if not request.is_json:
                return jsonify({'success': False, 'error': 'Content-Type debe ser application/json'}), 400
            data = request.get_json()
        else:
            data = request.args
        
        ssid = data.get('ssid', '').strip()
        password = data.get('password', '').strip()
        security = data.get('security', '').strip()

        # Validar entrada
        if not wifi_security.validate_ssid(ssid):
            return jsonify({'success': False, 'error': 'SSID inválido'}), 400
        if password and not wifi_security.validate_password(password):
            return jsonify({'success': False, 'error': 'Contraseña inválida'}), 400
        if not ssid:
            return jsonify({'success': False, 'error': 'El SSID es requerido'}), 400

        # --- Generar SIEMPRE el archivo wpa_supplicant.conf antes de intentar conectar ---
        try:
            wpa_conf_path = '/etc/wpa_supplicant/wpa_supplicant.conf'
            wpa_content = f'ctrl_interface=DIR=/var/run/wpa_supplicant GROUP=netdev\nupdate_config=1\ncountry=ES\n\nnetwork={{\n    ssid="{ssid}"\n'
            if password:
                wpa_content += f'    psk="{password}"\n'
            if security and security.upper() != 'NONE':
                wpa_content += f'    key_mgmt={security}\n'
            else:
                wpa_content += '    key_mgmt=NONE\n'
            wpa_content += '}'
            os.makedirs(os.path.dirname(wpa_conf_path), exist_ok=True)
            with open(wpa_conf_path, 'w') as f:
                f.write(wpa_content)
        except Exception as e:
            app.logger.error(f'Error generando wpa_supplicant.conf: {str(e)}')
            # Seguimos adelante, ya que el usuario espera el archivo generado siempre

        # Intentar conectar usando el gestor de conexión
        if wifi_connection.connect(ssid, password, security):
            if password:
                wifi_utils.save_credentials(ssid, password, security)
            return jsonify({'success': True, 'message': f'Conectado exitosamente a {ssid}'}), 200
        else:
            return jsonify({'success': False, 'error': 'Error al conectar a la red WiFi'}), 500

    except Exception as e:
        app.logger.error(f'Error en wifi_connect: {str(e)}')
        return jsonify({'success': False, 'error': str(e)}), 500

@wifi_bp.route('/api/wifi/scan', methods=['GET'])
def wifi_scan():
    """Escanea redes WiFi disponibles"""
    try:
        app.logger.info('Iniciando escaneo WiFi...')
        networks = wifi_connection.scan_networks()
        app.logger.info(f'Encontradas {len(networks)} redes WiFi')
        return jsonify({'success': True, 'networks': networks})
    except Exception as e:
        app.logger.error(f'Error en wifi_scan: {str(e)}')
        return jsonify({'success': False, 'error': str(e)}), 500

@wifi_bp.route('/api/wifi/disconnect', methods=['POST'])
def wifi_disconnect():
    """Desconecta de la red WiFi actual"""
    try:
        if wifi_connection.disconnect():
            return jsonify({'success': True, 'message': 'Desconectado exitosamente'}), 200
        return jsonify({'success': False, 'error': 'Error al desconectar'}), 500
    except Exception as e:
        app.logger.error(f'Error en wifi_disconnect: {str(e)}')
        return jsonify({'success': False, 'error': str(e)}), 500

@wifi_bp.route('/api/wifi/status', methods=['GET'])
def wifi_status():
    """Obtiene el estado actual de la conexión WiFi, incluyendo si está habilitada o bloqueada."""
    import subprocess
    try:
        ssid = wifi_connection.get_ssid()
        connected = wifi_connection.is_connected()
        quality = wifi_connection.check_connection_quality()

        # Determinar si la radio WiFi está habilitada usando nmcli
        nmcli_radio = 'disabled'
        try:
            nmcli_radio_out = subprocess.run(['nmcli', 'radio', 'wifi'], capture_output=True, text=True, timeout=3)
            nmcli_radio = nmcli_radio_out.stdout.strip().lower()
        except Exception:
            pass

        # Comprobar rfkill
        hard_blocked = False
        soft_blocked = False
        try:
            rfkill_out = subprocess.run(['rfkill', 'list', wifi_connection.interface], capture_output=True, text=True, timeout=3)
            for line in rfkill_out.stdout.splitlines():
                if 'Soft blocked:' in line:
                    soft_blocked = 'yes' in line
                if 'Hard blocked:' in line:
                    hard_blocked = 'yes' in line
        except Exception:
            pass

        # enabled será True si la radio está habilitada y no está bloqueada
        enabled = (nmcli_radio == 'enabled') and not hard_blocked and not soft_blocked

        return jsonify({
            'success': True,
            'status': {
                'connected': connected,
                'enabled': enabled and not hard_blocked and not soft_blocked,
                'hard_blocked': hard_blocked,
                'soft_blocked': soft_blocked,
                'ssid': ssid,
                'quality': quality.get('quality', 'unknown'),
                'signal': quality.get('signal', 'unknown')
            }
        })
    except Exception as e:
        app.logger.error(f'Error en wifi_status: {str(e)}')
        return jsonify({'success': False, 'error': str(e)}), 500

@wifi_bp.route('/api/wifi/stored_networks')
def wifi_stored_networks():
    """Devuelve la lista de redes WiFi almacenadas como un array de SSIDs"""
    try:
        credentials = wifi_utils.get_credentials()
        ssid_list = list(credentials.get('networks', {}).keys())
        return jsonify({
            'success': True,
            'networks': ssid_list,
            'last_connected': credentials.get('last_connected', [])
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@wifi_bp.route('/api/wifi/get_password', methods=['POST'])
def wifi_get_password():
    """Recupera la contraseña almacenada para un SSID específico"""
    try:
        if not request.is_json:
            return jsonify({'success': False, 'error': 'Content-Type debe ser application/json'}), 400
        data = request.get_json()
        ssid = data.get('ssid')
        
        if not ssid:
            return jsonify({'success': False, 'error': 'SSID es requerido'}), 400
        
        password = wifi_utils.get_credentials(ssid)
        if password:
            return jsonify({
                'success': True,
                'password': password
            })
        return jsonify({'success': False, 'error': 'No se encontraron credenciales'}), 404
    except Exception as e:
        app.logger.error(f'Error en wifi_get_password: {str(e)}')
        return jsonify({'success': False, 'error': str(e)}), 500

# --- Endpoints de Credenciales ---

@wifi_bp.route('/api/wifi/credentials', methods=['GET'])
def wifi_credentials():
    """Obtiene todas las credenciales WiFi almacenadas"""
    try:
        credentials = wifi_utils.get_credentials()
        return jsonify({'success': True, 'credentials': credentials})
    except Exception as e:
        app.logger.error(f'Error en wifi_credentials: {str(e)}')
        return jsonify({'success': False, 'error': str(e)}), 500

@wifi_bp.route('/api/wifi/credentials/<ssid>', methods=['GET'])
def wifi_get_password_by_ssid(ssid):
    """Obtiene la contraseña para una red WiFi específica"""
    try:
        password = wifi_utils.get_credentials(ssid)
        if password:
            return jsonify({'success': True, 'password': password})
        return jsonify({'success': False, 'error': 'No se encontraron credenciales'}), 404
    except Exception as e:
        app.logger.error(f'Error en wifi_get_password: {str(e)}')
        return jsonify({'success': False, 'error': str(e)}), 500

# --- AdBlock API ---

@wifi_bp.route('/api/adblock/update', methods=['POST'])
def adblock_update():
    """Ejecuta la actualización de listas AdBlock en segundo plano."""
    import subprocess
    import os
    lists = request.json.get('lists', 'easylist') if request.is_json else 'easylist'
    script_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'scripts', 'adblock.sh')
    log_path = '/opt/hostberry/logs/adblock_update.log'
    try:
        with open(log_path, 'w') as log_file:
            subprocess.Popen([
                'bash', script_path, '--lists', lists
            ], stdout=log_file, stderr=subprocess.STDOUT, close_fds=True)
        return jsonify({'success': True, 'message': 'Actualización iniciada en segundo plano'})
    except Exception as e:
        app.logger.error(f'Error al lanzar adblock.sh: {str(e)}')
        return jsonify({'success': False, 'error': str(e)}), 500

# --- Páginas de la UI ---

@wifi_bp.route('/wifi_scan')
def wifi_scan_page():
    """Muestra la página de escaneo de redes WiFi"""
    try:
        status = subprocess.run(['nmcli', 'radio', 'wifi'], capture_output=True, text=True)
        wifi_enabled = 'enabled' in status.stdout.lower()
        wifi_blocked = False
        app.logger.debug(f'[WiFi Page] wifi_blocked: {wifi_blocked} | wifi_enabled: {wifi_enabled}')
        return render_template(
            'wifi_scan.html',
            wifi_blocked=wifi_blocked,
            wifi_enabled=wifi_enabled,
        )
    except Exception as e:
        wifi_blocked = False
        app.logger.debug(f'[WiFi Page] wifi_blocked (except): {wifi_blocked}')
        return render_template('wifi_scan.html', wifi_blocked=wifi_blocked, error=str(e))

@wifi_bp.route('/hostapd')
def hostapd_page():
    """Muestra la página de configuración de HostAPD"""
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
        return render_template('hostapd.html', hostapd_installed=False, is_running=False, config=None, error=str(e))

# --- Configuración de HostAPD ---

@wifi_bp.route('/hostapd/config', methods=['POST'])
def hostapd_config():
    """Guarda la configuración de HostAPD"""
    try:
        config = request.form.get('config', '')
        if not config:
            return jsonify({'success': False, 'error': 'No config provided'}), 400
        with open('/etc/hostapd/hostapd.conf', 'w') as f:
            f.write(config)
        return jsonify({'success': True, 'message': 'Configuración guardada'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@wifi_bp.route('/hostapd/toggle', methods=['POST'])
def hostapd_toggle():
    """Inicia o detiene el servicio de HostAPD"""
    try:
        action = request.form.get('action')
        if action == 'start':
            subprocess.run(['systemctl', 'start', 'hostapd'], capture_output=True)
            return jsonify({'success': True, 'message': 'HostAPD iniciado'})
        elif action == 'stop':
            subprocess.run(['systemctl', 'stop', 'hostapd'], capture_output=True)
            return jsonify({'success': True, 'message': 'HostAPD detenido'})
        return jsonify({'success': False, 'error': 'Acción no válida'}), 400
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@wifi_bp.route('/hostapd/status')
def hostapd_status():
    """Obtiene el estado del servicio de HostAPD"""
    try:
        status = subprocess.run(['systemctl', 'is-active', 'hostapd'], capture_output=True, text=True)
        return jsonify({'success': True, 'is_running': status.returncode == 0})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# --- Radio WiFi ---

@wifi_bp.route('/disable_radio')
def disable_radio():
    """Desactiva la radio WiFi y baja la interfaz wlan0 (compatibilidad máxima con Raspberry Pi OS). Devuelve logs de cada comando ejecutado."""
    import time
    import traceback
    logs = []
    try:
        # 1. Bloquear la radio WiFi
        rfkill = subprocess.run(['sudo', 'rfkill', 'block', 'wifi'], capture_output=True, text=True)
        logs.append({
            'step': 'rfkill block wifi',
            'stdout': rfkill.stdout,
            'stderr': rfkill.stderr,
            'returncode': rfkill.returncode
        })
        time.sleep(1)

        # 2. Bajar la interfaz wlan0
        ip_link = subprocess.run(['sudo', 'ip', 'link', 'set', 'wlan0', 'down'], capture_output=True, text=True)
        logs.append({
            'step': 'ip link set wlan0 down',
            'stdout': ip_link.stdout,
            'stderr': ip_link.stderr,
            'returncode': ip_link.returncode
        })
        time.sleep(1)

        # 3. Verificar que la interfaz esté abajo
        ifconfig = subprocess.run(['ifconfig', 'wlan0'], capture_output=True, text=True)
        logs.append({
            'step': 'ifconfig wlan0',
            'stdout': ifconfig.stdout,
            'stderr': ifconfig.stderr,
            'returncode': ifconfig.returncode
        })
        if 'UP' not in ifconfig.stdout:
            return jsonify({'success': True, 'message': 'Radio WiFi desactivada exitosamente', 'logs': logs})
        else:
            return jsonify({'success': False, 'message': 'No se pudo desactivar la interfaz wlan0', 'logs': logs}), 500

    except Exception as e:
        logs.append({
            'step': 'exception',
            'error': str(e),
            'traceback': traceback.format_exc()
        })
        app.logger.error(f'Error al deshabilitar WiFi: {str(e)}')
        return jsonify({'success': False, 'error': str(e), 'logs': logs}), 500

@wifi_bp.route('/enable_radio')
def enable_radio():
    """Habilita la radio WiFi y asegura que la interfaz wlan0 esté activa (compatibilidad máxima con Raspberry Pi OS). Devuelve el resultado de cada comando ejecutado para depuración."""
    import time
    import traceback
    logs = []
    try:
        # 1. Desbloquear todas las interfaces (rfkill)
        rfkill = subprocess.run(['sudo', 'rfkill', 'unblock', 'all'], capture_output=True, text=True)
        logs.append({
            'step': 'rfkill unblock all',
            'stdout': rfkill.stdout,
            'stderr': rfkill.stderr,
            'returncode': rfkill.returncode
        })
        time.sleep(1)

        # 2. Levantar la interfaz wlan0 (ip link set up)
        ip_link = subprocess.run(['sudo', 'ip', 'link', 'set', 'wlan0', 'up'], capture_output=True, text=True)
        logs.append({
            'step': 'ip link set wlan0 up',
            'stdout': ip_link.stdout,
            'stderr': ip_link.stderr,
            'returncode': ip_link.returncode
        })
        time.sleep(1)

        # 3. Reconfigurar wpa_supplicant
        wpa = subprocess.run(['sudo', 'wpa_cli', '-i', 'wlan0', 'reconfigure'], capture_output=True, text=True)
        logs.append({
            'step': 'wpa_cli reconfigure',
            'stdout': wpa.stdout,
            'stderr': wpa.stderr,
            'returncode': wpa.returncode
        })
        time.sleep(1)

        # 4. Reiniciar dhcpcd (gestor de red típico en Raspberry Pi OS)
        dhcpcd_restart = subprocess.run(['sudo', 'systemctl', 'restart', 'dhcpcd'], capture_output=True, text=True)
        logs.append({
            'step': 'systemctl restart dhcpcd',
            'stdout': dhcpcd_restart.stdout,
            'stderr': dhcpcd_restart.stderr,
            'returncode': dhcpcd_restart.returncode
        })
        time.sleep(2)

        # 5. Verificar que la interfaz esté activa
        ifconfig = subprocess.run(['ifconfig', 'wlan0'], capture_output=True, text=True)
        logs.append({
            'step': 'ifconfig wlan0',
            'stdout': ifconfig.stdout,
            'stderr': ifconfig.stderr,
            'returncode': ifconfig.returncode
        })
        if 'UP' in ifconfig.stdout:
            return jsonify({'success': True, 'message': 'Radio WiFi habilitada exitosamente', 'logs': logs})
        else:
            return jsonify({'success': False, 'message': 'No se pudo activar la interfaz wlan0', 'logs': logs}), 500

    except Exception as e:
        logs.append({
            'step': 'exception',
            'error': str(e),
            'traceback': traceback.format_exc()
        })
        app.logger.error(f'Error al habilitar WiFi: {str(e)}')
        return jsonify({
            'success': False,
            'error': str(e),
            'logs': logs
        }), 500

@wifi_bp.route('/api/wifi/autoconnect', methods=['GET'])
def wifi_autoconnect():
    """Intenta conectarse automáticamente a la última red usada"""
    try:
        # Obtener la lista de redes guardadas
        credentials = wifi_utils.get_credentials()
        last_connected = credentials.get('last_connected', [])
        
        if not last_connected:
            return jsonify({'success': False, 'message': 'No hay redes guardadas'}), 404
            
        # Intentar conectar a cada red en orden hasta que una funcione
        for ssid in last_connected:
            cred = wifi_utils.get_credentials(ssid)
            if cred and 'password' in cred:
                password = cred['password']
                security = cred.get('security')
                if wifi_connection.connect(ssid, password, security):
                    return jsonify({
                        'success': True,
                        'ssid': ssid,
                        'message': f'Conectado exitosamente a {ssid}'
                    }), 200
                
        return jsonify({
            'success': False,
            'message': 'No se pudo conectar a ninguna red guardada'
        }), 500
        
    except Exception as e:
        app.logger.error(f'Error en wifi_autoconnect: {str(e)}')
        return jsonify({'success': False, 'error': str(e)}), 500

