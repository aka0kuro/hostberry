package main

import (
	"fmt"
	"os"
	"os/exec"
	"strconv"
	"strings"
	"time"
)

// getSystemInfo obtiene información del sistema (reemplaza system_info.lua)
func getSystemInfo() map[string]interface{} {
	result := make(map[string]interface{})

	// Hostname
	if hostname, err := exec.Command("hostname").Output(); err == nil {
		result["hostname"] = strings.TrimSpace(string(hostname))
	} else {
		result["hostname"] = "unknown"
	}

	// Kernel version
	if kernel, err := exec.Command("uname", "-r").Output(); err == nil {
		result["kernel_version"] = strings.TrimSpace(string(kernel))
	} else {
		result["kernel_version"] = "unknown"
	}

	// Architecture
	if arch, err := exec.Command("uname", "-m").Output(); err == nil {
		result["architecture"] = strings.TrimSpace(string(arch))
	} else {
		result["architecture"] = "unknown"
	}

	// Processor
	processorCmd := exec.Command("sh", "-c", "cat /proc/cpuinfo | grep -m1 'model name\\|Processor\\|Hardware' | cut -d ':' -f 2 | sed 's/^[[:space:]]*//'")
	if processor, err := processorCmd.Output(); err == nil {
		result["processor"] = strings.TrimSpace(string(processor))
	} else {
		result["processor"] = "ARM Processor"
	}

	// OS Version
	osVersion := "Unknown"
	if osRelease, err := os.ReadFile("/etc/os-release"); err == nil {
		lines := strings.Split(string(osRelease), "\n")
		for _, line := range lines {
			if strings.HasPrefix(line, "PRETTY_NAME=") {
				osVersion = strings.Trim(strings.TrimPrefix(line, "PRETTY_NAME="), "\"")
				break
			}
		}
	}
	result["os_version"] = osVersion

	// Uptime
	uptimeCmd := exec.Command("sh", "-c", "cat /proc/uptime | awk '{print int($1)}'")
	if uptimeOut, err := uptimeCmd.Output(); err == nil {
		if uptimeSeconds, err := strconv.Atoi(strings.TrimSpace(string(uptimeOut))); err == nil {
			result["uptime_seconds"] = uptimeSeconds
			result["boot_time"] = time.Now().Unix() - int64(uptimeSeconds)
		} else {
			result["uptime_seconds"] = 0
			result["boot_time"] = time.Now().Unix()
		}
	} else {
		result["uptime_seconds"] = 0
		result["boot_time"] = time.Now().Unix()
	}

	// Load average
	loadavgCmd := exec.Command("sh", "-c", "cat /proc/loadavg | awk '{print $1 \", \" $2 \", \" $3}'")
	if loadavg, err := loadavgCmd.Output(); err == nil {
		result["load_average"] = strings.TrimSpace(string(loadavg))
	} else {
		result["load_average"] = "0.00, 0.00, 0.00"
	}

	return result
}

