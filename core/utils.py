import datetime
import pytz
import time
# psutil se importa lazy cuando se necesita

# Helpers generales para fechas y zonas horarias

def format_datetime(dt, fmt='%Y-%m-%d %H:%M', tz='UTC'):
    """Formatea una fecha/hora con zona horaria"""
    if dt is None:
        return ''
    if isinstance(dt, (int, float)):
        dt = datetime.datetime.fromtimestamp(dt, pytz.timezone(tz))
    elif dt.tzinfo is None:
        dt = pytz.timezone(tz).localize(dt)
    return dt.strftime(fmt)


def get_current_time(tz='UTC'):
    """Obtiene la hora actual con zona horaria"""
    return datetime.datetime.now(pytz.timezone(tz))


def get_all_timezones():
    """Obtiene todas las zonas horarias disponibles"""
    return pytz.all_timezones


def get_network_stats():
    """Obtiene estadísticas de red"""
    try:
        net_io = psutil.net_io_counters()
        return {
            'bytes_sent': net_io.bytes_sent,
            'bytes_recv': net_io.bytes_recv,
            'packets_sent': net_io.packets_sent,
            'packets_recv': net_io.packets_recv,
            'timestamp': time.time()
        }
    except Exception as e:
        return {
            'bytes_sent': 0,
            'bytes_recv': 0,
            'packets_sent': 0,
            'packets_recv': 0,
            'timestamp': time.time(),
            'error': str(e)
        } 