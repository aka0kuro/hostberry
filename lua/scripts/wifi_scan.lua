-- Script Lua para escanear redes WiFi
-- Usa nmcli, iw, o iwlist dependiendo de lo disponible

local result = {}
result.networks = {}

-- Obtener interfaz WiFi (del parámetro o detectar automáticamente, con sudo)
local interface = params.interface or ""
if interface == "" then
    -- Detectar automáticamente
    local nmcli_iface = exec("sudo nmcli -t -f DEVICE,TYPE dev status 2>/dev/null | grep wifi | head -1 | cut -d: -f1")
    if nmcli_iface and nmcli_iface ~= "" then
        interface = string.gsub(nmcli_iface, "%s+", "")
    else
        -- Fallback: buscar wlan*
        local ip_iface = exec("ip -o link show | awk -F': ' '{print $2}' | grep -E '^wlan|^wl' | head -1")
        if ip_iface and ip_iface ~= "" then
            interface = string.gsub(ip_iface, "%s+", "")
        else
            interface = "wlan0"
        end
    end
end

log("INFO", "Usando interfaz WiFi: " .. interface)

-- Verificar que WiFi esté habilitado (usar rfkill en lugar de nmcli)
local wifi_enabled = false
local rfkill_check = exec("sudo rfkill list wifi 2>/dev/null")
if rfkill_check then
    local rfkill_lower = string.lower(rfkill_check)
    if not string.find(rfkill_lower, "hard blocked: yes") and not string.find(rfkill_lower, "soft blocked: yes") then
        wifi_enabled = true
    end
end

-- Si rfkill no está disponible, verificar con nmcli (pero no fallar si no está)
if not wifi_enabled then
    local nmcli_check = exec("sudo nmcli -t -f WIFI g 2>/dev/null")
    if nmcli_check then
        local nmcli_lower = string.lower(nmcli_check)
        wifi_enabled = string.find(nmcli_lower, "enabled") or string.find(nmcli_lower, "on")
    end
end

-- Si aún no está habilitado, verificar que la interfaz esté activa
if not wifi_enabled then
    local ip_check = exec("ip link show " .. interface .. " 2>/dev/null | grep -i 'state UP'")
    if ip_check and ip_check ~= "" then
        wifi_enabled = true
        log("INFO", "WiFi habilitado (interfaz activa)")
    end
end

if not wifi_enabled then
    log("WARN", "WiFi no está habilitado")
    result.success = false
    result.error = "WiFi no está habilitado"
    result.count = 0
    return result
end

-- Asegurar que la interfaz esté en modo managed (no AP) para poder escanear
-- Si está en modo AP, no podrá escanear
local iw_info = exec("iw dev " .. interface .. " info 2>/dev/null")
if iw_info then
    if string.find(iw_info, "type AP") then
        log("WARN", "Interfaz está en modo AP, no se puede escanear. Necesita estar en modo managed.")
        -- Intentar cambiar a modo managed temporalmente
        exec("sudo iw dev " .. interface .. " set type managed 2>/dev/null")
        os.execute("sleep 1")
    end
end

-- Método 1: Intentar usar nmcli primero (solo si NetworkManager está corriendo)
local nmcli_output, nmcli_err = nil, nil
if exec("pgrep NetworkManager > /dev/null 2>&1") == "" then
    log("INFO", "NetworkManager no está corriendo, usando iw directamente")
else
    local nmcli_cmd = "sudo nmcli -t -f SSID,SIGNAL,SECURITY,CHAN dev wifi list 2>&1"
    nmcli_output, nmcli_err = exec(nmcli_cmd)
end

if not nmcli_err and nmcli_output and nmcli_output ~= "" then
    log("INFO", "Usando nmcli para escanear")
    -- Parsear salida de nmcli (formato: SSID:SIGNAL:SECURITY:CHAN)
    for line in nmcli_output:gmatch("[^\r\n]+") do
        line = string.gsub(line, "^%s+", "")
        line = string.gsub(line, "%s+$", "")
        if line ~= "" and not string.find(line, "Error") and not string.find(line, "permission") then
            local parts = {}
            for part in string.gmatch(line, "([^:]+)") do
                table.insert(parts, part)
            end
            if #parts >= 2 then
                local ssid = parts[1]
                local signal = tonumber(parts[2]) or 0
                local security = parts[3] or "Open"
                local channel = parts[4] or ""
                
                if ssid and ssid ~= "" and ssid ~= "--" then
                    table.insert(result.networks, {
                        ssid = ssid,
                        signal = signal,
                        security = security,
                        channel = channel,
                        encrypted = security ~= "" and security ~= "Open" and security ~= "--"
                    })
                end
            end
        end
    end
