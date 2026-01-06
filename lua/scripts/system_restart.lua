-- Script Lua para reiniciar el sistema
-- Requiere permisos sudo

local result = {}

-- Verificar que tenemos parámetros (usuario que ejecuta)
local user = "unknown"
if params and params.user then
    user = params.user
end

log("INFO", "Reinicio del sistema solicitado por: " .. user)

-- Ejecutar comando de reinicio
local restart_cmd = "sudo shutdown -r +1"
local output, err = exec(restart_cmd)

if err then
    result.success = false
    result.error = err
    result.message = "Error al ejecutar comando de reinicio"
    log("ERROR", "Error reiniciando sistema: " .. tostring(err))
else
    result.success = true
    result.message = "Sistema se reiniciará en 1 minuto"
    result.output = output
    log("INFO", "Comando de reinicio ejecutado exitosamente")
end

return result
