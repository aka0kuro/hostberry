from flask import Blueprint, request, jsonify, render_template, current_app as app
import time
import subprocess
import shutil
import tempfile
import re
import os
from hostberry_config import HostBerryConfig
from . import *
from .wifi_utils import (
    get_wifi_ssid,
    is_wifi_connected,
    connect_wifi_wpasupplicant,
    get_wifi_credentials
)

wifi_bp = Blueprint('wifi', __name__)

# --- WiFi Utility Functions ---
def get_wifi_ssid():
    try:
        result = subprocess.run(['nmcli', '-t', '-f', 'GENERAL.CONNECTION', 'device', 'show', 'wlan0'], 
                               capture_output=True, text=True)
        if result.returncode == 0:
            for line in result.stdout.splitlines():
                if line.startswith('GENERAL.CONNECTION:'):
                    ssid = line.split(':', 1)[1].strip()
                    return ssid if ssid else None
        return None
    except Exception:
        return None

def is_wifi_connected():
    try:
        result = subprocess.run(['nmcli', '-t', '-f', 'GENERAL.STATE', 'device', 'show', 'wlan0'], 
                               capture_output=True, text=True)
        if result.returncode == 0:
            for line in result.stdout.splitlines():
                if line.startswith('GENERAL.STATE:') and '100 (connected)' in line:
                    return True
        return False
    except Exception:
        return False

def connect_wifi_wpasupplicant(ssid, password=None):
    return connect_wifi_nmcli(ssid, password)

def connect_wifi_nmcli(ssid, password=None):
    interface_name = 'wlan0'
    try:
        app.logger.info(f"Intentando conectar a SSID: {ssid} vía nmcli en la interfaz {interface_name}")
        
        # Asegurarse de que la interfaz WiFi esté habilitada
        try:
            subprocess.run(['nmcli', 'radio', 'wifi', 'on'], capture_output=True, check=False, timeout=5)
            time.sleep(1)  # Dar tiempo para que se complete
        except Exception as e:
            app.logger.warning(f"Error no crítico al activar radio WiFi: {e}")
        
        # Asegurarse de que la interfaz esté lista 
        try:
            subprocess.run(['ifconfig', interface_name, 'up'], capture_output=True, check=False, timeout=5)
            time.sleep(1)
        except Exception as e:
            app.logger.warning(f"Error no crítico al activar interfaz {interface_name}: {e}")
        
        # Desconectar de cualquier red actual
        try:
            disconnect_result = subprocess.run(['nmcli', 'device', 'disconnect', interface_name], 
                                              capture_output=True, text=True, timeout=10, check=False)
            if disconnect_result.returncode == 0:
                app.logger.info(f"Desconexión previa en {interface_name} completada.")
            else:
                app.logger.info(f"Comando de desconexión previa en {interface_name} finalizado: {disconnect_result.stderr or disconnect_result.stdout}")
            time.sleep(2)  # Dar más tiempo para que se complete la desconexión
        except Exception as e_disc:
            app.logger.warning(f"Error no fatal durante intento de desconexión previa: {e_disc}")
            
        # Comprobar si ya existe una conexión con ese nombre y eliminarla si es necesario
        try:
            check_conn = subprocess.run(['nmcli', 'connection', 'show', ssid], 
                                      capture_output=True, text=True, check=False, timeout=5)
            if check_conn.returncode == 0:
                app.logger.info(f"Conexión {ssid} ya existe, eliminándola antes de crear una nueva")
                subprocess.run(['nmcli', 'connection', 'delete', ssid], 
                              capture_output=True, text=True, check=False, timeout=5)
                time.sleep(1)
        except Exception as e_check:
            app.logger.warning(f"Error no fatal al verificar conexión existente: {e_check}")

        # Preparar el comando de conexión
        command = ['nmcli', 'device', 'wifi', 'connect', ssid, 'ifname', interface_name]
        if password:
            command.extend(['password', password])
        
        # Ejecutar con tiempo de espera extendido
        result = subprocess.run(command, capture_output=True, text=True, check=False, timeout=60)

        if result.returncode == 0:
            app.logger.info(f"Conexión nmcli para {ssid} exitosa. Salida: {result.stdout}")
            
            # Esperar a que la conexión se establezca completamente
            time.sleep(3)
            
            # Verificar que realmente se conectó
            verify_result = subprocess.run(['nmcli', '-t', '-f', 'GENERAL.CONNECTION', 'device', 'show', interface_name],
                                         capture_output=True, text=True, check=False, timeout=5)
            
            if verify_result.returncode == 0 and ssid in verify_result.stdout:
                app.logger.info(f"Verificación: conectado efectivamente a {ssid}")
                return True
            else:
                app.logger.warning(f"Verificación falló: La conexión a {ssid} parece no haberse establecido correctamente")
                # Intentar una vez más
                time.sleep(2)
                result = subprocess.run(command, capture_output=True, text=True, check=False, timeout=45)
                if result.returncode == 0:
                    app.logger.info(f"Segundo intento de conexión a {ssid} exitoso")
                    return True
                else:
                    app.logger.error(f"Segundo intento de conexión a {ssid} falló")
                    return False
        else:
            error_message = result.stderr.strip() if result.stderr else (result.stdout.strip() if result.stdout else "Error desconocido de nmcli")
            app.logger.error(f"Error conectando a WiFi {ssid}. Código: {result.returncode}. Error: {error_message}")
            
            # Limpiar la conexión fallida
            try:
                subprocess.run(['nmcli', 'connection', 'delete', ssid], 
                              capture_output=True, text=True, check=False, timeout=5)
            except Exception:
                pass  # Ignorar errores en la limpieza
                
            return False
            
    except subprocess.TimeoutExpired:
        app.logger.error(f"Timeout al intentar conectar a WiFi {ssid}")
        return False
    except Exception as e:
        app.logger.error(f'Excepción general conectando a WiFi {ssid}: {e}')
        return False

