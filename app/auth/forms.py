from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, BooleanField, SubmitField
from wtforms.validators import DataRequired, Length, Email, Optional, EqualTo, ValidationError

class LoginForm(FlaskForm):
    """Formulario de inicio de sesión"""
    username = StringField('Usuario', validators=[
        DataRequired('El nombre de usuario es obligatorio'),
        Length(min=3, max=64, message='El nombre de usuario debe tener entre 3 y 64 caracteres')
    ], render_kw={"placeholder": "Ingresa tu usuario"})
    
    password = PasswordField('Contraseña', validators=[
        DataRequired('La contraseña es obligatoria'),
        Length(min=8, message='La contraseña debe tener al menos 8 caracteres')
    ], render_kw={"placeholder": "Ingresa tu contraseña"})
    
    remember_me = BooleanField('Recordar sesión')
    submit = SubmitField('Iniciar Sesión')


class RegistrationForm(FlaskForm):
    """Formulario de registro de nuevos usuarios"""
    username = StringField('Usuario', validators=[
        DataRequired('El nombre de usuario es obligatorio'),
        Length(min=3, max=64, message='El nombre de usuario debe tener entre 3 y 64 caracteres')
    ], render_kw={"placeholder": "Elige un nombre de usuario"})
    
    password = PasswordField('Contraseña', validators=[
        DataRequired('La contraseña es obligatoria'),
        Length(min=8, message='La contraseña debe tener al menos 8 caracteres')
    ], render_kw={"placeholder": "Crea una contraseña segura"})
    
    password2 = PasswordField('Repetir Contraseña', validators=[
        DataRequired('Debes confirmar tu contraseña'),
        EqualTo('password', message='Las contraseñas no coinciden')
    ], render_kw={"placeholder": "Repite tu contraseña"})
    
    submit = SubmitField('Registrarse')
    
    def validate_username(self, username):
        """Validar que el nombre de usuario no esté en uso"""
        from app.models.user import User
        user = User.query.filter_by(username=username.data).first()
        if user is not None:
            raise ValidationError('Por favor usa un nombre de usuario diferente')


class ChangePasswordForm(FlaskForm):
    """Formulario para cambiar la contraseña"""
    old_password = PasswordField('Contraseña Actual', validators=[
        DataRequired('La contraseña actual es obligatoria')
    ], render_kw={"placeholder": "Ingresa tu contraseña actual"})
    
    new_password = PasswordField('Nueva Contraseña', validators=[
        DataRequired('La nueva contraseña es obligatoria'),
        Length(min=8, message='La contraseña debe tener al menos 8 caracteres')
    ], render_kw={"placeholder": "Ingresa tu nueva contraseña"})
    
    confirm_password = PasswordField('Confirmar Nueva Contraseña', validators=[
        DataRequired('Debes confirmar tu nueva contraseña'),
        EqualTo('new_password', message='Las contraseñas no coinciden')
    ], render_kw={"placeholder": "Confirma tu nueva contraseña"})
    
    submit = SubmitField('Cambiar Contraseña')
    
    def validate_old_password(self, field):
        """Validar que la contraseña actual sea correcta"""
        from flask_login import current_user
        if not current_user.check_password(field.data):
            raise ValidationError('La contraseña actual no es válida')
