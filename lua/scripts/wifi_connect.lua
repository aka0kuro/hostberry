-- Script Lua para conectar a una red WiFi
-- Usa wpa_supplicant directamente y guarda en /etc/wpa_supplicant/wpa_supplicant.conf

local result = {}

local ssid = params.ssid or ""
local password = params.password or ""
local user = params.user or "unknown"
local interface = params.interface or "wlan0"
local country = params.country or "US"

if ssid == "" then
    result.success = false
    result.error = "SSID requerido"
    return result
end

log("INFO", "Conectando a WiFi: " .. ssid .. " (usuario: " .. user .. ") usando wpa_supplicant")

-- Verificar si NetworkManager está gestionando la conexión activa
-- Si es así, NO detenerlo para evitar perder la sesión web
local nm_active = exec("nmcli -t -f STATE general status 2>/dev/null | head -1")
local nm_connected = false
if nm_active then
    local state = string.gsub(nm_active, "%s+", "")
    if state == "connected" or state == "connecting" then
        nm_connected = true
        log("INFO", "NetworkManager está gestionando una conexión activa, no se detendrá para preservar la sesión")
    end
end

-- Solo detener NetworkManager si NO está gestionando una conexión activa
-- Esto evita perder la sesión web cuando el usuario está conectado
if not nm_connected then
    log("INFO", "Deteniendo NetworkManager para evitar conflictos con wpa_supplicant")
    exec("sudo systemctl stop NetworkManager 2>/dev/null || true")
else
    log("INFO", "NetworkManager permanece activo para mantener la conexión actual")
end

-- Asegurar que la interfaz esté en modo managed (no AP) para poder conectarse
-- Si está en modo AP, cambiarla a managed temporalmente
local iw_info = exec("iw dev " .. interface .. " info 2>/dev/null")
if iw_info then
    if string.find(iw_info, "type AP") then
        log("INFO", "Interfaz está en modo AP, cambiando a modo managed para conexión STA")
        exec("sudo iw dev " .. interface .. " set type managed 2>/dev/null")
        os.execute("sleep 1")
    end
end

-- Asegurar que la interfaz esté activa
exec("sudo ip link set " .. interface .. " up 2>/dev/null")
os.execute("sleep 1")

-- Asegurar que wpa_supplicant esté corriendo
local wpa_pid = exec("pgrep -f 'wpa_supplicant.*" .. interface .. "'")
if not wpa_pid or wpa_pid == "" then
    log("INFO", "Iniciando wpa_supplicant en interfaz " .. interface)
    -- Iniciar wpa_supplicant si no está corriendo
    -- Crear archivo de configuración si no existe
    local wpa_config = "/etc/wpa_supplicant/wpa_supplicant-" .. interface .. ".conf"
    if not file_exists(wpa_config) then
        wpa_config = "/etc/wpa_supplicant/wpa_supplicant.conf"
        -- Si tampoco existe el archivo genérico, crearlo
        if not file_exists(wpa_config) then
            local default_config = "ctrl_interface=DIR=/var/run/wpa_supplicant GROUP=netdev\nupdate_config=1\ncountry=" .. country .. "\n"
            write_file(wpa_config, default_config)
            exec("sudo chmod 600 " .. wpa_config)
        else
            -- Actualizar country en el archivo existente si es necesario
            local config_content = read_file(wpa_config)
            if config_content then
                -- Verificar si ya tiene country configurado
                if not string.find(config_content, "country=") then
                    -- Agregar country al final del archivo
                    local updated_config = config_content .. "\ncountry=" .. country .. "\n"
                    write_file(wpa_config, updated_config)
                    exec("sudo chmod 600 " .. wpa_config)
                    log("INFO", "Added country code " .. country .. " to wpa_supplicant config")
                else
                    -- Actualizar country existente
                    local updated_config = string.gsub(config_content, "country=[A-Z][A-Z]", "country=" .. country)
                    if updated_config ~= config_content then
                        write_file(wpa_config, updated_config)
                        exec("sudo chmod 600 " .. wpa_config)
                        log("INFO", "Updated country code to " .. country .. " in wpa_supplicant config")
                    end
                end
            end
        end
    end
    
    local start_cmd = "sudo wpa_supplicant -B -i " .. interface .. " -c " .. wpa_config
    exec(start_cmd)
    os.execute("sleep 2") -- Esperar a que wpa_supplicant inicie
end

-- Usar wpa_cli para agregar la red a la configuración
local wpa_cli_cmd = "sudo wpa_cli -i " .. interface

-- Verificar si la red ya existe
local list_cmd = wpa_cli_cmd .. " list_networks"
local list_output = exec(list_cmd)
local network_exists = false
local network_id = nil

