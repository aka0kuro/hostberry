import subprocess
import os
import time
import logging
import hashlib
from flask import current_app as app
from cryptography.fernet import Fernet

logger = logging.getLogger(__name__)

class VPNUtils:
    def __init__(self):
        self._key = None
        self._credentials_path = os.path.join(os.path.dirname(__file__), 'vpn_credentials.json')
        self._key_file = os.path.join(os.path.dirname(__file__), '.vpn_key')
        
    def get_encryption_key(self):
        """Obtener o generar la clave de encriptación"""
        if self._key:
            return self._key
            
        if os.path.exists(self._key_file):
            try:
                with open(self._key_file, 'rb') as f:
                    key = f.read()
                    if key:
                        self._key = key
                        return key
            except Exception as e:
                logger.warning(f"Error al cargar clave existente: {e}")
                
        # Generar nueva clave
        key = Fernet.generate_key()
        try:
            with open(self._key_file, 'wb') as f:
                f.write(key)
        except Exception as e:
            logger.error(f"Error al guardar nueva clave: {e}")
        
        self._key = key
        return key

    def verify_sudo(self):
        """Verifica si el script tiene permisos sudo"""
        try:
            result = subprocess.run(['sudo', '-n', 'true'], capture_output=True)
            return result.returncode == 0
        except Exception:
            return False

    def verify_config_file(self, config_path):
        """Verifica la integridad del archivo de configuración"""
        try:
            if not os.path.exists(config_path):
                return False, "El archivo de configuración no existe"
                
            # Verificar permisos
            if oct(os.stat(config_path).st_mode)[-3:] != '644':
                return False, "Permisos incorrectos en el archivo de configuración"
                
            # Verificar contenido básico
            with open(config_path, 'r') as f:
                content = f.read()
                if not content.strip():
                    return False, "El archivo de configuración está vacío"
                    
                # Verificar directivas básicas
                required_directives = ['remote', 'dev']
                for directive in required_directives:
                    if directive not in content:
                        return False, f"Falta la directiva requerida: {directive}"
                        
            return True, "Archivo de configuración válido"
            
        except Exception as e:
            return False, f"Error verificando archivo de configuración: {str(e)}"

    def configure_vpn_routing(self):
        """Configura el enrutamiento para que todo el tráfico pase por la VPN"""
        if not self.verify_sudo():
            raise Exception("Se requieren permisos sudo para configurar el enrutamiento")

        try:
            # Obtener la interfaz de red principal
            route_cmd = subprocess.run(['ip', 'route', 'show', 'default'], capture_output=True, text=True)
            if route_cmd.returncode != 0 or not route_cmd.stdout.strip():
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
                        logger.error(f"Error parseando línea de ruta: {line} - {e}")
                        
            if not default_gateway or not default_interface:
                raise Exception("Formato de ruta por defecto inválido")
            
            # Guardar la configuración original de forma segura
            config_dir = '/etc/hostberry'
            if not os.path.exists(config_dir):
                os.makedirs(config_dir, mode=0o700)
                
            with open(os.path.join(config_dir, 'original_routes.txt'), 'w') as f:
                f.write(f"GATEWAY={default_gateway}\n")
                f.write(f"INTERFACE={default_interface}\n")
            os.chmod(os.path.join(config_dir, 'original_routes.txt'), 0o600)
            
            # Verificar que tun0 existe y está UP
            tun_status = subprocess.run(['ip', 'link', 'show', 'tun0'], capture_output=True, text=True)
            if tun_status.returncode != 0 or 'state DOWN' in tun_status.stdout:
                raise Exception("La interfaz tun0 no está activa")
            
            # Configurar enrutamiento
            subprocess.run(['ip', 'route', 'del', 'default'], check=True)
            subprocess.run(['ip', 'route', 'add', 'default', 'dev', 'tun0'], check=True)
            subprocess.run(['ip', 'route', 'add', default_gateway, 'dev', default_interface], check=True)
            
            # Configurar kill switch
            self._configure_kill_switch(default_gateway, default_interface)
            
            return True
            
        except Exception as e:
            logger.error(f"Error configurando enrutamiento VPN: {str(e)}")
            return False

    def _configure_kill_switch(self, default_gateway, default_interface):
        """Configura el kill switch de forma segura"""
        try:
            # Limpiar reglas existentes
            subprocess.run(['iptables', '-F'], check=True)
            subprocess.run(['iptables', '-X'], check=True)
            
            # Reglas básicas
            rules = [
                # Permitir tráfico local
                ['-A', 'INPUT', '-i', 'lo', '-j', 'ACCEPT'],
                ['-A', 'OUTPUT', '-o', 'lo', '-j', 'ACCEPT'],
                
                # Permitir tráfico VPN
                ['-A', 'INPUT', '-i', 'tun+', '-j', 'ACCEPT'],
                ['-A', 'OUTPUT', '-o', 'tun+', '-j', 'ACCEPT'],
                
                # Permitir DNS
                ['-A', 'OUTPUT', '-p', 'udp', '--dport', '53', '-j', 'ACCEPT'],
                ['-A', 'INPUT', '-p', 'udp', '--sport', '53', '-j', 'ACCEPT'],
                
                # Permitir conexiones establecidas
                ['-A', 'INPUT', '-m', 'state', '--state', 'ESTABLISHED,RELATED', '-j', 'ACCEPT'],
                ['-A', 'OUTPUT', '-m', 'state', '--state', 'ESTABLISHED,RELATED', '-j', 'ACCEPT'],
                
                # Permitir tráfico al servidor VPN
                ['-A', 'OUTPUT', '-o', default_interface, '-d', default_gateway, '-j', 'ACCEPT']
            ]
            
            for rule in rules:
                subprocess.run(['iptables'] + rule, check=True)
            
            # Bloquear todo lo demás
            subprocess.run(['iptables', '-P', 'INPUT', 'DROP'], check=True)
            subprocess.run(['iptables', '-P', 'OUTPUT', 'DROP'], check=True)
            subprocess.run(['iptables', '-P', 'FORWARD', 'DROP'], check=True)
            
            # Habilitar NAT
            with open('/proc/sys/net/ipv4/ip_forward', 'w') as f:
                f.write('1\n')
            subprocess.run(['iptables', '-t', 'nat', '-A', 'POSTROUTING', '-o', 'tun0', '-j', 'MASQUERADE'], check=True)
            
            # Marcar kill switch como activo
            with open('/etc/openvpn/killswitch_enabled', 'w') as f:
                f.write('1\n')
            
            return True
            
        except Exception as e:
            logger.error(f"Error configurando kill switch: {str(e)}")
            return False

    def restore_original_routing(self):
        """Restaura la configuración de red original de forma segura"""
        if not self.verify_sudo():
            raise Exception("Se requieren permisos sudo para restaurar el enrutamiento")

        try:
            # Desactivar kill switch
            if os.path.exists('/etc/openvpn/killswitch_enabled'):
                os.remove('/etc/openvpn/killswitch_enabled')
            
            # Desactivar tun0
            subprocess.run(['ip', 'link', 'set', 'tun0', 'down'], check=False)
            
            # Leer configuración original
            config_path = '/etc/hostberry/original_routes.txt'
            if not os.path.exists(config_path):
                raise Exception("No se encontró la configuración original")
                
            original_config = {}
            with open(config_path, 'r') as f:
                for line in f:
                    key, value = line.strip().split('=')
                    original_config[key] = value
            
            # Restaurar rutas
            subprocess.run(['ip', 'route', 'del', 'default'], check=False)
            subprocess.run([
                'ip', 'route', 'add', 'default',
                'via', original_config['GATEWAY'],
                'dev', original_config['INTERFACE']
            ], check=True)
            
            # Limpiar iptables
            subprocess.run(['iptables', '-F'], check=True)
            subprocess.run(['iptables', '-X'], check=True)
            subprocess.run(['iptables', '-t', 'nat', '-F'], check=True)
            
            # Restaurar políticas por defecto
            subprocess.run(['iptables', '-P', 'INPUT', 'ACCEPT'], check=True)
            subprocess.run(['iptables', '-P', 'OUTPUT', 'ACCEPT'], check=True)
            subprocess.run(['iptables', '-P', 'FORWARD', 'ACCEPT'], check=True)
            
            # Deshabilitar reenvío de IP
            with open('/proc/sys/net/ipv4/ip_forward', 'w') as f:
                f.write('0\n')
            
            # Eliminar archivo de configuración original
            if os.path.exists(config_path):
                os.remove(config_path)
            
            return True
            
        except Exception as e:
            logger.error(f"Error restaurando configuración original: {str(e)}")
            return False

vpn_utils = VPNUtils() 