end

-- Método 2: Usar iw directamente (más confiable cuando NetworkManager no está disponible)
if #result.networks == 0 then
    log("INFO", "Escaneando con iw en interfaz " .. interface)
    -- Asegurar que la interfaz esté activa
    exec("sudo ip link set " .. interface .. " up 2>/dev/null")
    os.execute("sleep 1")
    
    local iw_cmd = "sudo iw dev " .. interface .. " scan 2>&1"
    local iw_output, iw_err = exec(iw_cmd)
    
    if not iw_err and iw_output and iw_output ~= "" then
        local current_network = {}
        for line in iw_output:gmatch("[^\r\n]+") do
            if string.find(line, "SSID:") then
                if current_network.ssid then
                    table.insert(result.networks, current_network)
                end
                current_network = {}
                local ssid = string.match(line, "SSID: (.+)")
                if ssid then
                    current_network.ssid = ssid
                    current_network.security = "Unknown"
                    current_network.signal = 0
                end
            elseif string.find(line, "signal:") then
                local signal = string.match(line, "signal: (-?%d+)")
                if signal then
                    current_network.signal = tonumber(signal) or 0
                end
            elseif string.find(line, "freq:") then
                local freq = string.match(line, "freq: (%d+)")
                if freq then
                    -- Convertir frecuencia a canal aproximado
                    local f = tonumber(freq)
                    if f >= 2412 and f <= 2484 then
                        current_network.channel = tostring(math.floor((f - 2412) / 5) + 1)
                    elseif f >= 5000 and f <= 5825 then
                        current_network.channel = tostring(math.floor((f - 5000) / 5))
                    end
                end
            end
        end
        if current_network.ssid then
            table.insert(result.networks, current_network)
        end
    end
end

-- Método 3: Fallback a iwlist si aún no hay redes
if #result.networks == 0 then
    log("INFO", "Intentando con iwlist en interfaz " .. interface)
    local iwlist_cmd = "sudo iwlist " .. interface .. " scan 2>&1 | grep -E 'ESSID|Quality|Encryption|Channel' | head -40"
    local iwlist_output, iwlist_err = exec(iwlist_cmd)
    
    if not iwlist_err and iwlist_output and iwlist_output ~= "" then
        local current_network = {}
        for line in iwlist_output:gmatch("[^\r\n]+") do
            if string.find(line, "ESSID:") then
                if current_network.ssid then
                    table.insert(result.networks, current_network)
                end
                current_network = {}
                local ssid = string.match(line, 'ESSID:"(.-)"') or string.match(line, "ESSID:(.+)")
                if ssid then
                    current_network.ssid = string.gsub(ssid, "^%s+", "")
                    current_network.ssid = string.gsub(current_network.ssid, "%s+$", "")
                    current_network.security = "Unknown"
                    current_network.signal = 0
                end
            elseif string.find(line, "Quality=") then
                local signal = string.match(line, "Signal level=(-?%d+)")
                if signal then
                    current_network.signal = tonumber(signal) or 0
                end
            elseif string.find(line, "Encryption") then
                current_network.encrypted = not string.find(line, "key:off")
                current_network.security = current_network.encrypted and "WPA2" or "Open"
            elseif string.find(line, "Channel:") then
                local channel = string.match(line, "Channel:(%d+)")
                if channel then
                    current_network.channel = channel
                end
            end
        end
        if current_network.ssid then
            table.insert(result.networks, current_network)
        end
    end
end

result.count = #result.networks
result.success = true

if result.count == 0 then
    log("WARN", "No se encontraron redes WiFi")
    result.error = "No se encontraron redes. Verifica que WiFi esté habilitado y que haya redes disponibles."
end

return result
