# Estados y variables globales para la app HostBerry
import time

# AdBlock
global_adblock_update_status = {
    'updating': False, 
    'last_result': None, 
    'last_error': None,
    'progress': 0,
    'start_time': None
}

# Estadísticas de red
last_net_io = {}
last_stats_time = {}

# Estados de servicios
service_states = {
    'hostapd': {'running': False, 'last_check': None},
    'openvpn': {'running': False, 'last_check': None},
    'wireguard': {'running': False, 'last_check': None},
    'adblock': {'enabled': False, 'last_update': None}
}

# Configuración global
global_config = {
    'debug_mode': False,
    'log_level': 'INFO',
    'max_upload_size': 16 * 1024 * 1024,  # 16MB
    'session_timeout': 3600,  # 1 hora
    'max_login_attempts': 5
}

def reset_adblock_status():
    """Resetea el estado de AdBlock"""
    global global_adblock_update_status
    global_adblock_update_status = {
        'updating': False,
        'last_result': None,
        'last_error': None,
        'progress': 0,
        'start_time': None
    }

def update_service_state(service, state):
    """Actualiza el estado de un servicio"""
    global service_states
    if service in service_states:
        service_states[service].update(state)
        service_states[service]['last_check'] = time.time()

def get_service_state(service):
    """Obtiene el estado de un servicio"""
    return service_states.get(service, {}) 