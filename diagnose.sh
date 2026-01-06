#!/bin/bash

# Script de diagnóstico para HostBerry

echo "=== Diagnóstico de HostBerry ==="
echo ""

echo "1. Verificando si el proceso está corriendo:"
ps aux | grep -E "hostberry|Hostberry" | grep -v grep || echo "   ❌ No se encontró proceso hostberry"
echo ""

echo "2. Verificando si el puerto 8000 está en uso:"
if command -v netstat &> /dev/null; then
    sudo netstat -tlnp | grep 8000 || echo "   ❌ Puerto 8000 no está en uso"
elif command -v ss &> /dev/null; then
    sudo ss -tlnp | grep 8000 || echo "   ❌ Puerto 8000 no está en uso"
else
    echo "   ⚠️  No se encontró netstat ni ss"
fi
echo ""

echo "3. Verificando estado del servicio systemd:"
if systemctl is-active --quiet hostberry 2>/dev/null; then
    echo "   ✅ Servicio activo"
    systemctl status hostberry --no-pager -l | head -10
else
    echo "   ❌ Servicio no activo"
fi
echo ""

echo "4. Últimos logs del servicio:"
if [ -f /etc/systemd/system/hostberry.service ]; then
    sudo journalctl -u hostberry -n 30 --no-pager || echo "   ⚠️  No se pudieron leer logs"
else
    echo "   ⚠️  Servicio systemd no encontrado"
fi
echo ""

echo "5. Verificando archivos de instalación:"
if [ -d "/opt/hostberry" ]; then
    echo "   ✅ Directorio /opt/hostberry existe"
    if [ -f "/opt/hostberry/hostberry" ]; then
        echo "   ✅ Binario existe"
        ls -lh /opt/hostberry/hostberry
    else
        echo "   ❌ Binario no encontrado"
    fi
    if [ -f "/opt/hostberry/config.yaml" ]; then
        echo "   ✅ Config.yaml existe"
    else
        echo "   ⚠️  Config.yaml no encontrado"
    fi
else
    echo "   ❌ Directorio /opt/hostberry no existe"
fi
echo ""

echo "6. Verificando permisos:"
if [ -f "/opt/hostberry/hostberry" ]; then
    ls -l /opt/hostberry/hostberry | awk '{print "   Permisos:", $1, "Usuario:", $3, "Grupo:", $4}'
fi
echo ""

echo "7. Verificando conectividad:"
if command -v curl &> /dev/null; then
    echo "   Probando http://localhost:8000/health..."
    curl -s -m 5 http://localhost:8000/health || echo "   ❌ No responde"
else
    echo "   ⚠️  curl no instalado"
fi
echo ""

echo "=== Fin del diagnóstico ==="
echo ""
echo "Para ver logs en tiempo real:"
echo "  sudo journalctl -u hostberry -f"
echo ""
echo "Para reiniciar el servicio:"
echo "  sudo systemctl restart hostberry"
