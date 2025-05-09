#!/bin/bash

# --- Script de instalación robusto para Hostberry ---
# Este script instala todas las dependencias, clona el repositorio y configura la app en /opt/hostberry

set -e

# Verificar si se está ejecutando como root
if [ "$EUID" -ne 0 ]; then
    echo "Por favor, ejecuta este script como root (sudo)"
    exit 1
fi

# Modo de actualización y certificados
UPDATE_MODE=false
GENERATE_CERT=false
while [[ "$#" -gt 0 ]]; do
    case "$1" in
        --update) UPDATE_MODE=true ;;
        --cert) GENERATE_CERT=true ;;
        --network) NETWORK_CONFIG=true ;;
        *) echo "Uso: $0 [--update] [--cert] [--network]"; exit 1 ;;
    esac
    shift
done

# Generar certificados si se solicita
if [ "$GENERATE_CERT" = true ]; then
    generate_ssl_cert
fi

# Configurar red y firewall si se solicita
if [ "$NETWORK_CONFIG" = true ]; then
    configure_network_and_firewall
fi

handle_error() {
    echo "Error: $1"
    exit 1
}

# Dependencias de sistema
DEPS=(python3 python3-pip python3-venv openvpn resolvconf git curl dnsmasq hostapd iptables nftables libnss3-tools ufw)

# Función para configurar firewall y red
configure_network_and_firewall() {
    echo "Configurando firewall y red para Raspberry Pi..."
    
    # Habilitar IPv4 forwarding
    echo "net.ipv4.ip_forward=1" | sudo tee -a /etc/sysctl.conf
    sudo sysctl -p
    
    # Configurar UFW (Uncomplicated Firewall)
    sudo ufw reset
    sudo ufw default deny incoming
    sudo ufw default allow outgoing
    
    # Abrir puertos necesarios
    sudo ufw allow ssh
    sudo ufw allow 8443/tcp  # Puerto HTTPS para Hostberry
    sudo ufw allow 53/udp    # DNS
    sudo ufw allow 67/udp    # DHCP
    sudo ufw allow 68/udp    # DHCP
    
    # Habilitar firewall
    sudo ufw enable
    
    # Configurar interfaces de red
    # Ejemplo de configuración de punto de acceso WiFi
    echo "Configurando interfaces de red..."
    
    # Crear archivo de configuración para punto de acceso WiFi
    cat << EOF | sudo tee /etc/netplan/50-hostberry-wifi-ap.yaml
network:
  version: 2
  wifis:
    wlan_ap0:
      access-points:
        "HostBerry":
          password: "hostberry123"
      dhcp4: true
      optional: true
EOF
    
    # Aplicar configuración de red
    sudo netplan apply
    
    echo "Configuración de red y firewall completada."
}

# Variables para certificados SSL
SSL_DIR="/etc/hostberry/ssl"
SSL_HOSTNAME="hostberry.local"

# Función para generar certificados con mkcert
generate_ssl_cert() {
    # Crear directorio SSL si no existe
    mkdir -p "$SSL_DIR"
    
    # Instalar mkcert si no está instalado
    if ! command -v mkcert &> /dev/null; then
        echo "Instalando mkcert..."
        wget https://github.com/FiloSottile/mkcert/releases/download/v1.4.4/mkcert-v1.4.4-linux-amd64 -O /usr/local/bin/mkcert
        chmod +x /usr/local/bin/mkcert
        mkcert -install
    fi
    
    # Generar certificado
    cd "$SSL_DIR"
    mkcert "$SSL_HOSTNAME" "*.$(hostname -d)" localhost 127.0.0.1 ::1
    
    # Mostrar información del certificado
    echo "Certificados generados en $SSL_DIR:"
    ls -l
}

# Instalar dependencias
apt-get update || handle_error "No se pudo actualizar apt-get"
apt-get install -y "${DEPS[@]}" || handle_error "No se pudieron instalar las dependencias del sistema"

# Modo de instalación o actualización
if [ "$UPDATE_MODE" = false ]; then
    # Modo de instalación: eliminar instalación previa
    if [ -d /opt/hostberry ]; then
        echo "Eliminando instalación previa en /opt/hostberry..."
        systemctl stop hostberry-web.service 2>/dev/null || true
        rm -rf /opt/hostberry
    fi
