-- Script Lua para activar/desactivar WiFi
-- Usa nmcli, rfkill o ifconfig según disponibilidad

local result = {}
local user = params.user or "unknown"

log("INFO", "Cambiando estado de WiFi (usuario: " .. user .. ")")

-- Método 1: Intentar con nmcli
local nmcli_check = exec("nmcli -t -f WIFI g 2>/dev/null")
if nmcli_check and nmcli_check ~= "" then
    local state = string.lower(string.gsub(nmcli_check, "%s+", ""))
    local cmd
    
    if string.find(state, "enabled") or string.find(state, "on") then
        cmd = "nmcli radio wifi off"
    else
        cmd = "nmcli radio wifi on"
    end
    
    local output, err = exec("sudo " .. cmd .. " 2>/dev/null")
    if not err then
        result.success = true
        result.message = "WiFi toggle exitoso usando nmcli"
        result.method = "nmcli"
        log("INFO", "WiFi toggle exitoso usando nmcli")
        return result
    end
    
    -- Intentar sin sudo
    output, err = exec(cmd .. " 2>/dev/null")
    if not err then
        result.success = true
        result.message = "WiFi toggle exitoso usando nmcli"
        result.method = "nmcli"
        log("INFO", "WiFi toggle exitoso usando nmcli (sin sudo)")
        return result
    end
end

-- Método 2: Intentar con rfkill
local rfkill_check = exec("rfkill list wifi 2>/dev/null | grep -i 'wifi' | head -1")
if rfkill_check and rfkill_check ~= "" then
    local status_out = exec("rfkill list wifi 2>/dev/null | grep -i 'soft blocked'")
    local is_blocked = false
    if status_out and string.find(string.lower(status_out), "yes") then
        is_blocked = true
    end
    
    local cmd
    if is_blocked then
        cmd = "sudo rfkill unblock wifi"
    else
        cmd = "sudo rfkill block wifi"
    end
    
    local output, err = exec(cmd .. " 2>/dev/null")
    if not err then
        result.success = true
        result.message = "WiFi toggle exitoso usando rfkill"
        result.method = "rfkill"
        log("INFO", "WiFi toggle exitoso usando rfkill")
        return result
    end
end

-- Método 3: Intentar con ifconfig
local iw_out = exec("iwconfig 2>/dev/null | grep -i 'wlan' | head -1 | awk '{print $1}'")
if iw_out and iw_out ~= "" then
    local iface = string.gsub(iw_out, "%s+", "")
    if iface and iface ~= "" then
        local status_out = exec("iwconfig " .. iface .. " 2>/dev/null | grep -i 'unassociated'")
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
            result.message = "WiFi toggle exitoso usando ifconfig"
            result.method = "ifconfig"
            log("INFO", "WiFi toggle exitoso usando ifconfig")
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
