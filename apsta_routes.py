from flask import Blueprint, request, jsonify
import subprocess
import os
from auth import login_required

apsta_bp = Blueprint('apsta', __name__)

SCRIPT_PATH = os.path.join(os.path.dirname(__file__), 'wifi-ap-sta.sh')

@apsta_bp.route('/api/apsta', methods=['POST'])
@login_required
def apsta_control():
    """
    Controla el modo AP/STA ejecutando el script wifi-ap-sta.sh con los comandos adecuados.
    Recibe JSON con 'command' (configure/start/stop/status) y, opcionalmente, configuración (ssid, password, channel, band).
    """
    if not request.is_json:
        return jsonify({'success': False, 'error': 'Content-Type debe ser application/json'}), 400
    data = request.get_json()
    command = data.get('command')
    if command not in ['configure', 'start', 'stop', 'status']:
        return jsonify({'success': False, 'error': 'Comando inválido'}), 400

    # Si es 'configure', pasar variables de entorno para SSID, password, etc.
    env = os.environ.copy()
    for key in ['AP_SSID', 'AP_PASSWORD', 'AP_CHANNEL', 'AP_BAND']:
        if key.lower() in data:
            env[key] = str(data[key.lower()])

    try:
        result = subprocess.run([
            'sudo', SCRIPT_PATH, command
        ], env=env, capture_output=True, text=True, timeout=60)
        return jsonify({
            'success': result.returncode == 0,
            'stdout': result.stdout,
            'stderr': result.stderr,
            'message': 'OK' if result.returncode == 0 else 'Error al ejecutar el script',
            'code': result.returncode
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# Para registrar este blueprint, en app.py agrega:
# from apsta_routes import apsta_bp
# app.register_blueprint(apsta_bp)