// getSystemStats obtiene estadísticas del sistema (reemplaza system_stats.lua)
func getSystemStats() map[string]interface{} {
	result := make(map[string]interface{})

	// CPU usage - método 1: /proc/stat
	cpuCmd := exec.Command("sh", "-c", "grep 'cpu ' /proc/stat | awk '{usage=($2+$4)*100/($2+$3+$4+$5)} END {print usage}'")
	if cpuOut, err := cpuCmd.Output(); err == nil {
		cpuStr := strings.TrimSpace(string(cpuOut))
		cpuStr = strings.ReplaceAll(cpuStr, ",", ".")
		if cpuUsage, err := strconv.ParseFloat(cpuStr, 64); err == nil && cpuUsage >= 0 && cpuUsage <= 100 {
			result["cpu_usage"] = cpuUsage
		} else {
			// Fallback: usar top
			cpuCmd2 := exec.Command("sh", "-c", "top -bn1 | grep 'Cpu(s)' | awk -F'id,' '{split($1,a,\"%\"); for(i in a){if(a[i] ~ /^[0-9]/){print 100-a[i];break}}}'")
			if cpuOut2, err2 := cpuCmd2.Output(); err2 == nil {
				cpuStr2 := strings.TrimSpace(string(cpuOut2))
				cpuStr2 = strings.ReplaceAll(cpuStr2, ",", ".")
				if cpuUsage2, err2 := strconv.ParseFloat(cpuStr2, 64); err2 == nil && cpuUsage2 >= 0 && cpuUsage2 <= 100 {
					result["cpu_usage"] = cpuUsage2
				} else {
					result["cpu_usage"] = 0.0
				}
			} else {
				result["cpu_usage"] = 0.0
			}
		}
	} else {
		result["cpu_usage"] = 0.0
	}

	// Memory
	memCmd := exec.Command("sh", "-c", "free | grep Mem | awk '{printf \"%.2f\", $3/$2 * 100.0}'")
	if memOut, err := memCmd.Output(); err == nil {
		memStr := strings.TrimSpace(string(memOut))
		memStr = strings.ReplaceAll(memStr, ",", ".")
		if memUsage, err := strconv.ParseFloat(memStr, 64); err == nil && memUsage >= 0 && memUsage <= 100 {
			result["memory_usage"] = memUsage
		} else {
			result["memory_usage"] = 0.0
		}
	} else {
		result["memory_usage"] = 0.0
	}

	// Disk
	diskCmd := exec.Command("sh", "-c", "df / | tail -1 | awk '{print $5}' | sed 's/%//'")
	if diskOut, err := diskCmd.Output(); err == nil {
		if diskUsage, err := strconv.ParseFloat(strings.TrimSpace(string(diskOut)), 64); err == nil && diskUsage >= 0 && diskUsage <= 100 {
			result["disk_usage"] = diskUsage
		} else {
			result["disk_usage"] = 0.0
		}
	} else {
		result["disk_usage"] = 0.0
	}

	// Uptime
	uptimeCmd := exec.Command("sh", "-c", "cat /proc/uptime | awk '{print int($1)}'")
	if uptimeOut, err := uptimeCmd.Output(); err == nil {
		if uptimeSeconds, err := strconv.Atoi(strings.TrimSpace(string(uptimeOut))); err == nil {
			result["uptime"] = uptimeSeconds
		} else {
			result["uptime"] = 0
		}
	} else {
		result["uptime"] = 0
	}

	// CPU Temperature (Raspberry Pi)
	tempCmd := exec.Command("sh", "-c", "cat /sys/class/thermal/thermal_zone0/temp 2>/dev/null | awk '{print $1/1000}'")
	if tempOut, err := tempCmd.Output(); err == nil {
		if temp, err := strconv.ParseFloat(strings.TrimSpace(string(tempOut)), 64); err == nil {
			result["cpu_temperature"] = temp
		} else {
			result["cpu_temperature"] = 0.0
		}
	} else {
		result["cpu_temperature"] = 0.0
	}

	// CPU Cores
	coresCmd := exec.Command("nproc")
	if coresOut, err := coresCmd.Output(); err == nil {
		if cores, err := strconv.Atoi(strings.TrimSpace(string(coresOut))); err == nil {
			result["cpu_cores"] = cores
		} else {
			result["cpu_cores"] = 1
		}
	} else {
		result["cpu_cores"] = 1
	}

	// Hostname
	if hostname, err := exec.Command("hostname").Output(); err == nil {
		result["hostname"] = strings.TrimSpace(string(hostname))
	} else {
		result["hostname"] = "unknown"
	}

	// Kernel version
	if kernel, err := exec.Command("uname", "-r").Output(); err == nil {
		result["kernel_version"] = strings.TrimSpace(string(kernel))
	} else {
		result["kernel_version"] = "unknown"
	}

	// Architecture
	if arch, err := exec.Command("uname", "-m").Output(); err == nil {
		result["architecture"] = strings.TrimSpace(string(arch))
	} else {
		result["architecture"] = "unknown"
	}

	// Processor
	processorCmd := exec.Command("sh", "-c", "cat /proc/cpuinfo | grep -m1 'model name\\|Processor\\|Hardware' | cut -d ':' -f 2 | sed 's/^[[:space:]]*//'")
	if processor, err := processorCmd.Output(); err == nil {
		processorStr := strings.TrimSpace(string(processor))
		if processorStr != "" {
			result["processor"] = processorStr
		} else {
			result["processor"] = "ARM Processor"
		}
	} else {
		result["processor"] = "ARM Processor"
	}

	// OS Version
	osVersion := "Unknown"
	if osRelease, err := os.ReadFile("/etc/os-release"); err == nil {
		lines := strings.Split(string(osRelease), "\n")
		for _, line := range lines {
			if strings.HasPrefix(line, "PRETTY_NAME=") {
				osVersion = strings.Trim(strings.TrimPrefix(line, "PRETTY_NAME="), "\"")
				break
			}
		}
	}
	result["os_version"] = osVersion

	// Load average
	loadavgCmd := exec.Command("sh", "-c", "cat /proc/loadavg | awk '{print $1 \", \" $2 \", \" $3}'")
	if loadavg, err := loadavgCmd.Output(); err == nil {
		result["load_average"] = strings.TrimSpace(string(loadavg))
	} else {
		result["load_average"] = "0.00, 0.00, 0.00"
	}

	return result
}

// systemRestart reinicia el sistema (reemplaza system_restart.lua)
func systemRestart(delay int) map[string]interface{} {
	result := make(map[string]interface{})

	if delay < 0 {
		delay = 0
	}

	// Ejecutar comando de reinicio
	cmd := exec.Command("sh", "-c", fmt.Sprintf("sleep %d && sudo reboot", delay))
	if err := cmd.Start(); err != nil {
		result["success"] = false
		result["error"] = err.Error()
		return result
	}

	result["success"] = true
	result["message"] = fmt.Sprintf("Sistema se reiniciará en %d segundos", delay)
	return result
}

// systemShutdown apaga el sistema (reemplaza system_shutdown.lua)
func systemShutdown(delay int) map[string]interface{} {
	result := make(map[string]interface{})

	if delay < 0 {
		delay = 0
	}

	// Ejecutar comando de apagado
	cmd := exec.Command("sh", "-c", fmt.Sprintf("sleep %d && sudo shutdown -h now", delay))
	if err := cmd.Start(); err != nil {
		result["success"] = false
		result["error"] = err.Error()
		return result
	}

	result["success"] = true
	result["message"] = fmt.Sprintf("Sistema se apagará en %d segundos", delay)
	return result
}
