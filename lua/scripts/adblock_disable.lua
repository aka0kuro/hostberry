-- Script Lua para deshabilitar AdBlock

local result = {}
local user = params.user or "unknown"

log("INFO", "Deshabilitando AdBlock (usuario: " .. user .. ")")

-- Detener dnsmasq
local dnsmasq_cmd = "sudo systemctl stop dnsmasq"
exec(dnsmasq_cmd)

-- Detener pihole si está activo
local pihole_cmd = "sudo systemctl stop pihole-FTL"
exec(pihole_cmd)

result.success = true
result.message = "AdBlock deshabilitado"
log("INFO", "AdBlock deshabilitado exitosamente")

return result
