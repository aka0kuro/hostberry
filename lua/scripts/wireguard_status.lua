-- Script Lua para obtener estado de WireGuard

local result = {}

-- Verificar si WireGuard está activo
local wg_cmd = "wg show 2>/dev/null"
local wg_output = exec(wg_cmd)

result.active = (wg_output ~= nil and wg_output ~= "")
result.interfaces = {}

if result.active then
    -- Obtener interfaces
    local interfaces_cmd = "wg show interfaces 2>/dev/null"
    local interfaces_output = exec(interfaces_cmd)
    
    if interfaces_output then
        for iface in interfaces_output:gmatch("[^\r\n]+") do
            local interface_info = {}
            interface_info.name = iface
            
            -- Obtener detalles de la interfaz
            local details_cmd = "wg show " .. iface .. " 2>/dev/null"
            local details = exec(details_cmd)
            interface_info.details = details or ""
            
            table.insert(result.interfaces, interface_info)
        end
    end
else
    result.message = "WireGuard no está activo"
end

result.success = true

return result
