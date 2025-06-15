from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, current_app as app
from flask_babel import _
import subprocess
import re

wireguard_bp = Blueprint('wireguard', __name__)

@wireguard_bp.route('/wireguard', methods=['GET', 'POST'])
def wireguard_config():
    status = None
    ip = None
    peers = []
    interface_active = False
    if request.method == 'POST':
        action = request.form.get('action')
        try:
            if action == 'up':
                subprocess.run(["sudo", "wg-quick", "up", "wg0"], check=True, capture_output=True, text=True)
                flash(_('WireGuard interface activated'), 'success')
            elif action == 'down':
                subprocess.run(["sudo", "wg-quick", "down", "wg0"], check=True, capture_output=True, text=True)
                flash(_('WireGuard interface deactivated'), 'success')
            elif 'wg_file' in request.files:
                file = request.files['wg_file']
                if file and file.filename.endswith('.conf'):
                    config_path = '/etc/wireguard/wg0.conf'
                    # Ensure the directory exists and user has permissions
                    # This might require running as a different user or using sudo
                    file.save(config_path)
                    flash(_('WireGuard configuration saved'), 'success')
        except subprocess.CalledProcessError as e:
            flash(_('Error: %(error)s', error=e.stderr), 'danger')
        except Exception as e:
            flash(_('Unexpected error: %(error)s', error=str(e)), 'danger')
    
    # Get current status
    try:
        status_output = subprocess.check_output(["sudo", "wg", "show", "wg0"], text=True, stderr=subprocess.PIPE)
        status = status_output
        interface_active = True
        
        ip_output = subprocess.check_output(["ip", "addr", "show", "wg0"], text=True)
        ip_match = re.search(r'inet (\d+\.\d+\.\d+\.\d+)', ip_output)
        if ip_match:
            ip = ip_match.group(1)

        peer_pattern = r'peer: (.+?)\n.*?endpoint: (.+?)\n.*?allowed ips: (.+?)\n.*?transfer: (.+?)\n'
        peers = []
        for match in re.finditer(peer_pattern, status_output, re.DOTALL):
            peers.append({
                'pubkey': match.group(1),
                'endpoint': match.group(2),
                'allowed_ips': match.group(3),
                'transfer': match.group(4)
            })
    except subprocess.CalledProcessError:
        interface_active = False
    except Exception as e:
        flash(_('Error getting WireGuard status: %(error)s', error=str(e)), 'warning')
        
    return render_template(
        'wireguard.html',
        status=status,
        ip=ip,
        peers=peers,
        interface_active=interface_active,
        config=app.config
    )
