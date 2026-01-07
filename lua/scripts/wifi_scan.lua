-- Script Lua para escanear redes WiFi
-- Usa iwlist o nmcli dependiendo de lo disponible

local result = {}
result.networks = {}

-- Intentar usar nmcli primero (más moderno)
local nmcli_cmd = "nmcli -t -f SSID,SIGNAL,SECURITY dev wifi list 2>/dev/null"
local nmcli_output, nmcli_err = exec(nmcli_cmd)

if not nmcli_err and nmcli_output and nmcli_output ~= "" then
    -- Parsear salida de nmcli
    for line in nmcli_output:gmatch("[^\r\n]+") do
        local ssid, signal, security = line:match("([^:]+):([^:]+):([^:]+)")
        if ssid and ssid ~= "" then
            table.insert(result.networks, {
                ssid = ssid,
                signal = tonumber(signal) or 0,
                security = security or "Open",
                encrypted = security ~= "" and security ~= "Open"
            })
        end
    end
else
    -- Fallback a iwlist
    local iwlist_cmd = "sudo iwlist wlan0 scan 2>/dev/null | grep -E 'ESSID|Quality|Encryption'"
    local iwlist_output, iwlist_err = exec(iwlist_cmd)
    
    if not iwlist_err and iwlist_output and iwlist_output ~= "" then
        local current_network = {}
        for line in iwlist_output:gmatch("[^\r\n]+") do
            if line:match("ESSID:") then
                if current_network.ssid then
                    table.insert(result.networks, current_network)
                end
                current_network = {}
                current_network.ssid = line:match('ESSID:"(.-)"') or line:match("ESSID:(.+)")
            elseif line:match("Quality=") then
                local signal = line:match("Signal level=(-?%d+)")
                if signal then
                    current_network.signal = tonumber(signal) or 0
                end
            elseif line:match("Encryption") then
                current_network.encrypted = not line:match("key:off")
                current_network.security = current_network.encrypted and "WPA2" or "Open"
            end
        end
        if current_network.ssid then
            table.insert(result.networks, current_network)
        end
    end
end

result.count = #result.networks
result.success = true

return result
