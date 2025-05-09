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

# Mensaje final
echo "\n\033[1;32mInstalación completada correctamente.\033[0m"
echo "La aplicación Hostberry está instalada en /opt/hostberry y el servicio systemd está configurado como hostberry-web.service."
echo "Accede a la interfaz web en el puerto configurado por Flask/Gunicorn."
echo "Si necesitas configurar OpenVPN, edita /etc/openvpn/client.conf y reinicia el servicio correspondiente."
echo "\nSi tienes dudas, consulta el README del proyecto.\n"
