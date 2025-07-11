"""
Plantilla de modelo para app/models/
"""

from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

class ModeloEjemplo(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(64), unique=True, nullable=False)