# --- WiFi Endpoints ---

@wifi_bp.route('/api/wifi/connect', methods=['GET', 'POST'])
def wifi_connect():
    try:
        if request.method == 'POST':
            if not request.is_json:
                return jsonify({'success': False, 'error': 'Content-Type debe ser application/json'}), 400
            data = request.get_json()
        else:
            data = request.args
            
        ssid = data.get('ssid', '').strip()
        password = data.get('password', '').strip()
        
        if not ssid:
            return jsonify({'success': False, 'error': 'El SSID es requerido'}), 400
            
        # Intentar conectar usando nmcli
        if connect_wifi_nmcli(ssid, password):
            # Guardar credenciales si se proporcionó contraseña
            if password:
                save_wifi_credentials(ssid, password)
            return jsonify({'success': True, 'message': f'Conectado exitosamente a {ssid}'})
        else:
            return jsonify({'success': False, 'error': 'Error al conectar a la red WiFi'}), 500
            
    except Exception as e:
        app.logger.error(f'Error en wifi_connect: {str(e)}')
        return jsonify({'success': False, 'error': str(e)}), 500

@wifi_bp.route('/api/wifi/scan', methods=['GET'])
def wifi_scan():
    try:
        app.logger.info('Iniciando escaneo WiFi...')
        result = subprocess.run(
            ['nmcli', '-t', '-f', 'SSID,SIGNAL,SECURITY,BSSID', 'device', 'wifi', 'list'],
            capture_output=True,
            text=True,
            timeout=30
        )
        if result.returncode != 0:
            raise Exception(result.stderr or 'Failed to scan networks')
            
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

@wifi_bp.route('/api/wifi/disconnect', methods=['GET', 'POST'])
def wifi_disconnect():
    try:
        if request.method == 'POST':
            if not request.is_json:
                return jsonify({'success': False, 'error': 'Content-Type debe ser application/json'}), 400
            data = request.get_json()
        else:
            data = request.args
            
        ssid = data.get('ssid', '').strip()
        if not ssid:
            return jsonify({'success': False, 'error': 'El SSID es requerido'}), 400
            
        try:
            subprocess.run(['nmcli', 'device', 'disconnect', 'wlan0'], capture_output=True, check=False)
            subprocess.run(['nmcli', 'connection', 'delete', ssid], capture_output=True, check=False)
            app.logger.info(f'Desconectado exitosamente de {ssid}')
            return jsonify({'success': True, 'message': f'Desconectado exitosamente de {ssid}'})
        except subprocess.CalledProcessError as e:
            error_msg = e.stderr.strip() or 'Error desconocido al desconectar'
            app.logger.error(f'Error al desconectar de WiFi: {error_msg}')
            return jsonify({'success': False, 'error': f'Error al desconectar: {error_msg}'}), 400
            
    except Exception as e:
        app.logger.error(f'Error en wifi_disconnect: {str(e)}')
        return jsonify({'success': False, 'error': f'Error en la desconexión: {str(e)}'}), 500

