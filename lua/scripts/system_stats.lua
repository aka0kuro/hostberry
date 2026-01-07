-- Script Lua para obtener estadísticas del sistema
-- Este script se ejecuta desde Go y retorna un JSON-like table

local result = {}

-- Función auxiliar para normalizar números (reemplazar coma por punto)
local function normalize_number(str)
    if not str then return nil end
    return str:gsub(",", ".")
end

-- Obtener uso de CPU usando /proc/stat (más confiable y no depende de locale)
local cpu_cmd = "grep 'cpu ' /proc/stat | awk '{usage=($2+$4)*100/($2+$3+$4+$5)} END {print usage}'"
local cpu_output, cpu_err = exec(cpu_cmd)
-- En Lua, si hay error, cpu_err será un string, no nil
if cpu_output and cpu_output ~= "" and (cpu_err == nil or cpu_err == "") then
    cpu_output = normalize_number(cpu_output)
    local cpu_val = tonumber(cpu_output)
    if cpu_val and cpu_val >= 0 and cpu_val <= 100 then
        result.cpu_usage = cpu_val
    else
        result.cpu_usage = 0.0
    end
else
    -- Fallback: usar top
    local cpu_cmd2 = "top -bn1 | grep 'Cpu(s)' | awk -F'id,' '{split($1,a,\"%\"); for(i in a){if(a[i] ~ /^[0-9]/){print 100-a[i];break}}}'"
    local cpu_output2, cpu_err2 = exec(cpu_cmd2)
    if cpu_output2 and cpu_output2 ~= "" and (cpu_err2 == nil or cpu_err2 == "") then
        cpu_output2 = normalize_number(cpu_output2)
        local cpu_val2 = tonumber(cpu_output2)
        if cpu_val2 and cpu_val2 >= 0 and cpu_val2 <= 100 then
            result.cpu_usage = cpu_val2
        else
            result.cpu_usage = 0.0
        end
    else
        result.cpu_usage = 0.0
    end
end

-- Obtener uso de memoria usando free (método simple)
local mem_cmd = "free | grep Mem | awk '{printf \"%.2f\", $3/$2 * 100.0}'"
local mem_output, mem_err = exec(mem_cmd)
if mem_output and mem_output ~= "" and (mem_err == nil or mem_err == "") then
    mem_output = normalize_number(mem_output)
    local mem_val = tonumber(mem_output)
    if mem_val and mem_val >= 0 and mem_val <= 100 then
        result.memory_usage = mem_val
    else
        result.memory_usage = 0.0
    end
else
    result.memory_usage = 0.0
end

-- Obtener uso de disco usando df (método simple)
local disk_cmd = "df / | tail -1 | awk '{print $5}' | sed 's/%//'"
local disk_output, disk_err = exec(disk_cmd)
if disk_output and disk_output ~= "" and (disk_err == nil or disk_err == "") then
    local disk_val = tonumber(disk_output)
    if disk_val and disk_val >= 0 and disk_val <= 100 then
        result.disk_usage = disk_val
    else
        result.disk_usage = 0.0
    end
else
    result.disk_usage = 0.0
end

-- Obtener uptime
local uptime_cmd = "cat /proc/uptime | awk '{print int($1)}'"
local uptime_output = exec(uptime_cmd)
if uptime_output then
    result.uptime = tonumber(uptime_output) or 0
else
    result.uptime = 0
end

-- Obtener temperatura de CPU (Raspberry Pi)
local temp_cmd = "cat /sys/class/thermal/thermal_zone0/temp 2>/dev/null | awk '{print $1/1000}'"
local temp_output = exec(temp_cmd)
if temp_output then
    result.cpu_temperature = tonumber(temp_output) or 0.0
else
    result.cpu_temperature = 0.0
end

-- Obtener número de cores
local cores_cmd = "nproc"
local cores_output = exec(cores_cmd)
if cores_output then
    result.cpu_cores = tonumber(cores_output) or 1
else
    result.cpu_cores = 1
end

-- Obtener información del sistema
local hostname_cmd = "hostname"
result.hostname = exec(hostname_cmd) or "unknown"

local kernel_cmd = "uname -r"
result.kernel_version = exec(kernel_cmd) or "unknown"

local arch_cmd = "uname -m"
result.architecture = exec(arch_cmd) or "unknown"

-- Obtener información del procesador
local processor_cmd = "cat /proc/cpuinfo | grep -m1 'model name\\|Processor\\|Hardware' | cut -d ':' -f 2 | sed 's/^[[:space:]]*//'"
local processor_output = exec(processor_cmd)
if processor_output and processor_output ~= "" then
    result.processor = processor_output
else
    result.processor = "ARM Processor"
end

-- Obtener OS version
local os_version = "Unknown"
local os_release = read_file("/etc/os-release")
if os_release then
    for line in os_release:gmatch("[^\r\n]+") do
        if line:match("^PRETTY_NAME=") then
            os_version = line:match('PRETTY_NAME="(.-)"') or line:match("PRETTY_NAME=(.+)")
            break
        end
    end
end
result.os_version = os_version

-- Obtener load average
local loadavg_cmd = "cat /proc/loadavg | awk '{print $1 \", \" $2 \", \" $3}'"
result.load_average = exec(loadavg_cmd) or "0.00, 0.00, 0.00"

-- Retornar resultado (será convertido a JSON por Go)
return result
