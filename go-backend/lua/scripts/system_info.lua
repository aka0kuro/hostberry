-- Script Lua para obtener información del sistema
-- Similar a system_stats pero más detallado

local result = {}

-- Información básica del sistema
result.hostname = exec("hostname") or "unknown"
result.kernel_version = exec("uname -r") or "unknown"
result.architecture = exec("uname -m") or "unknown"

-- Procesador
local processor_cmd = "cat /proc/cpuinfo | grep -m1 'model name\\|Processor\\|Hardware' | cut -d ':' -f 2 | sed 's/^[[:space:]]*//'"
result.processor = exec(processor_cmd) or "ARM Processor"

-- OS Version
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

-- Python version (si existe)
local python_version = exec("python3 --version 2>/dev/null") or "N/A"
result.python_version = python_version

-- Uptime
local uptime_cmd = "cat /proc/uptime | awk '{print int($1)}'"
result.uptime_seconds = tonumber(exec(uptime_cmd)) or 0

-- Boot time
local boot_time = os.time() - (result.uptime_seconds or 0)
result.boot_time = boot_time

-- Load average
local loadavg_cmd = "cat /proc/loadavg | awk '{print $1 \", \" $2 \", \" $3}'"
result.load_average = exec(loadavg_cmd) or "0.00, 0.00, 0.00"

return result
