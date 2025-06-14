from flask import Blueprint, render_template, jsonify, session
from flask_babel import _
import psutil
import datetime
import os

from app.utils.network_utils import (
    get_network_interface, 
    get_ip_address,
    get_wifi_ssid,
    is_wifi_connected,
    get_cpu_temp,
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