@wifi_bp.route('/api/wifi/status')
def wifi_status():
    try:
        result = subprocess.run(['nmcli', '-t', '-f', 'GENERAL.CONNECTION,GENERAL.STATE', 'device', 'show', 'wlan0'], 
                               capture_output=True, text=True)
        wifi_enabled = True
        wifi_blocked = False
        is_connected = False
        actual_ssid = None
        connection_info = {}
        
        if result.returncode == 0:
            for line in result.stdout.splitlines():
                if line.startswith('GENERAL.CONNECTION:'):
                    actual_ssid = line.split(':', 1)[1].strip()
                    if actual_ssid:
                        connection_info['ssid'] = actual_ssid
                if line.startswith('GENERAL.STATE:') and '100 (connected)' in line:
                    is_connected = True
                    
        return jsonify({
            'success': True,
            'enabled': wifi_enabled,
            'blocked': wifi_blocked,
            'connected': is_connected,
            'current_connection': actual_ssid,
            'connection_info': connection_info
        })
        
    except Exception as e:
        app.logger.error(f'Error en wifi_status: {str(e)}')
        return jsonify({'success': False, 'error': str(e)}), 500

# --- Utilidades de credenciales WiFi ---
import os
import json
from cryptography.fernet import Fernet
from flask import render_template

@wifi_bp.route('/wifi_scan')
def wifi_scan_page():
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

@wifi_bp.route('/hostapd/config', methods=['POST'])
def hostapd_config():
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
    try:
        action = request.form.get('action', '')
        if action == 'start':
            subprocess.run(['systemctl', 'start', 'hostapd'], check=True)
        elif action == 'stop':
            subprocess.run(['systemctl', 'stop', 'hostapd'], check=True)
        else:
            return jsonify({'success': False, 'error': 'Acción inválida'}), 400
        return jsonify({'success': True, 'message': f'hostapd {action} ejecutado'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@wifi_bp.route('/hostapd/status')
def hostapd_status():
    try:
        status = subprocess.run(['systemctl', 'is-active', 'hostapd'], capture_output=True, text=True)
        is_running = status.returncode == 0
        return jsonify({'success': True, 'running': is_running, 'status': status.stdout.strip()})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@wifi_bp.route('/api/wifi/check_credentials', methods=['GET', 'POST'])
def check_wifi_credentials():
    try:
        if request.method == 'POST':
            if not request.is_json:
                return jsonify({'success': False, 'error': 'Content-Type debe ser application/json'}), 400
            data = request.get_json()
        else:
            data = request.args
            
        ssid = data.get('ssid', '').strip()
        if not ssid:
            return jsonify({'success': False, 'error': 'El SSID es requerido'}), 400
            
        saved_password = get_wifi_credentials(ssid)
        return jsonify({
            'success': True,
            'has_credentials': saved_password is not None
        })
        
    except Exception as e:
        app.logger.error(f'Error en check_wifi_credentials: {str(e)}')
        return jsonify({'success': False, 'error': str(e)}), 500

@wifi_bp.route('/api/wifi/enable_radio', methods=['POST'])
def enable_radio():
    try:
        result = subprocess.run(['nmcli', 'radio', 'wifi', 'on'], capture_output=True, text=True, check=True)
        app.logger.info(f"WiFi radio enabled: {result.stdout}")
        return jsonify({'success': True, 'message': 'WiFi radio enabled successfully.'})
    except subprocess.CalledProcessError as e:
        app.logger.error(f"Error enabling WiFi radio: {e.stderr}")
        return jsonify({'success': False, 'error': f'Failed to enable WiFi radio: {e.stderr}'}), 500
    except Exception as e:
        app.logger.error(f"Unexpected error enabling WiFi radio: {str(e)}")
        return jsonify({'success': False, 'error': f'An unexpected error occurred: {str(e)}'}), 500

# --- Utilidades para gestionar credenciales WiFi ---
def get_credentials_path():
    """Retorna la ruta al archivo de credenciales"""
    credentials_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'credentials')
    os.makedirs(credentials_dir, exist_ok=True)
    return os.path.join(credentials_dir, 'wifi_credentials.json')

def get_encryption_key():
    """Obtiene o genera una clave de encriptación para las contraseñas"""
    key_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'credentials', 'encryption_key.key')
    if os.path.exists(key_file):
        with open(key_file, 'rb') as f:
            return f.read()
    else:
        os.makedirs(os.path.dirname(key_file), exist_ok=True)
        key = Fernet.generate_key()
        with open(key_file, 'wb') as f:
            f.write(key)
        return key

