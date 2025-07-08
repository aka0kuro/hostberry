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
    
    for module_path, bp_name, url_prefix in blueprints:
        try:
            # Importar dinámicamente el módulo
            module = __import__(module_path, fromlist=[bp_name])
            # Obtener el blueprint
            bp = getattr(module, bp_name, None)
            if bp is not None and hasattr(bp, 'url_prefix'):
                # Si el blueprint ya tiene un prefijo, usarlo
                app.register_blueprint(bp)
            else:
                # Registrar con el prefijo especificado
                app.register_blueprint(bp, url_prefix=url_prefix)
            app.logger.info(f'Blueprint registrado: {bp_name} (prefijo: {url_prefix or "/"})')
        except ImportError as e:
            app.logger.error(f'Error al importar el blueprint {bp_name} desde {module_path}: {e}')
        except Exception as e:
            app.logger.error(f'Error al registrar el blueprint {bp_name}: {e}')
