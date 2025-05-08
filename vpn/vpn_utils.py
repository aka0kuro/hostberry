import subprocess
import os
import time
from flask import current_app as app

def configure_vpn_routing():
    """Configura el enrutamiento para que todo el tráfico pase por la VPN"""
    try:
        # Obtener la interfaz de red principal
        route_cmd = subprocess.run(['ip', 'route', 'show', 'default'], capture_output=True, text=True)
        if route_cmd.returncode != 0 or not route_cmd.stdout.strip():
            app.logger.error(f"Error ejecutando 'ip route show default': {route_cmd.stderr}")
            raise Exception("No se pudo obtener la ruta por defecto")

        # Buscar gateway e interfaz de manera robusta
        default_gateway = None
        default_interface = None
        for line in route_cmd.stdout.strip().split('\n'):
            parts = line.split()
            if 'via' in parts and 'dev' in parts:
                try:
                    default_gateway = parts[parts.index('via') + 1]
                    default_interface = parts[parts.index('dev') + 1]
                    break
                except Exception as e:
                    app.logger.error(f"Error parseando línea de ruta: {line} - {e}")
        if not default_gateway or not default_interface:
            app.logger.error(f"No se pudo encontrar gateway o interfaz en la ruta: {route_cmd.stdout}")
            raise Exception("Formato de ruta por defecto inválido")
        
        app.logger.info(f"Gateway por defecto: {default_gateway}, Interfaz: {default_interface}")
        
        # Guardar la configuración original
        with open('/etc/hostberry/original_routes.txt', 'w') as f:
            f.write(f"GATEWAY={default_gateway}\n")
            f.write(f"INTERFACE={default_interface}\n")
        
        # Verificar que tun0 existe y está UP antes de modificar rutas
        tun_status = subprocess.run(['ip', 'link', 'show', 'tun0'], capture_output=True, text=True)
        if tun_status.returncode != 0 or 'state DOWN' in tun_status.stdout:
            app.logger.error(f"tun0 no existe o está DOWN: {tun_status.stdout}")
            raise Exception("La interfaz tun0 no está activa. Verifica la conexión OpenVPN.")
        
        # Eliminar la ruta por defecto actual
        subprocess.run(['ip', 'route', 'del', 'default'], check=True)
        
        # Añadir ruta por defecto a través de tun0
        subprocess.run(['ip', 'route', 'add', 'default', 'dev', 'tun0'], check=True)
        
        # Mantener ruta al servidor VPN a través de la interfaz original
        subprocess.run(['ip', 'route', 'add', default_gateway, 'dev', default_interface], check=True)
        
        # Configurar iptables para el kill switch
        # Limpiar reglas existentes
        subprocess.run(['iptables', '-F'], check=True)
        subprocess.run(['iptables', '-X'], check=True)
        
        # Permitir tráfico local
        subprocess.run(['iptables', '-A', 'INPUT', '-i', 'lo', '-j', 'ACCEPT'], check=True)
        subprocess.run(['iptables', '-A', 'OUTPUT', '-o', 'lo', '-j', 'ACCEPT'], check=True)
        
        # Permitir tráfico en la interfaz VPN
        subprocess.run(['iptables', '-A', 'INPUT', '-i', 'tun+', '-j', 'ACCEPT'], check=True)
        subprocess.run(['iptables', '-A', 'OUTPUT', '-o', 'tun+', '-j', 'ACCEPT'], check=True)
        
        # Permitir tráfico DNS
        subprocess.run(['iptables', '-A', 'OUTPUT', '-p', 'udp', '--dport', '53', '-j', 'ACCEPT'], check=True)
        subprocess.run(['iptables', '-A', 'INPUT', '-p', 'udp', '--sport', '53', '-j', 'ACCEPT'], check=True)
        
        # Permitir tráfico establecido y relacionado
        subprocess.run(['iptables', '-A', 'INPUT', '-m', 'state', '--state', 'ESTABLISHED,RELATED', '-j', 'ACCEPT'], check=True)
        subprocess.run(['iptables', '-A', 'OUTPUT', '-m', 'state', '--state', 'ESTABLISHED,RELATED', '-j', 'ACCEPT'], check=True)
        
        # Permitir tráfico hacia el servidor VPN a través de la interfaz original
        subprocess.run(['iptables', '-A', 'OUTPUT', '-o', default_interface, '-d', default_gateway, '-j', 'ACCEPT'], check=True)
        
        # Bloquear todo el demás tráfico
        subprocess.run(['iptables', '-P', 'INPUT', 'DROP'], check=True)
        subprocess.run(['iptables', '-P', 'OUTPUT', 'DROP'], check=True)
        subprocess.run(['iptables', '-P', 'FORWARD', 'DROP'], check=True)
        
        # Habilitar el reenvío de IP
        with open('/proc/sys/net/ipv4/ip_forward', 'w') as f:
            f.write('1\n')
        
        # Configurar reglas de NAT
        subprocess.run(['iptables', '-t', 'nat', '-A', 'POSTROUTING', '-o', 'tun0', '-j', 'MASQUERADE'], check=True)
        
        app.logger.info("Configuración de enrutamiento VPN completada")
        return True
        
    except Exception as e:
        app.logger.error(f"Error configurando enrutamiento VPN: {str(e)}")
        return False

def restore_original_routing():
    """Restaura la configuración de red original"""
    try:
        # Intentar desactivar la interfaz tun0 primero
        tun0_down_result = subprocess.run(['ip', 'link', 'set', 'tun0', 'down'], check=False, capture_output=True, text=True)
        if tun0_down_result.returncode == 0:
            app.logger.info("Interfaz tun0 desactivada correctamente.")
        else:
            # No es necesariamente un error crítico si tun0 no existe o no se puede bajar, así que solo lo registramos.
            app.logger.warning(f"No se pudo desactivar la interfaz tun0 o ya estaba desactivada. Salida: {tun0_down_result.stderr or tun0_down_result.stdout}")

        # Leer la configuración original
        if not os.path.exists('/etc/hostberry/original_routes.txt'):
            raise Exception("No se encontró la configuración original")
            
        original_config = {}
        with open('/etc/hostberry/original_routes.txt', 'r') as f:
            for line in f:
                key, value = line.strip().split('=')
                original_config[key] = value
        
        # Eliminar la ruta por defecto actual
        subprocess.run(['ip', 'route', 'del', 'default'], check=False)
        
        # Restaurar la ruta original
        subprocess.run([
            'ip', 'route', 'add', 'default',
            'via', original_config['GATEWAY'],
            'dev', original_config['INTERFACE']
        ], check=True)
        
        # Limpiar reglas de iptables
        subprocess.run(['iptables', '-F'], check=True)
        subprocess.run(['iptables', '-X'], check=True)
        subprocess.run(['iptables', '-t', 'nat', '-F'], check=True)
        
        # Restaurar políticas por defecto
        subprocess.run(['iptables', '-P', 'INPUT', 'ACCEPT'], check=True)
        subprocess.run(['iptables', '-P', 'OUTPUT', 'ACCEPT'], check=True)
        subprocess.run(['iptables', '-P', 'FORWARD', 'ACCEPT'], check=True)
        
        # Deshabilitar el reenvío de IP
        with open('/proc/sys/net/ipv4/ip_forward', 'w') as f:
            f.write('0\n')
        
        app.logger.info("Configuración de red original restaurada")
        return True
        
    except Exception as e:
        app.logger.error(f"Error restaurando configuración original: {str(e)}")
        return False 