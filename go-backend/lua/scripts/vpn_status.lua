-- Script Lua para obtener estado de VPN

local result = {}

-- Verificar OpenVPN
local openvpn_cmd = "systemctl is-active openvpn 2>/dev/null || pgrep openvpn > /dev/null && echo active || echo inactive"
local openvpn_status = exec(openvpn_cmd) or "inactive"
result.openvpn = {
    active = (openvpn_status == "active"),
    status = openvpn_status
}

-- Verificar WireGuard
local wg_cmd = "wg show 2>/dev/null | head -1"
local wg_output = exec(wg_cmd)
result.wireguard = {
    active = (wg_output ~= nil and wg_output ~= ""),
    interfaces = {}
}

if result.wireguard.active then
    -- Obtener interfaces WireGuard
    local wg_interfaces_cmd = "wg show interfaces 2>/dev/null"
    local wg_interfaces = exec(wg_interfaces_cmd)
    if wg_interfaces then
        for iface in wg_interfaces:gmatch("[^\r\n]+") do
            table.insert(result.wireguard.interfaces, iface)
        end
    end
end

result.success = true

return result
