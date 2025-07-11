# Hostberry

Proyecto Flask para gestión de red, seguridad, VPN y Adblock.

## Estructura

- `app/` - Código fuente principal
- `scripts/` - Scripts de utilidad (shell y Python)
- `requirements.txt` - Dependencias
- `wsgi.py` - Entrada WSGI
- `setup.sh` - Instalación inicial
- `babel.cfg` y `translations/` - Internacionalización

## Uso

1. Instala dependencias:
   ```bash
   pip install -r requirements.txt
   ```
2. Ejecuta la app:
   ```bash
   flask run
   ```
3. Scripts útiles en `scripts/`.

## Estructura recomendada

```
app/
    auth/
    config/
    errors/
    middleware/
    models/
    routes/
    services/
    static/
    templates/
    translations/
    utils/
    extensions.py
    __init__.py
scripts/
    adblock.sh
    init_db.py
    update_logo.sh
requirements.txt
wsgi.py
setup.sh
babel.cfg
README.md
```
