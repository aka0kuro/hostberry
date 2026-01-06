-- Script Lua para listar interfaces de red con detalles

local result = {}
result.interfaces = {}

-- Obtener todas las interfaces
local interfaces_cmd = "ip -o link show | awk -F': ' '{print $2}'"
local interfaces_output = exec(interfaces_cmd)

if interfaces_output then
    for iface in interfaces_output:gmatch("[^\r\n]+") do
        local interface_info = {}
        interface_info.name = iface
        
        -- Estado
        local state_cmd = "cat /sys/class/net/" .. iface .. "/operstate 2>/dev/null"
        interface_info.state = exec(state_cmd) or "unknown"
        interface_info.connected = (interface_info.state == "up")
        
        -- IP
        local ip_cmd = "ip addr show " .. iface .. " | grep 'inet ' | awk '{print $2}' | cut -d'/' -f1"
        interface_info.ip = exec(ip_cmd) or "N/A"
        
        -- MAC
        local mac_cmd = "cat /sys/class/net/" .. iface .. "/address 2>/dev/null"
        interface_info.mac = exec(mac_cmd) or "N/A"
        
        -- Gateway (para la interfaz activa)
        if interface_info.connected and interface_info.ip ~= "N/A" then
            local gateway_cmd = "ip route | grep default | awk '{print $3}'"
            interface_info.gateway = exec(gateway_cmd) or "N/A"
        else
            interface_info.gateway = "N/A"
        end
        
        table.insert(result.interfaces, interface_info)
    end
end

return result