def save_wifi_credentials(ssid, password):
    """Guarda las credenciales WiFi con encriptación"""
    try:
        credentials_file = get_credentials_path()
        
        # Leer credenciales existentes
        data = {}
        if os.path.exists(credentials_file):
            try:
                with open(credentials_file, 'r') as f:
                    file_content = f.read().strip()
                    if file_content:  # Verificar que el archivo no esté vacío
                        data = json.loads(file_content)
                    else:
                        data = {}  # Archivo vacío, inicializar como diccionario vacío
            except json.JSONDecodeError as e:
                app.logger.warning(f"Error al decodificar JSON de credenciales: {e}")
                # El archivo existe pero no es JSON válido, podría ser el formato antiguo
                old_credentials = {}
                try:
                    with open(credentials_file, 'r') as f:
                        old_content = f.read().strip()
                        if old_content:
                            old_credentials = json.loads(old_content)
                except:
                    app.logger.warning("No se pudieron recuperar credenciales antiguas")
                    old_credentials = {}
                
                # Crear nuevo formato con las credenciales antiguas
                data = {
                    "networks": {},
                    "last_connected": []
                }
                for old_ssid, old_pass in old_credentials.items():
                    # Almacenar las credenciales antiguas sin encriptar temporalmente
                    data["networks"][old_ssid] = {
                        "password": old_pass,
                        "last_used": time.time(),
                        "encrypted": False
                    }
                    if old_ssid not in data["last_connected"]:
                        data["last_connected"].insert(0, old_ssid)
        else:
            # Inicializar nueva estructura
            data = {
                "networks": {},
                "last_connected": []
            }
        
        # Asegurarse de que la estructura es correcta
        if "networks" not in data:
            data["networks"] = {}
        if "last_connected" not in data:
            data["last_connected"] = []
        
        # Preparar encriptación
        key = get_encryption_key()
        cipher_suite = Fernet(key)
        
        # Re-encriptar cualquier contraseña no encriptada (migración)
        for net_ssid, net_data in data["networks"].items():
            if isinstance(net_data, str):
                # Formato antiguo donde el valor es directamente la contraseña
                plain_password = net_data
                data["networks"][net_ssid] = {
                    "password": cipher_suite.encrypt(plain_password.encode()).decode(),
                    "last_used": time.time(),
                    "encrypted": True
                }
            elif isinstance(net_data, dict) and not net_data.get("encrypted", False):
                # Formato nuevo pero sin encriptar
                plain_password = net_data.get("password", "")
                data["networks"][net_ssid]["password"] = cipher_suite.encrypt(plain_password.encode()).decode()
                data["networks"][net_ssid]["encrypted"] = True
        
        # Encriptar y guardar la nueva contraseña
        data["networks"][ssid] = {
            "password": cipher_suite.encrypt(password.encode()).decode(),
            "last_used": time.time(),
            "encrypted": True
        }
        
        # Actualizar lista de últimas redes
        if ssid in data["last_connected"]:
            data["last_connected"].remove(ssid)
        data["last_connected"].insert(0, ssid)
        data["last_connected"] = data["last_connected"][:5]  # Mantener solo las 5 más recientes
        
        # Guardar credenciales actualizadas
        with open(credentials_file, 'w') as f:
            json.dump(data, f, indent=2)
        
        app.logger.info(f"Credenciales para {ssid} guardadas exitosamente (encriptadas)")
        return True
    except Exception as e:
        app.logger.error(f"Error al guardar credenciales para {ssid}: {e}")
        return False

