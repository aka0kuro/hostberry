from flask import Blueprint, render_template, jsonify, session
from app.utils.i18n_utils import get_locale, inject_get_locale, set_language, check_lang
from app.utils.log_utils import get_logs
from app.utils.security_utils import FAILED_ATTEMPTS, BLOCKED_IPS
from flask_babel import _
from flask_login import login_required, current_user
import psutil
import os
import json
import platform
import socket
import time
import subprocess
from datetime import datetime, timedelta
import logging

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def get_cpu_temp():
    """Obtiene la temperatura de la CPU en grados Celsius"""
    try:
        if os.path.exists('/sys/class/thermal/thermal_zone0/temp'):
            with open('/sys/class/thermal/thermal_zone0/temp', 'r') as f:
                temp = int(f.read().strip()) / 1000.0
                return round(temp, 1)
        elif os.path.exists('/sys/class/hwmon'):
            # Intentar encontrar el archivo de temperatura en hwmon
            for hwmon in os.listdir('/sys/class/hwmon'):
                hwmon_path = os.path.join('/sys/class/hwmon', hwmon)
                if os.path.isdir(hwmon_path):
                    for file in os.listdir(hwmon_path):
                        if file.startswith('temp') and file.endswith('_input'):
                            with open(os.path.join(hwmon_path, file), 'r') as f:
                                temp = int(f.read().strip()) / 1000.0
                                return round(temp, 1)
        # Si no se encuentra la temperatura, usar psutil (menos preciso)
        if hasattr(psutil, 'sensors_temperatures'):
            temps = psutil.sensors_temperatures()
            for name, entries in temps.items():
                for entry in entries:
                    if 'core' in name.lower() or 'cpu' in name.lower() or 'pch' in name.lower():
                        return round(entry.current, 1)
        return 0.0
    except Exception as e:
        logger.error(f"Error obteniendo temperatura de CPU: {e}")
        return 0.0

from app.utils.network_utils import (
    get_network_interface, 
    get_ip_address,
    get_wifi_ssid,
    is_wifi_connected,
    run_command
)
from app.auth import login_required

# Crear Blueprint
main_bp = Blueprint('main', __name__)

@main_bp.route('/')
@login_required
def index():
    """Página principal con estadísticas del sistema"""
    try:
        # Obtener estadísticas del sistema
        interface = get_network_interface()
        
        # Obtener uso de CPU
        cpu_percent = psutil.cpu_percent(interval=1)
        cpu_temp = get_cpu_temp()
        
        # Obtener uso de memoria
        memory = psutil.virtual_memory()
        memory_total = round(memory.total / (1024 ** 3), 2)  # Convertir a GB
        memory_used = round(memory.used / (1024 ** 3), 2)
        memory_percent = memory.percent
        
        # Obtener uso de disco
        disk = psutil.disk_usage('/')
        disk_total = round(disk.total / (1024 ** 3), 2)
        disk_used = round(disk.used / (1024 ** 3), 2)
        disk_percent = disk.percent
        
        # Obtener información de red
        ip_address = get_ip_address(interface)
        ssid = get_wifi_ssid(interface)
        wifi_connected = is_wifi_connected(interface)
        
        # Obtener información del sistema
        boot_time = datetime.datetime.fromtimestamp(psutil.boot_time())
        uptime = datetime.datetime.now() - boot_time
        
        # Formatear tiempo de actividad
        days = uptime.days
        hours, remainder = divmod(uptime.seconds, 3600)
        minutes, _ = divmod(remainder, 60)
        uptime_str = f"{days}d {hours}h {minutes}m"
        
        # Información del sistema
        system_info = {
            'hostname': os.uname().nodename,
            'os': f"{os.uname().sysname} {os.uname().release}",
            'uptime': uptime_str,
            'cpu': {
                'usage': cpu_percent,
                'temp': cpu_temp,
                'cores': psutil.cpu_count(logical=False),
                'threads': psutil.cpu_count()
            },
            'memory': {
                'total': memory_total,
                'used': memory_used,
                'percent': memory_percent
            },
            'disk': {
                'total': disk_total,
                'used': disk_used,
                'percent': disk_percent
            },
            'network': {
                'interface': interface,
                'ip_address': ip_address,
                'ssid': ssid if wifi_connected else _("No conectado"),
                'connected': wifi_connected
            }
        }
        
        return render_template('index.html', system_info=system_info)
        
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@main_bp.route('/api/status')
@login_required
def api_status():
    """Endpoint de estado de la API"""
    return jsonify({
        'status': 'ok',
        'message': 'API en funcionamiento',
        'version': '1.0.0'
    })

@main_bp.route('/api/system/stats')
@login_required
def system_stats():
    """Obtiene estadísticas del sistema en tiempo real"""
    try:
        # Obtener estadísticas de CPU
        cpu_percent = psutil.cpu_percent(interval=1)
        cpu_temp = get_cpu_temp()
        
        # Obtener estadísticas de memoria
        memory = psutil.virtual_memory()
        memory_info = {
            'total': round(memory.total / (1024 ** 3), 2),  # GB
            'available': round(memory.available / (1024 ** 3), 2),
            'percent': memory.percent,
            'used': round(memory.used / (1024 ** 3), 2),
            'free': round(memory.free / (1024 ** 3), 2)
        }
        
        # Obtener estadísticas de red
        net_io = psutil.net_io_counters()
        network_info = {
            'bytes_sent': net_io.bytes_sent,
            'bytes_recv': net_io.bytes_recv,
            'packets_sent': net_io.packets_sent,
            'packets_recv': net_io.packets_recv
        }
        
        return jsonify({
            'status': 'success',
            'data': {
                'cpu': {
                    'percent': cpu_percent,
                    'temp': cpu_temp
                },
                'memory': memory_info,
                'network': network_info
            }
        })
        
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

# Registrar las rutas en el Blueprint
def init_app(app):
    app.register_blueprint(main_bp)
