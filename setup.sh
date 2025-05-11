#!/bin/bash

# Update system packages
echo "Updating system packages..."
sudo apt-get update

# Install Python and pip if not already installed
if ! command -v python3 &> /dev/null; then
    echo "Installing Python3..."
    sudo apt-get install -y python3 python3-pip
fi

# Verificar e instalar NetworkManager
if ! command -v nmcli &> /dev/null; then
    echo "Instalando NetworkManager..."
    sudo apt-get update
    sudo apt-get install -y network-manager
    
    # Reiniciar servicio
    sudo systemctl restart NetworkManager
    
    # Verificar instalación
    if ! command -v nmcli &> /dev/null; then
        echo "ERROR: No se pudo instalar NetworkManager"
        exit 1
    fi
else
    echo "NetworkManager ya está instalado"
fi

# Añadir usuario al grupo netdev
if ! groups $USER | grep -q "netdev"; then
    echo "Añadiendo usuario $USER al grupo netdev..."
    sudo usermod -aG netdev newgrp $USER
    echo "Usuario añadido. Debes reiniciar la sesión para aplicar los cambios."
else
    echo "El usuario ya está en el grupo netdev"
fi

echo "Instalando nmcli (NetworkManager) si no está presente"
sudo apt-get install -y network-manager

# Move project to /opt/hostberry
echo "Moving project to /opt/hostberry..."
sudo mkdir -p /opt/hostberry
sudo chown -R $USER:$USER /opt/hostberry
sudo cp -r . /opt/hostberry/
# Ensure service file is in the right location
if [ -f "hostberry-web.service" ]; then
    sudo cp hostberry-web.service /opt/hostberry/
fi
cd /opt/hostberry

# Install project dependencies
echo "Installing Python dependencies..."
python3 -m venv venv
source venv/bin/activate
if ! pip3 install -r requirements.txt; then
    echo "Error instalando dependencias Python. Abortando instalación."
    exit 1
fi

# Set up configuration
if [ ! -f ".env" ]; then
    echo "Creating .env file with generated FLASK_SECRET_KEY..."
    SECRET_KEY=$(openssl rand -hex 32)
    echo "FLASK_SECRET_KEY=$SECRET_KEY" > .env
    echo "DB_USER=hostberry" >> .env
    echo "DB_PASS=$(openssl rand -hex 16)" >> .env
    echo "Please review and add other required configurations to the .env file"
fi

# Set permissions for log files
echo "Setting up log directory..."
mkdir -p logs
touch logs/hostberry.log
chmod 666 logs/hostberry.log

# Install as systemd service (optional)
read -p "Would you like to install as a systemd service? [y/N] " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]
then
    echo "Installing systemd service..."
    sudo cp hostberry-web.service /etc/systemd/system/
    sudo systemctl daemon-reload
    sudo systemctl enable hostberry-web
    echo "Service installed. Start with: sudo systemctl start hostberry-web"
fi

echo "Installation complete!"
echo "Run the application with: python3 app.py"
