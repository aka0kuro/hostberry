#!/bin/bash

# Verificar si se está ejecutando como root
if [ "$EUID" -ne 0 ]; then 
    echo "Por favor, ejecuta este script como root (sudo)"
    exit 1
fi

# Función para manejar errores
handle_error() {
    echo "Error: $1"
    exit 1
}

# Actualizar repositorios e instalar dependencias
echo "Actualizando repositorios e instalando dependencias..."
apt-get update || handle_error "Error al actualizar repositorios"
apt-get install -y python3-pip python3-venv openvpn resolvconf || handle_error "Error al instalar dependencias"

# Crear directorio de la aplicación si no existe
echo "Configurando directorio de la aplicación..."
mkdir -p /opt/hostberry || handle_error "Error al crear directorio de la aplicación"

# Crear entorno virtual en la ubicación correcta
echo "Creando entorno virtual..."
python3 -m venv /opt/hostberry/venv || handle_error "Error al crear entorno virtual"
source /opt/hostberry/venv/bin/activate

# Actualizar pip
echo "Actualizando pip..."
pip install --upgrade pip || handle_error "Error al actualizar pip"

# Instalar dependencias de Python desde requirements.txt
echo "Instalando dependencias de Python..."
if [ -f "requirements.txt" ]; then
    pip install -r requirements.txt || handle_error "Error al instalar dependencias Python"
else
    handle_error "No se encontró el archivo requirements.txt"
fi

# Verificar instalación de dependencias
echo "Verificando instalación de dependencias..."
python3 -c "import flask; import dotenv" || handle_error "Error: Algunas dependencias no se instalaron correctamente"

# Configurar OpenVPN
echo "Configurando OpenVPN..."

# Detener el servicio OpenVPN si está corriendo
systemctl stop openvpn@client 2>/dev/null
systemctl stop openvpn 2>/dev/null

# Crear grupo openvpn y añadir www-data
echo "Configurando grupo y permisos para OpenVPN..."
groupadd -f openvpn || handle_error "Error al crear grupo openvpn"
usermod -aG openvpn www-data || handle_error "Error al añadir www-data al grupo openvpn"

# Crear directorios necesarios
mkdir -p /etc/openvpn/client || handle_error "Error al crear directorio client"
mkdir -p /etc/openvpn/auth || handle_error "Error al crear directorio auth"

# Establecer permisos de directorios
chown -R root:openvpn /etc/openvpn || handle_error "Error al establecer propietario de /etc/openvpn"
chmod -R 775 /etc/openvpn || handle_error "Error al establecer permisos de /etc/openvpn"
chmod 700 /etc/openvpn/auth || handle_error "Error al establecer permisos de auth"

# Crear script de actualización de DNS
echo "Configurando script de actualización de DNS..."
cat > /etc/openvpn/update-resolv-conf << 'EOF'
#!/bin/bash
# Script para actualizar resolv.conf cuando OpenVPN cambia el estado de la conexión

[ "$script_type" ] || exit 0

split_into_parts() {
    part1="$1"
    part2="$2"
    part3="$3"
}

case "$script_type" in
  up|down)
    split_into_parts $*
    ;;
  *)
    exit 0
    ;;
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

# Establecer permisos del script
chmod +x /etc/openvpn/update-resolv-conf || handle_error "Error al establecer permisos del script update-resolv-conf"

# Crear archivo de configuración base
echo "Creando archivo de configuración base..."
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

# Establecer permisos del archivo de configuración
chmod 644 /etc/openvpn/client.conf || handle_error "Error al establecer permisos del archivo de configuración"

# Habilitar y configurar el servicio OpenVPN
echo "Configurando servicio OpenVPN..."
systemctl daemon-reload || handle_error "Error al recargar systemd"
systemctl enable openvpn@client || handle_error "Error al habilitar servicio OpenVPN"

# Crear directorio para logs
mkdir -p /var/log/hostberry
chown -R www-data:www-data /var/log/hostberry

# Establecer permisos del directorio de la aplicación
chown -R www-data:www-data /opt/hostberry || handle_error "Error al establecer permisos de la aplicación"

# Reiniciar servicio
echo "Reiniciando servicio..."
systemctl restart hostberry || handle_error "Error al reiniciar HostBerry"

# Verificar estado de OpenVPN
echo "Verificando estado de OpenVPN..."
if ! systemctl is-active --quiet openvpn@client; then
    echo "Advertencia: El servicio OpenVPN no está activo. Esto es normal si no hay configuración de cliente."
fi

echo "Instalación completada. Por favor, reinicia el sistema para aplicar todos los cambios."
echo "Después de reiniciar, podrás configurar tu VPN desde la interfaz web."
