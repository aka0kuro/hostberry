def register_blueprints(app):
    """
    Registra todos los blueprints de la aplicación con manejo de errores consistente.
    """
    blueprints = [
        # (módulo, nombre_blueprint, prefijo_url)
        ('.main_routes', 'main_bp', ''),
        ('app.auth.routes', 'auth_bp', '/auth'),
        ('app.routes.wifi', 'wifi_bp', '/wifi'),
        ('app.routes.security_routes', 'security_bp', '/security'),
        ('app.routes.vpn_routes', 'vpn_bp', '/vpn'),
        ('app.routes.adblock_routes', 'adblock_bp', '/adblock'),
        ('app.routes.wireguard_routes', 'wireguard_bp', '/wireguard')
    ]
    
    registered_names = set()
    for module_path, bp_name, url_prefix in blueprints:
        try:
            app.logger.info(f'Intentando importar blueprint {bp_name} desde {module_path}')
            module = __import__(module_path, fromlist=[bp_name])
            bp = getattr(module, bp_name, None)
            if bp is None:
                app.logger.error(f'Blueprint {bp_name} no encontrado en {module_path}')
                continue
            app.logger.info(f'Intentando registrar blueprint {bp.name} (prefijo: {url_prefix})')
            if bp.name in registered_names:
                app.logger.warning(f'Blueprint {bp_name} ya registrado, se omite para evitar duplicidad')
                continue
            app.register_blueprint(bp, url_prefix=url_prefix)
            registered_names.add(bp.name)
            app.logger.info(f'Blueprint registrado: {bp_name} (prefijo: {url_prefix or "/"})')
        except ImportError as e:
            app.logger.error(f'Error al importar el blueprint {bp_name} desde {module_path}: {e}')
        except Exception as e:
            app.logger.error(f'Error al registrar el blueprint {bp_name}: {e}')
