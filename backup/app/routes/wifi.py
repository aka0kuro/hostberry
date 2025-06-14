import subprocess
import json
from flask import Blueprint, jsonify, request
from flask_login import login_required
from ..services.wifi_service import WiFiService

# Crear blueprint
wifi_bp = Blueprint('wifi', __name__)
wifi_service = WiFiService()

@wifi_bp.route('/scan', methods=['GET'])
@login_required
def scan_wifi():
    """Escanea redes WiFi disponibles"""
    try:
        networks = wifi_service.scan_networks()
        return jsonify({'status': 'success', 'networks': networks})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@wifi_bp.route('/connect', methods=['POST'])
@login_required
def connect_wifi():
    """Conecta a una red WiFi"""
    data = request.get_json()
    if not data or 'ssid' not in data:
        return jsonify({'status': 'error', 'message': 'Se requiere SSID'}), 400
    
    try:
        result = wifi_service.connect_to_network(
            ssid=data['ssid'],
            password=data.get('password'),
            security_type=data.get('security_type', 'wpa2')
        )
        return jsonify({'status': 'success', 'result': result})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@wifi_bp.route('/status', methods=['GET'])
@login_required
def wifi_status():
    """Obtiene el estado actual de la conexión WiFi"""
    try:
        status = wifi_service.get_connection_status()
        return jsonify({'status': 'success', 'data': status})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@wifi_bp.route('/ap/toggle', methods=['POST'])
@login_required
def toggle_ap_mode():
    """Activa/desactiva el modo punto de acceso"""
    try:
        enabled = request.json.get('enabled', False)
        config = request.json.get('config', {})
        
        if enabled:
            result = wifi_service.enable_ap_mode(
                ssid=config.get('ssid', 'HostBerryAP'),
                password=config.get('password', ''),
                channel=config.get('channel', 6)
            )
        else:
            result = wifi_service.disable_ap_mode()
            
        return jsonify({'status': 'success', 'result': result})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500