if list_output then
    for line in string.gmatch(list_output, "[^\r\n]+") do
        if string.find(line, ssid, 1, true) then
            -- Extraer el ID de la red
            local fields = {}
            for field in string.gmatch(line, "%S+") do
                table.insert(fields, field)
            end
            if #fields > 0 then
                network_id = fields[1]
                network_exists = true
                log("INFO", "Red " .. ssid .. " ya existe con ID: " .. network_id)
                break
            end
        end
    end
end

if not network_exists then
    -- Agregar nueva red
    log("INFO", "Agregando nueva red: " .. ssid)
    local add_cmd = wpa_cli_cmd .. " add_network"
    local add_output = exec(add_cmd)
    
    if add_output then
        network_id = string.gsub(add_output, "%s+", "")
        log("INFO", "Red agregada con ID: " .. network_id)
        
        -- Configurar SSID
        local set_ssid_cmd = wpa_cli_cmd .. " set_network " .. network_id .. " ssid '\"" .. ssid .. "\"'"
        exec(set_ssid_cmd)
        
        -- Configurar seguridad
        if password and password ~= "" then
            -- WPA/WPA2
            local set_psk_cmd = wpa_cli_cmd .. " set_network " .. network_id .. " psk '\"" .. password .. "\"'"
            exec(set_psk_cmd)
            local set_key_mgmt_cmd = wpa_cli_cmd .. " set_network " .. network_id .. " key_mgmt WPA-PSK"
            exec(set_key_mgmt_cmd)
        else
            -- Red abierta
            local set_key_mgmt_cmd = wpa_cli_cmd .. " set_network " .. network_id .. " key_mgmt NONE"
            exec(set_key_mgmt_cmd)
        end
        
        -- Habilitar la red
        local enable_cmd = wpa_cli_cmd .. " enable_network " .. network_id
        exec(enable_cmd)
        
        -- Guardar configuración permanentemente
        local save_cmd = wpa_cli_cmd .. " save_config"
        exec(save_cmd)
        
        log("INFO", "Configuración guardada en wpa_supplicant")
    else
        result.success = false
        result.error = "No se pudo agregar la red"
        return result
    end
else
    -- La red ya existe, habilitarla
    log("INFO", "Habilitando red existente: " .. ssid)
    local enable_cmd = wpa_cli_cmd .. " enable_network " .. network_id
    exec(enable_cmd)
    
    -- Si hay una contraseña nueva, actualizarla
    if password and password ~= "" then
        local set_psk_cmd = wpa_cli_cmd .. " set_network " .. network_id .. " psk '\"" .. password .. "\"'"
        exec(set_psk_cmd)
        local save_cmd = wpa_cli_cmd .. " save_config"
        exec(save_cmd)
    end
end

-- Intentar conectar
local select_cmd = wpa_cli_cmd .. " select_network " .. network_id
exec(select_cmd)

-- Esperar un momento para que se establezca la conexión
os.execute("sleep 5")

-- Verificar el estado de la conexión (con múltiples intentos)
local connected = false
local status_output = ""
local max_attempts = 5
local attempt = 0

while attempt < max_attempts and not connected do
    os.execute("sleep 2")
    local status_cmd = wpa_cli_cmd .. " status"
    status_output = exec(status_cmd) or ""
    
    if status_output then
        -- Verificar que realmente esté conectado
        if string.find(status_output, "wpa_state=COMPLETED") then
            -- Verificar que el SSID coincida
            local ssid_match = string.find(status_output, "ssid=" .. ssid, 1, true)
            if ssid_match then
                connected = true
                log("INFO", "WiFi conectado exitosamente: " .. ssid .. " (intento " .. (attempt + 1) .. ")")
                break
            end
        end
    end
    
    attempt = attempt + 1
    if attempt < max_attempts then
        log("INFO", "Esperando conexión... (intento " .. attempt .. "/" .. max_attempts .. ")")
        -- Intentar reconectar
        exec(wpa_cli_cmd .. " reconnect")
    end
end

if connected then
    result.success = true
    result.message = "Conectado a " .. ssid
    result.output = status_output or ""
    log("INFO", "WiFi conectado exitosamente: " .. ssid)
    
    -- Esperar un momento más para que se establezca la IP
    os.execute("sleep 2")
    
    -- Verificar que se obtuvo una IP
    local ip_check = exec("ip addr show " .. interface .. " 2>/dev/null | grep 'inet ' | awk '{print $2}' | cut -d/ -f1 | head -1")
    if ip_check and ip_check ~= "" then
        log("INFO", "IP obtenida: " .. ip_check)
    else
        log("WARNING", "Conectado pero sin IP aún, puede tardar unos segundos más")
    end
else
    result.success = false
    result.error = "No se pudo establecer la conexión después de " .. max_attempts .. " intentos"
    result.message = "Error conectando a " .. ssid
    result.output = status_output or ""
    log("ERROR", "Error conectando WiFi: " .. ssid .. " - Estado: " .. (status_output or "sin respuesta"))
end

return result
