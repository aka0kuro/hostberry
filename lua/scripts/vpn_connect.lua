-- Script Lua para conectar VPN
-- Soporta OpenVPN y WireGuard

local result = {}

local config = params.config or ""
local vpn_type = params.type or "openvpn"
local user = params.user or "unknown"

if config == "" then
    result.success = false
    result.error = "Configuración requerida"
    return result
end

log("INFO", "Conectando VPN tipo: " .. vpn_type .. " (usuario: " .. user .. ")")

if vpn_type == "openvpn" then
    -- Guardar configuración
    local config_file = "/etc/openvpn/client.conf"
    write_file(config_file, config)
    
    -- Iniciar OpenVPN
    local cmd = "sudo systemctl start openvpn@client"
    local output, err = exec(cmd)
    
    if err then
        result.success = false
        result.error = err
    else
        result.success = true
        result.message = "OpenVPN iniciado"
    end
    
elseif vpn_type == "wireguard" then
    -- Guardar configuración WireGuard
    local config_file = "/etc/wireguard/wg0.conf"
    write_file(config_file, config)
    
    -- Activar interfaz
    local cmd = "sudo wg-quick up wg0"
    local output, err = exec(cmd)
    
    if err then
        result.success = false
        result.error = err
    else
        result.success = true
        result.message = "WireGuard activado"
    end
else
    result.success = false
    result.error = "Tipo de VPN no soportado: " .. vpn_type
end

return result
