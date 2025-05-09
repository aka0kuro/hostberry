#!/bin/bash

# --- Script de instalación robusto para Hostberry ---
# Este script instala todas las dependencias, clona el repositorio y configura la app en /opt/hostberry

set -e

# Verificar si se está ejecutando como root
if [ "$EUID" -ne 0 ]; then
    echo "Por favor, ejecuta este script como root (sudo)"
    exit 1
fi

handle_error() {
    echo "Error: $1"
    exit 1
}

# Dependencias de sistema
DEPS=(python3 python3-pip python3-venv openvpn resolvconf git curl dnsmasq hostapd iptables nftables)

# Instalar dependencias
apt-get update || handle_error "No se pudo actualizar apt-get"
apt-get install -y "${DEPS[@]}" || handle_error "No se pudieron instalar las dependencias del sistema"

# Eliminar instalación previa si existe
if [ -d /opt/hostberry ]; then
    echo "Eliminando instalación previa en /opt/hostberry..."
    systemctl stop hostberry-web.service 2>/dev/null || true
    rm -rf /opt/hostberry
fi

# Clonar el repositorio
cd /opt

git clone https://github.com/aka0kuro/hostberry.git hostberry || handle_error "No se pudo clonar el repositorio"
cd /opt/hostberry

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