"""
Plantilla de blueprint de autenticación para app/auth/
"""

from flask import Blueprint, render_template, redirect, url_for, flash, request

bp = Blueprint('auth', __name__, url_prefix='/auth')

@bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        # Lógica de autenticación aquí
        flash('Intento de login')
        return redirect(url_for('main.index'))
    return render_template('security/login.html')
