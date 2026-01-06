# Guía de Instalación de HostBerry

## Instalación Automática (Recomendado)

### Requisitos Previos

- Sistema Linux (Debian, Ubuntu, Raspberry Pi OS)
- Acceso root (sudo)
- Conexión a internet
- Al menos 500MB de espacio libre

### Instalación Rápida

```bash
# Descargar el proyecto
git clone https://github.com/aka0kuro/Hostberry.git
cd Hostberry

# Ejecutar instalador
sudo ./install.sh
```

**Nota:** Si HostBerry ya está instalado, el instalador detectará la instalación existente y te preguntará si deseas actualizar. También puedes usar `sudo ./install.sh --update` para actualizar directamente.

El instalador automáticamente:
- ✅ Instala Go (si no está instalado)
- ✅ Instala dependencias (Lua, build-essential, etc.)
- ✅ Crea usuario del sistema `hostberry`
- ✅ Copia archivos a `/opt/hostberry`
- ✅ Compila el proyecto
- ✅ Crea servicio systemd
- ✅ Inicia el servicio

### Acceso a la Interfaz

Una vez instalado, accede a:
- `http://tu-ip:8000`
- `http://localhost:8000`

**Credenciales por defecto:**
- Usuario: `admin`
- Contraseña: `admin` (cambiar en el primer inicio)

## Instalación Manual

Si prefieres instalar manualmente:

### 1. Instalar Dependencias

```bash
sudo apt update
sudo apt install -y golang-go lua5.1 build-essential git wget curl
```

### 2. Configurar Go

Si instalaste Go desde el repositorio, ya está listo. Si lo descargaste manualmente:

```bash
export PATH=$PATH:/usr/local/go/bin
echo 'export PATH=$PATH:/usr/local/go/bin' >> ~/.bashrc
```

### 3. Clonar y Compilar

```bash
git clone https://github.com/aka0kuro/Hostberry.git
cd Hostberry
go mod download
go mod tidy
make build
```

### 4. Configurar

```bash
# Crear directorios
sudo mkdir -p /opt/hostberry
sudo mkdir -p /var/log/hostberry
sudo mkdir -p /opt/hostberry/data

# Copiar archivos
sudo cp -r * /opt/hostberry/
sudo cp config.yaml.example /opt/hostberry/config.yaml

# Editar configuración
sudo nano /opt/hostberry/config.yaml
```

### 5. Crear Usuario del Sistema

```bash
sudo useradd -r -s /bin/false -d /opt/hostberry hostberry
sudo chown -R hostberry:hostberry /opt/hostberry
sudo chown -R hostberry:hostberry /var/log/hostberry
```

### 6. Crear Servicio Systemd

```bash
sudo nano /etc/systemd/system/hostberry.service
```

Contenido:

```ini
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

[Install]
WantedBy=multi-user.target
```

### 7. Iniciar Servicio

```bash
sudo systemctl daemon-reload
sudo systemctl enable hostberry
sudo systemctl start hostberry
sudo systemctl status hostberry
```

## Gestión del Servicio

### Comandos Útiles

```bash
# Iniciar
sudo systemctl start hostberry

# Detener
sudo systemctl stop hostberry

# Reiniciar
sudo systemctl restart hostberry

# Ver estado
sudo systemctl status hostberry

# Ver logs en tiempo real
sudo journalctl -u hostberry -f

# Ver logs de aplicación
tail -f /var/log/hostberry/hostberry.log
```

## Desinstalación

### Desinstalación Automática

```bash
sudo ./uninstall.sh
```

### Desinstalación Manual

```bash
# Detener servicio
sudo systemctl stop hostberry
sudo systemctl disable hostberry

# Eliminar servicio
sudo rm /etc/systemd/system/hostberry.service
sudo systemctl daemon-reload

# Eliminar archivos (opcional)
sudo rm -rf /opt/hostberry
sudo rm -rf /var/log/hostberry
sudo userdel hostberry
```

## Solución de Problemas

### Error: "go: command not found"

```bash
# Instalar Go
sudo apt install golang-go

# O agregar al PATH
export PATH=$PATH:/usr/local/go/bin
```

### Error: "permission denied"

```bash
# Dar permisos de ejecución
chmod +x /opt/hostberry/hostberry
```

### Error: "port already in use"

```bash
# Cambiar puerto en config.yaml
sudo nano /opt/hostberry/config.yaml

# O matar proceso
sudo lsof -ti:8000 | xargs kill
```

### El servicio no inicia

```bash
# Ver logs detallados
sudo journalctl -u hostberry -n 50

# Verificar configuración
sudo /opt/hostberry/hostberry --help

# Ejecutar manualmente para ver errores
sudo -u hostberry /opt/hostberry/hostberry
```

### Error de compilación

```bash
# Limpiar y recompilar
cd /opt/hostberry
go clean
go mod download
go mod tidy
go build -o hostberry .
```

## Actualización

### Actualización Automática (Recomendado)

```bash
# Desde el directorio del proyecto
cd Hostberry
git pull
sudo ./install.sh --update

# O usar el script de actualización
sudo ./update.sh
```

El actualizador automáticamente:
- ✅ Crea backup de datos y configuración
- ✅ Detiene el servicio
- ✅ Actualiza archivos del proyecto
- ✅ Recompila el binario
- ✅ Reinicia el servicio
- ✅ Preserva tu configuración y datos

### Actualización Manual

```bash
cd /opt/hostberry

# Hacer backup
sudo cp -r data data.backup
sudo cp config.yaml config.yaml.backup

# Actualizar código (si usas git)
cd /ruta/al/proyecto
git pull
sudo cp -r * /opt/hostberry/

# Recompilar
cd /opt/hostberry
export PATH=$PATH:/usr/local/go/bin
sudo -u hostberry go mod download
sudo -u hostberry go mod tidy
sudo -u hostberry go build -o hostberry .

# Reiniciar servicio
sudo systemctl restart hostberry
```

## Configuración Avanzada

### Cambiar Puerto

Edita `/opt/hostberry/config.yaml`:

```yaml
server:
  port: 8080  # Cambiar aquí
```

Luego reinicia:
```bash
sudo systemctl restart hostberry
```

### Cambiar Base de Datos

Edita `/opt/hostberry/config.yaml`:

```yaml
database:
  type: "postgres"  # o "mysql"
  host: "localhost"
  port: 5432
  user: "hostberry"
  password: "tu_password"
  database: "hostberry"
```

### Configurar Logs

Los logs se guardan en:
- Systemd: `journalctl -u hostberry`
- Aplicación: `/var/log/hostberry/` (si está configurado)

## Seguridad

### Cambiar Contraseña por Defecto

1. Accede a la interfaz web
2. Ve a Perfil > Cambiar Contraseña
3. Cambia la contraseña de `admin`

### Configurar Firewall

```bash
# Permitir puerto 8000
sudo ufw allow 8000/tcp

# O solo desde red local
sudo ufw allow from 192.168.1.0/24 to any port 8000
```

### Cambiar JWT Secret

Edita `/opt/hostberry/config.yaml`:

```yaml
security:
  jwt_secret: "tu-secreto-muy-seguro-aqui"
```

Genera un secreto seguro:
```bash
openssl rand -hex 32
```

## Soporte

Para más ayuda:
- Revisa los logs: `journalctl -u hostberry -f`
- Consulta el README.md
- Abre un issue en GitHub
