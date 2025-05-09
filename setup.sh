#!/bin/bash

# Colores para logs
ANSI_GREEN='\033[0;32m'
ANSI_YELLOW='\033[0;33m'
ANSI_RED='\033[0;31m'
ANSI_RESET='\033[0m'

# Variables globales
SSL_DIR="/etc/hostberry/ssl"
SSL_HOSTNAME="hostberry.local"
VENV_DIR="venv"
REQUIREMENTS="requirements.txt"
SYSTEMD_SERVICE="hostberry-web.service"

# Dependencias del sistema
DEPS=(python3 python3-pip python3-venv openvpn resolvconf git curl dnsmasq hostapd iptables nftables libnss3-tools ufw openssl wget)

# Función para loguear mensajes
log() {
    local color="$1"; shift
    echo -e "${color}$*${ANSI_RESET}"
}

# Manejo centralizado de errores
handle_error() {
    log "$ANSI_RED" "[ERROR] $*" >&2
    exit 1
}

# Mostrar resumen de acciones
show_summary() {
    log "$ANSI_GREEN" "[INFO] Resumen de acciones"
    echo "[RESUMEN] Acciones solicitadas:"
    [ "$UPDATE_MODE" = true ] && echo "  - Actualización de HostBerry"
    [ "$GENERATE_CERT" = true ] && echo "  - Generar certificados SSL"
    [ "$CONFIGURE_NETWORK" = true ] && echo "  - Configurar red y firewall"
    echo
}

# Procesar argumentos y ejecutar acciones
main() {
    UPDATE_MODE=false
    GENERATE_CERT=false
    CONFIGURE_NETWORK=false
    SHOW_HELP=false

    for arg in "$@"; do
        case $arg in
            --update)
                UPDATE_MODE=true
                ;;
            --cert)
                GENERATE_CERT=true
                ;;
            --network)
                CONFIGURE_NETWORK=true
                ;;
            -h|--help)
                SHOW_HELP=true
                ;;
            *)
                ;;
        esac
    done

    if [ "$SHOW_HELP" = true ] || [ $# -eq 0 ]; then
        show_help
    fi

    show_summary
    check_root

    if [ "$UPDATE_MODE" = true ]; then
        update_hostberry
        exit 0
    fi
    if [ "$GENERATE_CERT" = true ]; then
        generate_ssl_cert
        exit 0
    fi
    if [ "$CONFIGURE_NETWORK" = true ]; then
        configure_network
        exit 0
    fi
    # Si no se pasa ningún argumento relevante, mostrar ayuda
    show_help
}

main "$@"

# Configurar red y firewall
configure_network() {
    log "$ANSI_GREEN" "Configurando red y firewall..."
    # Instalar UFW si no está
    apt-get install -y ufw || handle_error "No se pudo instalar UFW"
    # Permitir puertos esenciales
    ufw allow 22/tcp   # SSH
    ufw allow 80/tcp   # HTTP
    ufw allow 443/tcp  # HTTPS
    # Habilitar reenvío de IP
    sed -i 's/^#net.ipv4.ip_forward=1/net.ipv4.ip_forward=1/' /etc/sysctl.conf
    sysctl -p
    # Configurar NAT para compartir Internet
    IFACE=$(ip route | grep default | awk '{print $5}' | head -n1)
    iptables -t nat -A POSTROUTING -o "$IFACE" -j MASQUERADE
    # Guardar reglas
    iptables-save > /etc/iptables/rules.v4
    # Habilitar UFW
    ufw --force enable
    log "$ANSI_GREEN" "Red y firewall configurados correctamente."
}

# Comprobar si el script se ejecuta como root
check_root() {
    if [[ $EUID -ne 0 ]]; then
        handle_error "Este script debe ejecutarse como root (sudo)"
    fi
}

# Mostrar ayuda
show_help() {
    echo "Uso: ./setup.sh [OPCIONES]"
    echo
    echo "Opciones:"
    echo "  --help         Mostrar esta ayuda y salir"
    echo "  --update       Actualizar la instalación de HostBerry"
    echo "  --cert         Generar certificados SSL con mkcert"
    echo "  --network      Configurar firewall y red para Raspberry Pi"
    echo
    echo "Ejemplos:"
    echo "  sudo ./setup.sh                   Instalación inicial"
    echo "  sudo ./setup.sh --update          Actualizar HostBerry"
    echo "  sudo ./setup.sh --cert            Generar certificados SSL"
    echo "  sudo ./setup.sh --network         Configurar red y firewall"
    echo "  sudo ./setup.sh --update --cert   Actualizar e instalar certificados"
    echo
    echo "Para más información, consulta la documentación de HostBerry."
    exit 0
}

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

