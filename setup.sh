#!/bin/bash

set -e

# Funciones de utilidad
handle_error() {
    echo "Error: $1"
    exit 1
}

# Función de ayuda para mostrar información de uso
show_help() {
    echo "Uso: $0 [OPCIONES]"
    echo ""
    echo "Opciones:"
    echo "  --help         Mostrar esta ayuda y salir"
    echo "  --update       Actualizar la instalación de HostBerry"
    echo "  --cert         Generar certificados SSL con mkcert"
    echo "  --network      Configurar firewall y red para Raspberry Pi"
    echo ""
    echo "Ejemplos:"
    echo "  sudo ./setup.sh                   Instalación inicial"
    echo "  sudo ./setup.sh --update          Actualizar HostBerry"
    echo "  sudo ./setup.sh --cert            Generar certificados SSL"
    echo "  sudo ./setup.sh --network         Configurar red y firewall"
    echo "  sudo ./setup.sh --update --cert   Actualizar e instalar certificados"
    echo ""
    echo "Para más información, consulta la documentación de HostBerry."
    exit 0
}

# Variables para certificados SSL
SSL_DIR="/etc/hostberry/ssl"
SSL_HOSTNAME="hostberry.local"

# Función para generar certificados con mkcert
generate_ssl_cert() {
    # Verificar permisos de root
    if [ "$EUID" -ne 0 ]; then
        echo "Error: Este comando debe ejecutarse como root (sudo)"
        exit 1
    fi

    # Crear directorio SSL si no existe
    mkdir -p "$SSL_DIR" || handle_error "No se pudo crear el directorio $SSL_DIR"
    
    # Instalar dependencias necesarias
    apt-get update || handle_error "No se pudo actualizar apt-get"
    apt-get install -y wget libnss3-tools || handle_error "No se pudieron instalar dependencias"
    
    # Instalar mkcert si no está instalado
    if ! command -v mkcert &> /dev/null; then
        echo "Instalando mkcert..."
        wget -q https://github.com/FiloSottile/mkcert/releases/download/v1.4.4/mkcert-v1.4.4-linux-amd64 -O /usr/local/bin/mkcert || handle_error "Descarga de mkcert fallida"
        chmod +x /usr/local/bin/mkcert || handle_error "No se pudo dar permiso de ejecución a mkcert"
        
        # Instalar mkcert para el usuario actual y root
        mkcert -install || handle_error "Instalación de mkcert fallida"
    fi
    
    # Generar certificado
    cd "$SSL_DIR" || handle_error "No se pudo cambiar al directorio $SSL_DIR"
    mkcert -cert-file hostberry.crt -key-file hostberry.key "$SSL_HOSTNAME" "*.$(hostname -d)" localhost 127.0.0.1 ::1 || handle_error "Generación de certificados fallida"
    
    # Mostrar información del certificado
    echo "Certificados generados en $SSL_DIR:"
    ls -l hostberry.{crt,key}
    
    # Establecer permisos seguros
    chmod 600 hostberry.key || handle_error "No se pudieron establecer permisos seguros"
    
    echo "Generación de certificados SSL completada."
}

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

# Verificar argumentos
for arg in "$@"; do
    case "$arg" in
        --help)
            show_help
            exit 0
            ;;
    esac
done

# Verificar si se está ejecutando como root
if [ "$EUID" -ne 0 ]; then
    echo "Por favor, ejecuta este script como root (sudo)"
    exit 1
fi

# Dependencias de sistema
DEPS=(python3 python3-pip python3-venv openvpn resolvconf git curl dnsmasq hostapd iptables nftables libnss3-tools ufw)

# Instalar dependencias
apt-get update || handle_error "No se pudo actualizar apt-get"
apt-get install -y "${DEPS[@]}" || handle_error "No se pudieron instalar las dependencias del sistema"

# Modo de actualización y certificados
UPDATE_MODE=false
GENERATE_CERT=false
NETWORK_CONFIG=false

# Parsear argumentos
while [[ "$#" -gt 0 ]]; do
    case "$1" in
        --help) show_help ;;
        --update) UPDATE_MODE=true ;;
        --cert) GENERATE_CERT=true ;;
        --network) NETWORK_CONFIG=true ;;
        *) echo "Opción no reconocida: $1"; show_help ;;
    esac
    shift
done

