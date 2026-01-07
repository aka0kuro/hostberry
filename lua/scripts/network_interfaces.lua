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
        
        -- IP y máscara de red
        local ip_cmd = "ip addr show " .. iface .. " | grep 'inet ' | awk '{print $2}'"
        local ip_output = exec(ip_cmd)
        if ip_output then
            -- Formato: "192.168.1.100/24"
            local ip_parts = {}
            for part in ip_output:gmatch("[^/]+") do
                table.insert(ip_parts, part)
            end
            if #ip_parts > 0 then
                interface_info.ip = ip_parts[1]:match("^%s*(.-)%s*$") or "N/A"
                if #ip_parts > 1 then
                    interface_info.netmask = ip_parts[2]:match("^%s*(.-)%s*$") or "N/A"
                end
            else
                interface_info.ip = "N/A"
            end
        else
            interface_info.ip = "N/A"
        end
        
        -- MAC
        local mac_cmd = "cat /sys/class/net/" .. iface .. "/address 2>/dev/null"
        interface_info.mac = exec(mac_cmd) or "N/A"
        
        -- Gateway (para la interfaz activa)
        if interface_info.connected and interface_info.ip ~= "N/A" then
            -- Intentar obtener gateway específico de la interfaz
            local gateway_cmd = "ip route | grep " .. iface .. " | grep default | awk '{print $3}' | head -1"
            interface_info.gateway = exec(gateway_cmd) or "N/A"
            
            -- Si no hay gateway específico, obtener el gateway por defecto
            if interface_info.gateway == "N/A" then
                local default_gateway_cmd = "ip route | grep default | awk '{print $3}' | head -1"
                interface_info.gateway = exec(default_gateway_cmd) or "N/A"
            end
        else
            interface_info.gateway = "N/A"
        end
        
        table.insert(result.interfaces, interface_info)
    end
end

return result
