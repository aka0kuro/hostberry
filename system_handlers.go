package main

import (
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

	// CPU usage
	cpuCmd := exec.Command("sh", "-c", "top -bn1 | grep 'Cpu(s)' | sed 's/.*, *\\([0-9.]*\\)%* id.*/\\1/' | awk '{print 100 - $1}'")
	if cpuOut, err := cpuCmd.Output(); err == nil {
		if cpuUsage, err := strconv.ParseFloat(strings.TrimSpace(string(cpuOut)), 64); err == nil {
			result["cpu_usage"] = cpuUsage
		} else {
			result["cpu_usage"] = 0.0
		}
	} else {
		result["cpu_usage"] = 0.0
	}

	// Memory
	memCmd := exec.Command("sh", "-c", "free -m | awk 'NR==2{printf \"%.2f\", $3*100/$2 }'")
	if memOut, err := memCmd.Output(); err == nil {
		if memUsage, err := strconv.ParseFloat(strings.TrimSpace(string(memOut)), 64); err == nil {
			result["memory_usage"] = memUsage
		} else {
			result["memory_usage"] = 0.0
		}
	} else {
		result["memory_usage"] = 0.0
	}

	// Disk
	diskCmd := exec.Command("sh", "-c", "df -h / | awk 'NR==2 {print $5}' | sed 's/%//'")
	if diskOut, err := diskCmd.Output(); err == nil {
		if diskUsage, err := strconv.ParseFloat(strings.TrimSpace(string(diskOut)), 64); err == nil {
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
			result["uptime_seconds"] = uptimeSeconds
		} else {
			result["uptime_seconds"] = 0
		}
	} else {
		result["uptime_seconds"] = 0
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
