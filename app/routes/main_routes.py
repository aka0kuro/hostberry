from flask import Blueprint, render_template, jsonify, session
from app.utils.i18n_utils import get_locale, inject_get_locale, set_language, check_lang
from app.utils.log_utils import get_logs
from app.utils.security_utils import FAILED_ATTEMPTS, BLOCKED_IPS
from flask_babel import _
from flask_login import login_required, current_user
from app.utils.network_utils import get_network_interface, get_ip_address, get_wifi_ssid, get_cpu_temp, is_wifi_connected
import psutil
import os
import json
import platform
import socket
import time
import subprocess
from datetime import datetime, timedelta
import logging
from datetime import datetime, timedelta

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def get_cpu_temp():
    """Obtiene la temperatura de la CPU en grados Celsius"""
    try:
        # Método 1: Leer directamente del sistema de archivos
        if os.path.exists('/sys/class/thermal/thermal_zone0/temp'):
            with open('/sys/class/thermal/thermal_zone0/temp', 'r') as f:
                temp = int(f.read().strip()) / 1000.0
                return round(temp, 1)
                
        # Método 2: Buscar en /sys/class/hwmon
        if os.path.exists('/sys/class/hwmon'):
            for hwmon in os.listdir('/sys/class/hwmon'):
                hwmon_path = os.path.join('/sys/class/hwmon', hwmon)
                if os.path.isdir(hwmon_path):
                    # Buscar archivo de temperatura
                    for file in os.listdir(hwmon_path):
                        if file.startswith('temp') and file.endswith('_input'):
                            try:
                                with open(os.path.join(hwmon_path, file), 'r') as f:
                                    temp = int(f.read().strip()) / 1000.0
                                    return round(temp, 1)
                            except (ValueError, IOError) as e:
                                logger.warning(f"No se pudo leer el archivo de temperatura {file}: {e}")
                                continue
        
        # Método 3: Usar psutil si está disponible
        if hasattr(psutil, 'sensors_temperatures'):
            try:
                temps = psutil.sensors_temperatures()
                for name, entries in temps.items():
                    for entry in entries:
                        if any(x in name.lower() for x in ['core', 'cpu', 'pch', 'k10temp']):
                            if hasattr(entry, 'current') and entry.current > 0:
                                return round(entry.current, 1)
            except Exception as e:
                logger.warning(f"Error al usar psutil para obtener temperatura: {e}")
        
        # Si no se pudo obtener la temperatura, devolver un valor por defecto
        logger.warning("No se pudo obtener la temperatura de la CPU, usando valor por defecto")
        return 0.0
        
    except Exception as e:
        logger.error(f"Error inesperado en get_cpu_temp: {e}")
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
        boot_time = datetime.fromtimestamp(psutil.boot_time())
        uptime = datetime.now() - boot_time
        
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
    stats = {}
    try:
        # Obtener estadísticas de CPU
        try:
            cpu_percent = psutil.cpu_percent(interval=1)
            stats['cpu_usage'] = round(cpu_percent, 1)
            logger.debug(f"Uso de CPU: {cpu_percent}%")
        except Exception as e:
            logger.error(f"Error al obtener uso de CPU: {e}")
            stats['cpu_usage'] = 0.0
        
        # Obtener temperatura de CPU
        try:
            cpu_temp = get_cpu_temp()
            stats['cpu_temp'] = cpu_temp
            logger.debug(f"Temperatura de CPU: {cpu_temp}°C")
        except Exception as e:
            logger.error(f"Error al obtener temperatura de CPU: {e}")
            stats['cpu_temp'] = 0.0
        
        # Obtener estadísticas de memoria
        try:
            memory = psutil.virtual_memory()
            memory_percent = memory.percent
            stats['memory_usage'] = round(memory_percent, 1)
            stats['memory_total'] = round(memory.total / (1024**3), 2)  # en GB
            stats['memory_used'] = round(memory.used / (1024**3), 2)     # en GB
            stats['memory_available'] = round(memory.available / (1024**3), 2)  # en GB
            logger.debug(f"Uso de memoria: {memory_percent}%")
        except Exception as e:
            logger.error(f"Error al obtener estadísticas de memoria: {e}")
            stats['memory_usage'] = 0.0
        
        # Obtener estadísticas de red
        try:
            net_io = psutil.net_io_counters()
            stats['bytes_sent'] = net_io.bytes_sent
            stats['bytes_recv'] = net_io.bytes_recv
            logger.debug(f"Tráfico de red: Enviados={net_io.bytes_sent}, Recibidos={net_io.bytes_recv}")

            # Obtener información de la interfaz de red
            stats['network_interface'] = get_network_interface()
            stats['ip_address'] = get_ip_address()
            stats['wifi_ssid'] = get_wifi_ssid()
            logger.debug(f"Info de red: Interfaz={stats['network_interface']}, IP={stats['ip_address']}, SSID={stats['wifi_ssid']}")

        except Exception as e:
            logger.error(f"Error al obtener estadísticas de red: {e}")
            stats['bytes_sent'] = 0
            stats['bytes_recv'] = 0
            stats['network_interface'] = 'N/A'
            stats['ip_address'] = 'N/A'
            stats['wifi_ssid'] = 'N/A'
        
        # Devolver en el formato esperado por el frontend
        return jsonify({
            'success': True,
            'stats': stats,
            'timestamp': datetime.utcnow().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Error inesperado en system_stats: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'message': 'Error al obtener estadísticas del sistema',
            'error': str(e),
            'stats': stats  # Devolver las estadísticas que se pudieron obtener
        }), 500

# Registrar las rutas en el Blueprint
def init_app(app):
    app.register_blueprint(main_bp)
