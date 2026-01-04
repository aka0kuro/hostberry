#!/bin/bash
# Script de diagnóstico para error 502 Bad Gateway
# Ejecutar en el servidor: ssh hostberry@192.168.1.148

echo "=========================================="
echo "Diagnóstico 502 Bad Gateway - HostBerry"
echo "=========================================="
echo ""

# Colores
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 1. Verificar si el servicio está corriendo
echo -e "${YELLOW}[1] Verificando servicio hostberry...${NC}"
if systemctl is-active --quiet hostberry.service; then
    echo -e "${GREEN}✓ Servicio hostberry está activo${NC}"
    systemctl status hostberry.service --no-pager -l | head -15
else
    echo -e "${RED}✗ Servicio hostberry NO está activo${NC}"
    echo "Intentando iniciar..."
    sudo systemctl start hostberry.service
    sleep 2
    systemctl status hostberry.service --no-pager -l | head -15
fi
echo ""

# 2. Verificar logs del servicio
echo -e "${YELLOW}[2] Últimas líneas del log del servicio:${NC}"
journalctl -u hostberry.service -n 50 --no-pager | tail -20
echo ""

# 3. Verificar si uvicorn está escuchando en el puerto
echo -e "${YELLOW}[3] Verificando puerto de la aplicación...${NC}"
PROD_PORT=$(grep -E "^PROD_PORT=" /opt/hostberry/.env 2>/dev/null | cut -d'=' -f2 || echo "8000")
echo "Puerto configurado: $PROD_PORT"
if netstat -tuln 2>/dev/null | grep -q ":$PROD_PORT " || ss -tuln 2>/dev/null | grep -q ":$PROD_PORT "; then
    echo -e "${GREEN}✓ Puerto $PROD_PORT está en uso${NC}"
    netstat -tuln 2>/dev/null | grep ":$PROD_PORT " || ss -tuln 2>/dev/null | grep ":$PROD_PORT "
else
    echo -e "${RED}✗ Puerto $PROD_PORT NO está en uso${NC}"
    echo "La aplicación no está escuchando en el puerto configurado"
fi
echo ""

# 4. Verificar nginx
echo -e "${YELLOW}[4] Verificando Nginx...${NC}"
if systemctl is-active --quiet nginx; then
    echo -e "${GREEN}✓ Nginx está activo${NC}"
    if sudo nginx -t 2>&1 | grep -q "successful"; then
        echo -e "${GREEN}✓ Configuración de Nginx es válida${NC}"
    else
        echo -e "${RED}✗ Configuración de Nginx tiene errores:${NC}"
        sudo nginx -t
    fi
else
    echo -e "${RED}✗ Nginx NO está activo${NC}"
fi
echo ""

# 5. Verificar logs de nginx
echo -e "${YELLOW}[5] Últimas líneas del log de error de Nginx:${NC}"
if [ -f /var/log/nginx/hostberry_error.log ]; then
    tail -20 /var/log/nginx/hostberry_error.log
else
    echo "Log no encontrado, intentando log general..."
    sudo tail -20 /var/log/nginx/error.log 2>/dev/null || echo "No se pudo acceder al log"
fi
echo ""

# 6. Verificar conexión local al backend
echo -e "${YELLOW}[6] Probando conexión local al backend...${NC}"
PROD_PORT=$(grep -E "^PROD_PORT=" /opt/hostberry/.env 2>/dev/null | cut -d'=' -f2 || echo "8000")
if curl -s -o /dev/null -w "%{http_code}" --max-time 5 http://127.0.0.1:$PROD_PORT/health > /dev/null 2>&1; then
    HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" --max-time 5 http://127.0.0.1:$PROD_PORT/health)
    echo -e "${GREEN}✓ Backend responde con código: $HTTP_CODE${NC}"
    curl -s --max-time 5 http://127.0.0.1:$PROD_PORT/health | head -5
else
    echo -e "${RED}✗ Backend NO responde en http://127.0.0.1:$PROD_PORT${NC}"
    echo "Esto indica que la aplicación no está corriendo o no está escuchando en ese puerto"
fi
echo ""

# 7. Verificar entorno virtual y dependencias
echo -e "${YELLOW}[7] Verificando entorno virtual...${NC}"
VENV_DIR=$(grep -E "^VENV_DIR=" /opt/hostberry/.env 2>/dev/null | cut -d'=' -f2 || echo "/opt/hostberry/venv")
if [ -d "$VENV_DIR" ]; then
    echo -e "${GREEN}✓ Entorno virtual encontrado en: $VENV_DIR${NC}"
    if [ -f "$VENV_DIR/bin/python3" ]; then
        echo "Python version: $($VENV_DIR/bin/python3 --version 2>&1)"
        if $VENV_DIR/bin/python3 -c "import fastapi" 2>/dev/null; then
            echo -e "${GREEN}✓ FastAPI está instalado${NC}"
        else
            echo -e "${RED}✗ FastAPI NO está instalado${NC}"
        fi
    fi
else
    echo -e "${RED}✗ Entorno virtual NO encontrado en: $VENV_DIR${NC}"
fi
echo ""

# 8. Verificar permisos y archivos
echo -e "${YELLOW}[8] Verificando archivos principales...${NC}"
APP_DIR=$(grep -E "^APP_DIR=" /opt/hostberry/.env 2>/dev/null | cut -d'=' -f2 || echo "/opt/hostberry")
if [ -f "$APP_DIR/main.py" ]; then
    echo -e "${GREEN}✓ main.py encontrado${NC}"
    if python3 -m py_compile "$APP_DIR/main.py" 2>/dev/null; then
        echo -e "${GREEN}✓ main.py no tiene errores de sintaxis${NC}"
    else
        echo -e "${RED}✗ main.py tiene errores de sintaxis:${NC}"
        python3 -m py_compile "$APP_DIR/main.py" 2>&1 | head -10
    fi
else
    echo -e "${RED}✗ main.py NO encontrado en: $APP_DIR${NC}"
fi
echo ""

# 9. Verificar configuración del proxy en nginx
echo -e "${YELLOW}[9] Verificando configuración del proxy...${NC}"
if [ -f /etc/nginx/sites-available/hostberry ]; then
    echo "Configuración encontrada:"
    grep -A 5 "proxy_pass" /etc/nginx/sites-available/hostberry | head -10
else
    echo -e "${RED}✗ Configuración de Nginx no encontrada${NC}"
fi
echo ""

# 10. Resumen y recomendaciones
echo -e "${YELLOW}[10] Resumen y recomendaciones:${NC}"
echo "=========================================="
echo ""
echo "Para solucionar el 502 Bad Gateway, verifica:"
echo "1. Que el servicio hostberry esté corriendo: sudo systemctl status hostberry"
echo "2. Que el puerto $PROD_PORT esté en uso: netstat -tuln | grep $PROD_PORT"
echo "3. Que Nginx pueda conectarse al backend: curl http://127.0.0.1:$PROD_PORT/health"
echo "4. Los logs del servicio: journalctl -u hostberry.service -f"
echo "5. Los logs de Nginx: tail -f /var/log/nginx/hostberry_error.log"
echo ""
echo "Comandos útiles:"
echo "  - Reiniciar servicio: sudo systemctl restart hostberry.service"
echo "  - Reiniciar Nginx: sudo systemctl restart nginx"
echo "  - Ver logs en tiempo real: journalctl -u hostberry.service -f"
echo ""

