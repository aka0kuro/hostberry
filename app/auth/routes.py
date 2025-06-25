from flask import Blueprint, render_template, redirect, url_for, flash, request, session
from flask_login import login_user, logout_user, login_required, current_user, login_fresh
from werkzeug.urls import url_parse
from ..extensions import db
from ..models.user import User
from .forms import LoginForm, RegistrationForm
from . import login_required, admin_required

# Crear Blueprint
auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    # Si el usuario ya está autenticado, redirigir al dashboard
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    
    form = LoginForm()
    if form.validate_on_submit():
        # Buscar usuario en la base de datos
        user = User.query.filter_by(username=form.username.data).first()
        
        # Verificar usuario y contraseña
        if user is None or not user.check_password(form.password.data):
            flash('Usuario o contraseña inválidos', 'danger')
            return redirect(url_for('auth.login'))
        
        # Iniciar sesión
        login_user(user, remember=form.remember_me.data)
        
        # Redirigir a la página a la que intentaba acceder o al dashboard
        next_page = request.args.get('next')
        if not next_page or url_parse(next_page).netloc != '':
            next_page = url_for('main.index')
        
        flash(f'¡Bienvenido de nuevo, {user.username}!', 'success')
        return redirect(next_page)
    
    return render_template('security/login.html', title='Iniciar Sesión', form=form)

@auth_bp.route('/logout')
@login_required
def logout():
    username = current_user.username
    logout_user()
    flash(f'Has cerrado sesión correctamente, {username}.', 'info')
    return redirect(url_for('auth.login'))

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    # Si el usuario ya está autenticado, redirigir al dashboard
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    
    form = RegistrationForm()
    if form.validate_on_submit():
        # Crear nuevo usuario
        user = User(
            username=form.username.data,
            email=f"{form.username.data}@localhost"  # Usar un correo por defecto
        )
        user.set_password(form.password.data)
        
        # Guardar en la base de datos
        db.session.add(user)
        db.session.commit()
        
        # Iniciar sesión automáticamente
        login_user(user)
        flash(f'¡Bienvenido a HostBerry, {user.username}!', 'success')
        return redirect(url_for('main.index'))
    
    return render_template('security/register.html', title='Registro', form=form)

@auth_bp.route('/account')
@login_required
def account():
    """Página de perfil del usuario"""
    return render_template('security/account.html', title='Mi Cuenta')

@auth_bp.route('/change_password', methods=['GET', 'POST'])
@login_required
def change_password():
    """Permite al usuario cambiar su contraseña"""
    from .forms import ChangePasswordForm
    
    form = ChangePasswordForm()
    if form.validate_on_submit():
        if current_user.check_password(form.old_password.data):
            current_user.set_password(form.new_password.data)
            db.session.commit()
            flash('Tu contraseña ha sido actualizada.', 'success')
            return redirect(url_for('auth.account'))
        else:
            flash('La contraseña actual no es válida.', 'danger')
    
    return render_template('security/change_password.html', title='Cambiar Contraseña', form=form)