else
    # Modo de actualización: detener servicio y hacer un backup
    echo "Modo de actualización activado"
    if [ -d /opt/hostberry ]; then
        systemctl stop hostberry-web.service 2>/dev/null || true
        
        # Crear directorio de backup si no existe
        mkdir -p /opt/hostberry_backups
        
        # Crear backup con marca de tiempo
        BACKUP_DIR="/opt/hostberry_backups/hostberry_backup_$(date +%Y%m%d_%H%M%S)"
        cp -r /opt/hostberry "$BACKUP_DIR"
        echo "Backup creado en: $BACKUP_DIR"
    fi
fi

# Manejar clonación del repositorio
cd /opt

# Configurar directorio seguro de Git
git config --global --add safe.directory /opt/hostberry

if [ "$UPDATE_MODE" = true ]; then
    # En modo de actualización, hacer pull en lugar de clonar
    cd /opt/hostberry
    
    # Cambiar permisos temporalmente si es necesario
    sudo chown -R $(whoami):$(whoami) /opt/hostberry
    
    git fetch origin
    git reset --hard origin/main
    git clean -fdx
    
    # Restaurar permisos originales
    sudo chown -R www-data:www-data /opt/hostberry
else
    # En modo de instalación, clonar normalmente
    git clone https://github.com/aka0kuro/hostberry.git hostberry || handle_error "No se pudo clonar el repositorio"
    cd /opt/hostberry
fi

# Si es modo de actualización, restaurar configuraciones personalizadas
if [ "$UPDATE_MODE" = true ]; then
    echo "Restaurando configuraciones personalizadas..."
    
    # Ejemplos de restauración (ajusta según tus necesidades específicas):
    if [ -f "$BACKUP_DIR/config.json" ]; then
        cp "$BACKUP_DIR/config.json" /etc/hostberry/config.json 2>/dev/null || true
    fi
    
    # Restaurar archivos de configuración personalizados
    # Añade aquí más restauraciones según tus necesidades
fi

# Dar permisos de ejecución al script de adblock
chmod +x scripts/adblock.sh || handle_error "No se pudo dar permisos de ejecución a scripts/adblock.sh"

# Crear entorno virtual
python3 -m venv venv || handle_error "No se pudo crear el entorno virtual"
source venv/bin/activate

# Actualizar pip
pip install --upgrade pip || handle_error "No se pudo actualizar pip"

# Instalar dependencias de Python
if [ -f requirements.txt ]; then
    pip install -r requirements.txt || handle_error "No se pudieron instalar las dependencias de Python"
else
    handle_error "No se encontró requirements.txt"
fi

# Crear directorio de logs
mkdir -p /var/log/hostberry
chown -R www-data:www-data /var/log/hostberry

# Copiar y configurar el servicio systemd
if [ -f hostberry-web.service ]; then
    cp hostberry-web.service /etc/systemd/system/hostberry-web.service
    systemctl daemon-reload
    systemctl enable hostberry-web.service
    systemctl restart hostberry-web.service
else
    echo "Advertencia: No se encontró hostberry-web.service, deberás configurarlo manualmente."
fi

# Configuración de OpenVPN
systemctl stop openvpn@client 2>/dev/null || true
systemctl stop openvpn 2>/dev/null || true

groupadd -f openvpn || true
usermod -aG openvpn www-data || true

mkdir -p /etc/openvpn/client
mkdir -p /etc/openvpn/auth
chown -R root:openvpn /etc/openvpn
chmod -R 775 /etc/openvpn
chmod 700 /etc/openvpn/auth

cat > /etc/openvpn/update-resolv-conf << 'EOF'
#!/bin/bash
[ "$script_type" ] || exit 0
split_into_parts() { part1="$1"; part2="$2"; part3="$3"; }
case "$script_type" in
  up|down) split_into_parts $* ;;
  *) exit 0 ;;
esac
[ -x /sbin/resolvconf ] || exit 0
case "$script_type" in
    up)
        for optionname in ${!foreign_option_*} ; do
            option="${!optionname}"
            split_into_parts $option
            if [ "$part1" = "dhcp-option" ] ; then
                if [ "$part2" = "DNS" ] ; then
                    echo "nameserver $part3" | /sbin/resolvconf -a "${dev}.openvpn"
                fi
            fi
        done
        ;;
    down)
        /sbin/resolvconf -d "${dev}.openvpn"
        ;;
esac
EOF
chmod +x /etc/openvpn/update-resolv-conf

cat > /etc/openvpn/client.conf << 'EOF'
client
dev tun
proto udp
resolv-retry infinite
nobind
persist-key
persist-tun
remote-cert-tls server
cipher AES-256-GCM
auth SHA256
key-direction 1
verb 3
script-security 2
up /etc/openvpn/update-resolv-conf
down /etc/openvpn/update-resolv-conf
EOF
chmod 644 /etc/openvpn/client.conf
systemctl daemon-reload
systemctl enable openvpn@client

