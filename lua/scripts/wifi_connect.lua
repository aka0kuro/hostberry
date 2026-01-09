-- Script Lua para conectar a una red WiFi
-- Usa wpa_supplicant directamente y guarda en /etc/wpa_supplicant/wpa_supplicant.conf

local result = {}

local ssid = params.ssid or ""
local password = params.password or ""
local user = params.user or "unknown"
local interface = params.interface or "wlan0"

if ssid == "" then
    result.success = false
    result.error = "SSID requerido"
    return result
end

log("INFO", "Conectando a WiFi: " .. ssid .. " (usuario: " .. user .. ") usando wpa_supplicant")

-- Detener NetworkManager si está corriendo para evitar conflictos
exec("sudo systemctl stop NetworkManager 2>/dev/null || true")

-- Asegurar que wpa_supplicant esté corriendo
local wpa_pid = exec("pgrep -f 'wpa_supplicant.*" .. interface .. "'")
if not wpa_pid or wpa_pid == "" then
    log("INFO", "Iniciando wpa_supplicant en interfaz " .. interface)
    -- Iniciar wpa_supplicant si no está corriendo
    local wpa_config = "/etc/wpa_supplicant/wpa_supplicant-" .. interface .. ".conf"
    if not file_exists(wpa_config) then
        wpa_config = "/etc/wpa_supplicant/wpa_supplicant.conf"
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
os.execute("sleep 3")

-- Verificar el estado de la conexión
local status_cmd = wpa_cli_cmd .. " status"
local status_output = exec(status_cmd)
local connected = false

if status_output then
    if string.find(status_output, "wpa_state=COMPLETED") or string.find(status_output, "ssid=" .. ssid) then
        connected = true
    end
end

if connected then
    result.success = true
    result.message = "Conectado a " .. ssid
    result.output = status_output or ""
    log("INFO", "WiFi conectado exitosamente: " .. ssid)
else
    result.success = false
    result.error = "No se pudo establecer la conexión"
    result.message = "Error conectando a " .. ssid
    log("ERROR", "Error conectando WiFi: " .. ssid)
end

return result