# Comprobar e instalar dependencias
check_and_install_deps() {
    log "$ANSI_YELLOW" "Comprobando dependencias del sistema..."
    apt-get update
    apt-get install -y "${DEPS[@]}" || handle_error "No se pudieron instalar las dependencias del sistema"
}

# Crear o recrear entorno virtual
setup_venv() {
    if [ -d "$VENV_DIR" ]; then
        log "$ANSI_YELLOW" "Eliminando entorno virtual anterior..."
        rm -rf "$VENV_DIR"
    fi
    log "$ANSI_YELLOW" "Creando entorno virtual..."
    python3 -m venv "$VENV_DIR" || handle_error "No se pudo crear el entorno virtual"
    source "$VENV_DIR/bin/activate"
    pip install --upgrade pip
    pip install --upgrade -r "$REQUIREMENTS" || handle_error "No se pudieron instalar las dependencias de Python"
}

# Función para generar certificados SSL
generate_ssl_cert() {
    local ANSI_GREEN='\033[0;32m'
    local ANSI_YELLOW='\033[0;33m'
    local ANSI_RESET='\033[0m'

    # Verificar si ya está instalado mkcert
    if ! command -v mkcert &> /dev/null; then
        echo -e "${ANSI_YELLOW}Instalando mkcert...${ANSI_RESET}"
        
        # Instalar dependencias
        apt-get update
        apt-get install -y wget libnss3-tools

        # Descargar mkcert para Raspberry Pi 64-bit
        wget https://github.com/FiloSottile/mkcert/releases/download/v1.4.4/mkcert-v1.4.4-linux-arm64 -O /usr/local/bin/mkcert
        chmod +x /usr/local/bin/mkcert
    fi

    # Directorio para certificados
    local SSL_DIR="/etc/hostberry/ssl"
    mkdir -p "$SSL_DIR"

    # Instalar mkcert para el sistema
    mkcert -install

    # Generar certificados
    cd "$SSL_DIR"
    
    # Obtener nombres de host
    local HOSTNAME=$(hostname)
    local DOMAIN=$(hostname -d || echo "local")

    echo -e "${ANSI_GREEN}Generando certificados para:${ANSI_RESET}"
    echo "  * hostberry.local"
    echo "  * $HOSTNAME"
    echo "  * localhost"
    echo "  * 127.0.0.1"

    # Generar certificados
    mkcert -cert-file hostberry.crt -key-file hostberry.key \
        hostberry.local \
        "$HOSTNAME" \
        "*.$(hostname -d)" \
        localhost \
        127.0.0.1

    # Verificar certificados
    if [ ! -f hostberry.crt ] || [ ! -f hostberry.key ]; then
        echo -e "${ANSI_YELLOW}Error: No se generaron los certificados${ANSI_RESET}"
        return 1
    fi

    # Establecer permisos
    chmod 600 hostberry.key
    chmod 644 hostberry.crt

    # Mostrar detalles del certificado
    echo -e "${ANSI_GREEN}Detalles del certificado:${ANSI_RESET}"
    openssl x509 -in hostberry.crt -text -noout | grep -E 'Subject:|Not Before:|Not After :'

    echo -e "${ANSI_GREEN}Certificados SSL generados exitosamente en $SSL_DIR${ANSI_RESET}"
    return 0
    openssl x509 -in hostberry.crt -text -noout | grep -E 'Subject:|Not Before:|Not After :' | sed 's/^/      /'
    
    # Verificar la clave privada
    if ! openssl rsa -check -in hostberry.key > /dev/null 2>&1; then
        handle_error "La clave privada no es válida"
    fi
    
    # Verificar que la clave coincide con el certificado
    CERT_HASH=$(openssl x509 -noout -modulus -in hostberry.crt | openssl md5)
    KEY_HASH=$(openssl rsa -noout -modulus -in hostberry.key | openssl md5)
    
    if [ "$CERT_HASH" != "$KEY_HASH" ]; then
        handle_error "La clave privada no coincide con el certificado"
    fi
    
    echo "    * Clave privada: Verificada"
    echo "    * Certificado: Válido"
    
    # Copiar certificados a un directorio de configuración si es necesario
    mkdir -p /etc/hostberry/ssl
    cp hostberry.{crt,key} /etc/hostberry/ssl/ || handle_error "No se pudieron copiar los certificados"
    
    echo "[ÉXITO] Generación y verificación de certificados SSL completada."
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
DEPS=(python3 python3-pip python3-venv openvpn resolvconf git curl dnsmasq hostapd iptables nftables libnss3-tools ufw openssl)

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
        --update) 
            UPDATE_MODE=true
            echo "[INFO] Modo de actualización activado" ;;
        --cert) 
            GENERATE_CERT=true
            echo "[INFO] Generación de certificados SSL activada" ;;
        --network) 
            NETWORK_CONFIG=true
            echo "[INFO] Configuración de red activada" ;;
        *) echo "Opción no reconocida: $1"; show_help ;;
    esac
    shift