# Mostrar ayuda si no se proporcionan argumentos
if [ $# -eq 0 ]; then
    show_help
fi

# Generar certificados SSL si se solicita
if [ "$GENERATE_CERT" = true ]; then
    generate_ssl_cert
fi

# Configurar red si se solicita
if [ "$NETWORK_CONFIG" = true ]; then
    configure_network_and_firewall
fi

# Modo de actualización
if [ "$UPDATE_MODE" = true ]; then
    echo "Actualizando dependencias y configuración..."
    
    # Actualizar dependencias del sistema
    apt-get update
    apt-get upgrade -y
    apt-get install -y "${DEPS[@]}"
    
    # Recrear entorno virtual
    if [ -d venv ]; then
        rm -rf venv
    fi
    
    # Crear nuevo entorno virtual
    python3 -m venv venv || handle_error "No se pudo crear el entorno virtual"
    
    # Activar entorno virtual e instalar dependencias
    source venv/bin/activate
    pip install --upgrade pip
    pip install --upgrade -r requirements.txt || handle_error "No se pudieron actualizar las dependencias de Python"
    
    # Actualizar permisos de scripts
    chmod +x scripts/*.sh
    
    # Actualizar servicio systemd
    cp hostberry-web.service /etc/systemd/system/ || handle_error "No se pudo actualizar el archivo de servicio"
    systemctl daemon-reload
    systemctl enable hostberry-web.service
    
    echo "Actualización completada."
fi

# Modo de instalación: eliminar instalación previa
if [ "$UPDATE_MODE" = false ]; then
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

# Clonar el repositorio
cd /opt

if [ "$UPDATE_MODE" = true ]; then
    # En modo de actualización, hacer pull en lugar de clonar
    cd /opt/hostberry
    git fetch origin
    git reset --hard origin/main
    git clean -fdx
else
    # En modo de instalación, clonar normalmente
    git clone https://github.com/aka0kuro/hostberry.git hostberry || handle_error "No se pudo clonar el repositorio"
    cd /opt/hostberry
fi

# Generar certificados si se solicita
if [ "$GENERATE_CERT" = true ]; then
    generate_ssl_cert
fi

# Configurar red y firewall si se solicita
if [ "$NETWORK_CONFIG" = true ]; then
    configure_network_and_firewall
fi

# Dar permisos de ejecución al script de adblock
chmod +x scripts/adblock.sh || handle_error "No se pudo dar permisos de ejecución a scripts/adblock.sh"

# Proceso de actualización o instalación
if [ "$UPDATE_MODE" = true ]; then
    echo "Actualizando dependencias y configuración..."
    
    # Actualizar dependencias del sistema
    apt-get update
    apt-get upgrade -y
    apt-get install -y "${DEPS[@]}"
    
    # Recrear entorno virtual
    if [ -d venv ]; then
        rm -rf venv
    fi
    
    # Crear nuevo entorno virtual
    python3 -m venv venv || handle_error "No se pudo crear el entorno virtual"
    
    # Activar entorno virtual e instalar dependencias
    source venv/bin/activate
    pip install --upgrade pip
    pip install --upgrade -r requirements.txt || handle_error "No se pudieron actualizar las dependencias de Python"
    
    # Actualizar permisos de scripts
    chmod +x scripts/*.sh
    
    # Actualizar servicio systemd
    cp hostberry-web.service /etc/systemd/system/ || handle_error "No se pudo actualizar el archivo de servicio"
    systemctl daemon-reload
    systemctl enable hostberry-web.service
    
    # Reiniciar servicio
    systemctl restart hostberry-web.service || handle_error "No se pudo reiniciar el servicio"
    
    echo "Actualización de HostBerry completada."
else
    # Proceso de instalación inicial
    python3 -m venv venv || handle_error "No se pudo crear el entorno virtual"
    
    # Activar entorno virtual e instalar dependencias
    source venv/bin/activate
    pip install --upgrade pip
    pip install -r requirements.txt || handle_error "No se pudieron instalar las dependencias de Python"
    
    # Configurar servicio systemd
    cp hostberry-web.service /etc/systemd/system/ || handle_error "No se pudo copiar el archivo de servicio"
    systemctl daemon-reload
    systemctl enable hostberry-web.service
    systemctl start hostberry-web.service || handle_error "No se pudo iniciar el servicio"
    
    echo "Instalación de HostBerry completada."
fi

# Limpiar archivos temporales y backups antiguos
find /opt/hostberry_backups/ -type d -mtime +30 -exec rm -rf {} + 2>/dev/null
