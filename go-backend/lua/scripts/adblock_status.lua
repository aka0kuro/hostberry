-- Script Lua para obtener estado de AdBlock

local result = {}

-- Verificar si AdBlock está activo (dnsmasq o pihole)
local dnsmasq_cmd = "systemctl is-active dnsmasq 2>/dev/null || echo inactive"
local dnsmasq_status = exec(dnsmasq_cmd) or "inactive"

local pihole_cmd = "systemctl is-active pihole-FTL 2>/dev/null || echo inactive"
local pihole_status = exec(pihole_cmd) or "inactive"

result.active = (dnsmasq_status == "active" or pihole_status == "active")
result.type = "none"

if dnsmasq_status == "active" then
    result.type = "dnsmasq"
elseif pihole_status == "active" then
    result.type = "pihole"
end

-- Verificar si hay listas de bloqueo configuradas
if result.active then
    local hosts_file = "/etc/hosts"
    local hosts_content = read_file(hosts_file)
    if hosts_content then
        local blocked_count = 0
        for _ in hosts_content:gmatch("0%.0%.0%.0") do
            blocked_count = blocked_count + 1
        end
        result.blocked_domains = blocked_count
    end
end

result.success = true

return result
