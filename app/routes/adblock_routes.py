from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app as app
from flask_babel import _
import subprocess
import os
from app.config import save_config

adblock_bp = Blueprint('adblock', __name__)

@adblock_bp.route('/adblock', methods=['GET', 'POST'])
def adblock_config():
    if request.method == 'POST':
        try:
            adblock_enabled = request.form.get('adblock_enabled') == 'on'
            save_config('ADBLOCK_ENABLED', adblock_enabled)
            
            script_path = '/usr/local/bin/adblock.sh'
            if not os.path.exists(script_path):
                 flash(_('Required script not found at %(path)s', path=script_path), 'warning')
                 return redirect(url_for('adblock.adblock_config'))

            if adblock_enabled:
                result = subprocess.run(
                    [script_path],
                    check=True,
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
                    check=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True
                )
                flash(_('AdBlock disabled'), 'success')

        except subprocess.CalledProcessError as e:
            flash(_('Script execution failed: %(error)s', error=e.stderr), 'danger')
        except Exception as e:
            flash(_('Error configuring AdBlock: %(error)s', error=str(e)), 'danger')
        return redirect(url_for('adblock.adblock_config'))

    adblock_status = app.config.get('ADBLOCK_ENABLED', False)
    last_updated = None
    try:
        with open('/etc/hostberry/adblock/last_updated', 'r') as f:
            last_updated = f.read().strip()
    except FileNotFoundError:
        pass # It's okay if the file doesn't exist yet

    return render_template(
        'adblock.html',
        adblock_status=adblock_status,
        last_updated=last_updated
    )

@adblock_bp.route('/adblock/update', methods=['POST'])
def adblock_update():
    try:
        script_path = '/usr/local/bin/adblock_update.sh'
        if not os.path.exists(script_path):
            flash(_('Required script not found at %(path)s', path=script_path), 'warning')
            return redirect(url_for('adblock.adblock_config'))

        result = subprocess.run(
            [script_path],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        if result.returncode == 0:
            flash(_('AdBlock lists updated successfully!'), 'success')
        else:
            flash(_('Error updating AdBlock lists: ') + result.stderr, 'danger')

    except subprocess.CalledProcessError as e:
        flash(_('Script execution failed: %(error)s', error=e.stderr), 'danger')
    except Exception as e:
        app.logger.error(f"AdBlock update error: {str(e)}")
        flash(_('Error updating AdBlock lists'), 'danger')
    return redirect(url_for('adblock.adblock_config'))
