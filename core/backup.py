"""
Sistema de backup automático para HostBerry
"""

import os
import shutil
import tarfile
import gzip
import json
import hashlib
import io
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, Optional
import logging

from config.settings import settings
from core.i18n import get_text

logger = logging.getLogger(__name__)

class BackupManager:
    """Gestor de backups automáticos con encriptación"""
    
    def __init__(self):
        # Usar ruta absoluta del directorio de la aplicación
        app_dir = Path(__file__).parent.parent
        self.backup_dir = app_dir / "backups"
        self.backup_dir.mkdir(exist_ok=True)
        
        # Generar clave de encriptación si no existe
        if not settings.encryption_key:
            settings.encryption_key = os.urandom(32).hex()
    
    def create_backup(self, include_logs: bool = True, 
                      include_uploads: bool = True) -> Optional[str]:
        """Crear backup completo del sistema"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_name = f"hostberry_backup_{timestamp}.tar.gz"
            backup_path = self.backup_dir / backup_name
            
            # Crear archivo tar.gz
            with tarfile.open(backup_path, "w:gz") as tar:
                # Backup de base de datos
                if Path("hostberry.db").exists():
                    tar.add("hostberry.db", arcname="database/hostberry.db")
                
                # Backup de configuración
                if Path("config").exists():
                    tar.add("config", arcname="config")
                
                # Backup de logs (opcional)
                if include_logs and Path("logs").exists():
                    tar.add("logs", arcname="logs")
                
                # Backup de uploads (opcional)
                if include_uploads and Path("uploads").exists():
                    tar.add("uploads", arcname="uploads")
                
                # Backup de archivos de configuración del sistema
                system_configs = [
                    "/etc/hostapd/hostapd.conf",
                    "/etc/wpa_supplicant/wpa_supplicant.conf",
                    "/etc/openvpn/client.conf",
                    "/etc/wireguard/wg0.conf"
                ]
                
                for config_file in system_configs:
                    if Path(config_file).exists():
                        tar.add(config_file, arcname=f"system_configs/{os.path.basename(config_file)}")
                
                # Metadata del backup
                metadata = {
                    "timestamp": timestamp,
                    "version": "2.0.0",
                    "includes_logs": include_logs,
                    "includes_uploads": include_uploads,
                    "created_by": "HostBerry Backup Manager"
                }
                
                # Agregar metadata
                metadata_content = json.dumps(metadata, indent=2)
                tar_info = tarfile.TarInfo("metadata.json")
                tar_info.size = len(metadata_content.encode())
                tar.addfile(tar_info, io.BytesIO(metadata_content.encode()))
            
            # Encriptar backup si está habilitado
            if settings.backup_encryption_enabled:
                self._encrypt_backup(backup_path)
            
            # Limpiar backups antiguos
            self._cleanup_old_backups()
            
            logger.info(f"✅ Backup creado: {backup_path}")
            return str(backup_path)
            
        except Exception as e:
            logger.error(f"❌ Error creando backup: {e}")
            return None
    
    def _encrypt_backup(self, backup_path: Path):
        """Encriptar archivo de backup"""
        try:
            from cryptography.fernet import Fernet
            from cryptography.hazmat.primitives import hashes
            from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
            import base64
            
            # Generar clave de encriptación
            salt = os.urandom(16)
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=salt,
                iterations=100000,
            )
            key = base64.urlsafe_b64encode(kdf.derive(settings.encryption_key.encode()))
            
            # Encriptar archivo
            fernet = Fernet(key)
            
            with open(backup_path, 'rb') as f:
                data = f.read()
            
            encrypted_data = fernet.encrypt(data)
            
            # Guardar archivo encriptado
            encrypted_path = backup_path.with_suffix('.tar.gz.enc')
            with open(encrypted_path, 'wb') as f:
                f.write(salt + encrypted_data)
            
            # Eliminar archivo original
            backup_path.unlink()
            
            logger.info(f"✅ Backup encriptado: {encrypted_path}")
            
        except ImportError:
            logger.warning("cryptography no disponible, backup sin encriptar")
        except Exception as e:
            logger.error(f"❌ Error encriptando backup: {e}")
    
    def restore_backup(self, backup_path: str, target_dir: str = None) -> bool:
        """Restaurar backup"""
        try:
            backup_file = Path(backup_path)
            if not backup_file.exists():
                logger.error(f"❌ Archivo de backup no encontrado: {backup_path}")
                return False
            
            # Desencriptar si es necesario
            if backup_file.suffix == '.enc':
                backup_file = self._decrypt_backup(backup_file)
                if not backup_file:
                    return False
            
            # Crear directorio temporal
            temp_dir = Path("temp_restore")
            temp_dir.mkdir(exist_ok=True)
            
            # Extraer backup
            with tarfile.open(backup_file, "r:gz") as tar:
                tar.extractall(temp_dir)
            
            # Restaurar archivos
            if target_dir:
                restore_dir = Path(target_dir)
            else:
                restore_dir = Path(".")
            
            # Restaurar base de datos
            db_backup = temp_dir / "database" / "hostberry.db"
            if db_backup.exists():
                shutil.copy2(db_backup, restore_dir / "hostberry.db")
            
            # Restaurar configuración
            config_backup = temp_dir / "config"
            if config_backup.exists():
                if (restore_dir / "config").exists():
                    shutil.rmtree(restore_dir / "config")
                shutil.copytree(config_backup, restore_dir / "config")
            
            # Restaurar logs
            logs_backup = temp_dir / "logs"
            if logs_backup.exists():
                if (restore_dir / "logs").exists():
                    shutil.rmtree(restore_dir / "logs")
                shutil.copytree(logs_backup, restore_dir / "logs")
            
            # Limpiar directorio temporal
            shutil.rmtree(temp_dir)
            
            logger.info(f"✅ Backup restaurado desde: {backup_path}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error restaurando backup: {e}")
            return False
    
    def _decrypt_backup(self, encrypted_path: Path) -> Optional[Path]:
        """Desencriptar archivo de backup"""
        try:
            from cryptography.fernet import Fernet
            from cryptography.hazmat.primitives import hashes
            from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
            import base64
            
            with open(encrypted_path, 'rb') as f:
                data = f.read()
            
            # Extraer salt y datos encriptados
            salt = data[:16]
            encrypted_data = data[16:]
            
            # Generar clave
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=salt,
                iterations=100000,
            )
            key = base64.urlsafe_b64encode(kdf.derive(settings.encryption_key.encode()))
            
            # Desencriptar
            fernet = Fernet(key)
            decrypted_data = fernet.decrypt(encrypted_data)
            
            # Guardar archivo desencriptado
            decrypted_path = encrypted_path.with_suffix('')
            with open(decrypted_path, 'wb') as f:
                f.write(decrypted_data)
            
            return decrypted_path
            
        except ImportError:
            logger.error("cryptography no disponible para desencriptar")
            return None
        except Exception as e:
            logger.error(f"❌ Error desencriptando backup: {e}")
            return None
    
    def _cleanup_old_backups(self):
        """Limpiar backups antiguos"""
        try:
            current_time = datetime.now()
            retention_days = settings.backup_retention_days
            
            for backup_file in self.backup_dir.glob("*.tar.gz*"):
                file_age = current_time - datetime.fromtimestamp(backup_file.stat().st_mtime)
                if file_age.days > retention_days:
                    backup_file.unlink()
                    logger.info(f"🗑️ Backup antiguo eliminado: {backup_file}")
                    
        except Exception as e:
            logger.error(f"❌ Error limpiando backups antiguos: {e}")
    
    def list_backups(self) -> list:
        """Listar backups disponibles"""
        backups = []
        for backup_file in self.backup_dir.glob("*.tar.gz*"):
            stat = backup_file.stat()
            backups.append({
                "name": backup_file.name,
                "size": stat.st_size,
                "created": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                "encrypted": backup_file.suffix == '.enc'
            })
        return sorted(backups, key=lambda x: x["created"], reverse=True)
    
    def get_backup_info(self, backup_path: str) -> Optional[Dict[str, Any]]:
        """Obtener información de un backup"""
        try:
            backup_file = Path(backup_path)
            if not backup_file.exists():
                return None
            
            # Desencriptar si es necesario
            if backup_file.suffix == '.enc':
                backup_file = self._decrypt_backup(backup_file)
                if not backup_file:
                    return None
            
            # Extraer metadata
            with tarfile.open(backup_file, "r:gz") as tar:
                try:
                    metadata_member = tar.getmember("metadata.json")
                    metadata_file = tar.extractfile(metadata_member)
                    metadata = json.loads(metadata_file.read().decode())
                    return metadata
                except KeyError:
                    return None
                    
        except Exception as e:
            logger.error(f"❌ Error obteniendo información del backup: {e}")
            return None

# Instancia global del gestor de backups
backup_manager = BackupManager()

# Funciones de conveniencia
def create_system_backup(include_logs: bool = True, include_uploads: bool = True) -> Optional[str]:
    """Crear backup del sistema"""
    return backup_manager.create_backup(include_logs, include_uploads)

def restore_system_backup(backup_path: str, target_dir: str = None) -> bool:
    """Restaurar backup del sistema"""
    return backup_manager.restore_backup(backup_path, target_dir)

def list_system_backups() -> list:
    """Listar backups del sistema"""
    return backup_manager.list_backups()

def get_backup_details(backup_path: str) -> Optional[Dict[str, Any]]:
    """Obtener detalles de un backup"""
    return backup_manager.get_backup_info(backup_path) 