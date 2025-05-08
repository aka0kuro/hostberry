from flask import render_template, jsonify, request, current_app as app, redirect, url_for
import os
import subprocess
import logging
from datetime import datetime
from . import adblock_bp
import json
import time
import re

# Estado global para saber si hay una actualización en curso
global_adblock_update_status = {'updating': False, 'last_result': None, 'last_error': None}

# NUEVO: Definir rutas relativas al proyecto para los archivos de configuración
APP_ROOT = os.path.dirname(os.path.abspath(__file__))
INSTANCE_FOLDER = os.path.join(os.path.dirname(APP_ROOT), 'instance')
ADBLOCK_CONFIG_DIR = os.path.join(INSTANCE_FOLDER, 'adblock_config')

ADBLOCK_SETTINGS_FILE = os.path.join(ADBLOCK_CONFIG_DIR, 'settings.json')
ADBLOCK_CUSTOM_DOMAINS_FILE = os.path.join(ADBLOCK_CONFIG_DIR, 'custom_domains.txt')
ADBLOCK_WHITELIST_FILE = os.path.join(ADBLOCK_CONFIG_DIR, 'whitelist.txt')
ADBLOCK_HOSTS_FILE = '/etc/hosts'

# NUEVO: Crear los directorios y archivos necesarios si no existen
def ensure_adblock_dirs():
    os.makedirs(ADBLOCK_CONFIG_DIR, exist_ok=True)
    if not os.path.exists(ADBLOCK_SETTINGS_FILE):
        with open(ADBLOCK_SETTINGS_FILE, 'w') as f:
            json.dump({
                'enabled': False,
                'update_frequency': 'daily',
                'block_youtube_ads': True,
                'whitelist_mode': False,
                'last_updated': 0
            }, f, indent=2)
    if not os.path.exists(ADBLOCK_CUSTOM_DOMAINS_FILE):
        with open(ADBLOCK_CUSTOM_DOMAINS_FILE, 'w') as f:
            f.write("# Custom blocked domains - one per line\n")
    if not os.path.exists(ADBLOCK_WHITELIST_FILE):
        with open(ADBLOCK_WHITELIST_FILE, 'w') as f:
            f.write("# Whitelisted domains - one per line\n")

# Llamar a esta función al cargar el módulo
ensure_adblock_dirs()

def get_adblock_settings():
    """Lee la configuración actual de AdBlock"""
    try:
        with open(ADBLOCK_SETTINGS_FILE, 'r') as f:
            return json.load(f)
    except Exception as e:
        app.logger.error(f"Error leyendo settings de AdBlock: {e}")
        # Devolver configuración por defecto si hay error
        return {
            'enabled': True, 'update_frequency': 'daily', 
            'block_youtube_ads': True, 'whitelist_mode': False,
            'last_updated': 0
        }

def save_adblock_settings(settings):
    """Guarda la configuración de AdBlock"""
    try:
        with open(ADBLOCK_SETTINGS_FILE, 'w') as f:
            json.dump(settings, f, indent=2)
        return True
    except Exception as e:
        app.logger.error(f"Error guardando settings de AdBlock: {e}")
        return False

def is_adblock_enabled():
    """Verifica si AdBlock está habilitado en la configuración"""
    settings = get_adblock_settings()
    return settings.get('enabled', True)

