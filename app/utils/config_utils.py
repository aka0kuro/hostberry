import os
import json
from dotenv import load_dotenv
import logging

logger = logging.getLogger(__name__)

class HostBerryConfig:
    def __init__(self, config_path='config.json'):
        self.config_path = config_path
        self.config = self._load_config()
        load_dotenv()

    def _load_config(self):
        """Carga la configuración desde el archivo JSON"""
        try:
            with open(self.config_path, 'r') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            logger.warning(f"No se pudo cargar la configuración: {e}")
            return {}

    def get_current_config(self):
        """Obtiene la configuración actual"""
        return self.config

    def save_json_config(self, config):
        """Guarda la configuración en el archivo JSON"""
        try:
            with open(self.config_path, 'w') as f:
                json.dump(config, f, indent=4)
            self.config = config
            return True
        except Exception as e:
            logger.error(f"Error al guardar la configuración: {e}")
            return False
