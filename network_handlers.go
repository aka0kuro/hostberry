package main

import (
	"fmt"
	"os/exec"
	"strings"
	"time"
)

// getNetworkInterfaces obtiene la lista de interfaces de red (reemplaza network_interfaces.lua)
// Esta función ya está implementada en handlers.go como fallback, pero la mejoramos aquí
func getNetworkInterfaces() map[string]interface{} {
	result := make(map[string]interface{})
	interfaces := []map[string]interface{}{}

	// Obtener lista de interfaces
	cmd := exec.Command("sh", "-c", "ip -o link show | awk -F': ' '{print $2}'")
	output, err := cmd.Output()
	if err != nil {
		log.Printf("⚠️ Error obteniendo interfaces: %v", err)
		result["interfaces"] = interfaces
		result["success"] = true
		result["count"] = 0
		return result
	}

	lines := strings.Split(strings.TrimSpace(string(output)), "\n")
	log.Printf("📡 Interfaces encontradas: %v", lines)

	for _, ifaceName := range lines {
		ifaceName = strings.TrimSpace(ifaceName)
		if ifaceName == "" || ifaceName == "lo" {
			continue
		}

		// Verificar que la interfaz existe
		ifaceCheckCmd := exec.Command("sh", "-c", fmt.Sprintf("ip link show %s 2>/dev/null", ifaceName))
		if ifaceCheckErr := ifaceCheckCmd.Run(); ifaceCheckErr != nil {
			log.Printf("⚠️ Interface %s no existe o no es accesible, saltando", ifaceName)
			continue
		}

		log.Printf("✅ Procesando interfaz: %s", ifaceName)

		iface := map[string]interface{}{
			"name":  ifaceName,
			"ip":    "N/A",
			"mac":   "N/A",
			"state": "unknown",
		}

		// Obtener estado
		stateCmd := exec.Command("sh", "-c", fmt.Sprintf("cat /sys/class/net/%s/operstate 2>/dev/null", ifaceName))
		if stateOut, err := stateCmd.Output(); err == nil {
			state := strings.TrimSpace(string(stateOut))
			if state == "" {
				// Si operstate está vacío, verificar con ip link show
				ipStateCmd := exec.Command("sh", "-c", fmt.Sprintf("ip link show %s 2>/dev/null | grep -o 'state [A-Z]*' | awk '{print $2}'", ifaceName))
				if ipStateOut, ipStateErr := ipStateCmd.Output(); ipStateErr == nil {
					state = strings.TrimSpace(string(ipStateOut))
				}
				if state == "" {
					state = "unknown"
				}
			}
			iface["state"] = state
		}

		// Para ap0, asegurar que se muestre incluso si está down
		if ifaceName == "ap0" {
			log.Printf("📡 Interfaz ap0 encontrada, estado: %s", iface["state"])
			// Verificar si ap0 está activa, si no, intentar activarla
			if iface["state"] == "down" || iface["state"] == "unknown" {
				log.Printf("⚠️ ap0 está down, intentando activarla...")
				activateCmd := exec.Command("sh", "-c", "sudo ip link set ap0 up 2>/dev/null")
				if activateErr := activateCmd.Run(); activateErr == nil {
					time.Sleep(500 * time.Millisecond)
					// Verificar estado nuevamente
					stateCmd2 := exec.Command("sh", "-c", "cat /sys/class/net/ap0/operstate 2>/dev/null")
					if stateOut2, err2 := stateCmd2.Output(); err2 == nil {
						newState := strings.TrimSpace(string(stateOut2))
						if newState != "" {
							iface["state"] = newState
							log.Printf("✅ ap0 activada, nuevo estado: %s", newState)
						}
					}
				}
			}
		}

		// Para interfaces WiFi (wlan*), verificar también el estado de wpa_supplicant
		if strings.HasPrefix(ifaceName, "wlan") {
			// Verificar si wpa_supplicant reporta conexión
			wpaStatusCmd := exec.Command("sh", "-c", fmt.Sprintf("sudo wpa_cli -i %s status 2>/dev/null | grep 'wpa_state=' | cut -d= -f2", ifaceName))
			if wpaStateOut, err := wpaStatusCmd.Output(); err == nil {
				wpaState := strings.TrimSpace(string(wpaStateOut))
				iface["wpa_state"] = wpaState
				if wpaState == "COMPLETED" {
					// wpa_supplicant dice COMPLETED, pero necesitamos verificar IP más adelante
					iface["state"] = "up"
				} else if wpaState == "ASSOCIATING" || wpaState == "ASSOCIATED" || wpaState == "4WAY_HANDSHAKE" || wpaState == "GROUP_HANDSHAKE" {
					// En proceso de conexión
					iface["state"] = "connecting"
				} else {
					// No conectado
					iface["state"] = "down"
				}
			}
		}

		// Obtener IP (múltiples métodos)
		ipCmd := exec.Command("sh", "-c", fmt.Sprintf("ip addr show %s 2>/dev/null | grep 'inet ' | awk '{print $2}' | head -1", ifaceName))
		if ipOut, err := ipCmd.Output(); err == nil {
			ipLine := strings.TrimSpace(string(ipOut))
			if ipLine != "" {
				parts := strings.Split(ipLine, "/")
				iface["ip"] = parts[0]
				if len(parts) > 1 {
					iface["netmask"] = parts[1]
				}
			}
		}

		// Si no se obtuvo IP, intentar con sudo
		if iface["ip"] == "N/A" || iface["ip"] == "" {
			ipCmdSudo := exec.Command("sh", "-c", fmt.Sprintf("sudo ip addr show %s 2>/dev/null | grep 'inet ' | awk '{print $2}' | head -1", ifaceName))
			if ipOutSudo, err := ipCmdSudo.Output(); err == nil {
				ipLineSudo := strings.TrimSpace(string(ipOutSudo))
				if ipLineSudo != "" {
					parts := strings.Split(ipLineSudo, "/")
					iface["ip"] = parts[0]
					if len(parts) > 1 {
						iface["netmask"] = parts[1]
					}
				}
			}
		}

		// Si aún no hay IP, intentar con ifconfig
		if iface["ip"] == "N/A" || iface["ip"] == "" {
			ifconfigCmd := exec.Command("sh", "-c", fmt.Sprintf("ifconfig %s 2>/dev/null | grep 'inet ' | awk '{print $2}' | head -1", ifaceName))
			if ifconfigOut, err := ifconfigCmd.Output(); err == nil {
				ifconfigLine := strings.TrimSpace(string(ifconfigOut))
				ifconfigLine = strings.TrimPrefix(ifconfigLine, "addr:")
				if ifconfigLine != "" {
					iface["ip"] = ifconfigLine
				}
			}
		}

		// Si aún no hay IP, intentar con hostname -I
		if iface["ip"] == "N/A" || iface["ip"] == "" {
			hostnameCmd := exec.Command("sh", "-c", "hostname -I 2>/dev/null | awk '{print $1}'")
			if hostnameOut, err := hostnameCmd.Output(); err == nil {
				hostnameIP := strings.TrimSpace(string(hostnameOut))
				if hostnameIP != "" {
					checkCmd := exec.Command("sh", "-c", fmt.Sprintf("ip addr show %s 2>/dev/null | grep -q '%s' && echo '%s'", ifaceName, hostnameIP, hostnameIP))
					if checkOut, err := checkCmd.Output(); err == nil {
						checkIP := strings.TrimSpace(string(checkOut))
						if checkIP != "" {
							iface["ip"] = checkIP
						}
					}
				}
			}
		}

		// Si la interfaz está "up" pero no tiene IP, podría estar esperando DHCP
		if (iface["state"] == "up" || iface["state"] == "connected" || iface["state"] == "connecting") && (iface["ip"] == "N/A" || iface["ip"] == "") {
			dhcpCheck := exec.Command("sh", "-c", fmt.Sprintf("ps aux | grep -E '[d]hclient|udhcpc' | grep %s", ifaceName))
			if dhcpOut, err := dhcpCheck.Output(); err == nil {
				dhcpLine := strings.TrimSpace(string(dhcpOut))
				if dhcpLine != "" {
					iface["ip"] = "Obtaining IP..."
				}
			}
		}

		// Para interfaces WiFi, verificar el estado real de conexión
		if strings.HasPrefix(ifaceName, "wlan") {
			if wpaState, hasWpaState := iface["wpa_state"]; hasWpaState && wpaState == "COMPLETED" {
				if iface["ip"] == "N/A" || iface["ip"] == "" || iface["ip"] == "Obtaining IP..." {
					iface["connected"] = false
					iface["state"] = "connecting"
				} else {
					iface["connected"] = true
					iface["state"] = "connected"
				}
			} else if wpaState, hasWpaState := iface["wpa_state"]; hasWpaState && (wpaState == "ASSOCIATING" || wpaState == "ASSOCIATED" || wpaState == "4WAY_HANDSHAKE" || wpaState == "GROUP_HANDSHAKE") {
				iface["connected"] = false
				iface["state"] = "connecting"
			} else {
				iface["connected"] = false
				if iface["state"] != "down" {
					iface["state"] = "down"
				}
			}
		} else {
			// Para interfaces no WiFi
			if iface["ip"] != "N/A" && iface["ip"] != "" && iface["ip"] != "Obtaining IP..." {
				iface["connected"] = true
				if iface["state"] == "up" {
					iface["state"] = "connected"
				}
			} else {
				iface["connected"] = false
			}
		}

	// Obtener MAC
	macCmd := exec.Command("sh", "-c", fmt.Sprintf("cat /sys/class/net/%s/address 2>/dev/null", ifaceName))
	if macOut, err := macCmd.Output(); err == nil {
		mac := strings.TrimSpace(string(macOut))
		if mac != "" {
			iface["mac"] = mac
		}
	}

	// Obtener gateway
	if iface["connected"] == true && iface["ip"] != "N/A" {
		gatewayCmd := exec.Command("sh", "-c", fmt.Sprintf("ip route | grep %s | grep default | awk '{print $3}' | head -1", ifaceName))
		if gatewayOut, err := gatewayCmd.Output(); err == nil {
			gateway := strings.TrimSpace(string(gatewayOut))
			if gateway != "" {
				iface["gateway"] = gateway
			}
		}
		if iface["gateway"] == nil || iface["gateway"] == "" {
			defaultGatewayCmd := exec.Command("sh", "-c", "ip route | grep default | awk '{print $3}' | head -1")
			if defaultGatewayOut, err := defaultGatewayCmd.Output(); err == nil {
				defaultGateway := strings.TrimSpace(string(defaultGatewayOut))
				if defaultGateway != "" {
					iface["gateway"] = defaultGateway
				}
			}
		}
	} else {
		iface["gateway"] = "N/A"
	}

		interfaces = append(interfaces, iface)
	}

	result["interfaces"] = interfaces
	result["success"] = true
	result["count"] = len(interfaces)

	return result
}

