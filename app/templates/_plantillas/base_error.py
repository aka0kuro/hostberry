"""
Plantilla de manejo de errores para app/errors/
"""

from flask import render_template

def page_not_found(e):
    return render_template('errors/404.html'), 404