def get_wifi_credentials(ssid=None):
    """
    Recupera las credenciales WiFi.
    Si se proporciona un SSID, devuelve la contraseña de esa red.
    Si no, devuelve todas las credenciales.
    """
    try:
        credentials_file = get_credentials_path()
        
        if not os.path.exists(credentials_file):
            return None if ssid else {"networks": {}, "last_connected": []}
        
        try:
            with open(credentials_file, 'r') as f:
                file_content = f.read().strip()
                if not file_content:
                    return None if ssid else {"networks": {}, "last_connected": []}
                
                try:
                    data = json.loads(file_content)
                except json.JSONDecodeError:
                    # Intenta leer el formato antiguo
                    old_data = {}
                    try:
                        old_data = json.loads(file_content)
                    except:
                        app.logger.error("No se pudo interpretar el archivo de credenciales")
                        return None if ssid else {"networks": {}, "last_connected": []}
                    
                    # Convertir formato antiguo
                    data = {
                        "networks": {},
                        "last_connected": []
                    }
                    for old_ssid, old_pass in old_data.items():
                        data["networks"][old_ssid] = {
                            "password": old_pass,
                            "last_used": time.time(),
                            "encrypted": False
                        }
                        if old_ssid not in data["last_connected"]:
                            data["last_connected"].append(old_ssid)
                
                # Verificar formato correcto
                if "networks" not in data:
                    data["networks"] = {}
                if "last_connected" not in data:
                    data["last_connected"] = []
                
                # Si solo queremos un SSID específico
                if ssid:
                    # Buscar primero en el nuevo formato
                    if ssid in data["networks"]:
                        net_data = data["networks"][ssid]
                        
                        # Si es un diccionario, está en el nuevo formato
                        if isinstance(net_data, dict):
                            try:
                                # Si está encriptado, desencriptar
                                if net_data.get("encrypted", False):
                                    key = get_encryption_key()
                                    cipher_suite = Fernet(key)
                                    encrypted_password = net_data.get("password", "").encode()
                                    password = cipher_suite.decrypt(encrypted_password).decode()
                                else:
                                    # No encriptado pero nuevo formato
                                    password = net_data.get("password", "")
                                
                                return password
                            except Exception as e:
                                app.logger.error(f"Error desencriptando contraseña: {e}")
                                return None
                        else:
                            # Formato antiguo, la contraseña está en texto plano
                            return net_data
                    
                    # No se encontró el SSID
                    return None
                else:
                    # Devolver información sobre redes sin exponer contraseñas
                    networks_info = {}
                    for net_ssid in data["networks"]:
                        net_data = data["networks"][net_ssid]
                        if isinstance(net_data, dict):
                            networks_info[net_ssid] = {
                                "last_used": net_data.get("last_used", 0)
                            }
                        else:
                            # Formato antiguo
                            networks_info[net_ssid] = {
                                "last_used": 0
                            }
                    
                    return {
                        "networks": list(networks_info.keys()),
                        "last_connected": data["last_connected"]
                    }
                
        except Exception as e:
            app.logger.error(f"Error leyendo credenciales: {e}")
            return None if ssid else {"networks": {}, "last_connected": []}
            
    except Exception as e:
        app.logger.error(f"Error general en get_wifi_credentials: {e}")
        return None if ssid else {"networks": {}, "last_connected": []}

@wifi_bp.route('/api/wifi/stored_networks')
def wifi_stored_networks():
    """Devuelve la lista de redes WiFi almacenadas"""
    try:
        credentials = get_wifi_credentials()
        return jsonify({
            'success': True,
            'networks': credentials.get('networks', []),
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
        
        password = get_wifi_credentials(ssid)
        if password:
            return jsonify({
                'success': True,
                'password': password
            })
        else:
            return jsonify({'success': False, 'message': 'No credentials found for this network'}), 404
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@wifi_bp.route('/api/wifi/autoconnect')
def wifi_autoconnect():
    """Intenta conectarse automáticamente a la última red utilizada"""
    try:
        # Verificar si ya estamos conectados
        current_ssid = get_wifi_ssid()
        if current_ssid:
            return jsonify({
                'success': True, 
                'already_connected': True,
                'ssid': current_ssid,
                'message': f'Already connected to {current_ssid}'
            })
        
        # Intentar conectar a la última red conocida
        credentials = get_wifi_credentials()
        last_connected = credentials.get('last_connected', [])
        
        if not last_connected:
            return jsonify({
                'success': False,
                'message': 'No previous connections found'
            }), 404
        
        # Intentar las últimas redes conocidas en orden
        for ssid in last_connected:
            password = get_wifi_credentials(ssid)
            if password:
                if connect_wifi_nmcli(ssid, password):
                    return jsonify({
                        'success': True,
                        'ssid': ssid,
                        'message': f'Successfully connected to {ssid}'
                    })
        
        return jsonify({
            'success': False,
            'message': 'Failed to connect to any known network'
        }), 404
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
