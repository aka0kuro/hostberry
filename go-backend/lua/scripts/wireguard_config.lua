-- Script Lua para configurar WireGuard

local result = {}

local config = params.config or ""
local user = params.user or "unknown"

if config == "" then
    result.success = false
    result.error = "Configuración requerida"
    return result
end

log("INFO", "Configurando WireGuard (usuario: " .. user .. ")")

-- Guardar configuración
local config_file = "/etc/wireguard/wg0.conf"
local write_result, write_err = write_file(config_file, config)

if write_err then
    result.success = false
    result.error = write_err
    result.message = "Error guardando configuración"
    log("ERROR", "Error guardando configuración WireGuard: " .. tostring(write_err))
    return result
end

-- Recargar configuración si ya está activo
local wg_status = exec("wg show wg0 2>/dev/null")
if wg_status and wg_status ~= "" then
    -- Reiniciar interfaz
    exec("sudo wg-quick down wg0 2>/dev/null")
    exec("sudo wg-quick up wg0 2>/dev/null")
    result.message = "WireGuard reiniciado con nueva configuración"
else
    result.message = "Configuración guardada (no activa)"
end

result.success = true
log("INFO", "WireGuard configurado exitosamente")

return result
