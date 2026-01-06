-- Script Lua para habilitar AdBlock

local result = {}
local user = params.user or "unknown"

log("INFO", "Habilitando AdBlock (usuario: " .. user .. ")")

-- Iniciar dnsmasq si está disponible
local dnsmasq_cmd = "sudo systemctl start dnsmasq"
local output, err = exec(dnsmasq_cmd)

if err then
    -- Intentar con pihole
    local pihole_cmd = "sudo systemctl start pihole-FTL"
    output, err = exec(pihole_cmd)
end

if err then
    result.success = false
    result.error = err
    result.message = "Error iniciando servicio AdBlock"
    log("ERROR", "Error habilitando AdBlock: " .. tostring(err))
else
    result.success = true
    result.message = "AdBlock habilitado"
    log("INFO", "AdBlock habilitado exitosamente")
end

return result
