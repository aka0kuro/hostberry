from flask import Blueprint, request, jsonify, render_template, session, flash, redirect, url_for
from app.utils.i18n_utils import get_locale, inject_get_locale, set_language, check_lang
from app.utils.log_utils import get_logs
from app.utils.security_utils import FAILED_ATTEMPTS, BLOCKED_IPS
from flask_babel import _
import subprocess
import json
import os
import re
import time
from functools import wraps

from app.services.wifi_service import WiFiService
from app.auth import login_required, admin_required
from app.utils.network_utils import run_command

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
    """Endpoint para escanear redes WiFi"""
    try:
        networks = wifi_service.scan_networks()
        return jsonify({
            'status': 'success',
            'data': networks
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@wifi_bp.route('/connect', methods=['POST'])
@login_required
def wifi_connect():
    """Conecta a una red WiFi"""
    try:
        data = request.get_json()
        ssid = data.get('ssid')
        password = data.get('password')
        security_type = data.get('security_type', 'wpa2')
        
        if not ssid:
            return jsonify({
                'status': 'error',
                'message': 'Se requiere el SSID de la red'
            }), 400
            
        # Intentar conectar
        success = wifi_service.connect_to_network(ssid, password, security_type)
        
        if success:
            return jsonify({
                'status': 'success',
                'message': f'Conectado a {ssid}'
            })
        else:
            return jsonify({
                'status': 'error',
                'message': 'No se pudo conectar a la red'
            }), 400
            
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@wifi_bp.route('/status', methods=['GET'])
@login_required
def wifi_status():
    """Obtiene el estado actual de la conexión WiFi"""
    try:
        status = wifi_service.get_connection_status()
        return jsonify({
            'status': 'success',
            'data': status
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@wifi_bp.route('/ap/toggle', methods=['POST'])
@admin_required
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
