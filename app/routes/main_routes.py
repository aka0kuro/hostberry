from flask import Blueprint, render_template, jsonify, session
from app.utils.i18n_utils import get_locale, inject_get_locale, set_language, check_lang
from app.utils.log_utils import get_logs
from app.utils.security_utils import FAILED_ATTEMPTS, BLOCKED_IPS
from flask_babel import _
from flask_login import login_required, current_user
from app.utils.network_utils import (
    get_network_interface, 
    get_ip_address,
    get_wifi_ssid,
    is_wifi_connected,
    run_command,
    get_cpu_temp
)
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

from app.auth import login_required

# Crear Blueprint
main_routes_bp = Blueprint('main_routes', __name__)

@main_routes_bp.route('/')
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
        
        # Valores por defecto para las características
        adblock_enabled = False
        vpn_enabled = False
        firewall_enabled = False
        
        # Obtener estado de los servicios (implementar estas funciones según sea necesario)
        try:
            # Ejemplo: verificar si el servicio de adblock está activo
            # adblock_enabled = check_adblock_status()
            pass
        except Exception as e:
            print(f"Error al verificar estado de adblock: {e}")
            
        try:
            # Ejemplo: verificar si el servicio de VPN está activo
            # vpn_enabled = check_vpn_status()
            pass
        except Exception as e:
            print(f"Error al verificar estado de VPN: {e}")
            
        try:
            # Ejemplo: verificar si el firewall está activo
            # firewall_enabled = check_firewall_status()
            pass
        except Exception as e:
            print(f"Error al verificar estado del firewall: {e}")
        
        # Obtener logs del sistema
        logs = get_logs() if hasattr(get_logs, '__call__') else []
        
        return render_template(
            'index.html',
            system_info=system_info,
            adblock_enabled=adblock_enabled,
            vpn_enabled=vpn_enabled,
            firewall_enabled=firewall_enabled,
            network_interface=interface,
            local_ip=ip_address,
            wifi_ssid=ssid if wifi_connected else None,
            hostapd_status='Active' if wifi_connected else 'Inactive',
            logs=logs
        )
        
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@main_routes_bp.route('/api/status')
@login_required
def api_status():
    """Endpoint de estado de la API"""
    return jsonify({
        'status': 'ok',
        'message': 'API en funcionamiento',
        'version': '1.0.0'
    })

@main_routes_bp.route('/api/system/stats')
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
    app.register_blueprint(main_routes_bp)
