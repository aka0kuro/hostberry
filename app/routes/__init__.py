def register_blueprints(app):
    """
    Registra todos los blueprints de la aplicación
    """
    from .main import main_bp
    from .wifi import wifi_bp
    from .vpn import vpn_bp
    from .system import system_bp
    from .adblock import adblock_bp
    from app.auth.routes import auth_bp
    
    # Registrar blueprints
    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(wifi_bp, url_prefix='/api/wifi')
    app.register_blueprint(vpn_bp, url_prefix='/api/vpn')
    app.register_blueprint(system_bp, url_prefix='/api/system')
    app.register_blueprint(adblock_bp, url_prefix='/api/adblock')
