# Guía de Instalación en Raspberry Pi 3

## Requisitos Previos

- Raspberry Pi 3 (o superior)
- Raspberry Pi OS (Debian-based)
- Acceso SSH o terminal
- Al menos 1GB de RAM libre
- Conexión a internet

## Paso 1: Instalar Go

```bash
# Actualizar sistema
sudo apt update
sudo apt upgrade -y

# Instalar Go
sudo apt install golang-go -y

# Verificar instalación
go version
```

Si necesitas una versión más reciente de Go:

```bash
# Descargar Go 1.21
wget https://go.dev/dl/go1.21.5.linux-armv6l.tar.gz

# Extraer
sudo rm -rf /usr/local/go
sudo tar -C /usr/local -xzf go1.21.5.linux-armv6l.tar.gz

# Agregar a PATH
echo 'export PATH=$PATH:/usr/local/go/bin' >> ~/.bashrc
source ~/.bashrc

# Verificar
go version
```

## Paso 2: Instalar Lua (opcional, para scripts del sistema)

```bash
sudo apt install lua5.1 -y
```

## Paso 3: Clonar y Compilar

```bash
# Clonar repositorio
cd ~
git clone https://github.com/aka0kuro/Hostberry.git
cd Hostberry

# Instalar dependencias de Go
go mod download

# Compilar
make build

# O directamente
go build -o hostberry
```

## Paso 4: Configuración

```bash
# Crear directorio de datos
mkdir -p data

# Copiar configuración de ejemplo
cp config.yaml.example config.yaml

# Editar configuración
nano config.yaml
```

Configuración mínima en `config.yaml`:

```yaml
server:
  host: "0.0.0.0"
  port: 8000
  debug: false

database:
  type: "sqlite"
  path: "data/hostberry.db"

security:
  jwt_secret: "cambiar-por-secreto-seguro-aqui"
  token_expiry: 1440
  bcrypt_cost: 10
  rate_limit_rps: 10

lua:
  scripts_path: "lua/scripts"
  enabled: true
```

## Paso 5: Ejecutar

### Modo desarrollo (foreground)

```bash
./hostberry
```

### Modo producción (background)

```bash
# Crear servicio systemd
sudo nano /etc/systemd/system/hostberry.service
```

Contenido del servicio:

```ini
[Unit]
Description=HostBerry Network Management System
After=network.target

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/Hostberry
ExecStart=/home/pi/Hostberry/hostberry
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Activar servicio:

```bash
# Recargar systemd
sudo systemctl daemon-reload

# Habilitar al inicio
sudo systemctl enable hostberry

# Iniciar servicio
sudo systemctl start hostberry

# Ver estado
sudo systemctl status hostberry

# Ver logs
sudo journalctl -u hostberry -f
```

## Paso 6: Acceder a la Interfaz

Abre tu navegador y ve a:

```
http://raspberrypi:8000
```

O si conoces la IP de tu Raspberry Pi:

```
http://192.168.1.XXX:8000
```

**Credenciales por defecto:**
- Usuario: `admin`
- Contraseña: `admin` (cambiar en primer inicio)

## Solución de Problemas

### Error: "go: command not found"
- Instala Go: `sudo apt install golang-go`
- O agrega Go al PATH: `export PATH=$PATH:/usr/local/go/bin`

### Error: "permission denied"
- Da permisos de ejecución: `chmod +x hostberry`
- O ejecuta con sudo si es necesario

### Error: "port already in use"
- Cambia el puerto en `config.yaml`
- O mata el proceso: `sudo lsof -ti:8000 | xargs kill`

### Error: "database locked"
- Cierra otras instancias de HostBerry
- Verifica permisos en `data/hostberry.db`

## Actualizar HostBerry

```bash
cd ~/Hostberry

# Hacer backup
cp -r data data.backup

# Actualizar código
git pull

# Recompilar
make build

# Reiniciar servicio
sudo systemctl restart hostberry
```

## Desinstalar

```bash
# Detener servicio
sudo systemctl stop hostberry
sudo systemctl disable hostberry
sudo rm /etc/systemd/system/hostberry.service

# Eliminar archivos
cd ~
rm -rf Hostberry
```

## Optimizaciones para Raspberry Pi

### Reducir uso de memoria

En `config.yaml`:

```yaml
server:
  debug: false  # Desactivar en producción

security:
  rate_limit_rps: 5  # Reducir rate limiting
```

### Compilar con optimizaciones

```bash
# Build optimizado para ARM
CGO_ENABLED=1 GOOS=linux GOARCH=arm GOARM=7 go build -ldflags="-s -w" -o hostberry
```

### Usar swap si es necesario

```bash
# Crear swap de 1GB
sudo fallocate -l 1G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile

# Hacer permanente
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
```
