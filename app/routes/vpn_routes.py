from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app as app
from flask_babel import _
from hostberry_config import HostBerryConfig

vpn_bp = Blueprint('vpn', __name__)

config = HostBerryConfig()

@vpn_bp.route('/vpn_config', methods=['GET', 'POST'])
def vpn_config():
    if request.method == 'POST':
        new_config = {
            'VPN_ENABLED': request.form.get('vpn_enabled') == 'on',
            'VPN_PROVIDER': request.form.get('vpn_provider'),
            'VPN_COUNTRY': request.form.get('vpn_country')
        }
        config.update_config(new_config)
        flash(_('VPN configuration updated successfully!'), 'success')
        return redirect(url_for('vpn.vpn_config'))
    current_config = config.get_current_config()
    return render_template('vpn.html', 
        config=current_config,
        vpn_providers=['OpenVPN', 'WireGuard', 'IPSec'],
        vpn_countries=['US', 'UK', 'DE', 'FR', 'JP'],
        vpn_status={
            'connected': False,
            'ip_address': None,
            'location': None
        }
    )

@vpn_bp.route('/vpn/toggle', methods=['POST'])
def vpn_toggle():
    try:
        # Toggle VPN connection logic here
        flash(_('VPN connection toggled successfully'), 'success')
    except Exception as e:
        app.logger.error(f"VPN toggle error: {e}")
        flash(_('Error toggling VPN connection'), 'danger')
    return redirect(url_for('vpn.vpn_config'))
