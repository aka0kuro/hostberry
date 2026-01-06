#!/bin/bash

# Script para actualizar el servicio systemd de HostBerry de Python a Go

set -e

echo "=== Actualizando servicio HostBerry de Python a Go ==="
echo ""

# Verificar que se ejecuta como root
if [ "$EUID" -ne 0 ]; then 
    echo "❌ Este script debe ejecutarse como root (usa sudo)"
    exit 1
fi

# Verificar que el binario existe
if [ ! -f "/opt/hostberry/hostberry" ]; then
    echo "❌ Binario de Go no encontrado en /opt/hostberry/hostberry"
    echo ""
    echo "Opciones:"
    echo "1. Si tienes el binario compilado localmente:"
    echo "   sudo cp hostberry /opt/hostberry/hostberry"
    echo "   sudo chown hostberry:hostberry /opt/hostberry/hostberry"
    echo "   sudo chmod +x /opt/hostberry/hostberry"
    echo ""
    echo "2. O compilar e instalar:"
    echo "   make build"
    echo "   sudo ./install.sh --update"
    exit 1
fi

echo "✅ Binario encontrado: /opt/hostberry/hostberry"
ls -lh /opt/hostberry/hostberry
echo ""

# Detener servicio actual
echo "🛑 Deteniendo servicio actual..."
systemctl stop hostberry 2>/dev/null || true
echo "✅ Servicio detenido"
echo ""

# Actualizar servicio systemd
echo "📝 Actualizando servicio systemd..."
cat > /etc/systemd/system/hostberry.service <<'EOF'
[Unit]
Description=HostBerry - Sistema de Gestión de Red
After=network.target

[Service]
Type=simple
User=hostberry
Group=hostberry
WorkingDirectory=/opt/hostberry
ExecStart=/opt/hostberry/hostberry
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal
SyslogIdentifier=hostberry

# Seguridad
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=/opt/hostberry /var/log/hostberry /opt/hostberry/data

# Recursos
LimitNOFILE=65536

[Install]
WantedBy=multi-user.target
EOF

echo "✅ Servicio actualizado"
echo ""

# Asegurar permisos del binario
echo "🔐 Configurando permisos..."
chown hostberry:hostberry /opt/hostberry/hostberry
chmod +x /opt/hostberry/hostberry
echo "✅ Permisos configurados"
echo ""

# Recargar systemd
echo "🔄 Recargando systemd..."
systemctl daemon-reload
echo "✅ Systemd recargado"
echo ""

# Iniciar servicio
echo "🚀 Iniciando servicio..."
systemctl enable hostberry
systemctl start hostberry

# Esperar un momento y verificar
sleep 2

if systemctl is-active --quiet hostberry; then
    echo "✅ Servicio iniciado correctamente"
    echo ""
    echo "Estado del servicio:"
    systemctl status hostberry --no-pager -l | head -15
    echo ""
    echo "Para ver logs en tiempo real:"
    echo "  sudo journalctl -u hostberry -f"
else
    echo "❌ El servicio no se inició correctamente"
    echo ""
    echo "Revisa los logs:"
    echo "  sudo journalctl -u hostberry -n 50"
    exit 1
fi