def apply_adblock_rules():
    """
    Aplica las reglas de AdBlock (combinando listas y custom).
    Esto es una simplificación. En un sistema real, usarías dnsmasq, pi-hole, o similar.
    Aquí simularemos la modificación de /etc/hosts (¡CUIDADO! Esto es solo para demo).
    """
    try:
        # Este es un ejemplo MUY BÁSICO y NO RECOMENDADO para producción.
        # Usar /etc/hosts para bloqueo a gran escala es ineficiente y riesgoso.
        
        # Leer dominios personalizados
        custom_domains = []
        if os.path.exists(ADBLOCK_CUSTOM_DOMAINS_FILE):
            with open(ADBLOCK_CUSTOM_DOMAINS_FILE, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#'):
                        custom_domains.append(line)
        
        # Leer dominios de la whitelist
        whitelist = []
        if os.path.exists(ADBLOCK_WHITELIST_FILE):
            with open(ADBLOCK_WHITELIST_FILE, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#'):
                        whitelist.append(line)

        # Construir contenido del /etc/hosts
        # Primero, conservar contenido original no relacionado con AdBlock
        original_hosts_content = []
        if os.path.exists(ADBLOCK_HOSTS_FILE):
            with open(ADBLOCK_HOSTS_FILE, 'r') as f:
                for line in f:
                    if not ("# Added by HostBerry AdBlock" in line or "0.0.0.0" in line and " # HostBerry AdBlock" in line):
                        original_hosts_content.append(line.strip())
        
        hosts_content = "\n".join(original_hosts_content)
        hosts_content += "\n# ---- HostBerry AdBlock Start ----\n"
        
        if is_adblock_enabled():
            # Añadir dominios de listas de bloqueo (simulado)
            # En un sistema real, aquí se procesarían las listas descargadas.
            # Por ahora, solo usaremos los dominios personalizados.
            
            domains_to_block = set(custom_domains) - set(whitelist)
            
            for domain in domains_to_block:
                hosts_content += f"0.0.0.0 {domain} # HostBerry AdBlock\n"
        
        hosts_content += "# ---- HostBerry AdBlock End ----\n"
        
        # Escribir al /etc/hosts (¡REQUIERE PERMISOS DE SUPERUSUARIO!)
        # Esto fallará si la aplicación no corre como root.
        try:
            with open(ADBLOCK_HOSTS_FILE, 'w') as f:
                f.write(hosts_content)
            app.logger.info("Reglas de AdBlock aplicadas a /etc/hosts")
            
            # Forzar recarga de dnsmasq si existe
            subprocess.run(['systemctl', 'restart', 'dnsmasq'], capture_output=True, text=True)
            
        except PermissionError:
            app.logger.error("Error de permisos al escribir en /etc/hosts. AdBlock no se aplicará.")
            return False
            
        return True
    except Exception as e:
        app.logger.error(f"Error aplicando reglas de AdBlock: {e}")
        return False

@adblock_bp.route('/adblock', methods=['GET', 'POST'])
def adblock_config_page():
    """Página de configuración de AdBlock."""
    if request.method == 'POST':
        current_settings = get_adblock_settings()
        settings_changed_by_form = False # Tracks if core settings like 'enabled' or 'frequency' changed

        # Handle AdBlock enable/disable switch
        # Browsers typically send the field if checked, or omit it if unchecked.
        new_enabled_status = 'adblock_enabled' in request.form
        if current_settings.get('enabled') != new_enabled_status:
            current_settings['enabled'] = new_enabled_status
            settings_changed_by_form = True

        # Handle update frequency
        if 'update_frequency' in request.form:
            new_frequency = request.form['update_frequency']
            if current_settings.get('update_frequency') != new_frequency:
                current_settings['update_frequency'] = new_frequency
                settings_changed_by_form = True
        
        if settings_changed_by_form:
            if not save_adblock_settings(current_settings):
                app.logger.error("Failed to save AdBlock settings (enable/frequency).")
                # Consider adding flash messages for user feedback here and in other error/success cases

        # Handle "Update Lists Now" button (name="action" value="update")
        if request.form.get('action') == 'update':
            app.logger.info("Manual AdBlock list update initiated by user via scripts/adblock.sh.")
            script_path = os.path.join(app.root_path, '..', 'scripts', 'adblock.sh') # app.root_path es la carpeta de la app (hostberry)
            try:
                # Asegurarse que el script es ejecutable
                # No es ideal cambiar permisos en cada ejecución, pero asegura que funcione
                # Lo ideal sería que el script ya tenga permisos de ejecución.
                os.chmod(script_path, 0o755)
                
                result = subprocess.run([script_path], capture_output=True, text=True, check=False)
                if result.returncode == 0:
                    app.logger.info(f"scripts/adblock.sh executed successfully. Output:\n{result.stdout}")
                    # Actualizar timestamp después de ejecución exitosa
                    current_settings_for_update = get_adblock_settings()
                    current_settings_for_update['last_updated'] = int(time.time())
                    if not save_adblock_settings(current_settings_for_update):
                        app.logger.error("Failed to save AdBlock last_updated timestamp after script execution.")
                else:
                    app.logger.error(f"scripts/adblock.sh failed. Return code: {result.returncode}\nStdout:\n{result.stdout}\nStderr:\n{result.stderr}")

            except FileNotFoundError:
                app.logger.error(f"Script not found: {script_path}")
            except Exception as e:
                app.logger.error(f"Error executing scripts/adblock.sh: {str(e)}")
            
            # Siempre aplicar reglas después de intentar actualizar, ya sea que el script falle o no,
            # por si el script tuvo éxito parcial o si las reglas dependen de un timestamp que sí se actualizó.
            if not apply_adblock_rules():
                app.logger.error("Failed to apply AdBlock rules after attempting script execution.")
        elif settings_changed_by_form: # Only apply rules if core settings changed, and not a manual update (which already applied rules)
            if not apply_adblock_rules():
                app.logger.error("Failed to apply AdBlock rules after settings change.")

        return redirect(url_for('adblock.adblock_config_page'))

    # GET request logic (as modified by user in Step 18 and viewed in Step 61) starts below:
    settings = get_adblock_settings()
    
    total_domains_in_custom_lists = 0
    try:
        if os.path.exists(ADBLOCK_CUSTOM_DOMAINS_FILE):
             with open(ADBLOCK_CUSTOM_DOMAINS_FILE, 'r') as f:
                total_domains_in_custom_lists = len([line for line in f if line.strip() and not line.startswith('#')])
    except Exception as e:
        app.logger.error(f"Error contando dominios custom para la página de config: {e}")

    # Estas son estadísticas iniciales. El JavaScript las actualizará con datos más precisos.
    # 'rules_active' es lo que necesita {{ stats.rules_active }} en tu plantilla.
    initial_stats = {
        'rules_active': total_domains_in_custom_lists,
        'total_domains': total_domains_in_custom_lists, # Será actualizado por JS
        'blocked_today': "0",                      # Placeholder, será actualizado por JS
        'total_blocked': "0"                       # Placeholder, será actualizado por JS
    }
    
    # Pasar también el estado de 'enabled' y 'last_updated' si la plantilla los usa directamente
    # Aunque el JavaScript también los cargará.
    return render_template(
        'adblock.html', 
        title='AdBlock Configuration', 
        stats=initial_stats, # Aquí pasamos el objeto stats
        adblock_enabled=settings.get('enabled', True),
        last_updated=settings.get('last_updated', 0)
    )

@adblock_bp.route('/adblock/status')
def adblock_status_endpoint():
    """Obtener el estado actual de AdBlock y estadísticas"""
    settings = get_adblock_settings()
    
    # Simulación de estadísticas
    total_domains_in_lists = 0 # Esto se calcularía de las listas reales
    try:
        if os.path.exists(ADBLOCK_CUSTOM_DOMAINS_FILE):
             with open(ADBLOCK_CUSTOM_DOMAINS_FILE, 'r') as f:
                total_domains_in_lists += len([line for line in f if line.strip() and not line.startswith('#')])
    except:
        pass

    # Las estadísticas de dominios bloqueados requerirían un análisis de logs de dnsmasq/pihole
    stats = {
        'total_domains': total_domains_in_lists, 
        'blocked_today': 0, # Simulado
        'total_blocked': 0  # Simulado
    }
    
    return jsonify({
        'enabled': settings.get('enabled', True),
        'last_updated': settings.get('last_updated', 0),
        'stats': stats
    })

@adblock_bp.route('/adblock/toggle', methods=['POST'])
def adblock_toggle_endpoint():
    """Habilitar o deshabilitar AdBlock"""
    try:
        data = request.get_json()
        enable = data.get('enabled', False)
        
        settings = get_adblock_settings()
        settings['enabled'] = enable
        
        if save_adblock_settings(settings):
            if apply_adblock_rules():
                return jsonify({'success': True, 'message': f'AdBlock {"habilitado" if enable else "deshabilitado"}'})
            else:
                return jsonify({'success': False, 'error': 'Error aplicando reglas de AdBlock'}), 500
        else:
            return jsonify({'success': False, 'error': 'Error guardando la configuración'}), 500
    except Exception as e:
        app.logger.error(f"Error en toggle AdBlock: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@adblock_bp.route('/adblock/update', methods=['POST'])
def adblock_update_lists_endpoint():
    """Iniciar una actualización de las listas de AdBlock"""
    global global_adblock_update_status
    
    if global_adblock_update_status.get('updating', False):
        return jsonify({'success': False, 'error': 'Actualización ya en progreso'}), 409

    try:
        global_adblock_update_status['updating'] = True
        global_adblock_update_status['last_result'] = None
        global_adblock_update_status['last_error'] = None
        
        app.logger.info("Iniciando actualización de listas de AdBlock...")
        
        # Simular la ejecución del script de actualización.
        # En un sistema real, este script descargaría listas y las procesaría.
        # Por ejemplo, /etc/hostberry/adblock/update.sh
        
        # --- INICIO SIMULACIÓN DE update.sh ---
        time.sleep(5) # Simular trabajo
        simulated_output = "Listas descargadas: list1.txt, list2.txt\nDominios procesados: 150000\n"
        # --- FIN SIMULACIÓN DE update.sh ---
        
        # En lugar de llamar a un script externo directamente aquí por ahora,
        # actualizaremos la marca de tiempo y aplicaremos reglas.
        # El script update.sh debería ser responsable de descargar las listas.
        
        settings = get_adblock_settings()
        settings['last_updated'] = int(time.time())
        save_adblock_settings(settings)
        
        if apply_adblock_rules():
            global_adblock_update_status['last_result'] = simulated_output + "\nReglas de AdBlock aplicadas."
            app.logger.info("Actualización de listas de AdBlock completada.")
        else:
            global_adblock_update_status['last_error'] = "Error aplicando reglas después de la actualización."
            app.logger.error("Error aplicando reglas de AdBlock después de la actualización.")
            raise Exception("Error aplicando reglas después de la actualización.")

        global_adblock_update_status['updating'] = False
        return jsonify({'success': True, 'message': 'Listas de AdBlock actualizadas y reglas aplicadas'})
        
    except Exception as e:
        app.logger.error(f"Error actualizando AdBlock: {e}")
        global_adblock_update_status['last_error'] = str(e)
        global_adblock_update_status['updating'] = False
        return jsonify({'success': False, 'error': f'Error actualizando listas: {str(e)}'}), 500

@adblock_bp.route('/adblock/update_status') # Para polling del estado de actualización
def adblock_get_update_status_endpoint():
    global global_adblock_update_status
    return jsonify(global_adblock_update_status)

@adblock_bp.route('/adblock/logs')
def adblock_logs_endpoint():
    """Obtener los logs de AdBlock (simulado)"""
    # Esto requeriría parsear logs de dnsmasq o similar
    # Por ahora, devolvemos datos de ejemplo.
    logs = []
    try:
        # Simulación basada en /etc/hosts si es posible, o ejemplo
        # Esto es muy ineficiente para logs reales.
        if os.path.exists(ADBLOCK_HOSTS_FILE) and is_adblock_enabled():
            with open(ADBLOCK_HOSTS_FILE, 'r') as f:
                count = 0
                for line in f:
                    if "0.0.0.0" in line and "# HostBerry AdBlock" in line:
                        parts = line.split()
                        if len(parts) > 1:
                            domain = parts[1]
                            logs.append({
                                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                                'domain': domain
                            })
                            count += 1
                            if count >= 20: # Limitar a 20 para el ejemplo
                                break
        if not logs: # Si no hay nada o está deshabilitado
            logs.append({'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'), 'domain': 'example-blocked.com (simulated)'})
            logs.append({'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'), 'domain': 'another-ad-domain.net (simulated)'})
    except Exception as e:
        app.logger.error(f"Error simulando logs de AdBlock: {e}")
    return jsonify({'logs': logs[::-1]}) # Más recientes primero

# --- Rutas para listas personalizadas y whitelist ---
def read_domain_list(filepath):
    if not os.path.exists(filepath):
        return []
    with open(filepath, 'r') as f:
        return [line.strip() for line in f if line.strip() and not line.startswith('#')]

def write_domain_list(filepath, domains):
    with open(filepath, 'w') as f:
        f.write("# Auto-generated by HostBerry\n")
        for domain in sorted(list(set(domains))): # Eliminar duplicados y ordenar
            if domain: # Asegurar que no sea una cadena vacía
                f.write(domain + '\n')

@adblock_bp.route('/adblock/custom_domains', methods=['GET'])
def adblock_get_custom_domains():
    domains = read_domain_list(ADBLOCK_CUSTOM_DOMAINS_FILE)
    return jsonify({'domains': domains})

@adblock_bp.route('/adblock/add_domain', methods=['POST'])
def adblock_add_custom_domain():
    try:
        data = request.get_json()
        domain = data.get('domain', '').strip().lower()
        if not domain or not re.match(r"^[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$", domain):
            return jsonify({'success': False, 'error': 'Dominio inválido'}), 400
        
        domains = read_domain_list(ADBLOCK_CUSTOM_DOMAINS_FILE)
        if domain not in domains:
            domains.append(domain)
            write_domain_list(ADBLOCK_CUSTOM_DOMAINS_FILE, domains)
            apply_adblock_rules() # Re-aplicar reglas
        return jsonify({'success': True, 'message': f'Dominio {domain} añadido'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@adblock_bp.route('/adblock/remove_domain', methods=['POST'])
def adblock_remove_custom_domain():
    try:
        data = request.get_json()
        domain_to_remove = data.get('domain', '').strip().lower()
        
        domains = read_domain_list(ADBLOCK_CUSTOM_DOMAINS_FILE)
        if domain_to_remove in domains:
            domains.remove(domain_to_remove)
            write_domain_list(ADBLOCK_CUSTOM_DOMAINS_FILE, domains)
            apply_adblock_rules() # Re-aplicar reglas
        return jsonify({'success': True, 'message': f'Dominio {domain_to_remove} eliminado'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@adblock_bp.route('/adblock/whitelist_domain', methods=['POST'])
def adblock_whitelist_domain():
    try:
        data = request.get_json()
        domain_to_whitelist = data.get('domain', '').strip().lower()
        if not domain_to_whitelist or not re.match(r"^[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$", domain_to_whitelist):
            return jsonify({'success': False, 'error': 'Dominio inválido para whitelist'}), 400
        
        whitelist = read_domain_list(ADBLOCK_WHITELIST_FILE)
        if domain_to_whitelist not in whitelist:
            whitelist.append(domain_to_whitelist)
            write_domain_list(ADBLOCK_WHITELIST_FILE, whitelist)
            apply_adblock_rules() # Re-aplicar reglas
        return jsonify({'success': True, 'message': f'Dominio {domain_to_whitelist} añadido a la whitelist'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
        
@adblock_bp.route('/adblock/settings', methods=['GET'])
def adblock_get_settings_endpoint():
    settings = get_adblock_settings()
    return jsonify({'settings': settings})

@adblock_bp.route('/adblock/save_settings', methods=['POST'])
def adblock_save_settings_endpoint():
    try:
        data = request.get_json()
        
        current_settings = get_adblock_settings()
        
        # Actualizar solo los campos permitidos
        allowed_keys = ['update_frequency', 'block_youtube_ads', 'whitelist_mode']
        for key in allowed_keys:
            if key in data:
                current_settings[key] = data[key]
        
        if save_adblock_settings(current_settings):
            apply_adblock_rules() # Re-aplicar reglas si la configuración afecta el bloqueo
            return jsonify({'success': True, 'message': 'Configuración guardada'})
        else:
            return jsonify({'success': False, 'error': 'Error guardando configuración'}), 500
    except Exception as e:
        app.logger.error(f"Error guardando config AdBlock: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500 