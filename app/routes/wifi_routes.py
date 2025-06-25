from flask import Blueprint, request, jsonify, render_template, session, flash, redirect, url_for, abort
from app.utils.i18n_utils import get_locale, inject_get_locale, set_language, check_lang
from app.utils.log_utils import get_logs
from app.utils.security_utils import FAILED_ATTEMPTS, BLOCKED_IPS
from flask_babel import _
from flask_login import current_user, login_required
import subprocess
import json
import os
import re
import time
import logging
from functools import wraps
from typing import Dict, List, Optional, Tuple, Any, Union

from app.services.wifi_service import WiFiService
from app.utils.network_config import get_wifi_networks, connect_to_wifi, get_network_interfaces
from app.utils.network_utils import run_command, is_wifi_connected, get_wifi_ssid, get_network_interface

logger = logging.getLogger(__name__)

# Crear Blueprint
wifi_bp = Blueprint('wifi', __name__, url_prefix='/wifi')

# Inicializar servicio
wifi_service = WiFiService()

@wifi_bp.route('/')
@login_required
def wifi_scan_page():
    """Página de escaneo de redes WiFi"""
    return render_template('wifi/scan.html')

@wifi_bp.route('/scan', methods=['GET'])
@login_required
def wifi_scan():
    """
    Endpoint para escanear redes WiFi disponibles.
    Devuelve una lista de redes en formato JSON.
    """
    try:
        networks = get_wifi_networks()
        return jsonify({
            'status': 'success',
            'networks': networks
        })
    except Exception as e:
        logger.error(f"Error al escanear redes WiFi: {e}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500
    """Endpoint para escanear redes WiFi"""
    try:
        networks = wifi_service.scan_networks()
        return jsonify({
            'status': 'success',
            'data': networks
        })
    except Exception as e:
        return jsonify({

@wifi_bp.route('/connect', methods=['POST'])
@login_required
def wifi_connect():
    """
    Endpoint para conectarse a una red WiFi.
    Espera un JSON con 'ssid' y 'password'.
    """
    try:
        data = request.get_json()
        if not data or 'ssid' not in data or 'password' not in data:
            return jsonify({'status': 'error', 'message': 'Se requieren SSID y contraseña'}), 400
        
        ssid = data['ssid']
        password = data['password']
        
        # Validación básica
        if not ssid or not isinstance(ssid, str) or len(ssid) > 32:
            return jsonify({'status': 'error', 'message': 'SSID no válido'}), 400
            
        if not password or not isinstance(password, str) or len(password) < 8 or len(password) > 63:
            return jsonify({'status': 'error', 'message': 'La contraseña debe tener entre 8 y 63 caracteres'}), 400
        
        # Intentar conectar
        success, message = connect_to_wifi(ssid, password)
        
        if success:
            return jsonify({
                'status': 'success',
                'message': message or 'Conexión exitosa'
            })
        else:
            return jsonify({
                'status': 'error',
                'message': message or 'Error al conectar a la red WiFi'
            }), 400
            
    except Exception as e:
        logger.error(f"Error en wifi_connect: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': 'Error interno del servidor'
        }), 500

@wifi_bp.route('/status')
@login_required
def wifi_status():
    """
    Endpoint para obtener el estado actual de la conexión WiFi.
    Devuelve información sobre la conexión actual.
    """
    try:
        interface = get_network_interface()
        connected = is_wifi_connected(interface)
        ssid = get_wifi_ssid(interface) if connected else None
        
        # Obtener dirección IP
        ip_address = None
        if interface:
            try:
                import psutil
                addrs = psutil.net_if_addrs().get(interface, [])
                for addr in addrs:
                    if addr.family == 2:  # AF_INET
                        ip_address = addr.address
                        break
            except Exception as e:
                logger.warning(f"No se pudo obtener la IP para {interface}: {e}")
        
        return jsonify({
            'status': 'success',
            'connected': connected,
            'ssid': ssid,
            'ip': ip_address or 'No disponible',
            'interface': interface or 'No disponible'
        })
        
    except Exception as e:
        logger.error(f"Error al obtener estado WiFi: {e}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@wifi_bp.route('/ap/toggle', methods=['POST'])
@login_required
def toggle_ap_mode():
    """Activa/desactiva el modo punto de acceso"""
    try:
        data = request.get_json()
        enable = data.get('enable', False)
        
        if enable:
            ssid = data.get('ssid', 'HostBerryAP')
            password = data.get('password', '')
            channel = data.get('channel', 6)
            
            success = wifi_service.enable_ap_mode(ssid, password, channel)
            if success:
                return jsonify({
                    'status': 'success',
                    'message': 'Modo punto de acceso activado',
                    'data': {'mode': 'ap', 'ssid': ssid}
                })
            else:
                return jsonify({
                    'status': 'error',
                    'message': 'No se pudo activar el modo punto de acceso'
                }), 500
        else:
            success = wifi_service.disable_ap_mode()
            if success:
                return jsonify({
                    'status': 'success',
                    'message': 'Modo punto de acceso desactivado',
                    'data': {'mode': 'client'}
                })
            else:
                return jsonify({
                    'status': 'error',
                    'message': 'No se pudo desactivar el modo punto de acceso'
                }), 500
                
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@wifi_bp.route('/ap/status', methods=['GET'])
@login_required
def ap_status():
    """Obtiene el estado actual del modo punto de acceso"""
    try:
        # Verificar si el servicio hostapd está activo
        result = subprocess.run(
            ['systemctl', 'is-active', 'hostapd'],
            capture_output=True,
            text=True
        )
        
        is_active = result.returncode == 0 and result.stdout.strip() == 'active'
        
        # Obtener configuración actual si está activo
        config = {}
        if is_active:
            try:
                with open('/etc/hostapd/hostapd.conf', 'r') as f:
                    for line in f:
                        if '=' in line:
                            key, value = line.strip().split('=', 1)
                            config[key] = value
            except FileNotFoundError:
                pass
        
        return jsonify({
            'status': 'success',
            'data': {
                'active': is_active,
                'config': config
            }
        })
        
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

# Registrar las rutas en el Blueprint
def init_app(app):
    app.register_blueprint(wifi_bp)
