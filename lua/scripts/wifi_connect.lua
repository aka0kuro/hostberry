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
local nmcli_cmd = "sudo nmcli device wifi connect '" .. ssid .. "'"
if password and password ~= "" then
    nmcli_cmd = nmcli_cmd .. " password '" .. password .. "'"
end

local output, err = exec(nmcli_cmd)

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
