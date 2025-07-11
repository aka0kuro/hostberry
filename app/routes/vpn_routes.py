from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app as app
from flask_babel import _
from app.config import save_env_config

vpn_bp = Blueprint('vpn', __name__)

@vpn_bp.route('/vpn_config', methods=['GET', 'POST'])
def vpn_config():
    if request.method == 'POST':
        save_env_config('VPN_ENABLED', request.form.get('vpn_enabled') == 'on')
        save_env_config('VPN_PROVIDER', request.form.get('vpn_provider'))
        save_env_config('VPN_COUNTRY', request.form.get('vpn_country'))
        
        flash(_('VPN configuration updated successfully!'), 'success')
        return redirect(url_for('vpn.vpn_config'))

    vpn_status = {
        'connected': False,
        'ip_address': None,
        'location': None
    }

    return render_template('vpn.html', 
        config=app.config,
        vpn_providers=['OpenVPN', 'WireGuard', 'IPSec'],
        vpn_countries=['US', 'UK', 'DE', 'FR', 'JP'],
        vpn_status=vpn_status
    )

@vpn_bp.route('/vpn/toggle', methods=['POST'])
def vpn_toggle():
    try:
        # La lógica para activar/desactivar la VPN iría aquí
        # Por ejemplo, llamar a un script de sistema.
        flash(_('VPN connection toggled successfully'), 'success')
    except Exception as e:
        app.logger.error(f"VPN toggle error: {e}")
        flash(_('Error toggling VPN connection'), 'danger')
    return redirect(url_for('vpn.vpn_config'))