# Permisos de la app
chown -R www-data:www-data /opt/hostberry

# --- Información de Acceso y Estado ---
echo -e "\n\033[1;34m--- Información de Acceso y Estado ---\033[0m"

# Intentar detectar la IP local principal
# Usamos hostname -I para obtener todas las IPs y awk para tomar la primera.
# Puedes cambiar 'eth0' o 'wlan0' si necesitas una interfaz específica.
INTERFACE_PRIORITY_LIST=("eth0" "wlan0" "enp0s3" "enp0s8") # Añade más interfaces si es necesario
LOCAL_IP=""

for iface in "${INTERFACE_PRIORITY_LIST[@]}"; do
    ip_addr=$(ip -4 addr show "$iface" 2>/dev/null | grep -oP 'inet \K[\d.]+' || true)
    if [ -n "$ip_addr" ]; then
        LOCAL_IP=$ip_addr
        break
    fi
done

if [ -z "$LOCAL_IP" ]; then
    # Fallback si no se encuentra IP en interfaces prioritarias
    LOCAL_IP=$( (hostname -I | awk '{print $1}') || true)
fi

if [ -n "$LOCAL_IP" ]; then
    echo "La IP local detectada es: \033[1;33m$LOCAL_IP\033[0m"
    ACCESS_URL_SUGGESTION="Accede a la interfaz web en http://$LOCAL_IP:<PUERTO_GUNICORN_FLASK>"
else
    echo "\033[1;31mNo se pudo detectar automáticamente la IP local.\033[0m Verifica tu configuración de red."
    ACCESS_URL_SUGGESTION="Accede a la interfaz web en la IP de tu servidor y el puerto configurado por Flask/Gunicorn."
fi

# Comprobar el estado del servicio web
SERVICE_NAME="hostberry-web.service"
echo -n "Comprobando estado del servicio '$SERVICE_NAME': "
if systemctl list-units --full -all | grep -q "$SERVICE_NAME"; then
    SERVICE_STATUS=$(systemctl is-active "$SERVICE_NAME" 2>/dev/null)
    if [ "$SERVICE_STATUS" = "active" ]; then
        echo -e "\033[1;32mActivo\033[0m"
        echo "Gunicorn/Flask debería estar ejecutándose a través de este servicio."
        echo "Verifica la configuración de '$SERVICE_NAME' o de tu aplicación para el PUERTO exacto."
        echo "Puedes intentar ver los logs con: journalctl -u $SERVICE_NAME -n 50 --no-pager"
    elif [ "$SERVICE_STATUS" = "inactive" ]; then
        echo -e "\033[1;31mInactivo\033[0m. Puedes intentar iniciarlo con: sudo systemctl start $SERVICE_NAME"
    elif [ "$SERVICE_STATUS" = "failed" ]; then
        echo -e "\033[1;31mFallido\033[0m. Revisa los logs con: sudo journalctl -u $SERVICE_NAME"
    else
        echo -e "\033[1;33mEstado desconocido ($SERVICE_STATUS)\033[0m. Revisa con: sudo systemctl status $SERVICE_NAME"
    fi
else
    echo -e "\033[1;33mServicio '$SERVICE_NAME' no encontrado o no cargado.\033[0m"
    echo "Esto puede ser normal si el script de servicio aún no se ha copiado o habilitado."
fi

echo "Para comprobar procesos específicos de gunicorn o flask manualmente:"
echo "  ps aux | grep -E 'gunicorn|flask'"
echo "  pgrep -afl gunicorn"
echo "  pgrep -afl flask"
echo "Para verificar puertos en escucha (ej. si tu app usa el puerto 8000 o 5000):"
echo "  sudo ss -tulnp | grep -E ':8000|:5000'"
echo -e "\033[1;34m-------------------------------------\033[0m"

# Mensaje final
echo -e "\n\033[1;32mInstalación completada correctamente.\033[0m"
echo "La aplicación Hostberry está instalada en /opt/hostberry."
echo "El servicio systemd asociado es '$SERVICE_NAME'."
echo -e "$ACCESS_URL_SUGGESTION"
echo "Recuerda reemplazar <PUERTO_GUNICORN_FLASK> con el puerto real que tu aplicación esté usando (e.g., 8000, 5000)."
echo "Si necesitas configurar OpenVPN, edita /etc/openvpn/client.conf y reinicia el servicio correspondiente."
echo -e "\nSi tienes dudas, consulta el README del proyecto o los logs del servicio.\n"