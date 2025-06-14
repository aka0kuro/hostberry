def register_blueprints(app):
    """
    Registra todos los blueprints de la aplicación
    """
    # Registrar blueprints principales
    from .main import main_bp
    app.register_blueprint(main_bp)
    
    # Registrar blueprints de autenticación
    try:
        from app.auth.routes import auth_bp
        app.register_blueprint(auth_bp, url_prefix='/auth')
    except ImportError as e:
        app.logger.warning(f"No se pudo cargar el blueprint de autenticación: {e}")
    
    # Registrar blueprints de API
    try:
        from .wifi import wifi_bp
        app.register_blueprint(wifi_bp, url_prefix='/api/wifi')
    except ImportError as e:
        app.logger.warning(f"No se pudo cargar el blueprint de WiFi: {e}")
    
    # Registrar blueprints opcionales
    optional_blueprints = [
        ('vpn', '/api/vpn'),
        ('system', '/api/system'),
        ('adblock', '/api/adblock')
    ]
    
    for module_name, url_prefix in optional_blueprints:
        try:
            module = __import__(f'app.routes.{module_name}', fromlist=[f'{module_name}_bp'])
            bp = getattr(module, f'{module_name}_bp')
            app.register_blueprint(bp, url_prefix=url_prefix)
        except (ImportError, AttributeError) as e:
            app.logger.warning(f"No se pudo cargar el blueprint {module_name}: {e}")
