-- Script Lua para apagar el sistema
-- Requiere permisos sudo

local result = {}

local user = "unknown"
if params and params.user then
    user = params.user
end

log("INFO", "Apagado del sistema solicitado por: " .. user)

-- Ejecutar comando de apagado
local shutdown_cmd = "sudo shutdown -h +1"
local output, err = exec(shutdown_cmd)

if err then
    result.success = false
    result.error = err
    result.message = "Error al ejecutar comando de apagado"
    log("ERROR", "Error apagando sistema: " .. tostring(err))
else
    result.success = true
    result.message = "Sistema se apagará en 1 minuto"
    result.output = output
    log("INFO", "Comando de apagado ejecutado exitosamente")
end

return result
