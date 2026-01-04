#!/bin/bash
# Script para corregir permisos y solucionar error 502 Bad Gateway

echo "🔧 Corrigiendo permisos para solucionar error 502..."

# Corregir permisos del directorio de base de datos
echo "📁 Corrigiendo permisos de /var/lib/hostberry..."
sudo chown -R hostberry:hostberry /var/lib/hostberry
sudo chmod 755 /var/lib/hostberry

# Asegurar que el archivo de base de datos existe y tiene permisos correctos
DB_FILE="/var/lib/hostberry/hostberry.db"
if [ ! -f "$DB_FILE" ]; then
    echo "📄 Creando archivo de base de datos..."
    sudo touch "$DB_FILE"
fi
sudo chown hostberry:hostberry "$DB_FILE"
sudo chmod 0660 "$DB_FILE"

# Corregir permisos de logs
echo "📝 Corrigiendo permisos de logs..."
sudo chown -R hostberry:hostberry /var/log/hostberry 2>/dev/null || true
sudo chmod 755 /var/log/hostberry 2>/dev/null || true

# Verificar permisos
echo ""
echo "✅ Verificando permisos:"
ls -la /var/lib/hostberry
echo ""

# Reiniciar el servicio
echo "🔄 Reiniciando servicio hostberry..."
sudo systemctl restart hostberry.service

# Esperar un momento para que el servicio inicie
echo "⏳ Esperando 8 segundos para que el servicio inicie..."
sleep 8

# Verificar estado
echo ""
echo "📊 Estado del servicio:"
systemctl status hostberry.service --no-pager | head -15

echo ""
echo "🔍 Verificando si el puerto 8000 está escuchando..."
if netstat -tlnp 2>/dev/null | grep -q :8000 || ss -tlnp 2>/dev/null | grep -q :8000; then
    echo "✅ Puerto 8000 está escuchando"
    echo ""
    echo "🧪 Probando conexión HTTP..."
    if curl -s http://127.0.0.1:8000/health > /dev/null 2>&1; then
        echo "✅ Servicio responde correctamente"
        echo ""
        echo "✅ El error 502 debería estar resuelto. Prueba acceder a http://localhost"
    else
        echo "⚠️ Servicio no responde aún, revisa los logs:"
        echo "   journalctl -u hostberry.service -n 50"
    fi
else
    echo "❌ Puerto 8000 no está escuchando"
    echo ""
    echo "📋 Últimos logs del servicio:"
    journalctl -u hostberry.service -n 20 --no-pager | tail -15
    echo ""
    echo "💡 Si el problema persiste, ejecuta:"
    echo "   sudo journalctl -u hostberry.service -f"
fi

