# Solución para Error 502 Bad Gateway

## Pasos para diagnosticar y solucionar el 502 en el servidor

### 1. Conectarse al servidor
```bash
ssh hostberry@192.168.1.148
```

### 2. Ejecutar el script de diagnóstico
```bash
# Copiar el script al servidor si no está
cd /opt/hostberry  # o donde esté el proyecto
bash diagnose_502.sh
```

### 3. Verificaciones rápidas manuales

#### Verificar que el servicio esté corriendo:
```bash
sudo systemctl status hostberry.service
```

#### Verificar que el puerto esté en uso:
```bash
# Ver qué puerto está configurado
grep PROD_PORT /opt/hostberry/.env

# Verificar que esté escuchando
netstat -tuln | grep 8000  # o el puerto configurado
# o
ss -tuln | grep 8000
```

#### Probar conexión local al backend:
```bash
curl http://127.0.0.1:8000/health
# o el puerto que esté configurado
```

#### Ver logs del servicio:
```bash
# Logs en tiempo real
sudo journalctl -u hostberry.service -f

# Últimas 50 líneas
sudo journalctl -u hostberry.service -n 50
```

#### Ver logs de Nginx:
```bash
# Logs de error
sudo tail -f /var/log/nginx/hostberry_error.log
# o
sudo tail -f /var/log/nginx/error.log
```

### 4. Soluciones comunes

#### Si el servicio no está corriendo:
```bash
sudo systemctl start hostberry.service
sudo systemctl enable hostberry.service
```

#### Si hay errores de importación (ModuleNotFoundError):
```bash
cd /opt/hostberry
source venv/bin/activate  # o la ruta del venv
pip install -r requirements.txt
```

#### Si el puerto no está en uso:
```bash
# Verificar configuración
cat /etc/systemd/system/hostberry.service | grep ExecStart

# Reiniciar el servicio
sudo systemctl restart hostberry.service
```

#### Si Nginx no puede conectar:
```bash
# Verificar configuración de Nginx
sudo nginx -t

# Verificar que el proxy_pass apunte al puerto correcto
grep proxy_pass /etc/nginx/sites-available/hostberry

# Reiniciar Nginx
sudo systemctl restart nginx
```

#### Si hay errores de sintaxis en el código:
```bash
cd /opt/hostberry
source venv/bin/activate
python3 -m py_compile main.py
```

### 5. Verificar configuración del servicio systemd

```bash
# Ver el archivo de servicio
cat /etc/systemd/system/hostberry.service

# Verificar que apunte al directorio correcto
# Verificar que use el venv correcto
# Verificar que use el puerto correcto
```

### 6. Reiniciar todo el stack

```bash
# Reiniciar servicio
sudo systemctl restart hostberry.service

# Esperar unos segundos
sleep 5

# Verificar que esté corriendo
sudo systemctl status hostberry.service

# Reiniciar Nginx
sudo systemctl restart nginx

# Verificar que todo funcione
curl http://127.0.0.1:8000/health
```

### 7. Si nada funciona, verificar manualmente

```bash
# Activar entorno virtual
cd /opt/hostberry
source venv/bin/activate

# Intentar iniciar manualmente
python3 -m uvicorn main:app --host 127.0.0.1 --port 8000

# Si funciona manualmente, el problema está en systemd
# Si no funciona, hay un error en el código o dependencias
```

## Errores comunes y soluciones

### Error: "ModuleNotFoundError: No module named 'fastapi'"
**Solución**: Instalar dependencias
```bash
cd /opt/hostberry
source venv/bin/activate
pip install -r requirements.txt
```

### Error: "Address already in use"
**Solución**: Cambiar puerto o matar proceso
```bash
# Ver qué proceso usa el puerto
sudo lsof -i :8000
# Matar proceso
sudo kill -9 <PID>
```

### Error: "Permission denied"
**Solución**: Verificar permisos
```bash
sudo chown -R hostberry:hostberry /opt/hostberry
```

### Error: "Connection refused" en Nginx
**Solución**: Verificar que el backend esté corriendo
```bash
# Verificar que el servicio esté activo
sudo systemctl status hostberry.service
# Verificar que el puerto esté en uso
netstat -tuln | grep 8000
```

## Contacto y soporte

Si el problema persiste después de seguir estos pasos, revisa:
1. Los logs completos del servicio
2. Los logs de Nginx
3. La configuración del servicio systemd
4. La configuración de Nginx

