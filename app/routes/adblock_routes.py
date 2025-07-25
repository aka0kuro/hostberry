

from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from flask_babel import _
import subprocess
import os

adblock_bp = Blueprint('adblock', __name__)

@adblock_bp.route('/', methods=['GET', 'POST'])
def adblock_config():
    """Configuración y activación/desactivación de AdBlock."""
    if request.method == 'POST':
        try:
            adblock_enabled = request.form.get('adblock_enabled') == 'on'
            script_path = '/usr/local/bin/adblock.sh'
            if not os.path.exists(script_path):
                flash(_('Required script not found at %(path)s', path=script_path), 'warning')
                return redirect(url_for('adblock.adblock_config'))

            if adblock_enabled:
                result = subprocess.run(
                    [script_path],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True
                )
                if result.returncode == 0:
                    flash(_('AdBlock enabled and lists updated!'), 'success')
                else:
                    flash(_('AdBlock enabled but update failed: %(error)s', error=result.stderr), 'warning')
            else:
                result = subprocess.run(
                    [script_path, '--disable'],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True
                )
                if result.returncode == 0:
                    flash(_('AdBlock disabled'), 'success')
                else:
                    flash(_('AdBlock disable failed: %(error)s', error=result.stderr), 'warning')
        except Exception as e:
            flash(_('Error configuring AdBlock: %(error)s', error=str(e)), 'danger')
        return redirect(url_for('adblock.adblock_config'))

    adblock_status = current_app.config.get('ADBLOCK_ENABLED', False)
    last_updated = None
    try:
        with open('/etc/hostberry/adblock/last_updated', 'r') as f:
            last_updated = f.read().strip()
    except FileNotFoundError:
        pass

    return render_template(
        'adblock/adblock.html',
        adblock_status=adblock_status,
        last_updated=last_updated
    )

@adblock_bp.route('/update', methods=['POST'])
def adblock_update():
    """Actualiza las listas de AdBlock manualmente."""
    try:
        script_path = '/usr/local/bin/adblock_update.sh'
        if not os.path.exists(script_path):
            flash(_('Required script not found at %(path)s', path=script_path), 'warning')
            return redirect(url_for('adblock.adblock_config'))

        result = subprocess.run(
            [script_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        if result.returncode == 0:
            flash(_('AdBlock lists updated successfully!'), 'success')
        else:
            flash(_('Error updating AdBlock lists: %(error)s', error=result.stderr), 'danger')

    except Exception as e:
        current_app.logger.error(f"AdBlock update error: {str(e)}")
        flash(_('Error updating AdBlock lists: %(error)s', error=str(e)), 'danger')
    return redirect(url_for('adblock.adblock_config'))
