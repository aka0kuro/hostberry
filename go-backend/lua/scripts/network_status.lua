-- Script Lua para obtener estado de la red

local result = {}
result.interfaces = {}

-- Obtener interfaces de red
local interfaces_cmd = "ip -o link show | awk -F': ' '{print $2}'"
local interfaces_output = exec(interfaces_cmd)

if interfaces_output then
    for iface in interfaces_output:gmatch("[^\r\n]+") do
        if iface ~= "lo" then
            local interface_info = {}
            interface_info.name = iface
            
            -- Obtener IP
            local ip_cmd = "ip addr show " .. iface .. " | grep 'inet ' | awk '{print $2}' | cut -d'/' -f1"
            interface_info.ip = exec(ip_cmd) or "N/A"
            
            -- Obtener estado (up/down)
            local state_cmd = "cat /sys/class/net/" .. iface .. "/operstate 2>/dev/null"
            interface_info.state = exec(state_cmd) or "unknown"
            
            -- Obtener MAC
            local mac_cmd = "cat /sys/class/net/" .. iface .. "/address 2>/dev/null"
            interface_info.mac = exec(mac_cmd) or "N/A"
            
            table.insert(result.interfaces, interface_info)
        end
    end
end

result.count = #result.interfaces
result.success = true

return result
