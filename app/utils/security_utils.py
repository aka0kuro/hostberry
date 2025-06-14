# Utilidades y estado global de seguridad
from collections import defaultdict

FAILED_ATTEMPTS = defaultdict(int)
BLOCKED_IPS = set()

# Aquí se pueden agregar funciones relacionadas con seguridad, bloqueo de IP, etc.
