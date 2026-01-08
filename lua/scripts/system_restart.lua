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
-- Intentar con systemctl primero (más moderno), luego con shutdown
local restart_cmd = "sudo systemctl reboot"
local output, err = exec(restart_cmd)

-- Si systemctl falla, intentar con shutdown
if err then
    log("WARN", "systemctl reboot falló, intentando con shutdown: " .. tostring(err))
    -- Buscar shutdown en rutas comunes
    local shutdown_paths = {"/usr/sbin/shutdown", "/sbin/shutdown", "shutdown"}
    local found = false
    for _, path in ipairs(shutdown_paths) do
        local test_cmd = "command -v " .. path .. " 2>/dev/null"
        local test_out, test_err = exec(test_cmd)
        if not test_err and test_out and test_out ~= "" then
            restart_cmd = "sudo " .. path .. " -r +1"
            output, err = exec(restart_cmd)
            found = true
            break
        end
    end
    if not found then
        -- Último recurso: intentar con reboot directo
        restart_cmd = "sudo reboot"
        output, err = exec(restart_cmd)
    end
end

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
