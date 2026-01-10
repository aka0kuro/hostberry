-- Script Lua para listar interfaces de red con detalles

local result = {}
result.interfaces = {}

-- Obtener todas las interfaces
local interfaces_cmd = "ip -o link show | awk -F': ' '{print $2}'"
local interfaces_output, exec_error = exec(interfaces_cmd)

if exec_error then
    log("ERROR", "Error ejecutando comando de interfaces: " .. tostring(exec_error))
end

if interfaces_output and interfaces_output ~= "" then
    for iface in interfaces_output:gmatch("[^\r\n]+") do
        iface = iface:match("^%s*(.-)%s*$") -- Trim whitespace
        -- Filtrar loopback y interfaces vacías
        if iface == "" or iface == "lo" then
            goto continue
        end
        
        -- Verificar que la interfaz realmente existe (incluyendo ap0)
        -- Esto asegura que interfaces virtuales como ap0 se muestren
        local iface_check_cmd = "ip link show " .. iface .. " 2>/dev/null"
        local iface_check_output, iface_check_error = exec(iface_check_cmd)
        if iface_check_error or not iface_check_output or iface_check_output == "" then
            log("WARNING", "Interface " .. iface .. " no existe o no es accesible, saltando")
            goto continue
        end
        
        local interface_info = {}
        interface_info.name = iface
        
        -- Estado
        local state_cmd = "cat /sys/class/net/" .. iface .. "/operstate 2>/dev/null"
        local state_output, _ = exec(state_cmd)
        interface_info.state = (state_output and state_output:match("^%s*(.-)%s*$")) or "unknown"
        interface_info.connected = false
        
        -- Para interfaces WiFi (wlan*), verificar también el estado de wpa_supplicant
        if string.find(iface, "^wlan") then
            -- Verificar si wpa_supplicant reporta conexión
            local wpa_state_cmd = "sudo wpa_cli -i " .. iface .. " status 2>/dev/null | grep 'wpa_state=' | cut -d= -f2"
            local wpa_state_output, _ = exec(wpa_state_cmd)
            if wpa_state_output and wpa_state_output ~= "" then
                local wpa_state = wpa_state_output:match("^%s*(.-)%s*$")
                interface_info.wpa_state = wpa_state
                if wpa_state == "COMPLETED" then
                    -- wpa_supplicant dice COMPLETED, pero necesitamos verificar IP más adelante
                    interface_info.state = "up"
                elseif wpa_state == "ASSOCIATING" or wpa_state == "ASSOCIATED" or wpa_state == "4WAY_HANDSHAKE" or wpa_state == "GROUP_HANDSHAKE" then
                    -- En proceso de conexión
                    interface_info.state = "connecting"
                else
                    -- No conectado
                    interface_info.state = "down"
                end
            end
        end
        
        -- IP y máscara de red
        -- Método 1: ip addr show (más confiable) - intentar sin sudo primero
        local ip_cmd = "ip addr show " .. iface .. " 2>/dev/null | grep 'inet ' | awk '{print $2}' | head -1"
        local ip_output, _ = exec(ip_cmd)
        if ip_output and ip_output ~= "" then
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
        
        -- Si no se obtuvo IP, intentar con sudo
        if interface_info.ip == "N/A" or interface_info.ip == "" then
            local ip_cmd_sudo = "sudo ip addr show " .. iface .. " 2>/dev/null | grep 'inet ' | awk '{print $2}' | head -1"
            local ip_output_sudo, _ = exec(ip_cmd_sudo)
            if ip_output_sudo and ip_output_sudo ~= "" then
                local ip_parts_sudo = {}
                for part in ip_output_sudo:gmatch("[^/]+") do
                    table.insert(ip_parts_sudo, part)
                end
                if #ip_parts_sudo > 0 then
                    interface_info.ip = ip_parts_sudo[1]:match("^%s*(.-)%s*$") or "N/A"
                    if #ip_parts_sudo > 1 then
                        interface_info.netmask = ip_parts_sudo[2]:match("^%s*(.-)%s*$") or "N/A"
                    end
                end
            end
        end
        
        -- Si no se obtuvo IP con el método anterior, intentar método alternativo
        if interface_info.ip == "N/A" or interface_info.ip == "" then
            -- Método 2: ifconfig (fallback)
            local ifconfig_cmd = "ifconfig " .. iface .. " 2>/dev/null | grep 'inet ' | awk '{print $2}' | head -1"
            local ifconfig_output, _ = exec(ifconfig_cmd)
            if ifconfig_output and ifconfig_output ~= "" then
                local ifconfig_ip = ifconfig_output:match("^%s*(.-)%s*$")
                -- Limpiar cualquier prefijo (ej: "addr:192.168.1.1" -> "192.168.1.1")
                ifconfig_ip = string.gsub(ifconfig_ip, "^addr:", "")
                if ifconfig_ip and ifconfig_ip ~= "" then
                    interface_info.ip = ifconfig_ip
                end
            end
        end
        
        -- Si aún no hay IP, intentar obtener desde hostname -I
        if interface_info.ip == "N/A" or interface_info.ip == "" then
            -- Método 3: hostname -I y verificar qué IP pertenece a esta interfaz
            local hostname_cmd = "hostname -I 2>/dev/null | awk '{print $1}'"
            local hostname_output, _ = exec(hostname_cmd)
            if hostname_output and hostname_output ~= "" then
                local hostname_ip = hostname_output:match("^%s*(.-)%s*$")
                if hostname_ip and hostname_ip ~= "" then
                    -- Verificar si esta IP está en la interfaz
                    local check_cmd = "ip addr show " .. iface .. " 2>/dev/null | grep -q '" .. hostname_ip .. "' && echo '" .. hostname_ip .. "'"
                    local check_output, _ = exec(check_cmd)
                    if check_output and check_output ~= "" then
                        local check_ip = check_output:match("^%s*(.-)%s*$")
                        if check_ip and check_ip ~= "" then
                            interface_info.ip = check_ip
                        end
                    end
                end
            end
        end
        
        -- Si la interfaz está "up" pero no tiene IP, podría estar esperando DHCP
        if (interface_info.state == "up" or interface_info.state == "connected" or interface_info.state == "connecting") and (interface_info.ip == "N/A" or interface_info.ip == "") then
            -- Verificar si hay un proceso DHCP corriendo
            local dhcp_cmd = "ps aux | grep -E '[d]hclient|udhcpc' | grep " .. iface
            local dhcp_output, _ = exec(dhcp_cmd)
            if dhcp_output and dhcp_output ~= "" then
                interface_info.ip = "Obtaining IP..."
            end
        end
        
        -- Para interfaces WiFi, verificar el estado real de conexión
        if string.find(iface, "^wlan") then
            -- Si wpa_supplicant dice COMPLETED pero no hay IP, aún no está completamente conectado
            if interface_info.wpa_state == "COMPLETED" then
                if interface_info.ip == "N/A" or interface_info.ip == "" or interface_info.ip == "Obtaining IP..." then
                    -- wpa_supplicant conectado pero sin IP aún
                    interface_info.connected = false
                    interface_info.state = "connecting"
                else
                    -- Realmente conectado con IP
                    interface_info.connected = true
                    interface_info.state = "connected"
                end
            elseif interface_info.wpa_state == "ASSOCIATING" or interface_info.wpa_state == "ASSOCIATED" or interface_info.wpa_state == "4WAY_HANDSHAKE" or interface_info.wpa_state == "GROUP_HANDSHAKE" then
                -- En proceso de conexión
                interface_info.connected = false
                interface_info.state = "connecting"
            else
                -- No conectado
                interface_info.connected = false
                if interface_info.state ~= "down" then
                    interface_info.state = "down"
                end
            end
        else
            -- Para interfaces no WiFi, usar el estado del sistema
            if interface_info.ip ~= "N/A" and interface_info.ip ~= "" and interface_info.ip ~= "Obtaining IP..." then
                interface_info.connected = true
                if interface_info.state == "up" then
                    interface_info.state = "connected"
                end
            else
                interface_info.connected = false
            end
        end
        
        -- MAC
        local mac_cmd = "cat /sys/class/net/" .. iface .. "/address 2>/dev/null"
        local mac_output, _ = exec(mac_cmd)
        interface_info.mac = (mac_output and mac_output:match("^%s*(.-)%s*$")) or "N/A"
        
        -- Gateway (para la interfaz activa)
        if interface_info.connected and interface_info.ip ~= "N/A" then
            -- Intentar obtener gateway específico de la interfaz
            local gateway_cmd = "ip route | grep " .. iface .. " | grep default | awk '{print $3}' | head -1"
            local gateway_output, _ = exec(gateway_cmd)
            interface_info.gateway = (gateway_output and gateway_output:match("^%s*(.-)%s*$")) or "N/A"
            
            -- Si no hay gateway específico, obtener el gateway por defecto
            if interface_info.gateway == "N/A" or interface_info.gateway == "" then
                local default_gateway_cmd = "ip route | grep default | awk '{print $3}' | head -1"
                local default_gateway_output, _ = exec(default_gateway_cmd)
                interface_info.gateway = (default_gateway_output and default_gateway_output:match("^%s*(.-)%s*$")) or "N/A"
            end
        else
            interface_info.gateway = "N/A"
        end
        
        table.insert(result.interfaces, interface_info)
        ::continue::
    end
end

-- Asegurar que siempre hay un campo interfaces (aunque esté vacío)
if not result.interfaces then
    result.interfaces = {}
end

result.success = true
result.count = #result.interfaces

return result
