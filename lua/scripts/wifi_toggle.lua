-- Script Lua para activar/desactivar WiFi
-- Usa nmcli, rfkill o ifconfig según disponibilidad

local result = {}
local user = params.user or "unknown"

log("INFO", "Cambiando estado de WiFi (usuario: " .. user .. ")")

-- Método 1: Intentar con nmcli (siempre con sudo)
local nmcli_check = exec("sudo nmcli -t -f WIFI g 2>/dev/null")
if nmcli_check and nmcli_check ~= "" then
    local state = string.lower(string.gsub(nmcli_check, "%s+", ""))
    local cmd
    local was_enabled = false
    
    if string.find(state, "enabled") or string.find(state, "on") then
        cmd = "sudo nmcli radio wifi off"
        was_enabled = true
    else
        cmd = "sudo nmcli radio wifi on"
        was_enabled = false
    end
    
    local output, err = exec(cmd .. " 2>/dev/null")
    if not err then
        -- Si se activó WiFi, también activar la interfaz específica
        if not was_enabled then
            -- Esperar 1 segundo
            os.execute("sleep 1")
            
            -- Detectar y activar la interfaz WiFi específica
            local iface_cmd = "sudo nmcli -t -f DEVICE,TYPE dev status 2>/dev/null | grep wifi | head -1 | cut -d: -f1"
            local iface_out = exec(iface_cmd)
            if iface_out and iface_out ~= "" then
                local iface = string.gsub(iface_out, "%s+", "")
                if iface and iface ~= "" then
                    -- Activar la interfaz específica
                    exec("sudo nmcli device set " .. iface .. " managed yes 2>/dev/null")
                    exec("sudo nmcli device connect " .. iface .. " 2>/dev/null")
                    os.execute("sleep 1")
                end
            end
            
            -- Verificar que se activó
            local verify_check = exec("sudo nmcli -t -f WIFI g 2>/dev/null")
            if verify_check then
                local verify_state = string.lower(string.gsub(verify_check, "%s+", ""))
                if string.find(verify_state, "enabled") or string.find(verify_state, "on") then
                    result.success = true
                    result.message = "WiFi activado exitosamente usando nmcli con sudo"
                    result.method = "nmcli"
                    log("INFO", "WiFi activado exitosamente usando nmcli con sudo")
                    return result
                end
            end
        end
        result.success = true
        result.message = "WiFi toggle exitoso usando nmcli con sudo"
        result.method = "nmcli"
        log("INFO", "WiFi toggle exitoso usando nmcli con sudo")
        return result
    end
end

local rfkill_check = exec("sudo rfkill list wifi 2>/dev/null | grep -i 'wifi' | head -1")
if rfkill_check and rfkill_check ~= "" then
    local status_out = exec("sudo rfkill list wifi 2>/dev/null | grep -i 'soft blocked'")
    local is_blocked = false
    if status_out and string.find(string.lower(status_out), "yes") then
        is_blocked = true
    end
    
    local cmd
    local was_enabled = false
    if is_blocked then
        cmd = "sudo rfkill unblock wifi"
        was_enabled = false
    else
        cmd = "sudo rfkill block wifi"
        was_enabled = true
    end
    
    local output, err = exec(cmd .. " 2>/dev/null")
    if not err then
        -- Si se activó WiFi, también activar la interfaz específica
        if not was_enabled then
            -- Esperar 1 segundo
            os.execute("sleep 1")
            
            -- Detectar y activar la interfaz WiFi específica usando ip
            local iface_cmd = "ip -o link show | awk -F': ' '{print $2}' | grep -E '^wlan|^wl' | head -1"
            local iface_out = exec(iface_cmd)
            if iface_out and iface_out ~= "" then
                local iface = string.gsub(iface_out, "%s+", "")
                if iface and iface ~= "" then
                    -- Activar la interfaz específica
                    exec("sudo ip link set " .. iface .. " up 2>/dev/null")
                    os.execute("sleep 1")
                end
            end
        end
        
        result.success = true
        result.message = "WiFi toggle exitoso usando rfkill con sudo"
        result.method = "rfkill"
        log("INFO", "WiFi toggle exitoso usando rfkill con sudo")
        return result
    end
end

-- Método 2: Intentar con ip/ifconfig (siempre con sudo)
local iw_out = exec("sudo iwconfig 2>/dev/null | grep -i 'wlan' | head -1 | awk '{print $1}'")
if iw_out and iw_out ~= "" then
    local iface = string.gsub(iw_out, "%s+", "")
    if iface and iface ~= "" then
        local status_out = exec("sudo iwconfig " .. iface .. " 2>/dev/null | grep -i 'unassociated'")
        local is_down = false
        if status_out and string.find(string.lower(status_out), "unassociated") then
            is_down = true
        end
        
        local cmd
        if is_down then
            cmd = "sudo ifconfig " .. iface .. " up"
        else
            cmd = "sudo ifconfig " .. iface .. " down"
        end
        
        local output, err = exec(cmd .. " 2>/dev/null")
        if not err then
            result.success = true
            result.message = "WiFi toggle exitoso usando ifconfig con sudo"
            result.method = "ifconfig"
            log("INFO", "WiFi toggle exitoso usando ifconfig con sudo")
            return result
        end
    end
end

-- Si todos los métodos fallan
result.success = false
result.error = "No se pudo cambiar el estado de WiFi. Verifica que tengas permisos sudo configurados (NOPASSWD) o que nmcli/rfkill estén disponibles."
result.message = "Error en WiFi toggle"
log("ERROR", "Error en WiFi toggle: " .. result.error)
return result