done

# Mostrar resumen de acciones
echo "[RESUMEN] Acciones solicitadas:"
[ "$UPDATE_MODE" = true ] && echo "  - Actualización de HostBerry"
[ "$GENERATE_CERT" = true ] && echo "  - Generación de certificados SSL"
[ "$NETWORK_CONFIG" = true ] && echo "  - Configuración de red y firewall"

# Mostrar ayuda si no se proporcionan argumentos
if [ $# -eq 0 ]; then
    show_help
fi

# Proceso de actualización y generación de certificados

# Generar certificados SSL si se solicita
if [ "$GENERATE_CERT" = true ]; then
    echo "[INICIO] Generación de certificados SSL"
    generate_ssl_cert
    echo "[FIN] Generación de certificados SSL completada"
fi

# Configurar red si se solicita
if [ "$NETWORK_CONFIG" = true ]; then
    echo "[INICIO] Configuración de red y firewall"
    configure_network_and_firewall
    echo "[FIN] Configuración de red y firewall completada"
fi

# Modo de actualización
if [ "$UPDATE_MODE" = true ]; then
    echo "[INICIO] Actualización de HostBerry"
    
    # Actualizar dependencias del sistema
    echo "  - Actualizando dependencias del sistema..."
    apt-get update || handle_error "No se pudo actualizar apt-get"
    apt-get upgrade -y || handle_error "Fallo en la actualización del sistema"
    apt-get install -y "${DEPS[@]}" || handle_error "No se pudieron instalar las dependencias"
    
    # Recrear entorno virtual
    echo "  - Recreando entorno virtual..."
    if [ -d venv ]; then
        rm -rf venv
    fi
    
    # Crear nuevo entorno virtual
    python3 -m venv venv || handle_error "No se pudo crear el entorno virtual"
    
    # Activar entorno virtual e instalar dependencias
    source venv/bin/activate
    pip install --upgrade pip || handle_error "No se pudo actualizar pip"
    pip install --upgrade -r requirements.txt || handle_error "No se pudieron actualizar las dependencias de Python"
    
    # Actualizar permisos de scripts
    echo "  - Actualizando permisos de scripts..."
    chmod +x scripts/*.sh
    
    # Actualizar servicio systemd
    echo "  - Actualizando servicio systemd..."
    cp hostberry-web.service /etc/systemd/system/ || handle_error "No se pudo actualizar el archivo de servicio"
    systemctl daemon-reload
    systemctl enable hostberry-web.service
    
    echo "[FIN] Actualización de HostBerry completada."
fi

# Verificar si se realizó alguna acción
if [ "$GENERATE_CERT" = false ] && [ "$UPDATE_MODE" = false ] && [ "$NETWORK_CONFIG" = false ]; then
    echo "[ADVERTENCIA] No se realizó ninguna acción. Use --help para ver las opciones disponibles."
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
update_hostberry() {
    log "$ANSI_GREEN" "Actualizando dependencias y configuración..."
    apt-get update
    apt-get upgrade -y
    check_and_install_deps
    setup_venv
    chmod +x scripts/*.sh
    cp "$SYSTEMD_SERVICE" /etc/systemd/system/ || handle_error "No se pudo actualizar el archivo de servicio"
    systemctl daemon-reload
    systemctl enable hostberry-web.service
    if [ "$GENERATE_CERT" = true ]; then
        log "$ANSI_YELLOW" "Generando nuevos certificados SSL..."
        generate_ssl_cert
    fi
    systemctl restart hostberry-web.service || handle_error "No se pudo reiniciar el servicio"
    log "$ANSI_GREEN" "Actualización de HostBerry completada."
}

if [ "$UPDATE_MODE" = true ]; then
    update_hostberry
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
