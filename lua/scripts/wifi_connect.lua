-- Script Lua para conectar a una red WiFi
-- Usa nmcli o wpa_supplicant según disponibilidad

local result = {}

local ssid = params.ssid or ""
local password = params.password or ""
local user = params.user or "unknown"

if ssid == "" then
    result.success = false
    result.error = "SSID requerido"
    return result
end

log("INFO", "Conectando a WiFi: " .. ssid .. " (usuario: " .. user .. ")")

-- Intentar con nmcli primero
-- Usar nmcli para guardar la conexión permanentemente
local nmcli_cmd
if password and password ~= "" then
    -- Conectar y guardar la contraseña para reconexión automática
    -- El comando 'nmcli device wifi connect' guarda automáticamente la conexión
    nmcli_cmd = "sudo nmcli device wifi connect '" .. ssid:gsub("'", "'\\''") .. "' password '" .. password:gsub("'", "'\\''") .. "'"
else
    -- Red abierta sin contraseña
    nmcli_cmd = "sudo nmcli device wifi connect '" .. ssid:gsub("'", "'\\''") .. "'"
end

local output, err = exec(nmcli_cmd)

-- Si la conexión fue exitosa, verificar y asegurar que esté guardada
if not err then
    -- Esperar un momento para que NetworkManager guarde la conexión
    os.execute("sleep 1")
    
    -- Verificar que la conexión esté guardada en NetworkManager
    local check_cmd = "sudo nmcli connection show | grep -i '" .. ssid:gsub("'", "'\\''") .. "'"
    local check_output = exec(check_cmd)
    
    if not check_output or check_output == "" then
        -- Si no está guardada, crear una conexión guardada explícitamente
        log("INFO", "Creando conexión guardada para: " .. ssid)
        local save_cmd = "sudo nmcli connection add type wifi con-name '" .. ssid:gsub("'", "'\\''") .. "' ifname '*' ssid '" .. ssid:gsub("'", "'\\''") .. "'"
        if password and password ~= "" then
            save_cmd = save_cmd .. " wifi-sec.key-mgmt wpa-psk wifi-sec.psk '" .. password:gsub("'", "'\\''") .. "'"
        else
            save_cmd = save_cmd .. " wifi-sec.key-mgmt none"
        end
        save_cmd = save_cmd .. " connection.autoconnect yes"
        exec(save_cmd)
    else
        -- Si ya existe, habilitar auto-conexión
        log("INFO", "Habilitando auto-conexión para: " .. ssid)
        local uuid_cmd = "sudo nmcli connection show | grep -i '" .. ssid:gsub("'", "'\\''") .. "' | head -1 | awk '{print $2}'"
        local uuid_output = exec(uuid_cmd)
        if uuid_output and uuid_output ~= "" then
            local uuid = string.gsub(uuid_output, "%s+", "")
            if uuid and uuid ~= "" then
                exec("sudo nmcli connection modify '" .. uuid:gsub("'", "'\\''") .. "' connection.autoconnect yes")
            end
        end
    end
end

if err then
    -- Fallback a wpa_supplicant
    log("INFO", "nmcli falló, intentando con wpa_supplicant")
    
    -- Crear configuración temporal
    local config_file = "/tmp/wpa_supplicant_" .. ssid .. ".conf"
    local config_content = "network={\n"
    config_content = config_content .. "    ssid=\"" .. ssid .. "\"\n"
    if password and password ~= "" then
        config_content = config_content .. "    psk=\"" .. password .. "\"\n"
    else
        config_content = config_content .. "    key_mgmt=NONE\n"
    end
    config_content = config_content .. "}\n"
    
    write_file(config_file, config_content)
    
    -- Conectar
    local wpa_cmd = "sudo wpa_supplicant -B -i wlan0 -c " .. config_file
    output, err = exec(wpa_cmd)
end

if err then
    result.success = false
    result.error = err
    result.message = "Error conectando a WiFi"
    log("ERROR", "Error conectando WiFi: " .. tostring(err))
else
    result.success = true
    result.message = "Conectado a " .. ssid
    result.output = output
    log("INFO", "WiFi conectado exitosamente: " .. ssid)
end

return result
