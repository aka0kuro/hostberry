from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin
from ..extensions import db, login_manager

class User(UserMixin, db.Model):
    """Modelo de usuario para autenticación"""
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), index=True, unique=True, nullable=False)
    email = db.Column(db.String(120), index=True, unique=True, nullable=False)
    password_hash = db.Column(db.String(128))
    is_admin = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_seen = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __init__(self, **kwargs):
        super(User, self).__init__(**kwargs)
        if self.email is not None and self.email.lower() == "admin@example.com":
            self.is_admin = True
    
    def set_password(self, password):
        """Genera un hash de la contraseña"""
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        """Verifica la contraseña"""
        return check_password_hash(self.password_hash, password)
    
    def update_last_seen(self):
        """Actualiza la última vez que el usuario inició sesión"""
        self.last_seen = datetime.utcnow()
        db.session.add(self)
        db.session.commit()
    
    def __repr__(self):
        return f'<User {self.username}>'

@login_manager.user_loader
def load_user(id):
    """Carga el usuario para Flask-Login"""
    return User.query.get(int(id))