// getNetworkStatus obtiene el estado de la red (reemplaza network_status.lua)
func getNetworkStatus() map[string]interface{} {
	result := make(map[string]interface{})

	// Obtener gateway por defecto
	gatewayCmd := exec.Command("sh", "-c", "ip route | grep default | awk '{print $3}' | head -1")
	if gatewayOut, err := gatewayCmd.Output(); err == nil {
		gateway := strings.TrimSpace(string(gatewayOut))
		if gateway != "" {
			result["gateway"] = gateway
		} else {
			result["gateway"] = "N/A"
		}
	} else {
		result["gateway"] = "N/A"
	}

	// Obtener DNS
	dnsCmd := exec.Command("sh", "-c", "cat /etc/resolv.conf 2>/dev/null | grep '^nameserver' | awk '{print $2}' | head -2")
	if dnsOut, err := dnsCmd.Output(); err == nil {
		dnsServers := strings.Split(strings.TrimSpace(string(dnsOut)), "\n")
		dnsList := []string{}
		for _, dns := range dnsServers {
			dns = strings.TrimSpace(dns)
			if dns != "" {
				dnsList = append(dnsList, dns)
			}
		}
		if len(dnsList) > 0 {
			result["dns"] = dnsList
		} else {
			result["dns"] = []string{"N/A"}
		}
	} else {
		result["dns"] = []string{"N/A"}
	}

	// Obtener hostname
	if hostname, err := exec.Command("hostname").Output(); err == nil {
		result["hostname"] = strings.TrimSpace(string(hostname))
	} else {
		result["hostname"] = "unknown"
	}

	return result
}
