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

# Crear directorios para recursos estáticos
echo "Creando directorios para recursos estáticos..."
mkdir -p static/css static/js static/webfonts static/fonts

# Descargar recursos estáticos
echo "Descargando recursos estáticos..."
# Bootstrap
curl -o static/css/bootstrap.min.css https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css
curl -o static/js/bootstrap.bundle.min.js https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js

# Bootstrap Icons
curl -o static/css/bootstrap-icons.css https://cdn.jsdelivr.net/npm/bootstrap-icons@1.10.0/font/bootstrap-icons.css
curl -o static/fonts/bootstrap-icons.woff https://cdn.jsdelivr.net/npm/bootstrap-icons@1.10.0/font/fonts/bootstrap-icons.woff
curl -o static/fonts/bootstrap-icons.woff2 https://cdn.jsdelivr.net/npm/bootstrap-icons@1.10.0/font/fonts/bootstrap-icons.woff2

# jQuery
curl -o static/js/jquery.min.js https://code.jquery.com/jquery-3.6.0.min.js

# Font Awesome
curl -o static/css/fontawesome.min.css https://cdnjs.cloudflare.com/ajax/libs/font-awesome/5.15.4/css/all.min.css
curl -o static/webfonts/fa-solid-900.woff2 https://cdnjs.cloudflare.com/ajax/libs/font-awesome/5.15.4/webfonts/fa-solid-900.woff2
curl -o static/webfonts/fa-solid-900.woff https://cdnjs.cloudflare.com/ajax/libs/font-awesome/5.15.4/webfonts/fa-solid-900.woff

# Crear archivo custom.css
echo "Creando archivo custom.css y connection-status.js para soporte sin conexión..."

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

# --- Permitir ejecutar adblock.sh con sudo sin contraseña ---
ADBLOCK_SCRIPT="/opt/hostberry/scripts/adblock.sh"
SUDOERS_LINE="$(whoami) ALL=(ALL) NOPASSWD: $ADBLOCK_SCRIPT"

# Solo añadir si no existe ya
if ! sudo grep -Fxq "$SUDOERS_LINE" /etc/sudoers; then
    echo "$SUDOERS_LINE" | sudo EDITOR='tee -a' visudo
    echo "Permiso sudoers añadido para $ADBLOCK_SCRIPT"
else
    echo "Permiso sudoers ya presente para $ADBLOCK_SCRIPT"
fi

echo "Installation complete!"
echo "Run the application with: python3 app.py"

# --- Instalar flask_babel en el entorno virtual ---
if [ -d "/opt/hostberry/venv" ]; then
    source /opt/hostberry/venv/bin/activate
    pip install flask_babel
    deactivate
else
    echo "No se encontró el entorno virtual en /opt/hostberry/venv"
fi

# --- Añadir flask_babel a requirements.txt si no está ---
if ! grep -q "^flask_babel" /opt/hostberry/requirements.txt; then
    echo "flask_babel" >> /opt/hostberry/requirements.txt
fi

# --- Crear/actualizar el archivo de servicio systemd ---
SERVICE_FILE="/etc/systemd/system/hostberry.service"
cat << EOF | sudo tee $SERVICE_FILE > /dev/null
[Unit]
Description=HostBerry Web
After=network.target

[Service]
User=$(whoami)
WorkingDirectory=/opt/hostberry
ExecStart=/opt/hostberry/venv/bin/python3 /opt/hostberry/app.py
Restart=always
Environment=FLASK_ENV=production

[Install]
WantedBy=multi-user.target
EOF

# --- Recargar systemd y reiniciar el servicio ---
sudo systemctl daemon-reload
sudo systemctl restart hostberry
sudo systemctl enable hostberry

echo "¡Configuración de systemd y flask_babel completada!"
