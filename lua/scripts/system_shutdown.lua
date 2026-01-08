-- Script Lua para apagar el sistema
-- Requiere permisos sudo

local result = {}

local user = "unknown"
if params and params.user then
    user = params.user
end

log("INFO", "Apagado del sistema solicitado por: " .. user)

-- Ejecutar comando de apagado
-- Intentar con systemctl primero (más moderno), luego con shutdown
-- NOTA: No incluir "sudo" - executeCommand lo agrega automáticamente si es necesario
local shutdown_cmd = "systemctl poweroff"
local output, err = exec(shutdown_cmd)

-- Si systemctl falla, intentar con shutdown
if err then
    log("WARN", "systemctl poweroff falló, intentando con shutdown: " .. tostring(err))
    -- Buscar shutdown en rutas comunes
    local shutdown_paths = {"/usr/sbin/shutdown", "/sbin/shutdown", "shutdown"}
    local found = false
    for _, path in ipairs(shutdown_paths) do
        local test_cmd = "command -v " .. path .. " 2>/dev/null"
        local test_out, test_err = exec(test_cmd)
        if not test_err and test_out and test_out ~= "" then
            shutdown_cmd = path .. " -h +1"
            output, err = exec(shutdown_cmd)
            found = true
            break
        end
    end
    if not found then
        -- Último recurso: intentar con poweroff directo
        shutdown_cmd = "poweroff"
        output, err = exec(shutdown_cmd)
    end
end

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
