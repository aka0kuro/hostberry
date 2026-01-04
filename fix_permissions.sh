#!/bin/bash
# Script para corregir permisos y solucionar el error 502
# Ejecutar en el servidor: ssh hostberry@192.168.1.148

echo "=========================================="
echo "Corrigiendo permisos - HostBerry"
echo "=========================================="
echo ""

# Colores
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Verificar que se ejecute como root o con sudo
if [ "$EUID" -ne 0 ]; then 
    echo -e "${YELLOW}Ejecutando con sudo...${NC}"
    exec sudo bash "$0" "$@"
fi

# Directorios a crear/corregir
DIRS=(
    "/var/lib/hostberry"
    "/var/lib/hostberry/uploads"
    "/var/lib/hostberry/instance"
    "/var/log/hostberry"
)

# Usuario y grupo del servicio
USER="hostberry"
GROUP="hostberry"

echo -e "${YELLOW}[1] Creando directorios necesarios...${NC}"
for dir in "${DIRS[@]}"; do
    if [ ! -d "$dir" ]; then
        mkdir -p "$dir"
        echo -e "${GREEN}✓ Creado: $dir${NC}"
    else
        echo -e "${GREEN}✓ Ya existe: $dir${NC}"
    fi
done
echo ""

echo -e "${YELLOW}[2] Corrigiendo permisos...${NC}"
for dir in "${DIRS[@]}"; do
    if [ -d "$dir" ]; then
        chown -R "$USER:$GROUP" "$dir"
        chmod 755 "$dir"
        echo -e "${GREEN}✓ Permisos corregidos: $dir${NC}"
    fi
done
echo ""

echo -e "${YELLOW}[3] Creando archivos de log si no existen...${NC}"
LOG_FILES=(
    "/var/log/hostberry/access.log"
    "/var/log/hostberry/error.log"
    "/var/log/hostberry/app.log"
    "/var/log/hostberry/hostberry.log"
)

for log_file in "${LOG_FILES[@]}"; do
    if [ ! -f "$log_file" ]; then
        touch "$log_file"
        chown "$USER:$GROUP" "$log_file"
        chmod 644 "$log_file"
        echo -e "${GREEN}✓ Creado: $log_file${NC}"
    fi
done
echo ""

echo -e "${YELLOW}[4] Verificando base de datos...${NC}"
DB_FILE="/var/lib/hostberry/hostberry.db"
if [ ! -f "$DB_FILE" ]; then
    touch "$DB_FILE"
    chown "$USER:$GROUP" "$DB_FILE"
    chmod 640 "$DB_FILE"
    echo -e "${GREEN}✓ Creado: $DB_FILE${NC}"
else
    chown "$USER:$GROUP" "$DB_FILE"
    chmod 640 "$DB_FILE"
    echo -e "${GREEN}✓ Permisos corregidos: $DB_FILE${NC}"
fi
echo ""

echo -e "${YELLOW}[5] Reiniciando servicio...${NC}"
systemctl restart hostberry.service
sleep 3

if systemctl is-active --quiet hostberry.service; then
    echo -e "${GREEN}✓ Servicio reiniciado correctamente${NC}"
else
    echo -e "${RED}✗ Error al reiniciar el servicio${NC}"
    echo "Ver logs: journalctl -u hostberry.service -n 50"
fi
echo ""

echo -e "${YELLOW}[6] Verificando estado...${NC}"
systemctl status hostberry.service --no-pager -l | head -15
echo ""

echo "=========================================="
echo -e "${GREEN}¡Permisos corregidos!${NC}"
echo "=========================================="
echo ""
echo "Verifica que el servicio esté corriendo:"
echo "  sudo systemctl status hostberry.service"
echo ""
echo "Verifica que el puerto esté en uso:"
echo "  netstat -tuln | grep 8000"
echo ""
echo "Prueba el backend:"
echo "  curl http://127.0.0.1:8000/health"
echo ""

