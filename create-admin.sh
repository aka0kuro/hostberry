#!/bin/bash

# Script para crear usuario admin en HostBerry

echo "=== Crear Usuario Admin en HostBerry ==="
echo ""

# Verificar que se ejecuta como root
if [ "$EUID" -ne 0 ]; then 
    echo "❌ Este script debe ejecutarse como root (usa sudo)"
    exit 1
fi

# Verificar que el binario existe
if [ ! -f "/opt/hostberry/hostberry" ]; then
    echo "❌ Binario no encontrado en /opt/hostberry/hostberry"
    echo "   Primero compila e instala el proyecto"
    exit 1
fi

# Verificar que la BD existe
DB_PATH="/opt/hostberry/data/hostberry.db"
if [ ! -f "$DB_PATH" ]; then
    echo "⚠️  Base de datos no encontrada en $DB_PATH"
    echo "   Se creará automáticamente al iniciar el servicio"
    echo ""
    echo "Iniciando servicio para crear BD y usuario admin..."
    systemctl restart hostberry
    sleep 3
    echo ""
fi

echo "📋 Credenciales por defecto de HostBerry:"
echo "   Usuario: admin"
echo "   Contraseña: admin"
echo ""
echo "Si el usuario admin no existe, se creará automáticamente"
echo "al iniciar el servicio (solo si la BD está vacía)."
echo ""
echo "Para verificar si el usuario existe, revisa los logs:"
echo "  sudo journalctl -u hostberry -n 50 | grep -i admin"
echo ""
echo "Si necesitas crear el usuario manualmente, puedes:"
echo "1. Detener el servicio: sudo systemctl stop hostberry"
echo "2. Eliminar la BD: sudo rm /opt/hostberry/data/hostberry.db"
echo "3. Reiniciar: sudo systemctl start hostberry"
echo "   (Esto creará una BD nueva con usuario admin)"
echo ""
