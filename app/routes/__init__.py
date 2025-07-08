def register_blueprints(app):
    """
    Registra todos los blueprints de la aplicación
    """
    # Blueprint principal
    try:
        from .main_routes import main_bp
        app.register_blueprint(main_bp)
    except ImportError as e:
        app.logger.error(f'Error al registrar el blueprint principal: {e}')

    # Blueprint de autenticación
    try:
        from app.auth.routes import auth_bp
        app.register_blueprint(auth_bp, url_prefix='/auth')
    except ImportError:
        pass

    # WiFi
    try:
        from app.routes.wifi import wifi_bp
        app.register_blueprint(wifi_bp, url_prefix='/wifi')
    except ImportError as e:
        app.logger.error(f'Error al registrar el blueprint WiFi: {e}')

    # Security
    try:
        from app.routes.security_routes import security_bp
        app.register_blueprint(security_bp, url_prefix='/security')
    except ImportError:
        pass

    # VPN
    try:
        from app.routes.vpn_routes import vpn_bp
        app.register_blueprint(vpn_bp, url_prefix='/vpn')
    except ImportError:
        pass

    # Adblock
    try:
        from app.routes.adblock_routes import adblock_bp
        app.register_blueprint(adblock_bp, url_prefix='/adblock')
    except ImportError:
        pass

    # WireGuard
    try:
        from app.routes.wireguard_routes import wireguard_bp
        app.register_blueprint(wireguard_bp, url_prefix='/wireguard')
    except ImportError:
        pass
