#!/bin/bash
# Script para verificar que el fix del 502 funcionó
# Ejecutar en el servidor

echo "=========================================="
echo "Verificación final - HostBerry"
echo "=========================================="
echo ""

# Colores
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 1. Verificar servicio
echo -e "${YELLOW}[1] Estado del servicio...${NC}"
if systemctl is-active --quiet hostberry.service; then
    echo -e "${GREEN}✓ Servicio está activo${NC}"
else
    echo -e "${RED}✗ Servicio NO está activo${NC}"
    exit 1
fi
echo ""

# 2. Verificar puerto
echo -e "${YELLOW}[2] Verificando puerto 8000...${NC}"
if netstat -tuln 2>/dev/null | grep -q ":8000 " || ss -tuln 2>/dev/null | grep -q ":8000 "; then
    echo -e "${GREEN}✓ Puerto 8000 está en uso${NC}"
    netstat -tuln 2>/dev/null | grep ":8000 " || ss -tuln 2>/dev/null | grep ":8000 "
else
    echo -e "${RED}✗ Puerto 8000 NO está en uso${NC}"
    exit 1
fi
echo ""

# 3. Probar endpoint de health
echo -e "${YELLOW}[3] Probando endpoint /health...${NC}"
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" --max-time 5 http://127.0.0.1:8000/health 2>/dev/null)
if [ "$HTTP_CODE" = "200" ]; then
    echo -e "${GREEN}✓ Backend responde correctamente (HTTP $HTTP_CODE)${NC}"
    echo "Respuesta:"
    curl -s --max-time 5 http://127.0.0.1:8000/health | head -5
else
    echo -e "${RED}✗ Backend NO responde correctamente (HTTP $HTTP_CODE)${NC}"
    exit 1
fi
echo ""

# 4. Verificar logs recientes
echo -e "${YELLOW}[4] Verificando logs recientes (sin errores)...${NC}"
ERRORS=$(journalctl -u hostberry.service -n 20 --no-pager 2>/dev/null | grep -i "error\|exception\|traceback" | wc -l)
if [ "$ERRORS" -eq 0 ]; then
    echo -e "${GREEN}✓ No hay errores en los logs recientes${NC}"
else
    echo -e "${YELLOW}⚠ Se encontraron $ERRORS posibles errores en los logs${NC}"
    echo "Últimas líneas:"
    journalctl -u hostberry.service -n 10 --no-pager | tail -5
fi
echo ""

# 5. Verificar Nginx puede conectar
echo -e "${YELLOW}[5] Verificando que Nginx pueda conectar...${NC}"
if systemctl is-active --quiet nginx; then
    echo -e "${GREEN}✓ Nginx está activo${NC}"
    # Probar desde Nginx (simular)
    if curl -s -o /dev/null -w "%{http_code}" --max-time 5 http://127.0.0.1:8000/health > /dev/null 2>&1; then
        echo -e "${GREEN}✓ Nginx puede conectar al backend${NC}"
    else
        echo -e "${RED}✗ Nginx NO puede conectar al backend${NC}"
    fi
else
    echo -e "${YELLOW}⚠ Nginx NO está activo${NC}"
fi
echo ""

# 6. Verificar desde fuera (si es posible)
echo -e "${YELLOW}[6] Resumen final...${NC}"
echo "=========================================="
echo -e "${GREEN}✓ Servicio: ACTIVO${NC}"
echo -e "${GREEN}✓ Puerto: EN USO${NC}"
echo -e "${GREEN}✓ Backend: RESPONDE${NC}"
echo ""
echo "El servicio debería estar funcionando correctamente."
echo "Prueba acceder desde el navegador:"
echo "  http://192.168.1.148"
echo ""
echo "Si aún ves 502, verifica:"
echo "  1. Nginx está corriendo: sudo systemctl status nginx"
echo "  2. Logs de Nginx: sudo tail -f /var/log/nginx/hostberry_error.log"
echo "  3. Logs del servicio: sudo journalctl -u hostberry.service -f"
echo ""

