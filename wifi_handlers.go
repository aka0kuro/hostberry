package main

import (
	"fmt"
	"log"
	"os"
	"os/exec"
	"regexp"
	"strconv"
	"strings"
	"time"
)

// scanWiFiNetworks escanea redes WiFi disponibles (reemplaza wifi_scan.lua)
func scanWiFiNetworks(interfaceName string) map[string]interface{} {
	result := make(map[string]interface{})
	networks := []map[string]interface{}{}

	if interfaceName == "" {
		interfaceName = DefaultWiFiInterface
	}

	// Asegurar que la interfaz esté activa
	executeCommand(fmt.Sprintf("sudo ip link set %s up 2>/dev/null || true", interfaceName))
	time.Sleep(1 * time.Second)

	// Escanear redes usando iw
	scanCmd := exec.Command("sh", "-c", fmt.Sprintf("sudo iw dev %s scan 2>/dev/null | grep -E 'SSID:|signal:|freq:|WPA:|RSN:'", interfaceName))
	scanOut, err := scanCmd.Output()
	if err != nil {
		log.Printf("Error escaneando WiFi: %v", err)
		result["success"] = false
		result["error"] = fmt.Sprintf("Error escaneando redes: %v", err)
		result["networks"] = networks
		return result
	}

	// Parsear salida
	lines := strings.Split(string(scanOut), "\n")
	currentNetwork := make(map[string]interface{})
	
	for _, line := range lines {
		line = strings.TrimSpace(line)
		if strings.HasPrefix(line, "BSS ") {
			// Nueva red, guardar la anterior si existe
			if len(currentNetwork) > 0 && currentNetwork["ssid"] != nil {
				networks = append(networks, currentNetwork)
			}
			currentNetwork = make(map[string]interface{})
		} else if strings.Contains(line, "SSID:") {
			// Extraer SSID
			ssid := strings.TrimPrefix(line, "SSID:")
			ssid = strings.TrimSpace(ssid)
			if ssid != "" {
				currentNetwork["ssid"] = ssid
			}
		} else if strings.Contains(line, "signal:") {
			// Extraer señal
			re := regexp.MustCompile(`signal:\s*(-?\d+\.?\d*)`)
			matches := re.FindStringSubmatch(line)
			if len(matches) > 1 {
				if signalNum, err := strconv.ParseFloat(matches[1], 64); err == nil {
					if signalNum > 0 {
						signalNum = -signalNum
					}
					if signalNum >= -100 && signalNum <= -30 {
						currentNetwork["signal"] = int(signalNum)
					}
				}
			}
		} else if strings.Contains(line, "freq:") {
			// Extraer frecuencia y convertir a canal
			re := regexp.MustCompile(`freq:\s*(\d+)`)
			matches := re.FindStringSubmatch(line)
			if len(matches) > 1 {
				if freq, err := strconv.Atoi(matches[1]); err == nil {
					var channel int
					if freq >= 2412 && freq <= 2484 {
						channel = (freq-2412)/5 + 1
					} else if freq >= 5000 && freq <= 5825 {
						channel = (freq - 5000) / 5
					} else if freq >= 5955 && freq <= 7115 {
						channel = (freq - 5955) / 5
					}
					if channel > 0 {
						currentNetwork["channel"] = channel
					}
				}
			}
		} else if strings.Contains(line, "WPA:") || strings.Contains(line, "RSN:") {
			// Detectar seguridad
			if strings.Contains(line, "WPA3") || strings.Contains(line, "SAE") {
				currentNetwork["security"] = "WPA3"
			} else if strings.Contains(line, "WPA2") || strings.Contains(line, "WPA") {
				currentNetwork["security"] = "WPA2"
			} else {
				currentNetwork["security"] = "Open"
			}
		}
	}

	// Agregar última red
	if len(currentNetwork) > 0 && currentNetwork["ssid"] != nil {
		networks = append(networks, currentNetwork)
	}

	result["success"] = true
	result["networks"] = networks
	result["count"] = len(networks)

	return result
}

// connectWiFi conecta a una red WiFi (reemplaza wifi_connect.lua)
func connectWiFi(ssid, password, interfaceName, country, user string) map[string]interface{} {
	result := make(map[string]interface{})

	if ssid == "" {
		result["success"] = false
		result["error"] = "SSID requerido"
		return result
	}

	if interfaceName == "" {
		interfaceName = DefaultWiFiInterface
	}
	if country == "" {
		country = "US"
	}
	if user == "" {
		user = "unknown"
	}

	log.Printf("Conectando a WiFi: %s (usuario: %s) usando wpa_supplicant", ssid, user)

	// Verificar si NetworkManager está gestionando la conexión activa
	nmActiveCmd := exec.Command("sh", "-c", "nmcli -t -f STATE general status 2>/dev/null | head -1")
	nmActiveOut, _ := nmActiveCmd.Output()
	nmConnected := false
	if strings.TrimSpace(string(nmActiveOut)) == "connected" || strings.TrimSpace(string(nmActiveOut)) == "connecting" {
		nmConnected = true
		log.Printf("NetworkManager está gestionando una conexión activa, no se detendrá para preservar la sesión")
	}

	// Solo detener NetworkManager si NO está gestionando una conexión activa
	if !nmConnected {
		log.Printf("Deteniendo NetworkManager para evitar conflictos con wpa_supplicant")
		executeCommand("sudo systemctl stop NetworkManager 2>/dev/null || true")
	} else {
		log.Printf("NetworkManager permanece activo para mantener la conexión actual")
	}

	// Detener hostapd si está corriendo
	hostapdRunning, _ := exec.Command("sh", "-c", "pgrep hostapd 2>/dev/null").Output()
	if strings.TrimSpace(string(hostapdRunning)) != "" {
		log.Printf("Deteniendo hostapd para liberar la interfaz WiFi")
		executeCommand("sudo systemctl stop hostapd 2>/dev/null || true")
		executeCommand("sudo pkill hostapd 2>/dev/null || true")
		time.Sleep(2 * time.Second)
	}

	// Asegurar que la interfaz esté en modo managed
	iwInfoCmd := exec.Command("sh", "-c", fmt.Sprintf("iw dev %s info 2>/dev/null", interfaceName))
	if iwInfoOut, err := iwInfoCmd.Output(); err == nil {
		if strings.Contains(string(iwInfoOut), "type AP") {
			log.Printf("Interfaz está en modo AP, cambiando a modo managed para conexión STA")
			executeCommand(fmt.Sprintf("sudo iw dev %s set type managed 2>/dev/null", interfaceName))
			time.Sleep(2 * time.Second)
		}
	}

	// Asegurar que la interfaz esté activa y no bloqueada
	executeCommand("sudo rfkill unblock wifi 2>/dev/null || true")
	executeCommand(fmt.Sprintf("sudo ip link set %s down 2>/dev/null", interfaceName))
	time.Sleep(1 * time.Second)
	executeCommand(fmt.Sprintf("sudo ip link set %s up 2>/dev/null", interfaceName))
	time.Sleep(2 * time.Second)

	// Detener cualquier instancia de wpa_supplicant existente
	wpaPid, _ := exec.Command("sh", "-c", fmt.Sprintf("pgrep -f 'wpa_supplicant.*%s'", interfaceName)).Output()
	if strings.TrimSpace(string(wpaPid)) != "" {
		log.Printf("Deteniendo wpa_supplicant existente para reiniciar limpiamente")
		executeCommand(fmt.Sprintf("sudo pkill -f 'wpa_supplicant.*%s' 2>/dev/null || true", interfaceName))
		time.Sleep(2 * time.Second)
	}

	// Asegurar que wpa_supplicant esté corriendo
	wpaPid, _ = exec.Command("sh", "-c", fmt.Sprintf("pgrep -f 'wpa_supplicant.*%s'", interfaceName)).Output()
	if strings.TrimSpace(string(wpaPid)) == "" {
		log.Printf("Iniciando wpa_supplicant en interfaz %s", interfaceName)
		
		wpaConfig := fmt.Sprintf("/etc/wpa_supplicant/wpa_supplicant-%s.conf", interfaceName)
		if _, err := os.Stat(wpaConfig); os.IsNotExist(err) {
			wpaConfig = "/etc/wpa_supplicant/wpa_supplicant.conf"
			if _, err := os.Stat(wpaConfig); os.IsNotExist(err) {
				defaultConfig := fmt.Sprintf("ctrl_interface=DIR=/var/run/wpa_supplicant GROUP=netdev\nupdate_config=1\ncountry=%s\n", country)
				os.WriteFile(wpaConfig, []byte(defaultConfig), 0600)
			} else {
				// Actualizar country en el archivo existente
				configContent, _ := os.ReadFile(wpaConfig)
				configStr := string(configContent)
				if !strings.Contains(configStr, "country=") {
					configStr += fmt.Sprintf("\ncountry=%s\n", country)
					os.WriteFile(wpaConfig, []byte(configStr), 0600)
				} else {
					re := regexp.MustCompile(`country=[A-Z][A-Z]`)
					configStr = re.ReplaceAllString(configStr, fmt.Sprintf("country=%s", country))
					os.WriteFile(wpaConfig, []byte(configStr), 0600)
				}
			}
		}

		// Limpiar el socket de control anterior
		executeCommand(fmt.Sprintf("sudo rm -rf /var/run/wpa_supplicant/%s 2>/dev/null || true", interfaceName))

		startCmd := fmt.Sprintf("sudo wpa_supplicant -B -i %s -c %s -D nl80211,wext", interfaceName, wpaConfig)
		startOut, _ := executeCommand(startCmd)
		log.Printf("wpa_supplicant start output: %s", strings.TrimSpace(startOut))
		time.Sleep(3 * time.Second)

		// Verificar que wpa_supplicant se inició
		wpaPid, _ = exec.Command("sh", "-c", fmt.Sprintf("pgrep -f 'wpa_supplicant.*%s'", interfaceName)).Output()
		if strings.TrimSpace(string(wpaPid)) == "" {
			log.Printf("ERROR: wpa_supplicant no se inició correctamente")
			result["success"] = false
			result["error"] = "No se pudo iniciar wpa_supplicant"
			return result
		} else {
			log.Printf("wpa_supplicant iniciado correctamente con PID: %s", strings.TrimSpace(string(wpaPid)))
		}
	}

	// Usar wpa_cli para agregar la red
	wpaCliCmd := fmt.Sprintf("sudo wpa_cli -i %s", interfaceName)

	// Verificar si la red ya existe
	listCmd := fmt.Sprintf("%s list_networks", wpaCliCmd)
	listOut, _ := executeCommand(listCmd)
	networkExists := false
	networkID := ""

	if strings.Contains(listOut, ssid) {
		// La red existe, extraer ID
		lines := strings.Split(listOut, "\n")
		for _, line := range lines {
			fields := strings.Fields(line)
			if len(fields) > 0 && strings.Contains(line, ssid) {
				networkID = fields[0]
				networkExists = true
				log.Printf("Red %s ya existe con ID: %s", ssid, networkID)
				break
			}
		}
	}

	if !networkExists {
		// Agregar nueva red
		log.Printf("Agregando nueva red: %s", ssid)
		addCmd := fmt.Sprintf("%s add_network", wpaCliCmd)
		addOut, _ := executeCommand(addCmd)
		networkID = strings.TrimSpace(addOut)
		log.Printf("Red agregada con ID: %s", networkID)

		// Configurar SSID
		setSsidCmd := fmt.Sprintf("%s set_network %s ssid '\"%s\"'", wpaCliCmd, networkID, ssid)
		ssidResult, _ := executeCommand(setSsidCmd)
		log.Printf("SSID set result: %s", strings.TrimSpace(ssidResult))

		// Configurar seguridad
		if password != "" {
			setPskCmd := fmt.Sprintf("%s set_network %s psk '\"%s\"'", wpaCliCmd, networkID, password)
			pskResult, _ := executeCommand(setPskCmd)
			log.Printf("PSK set result: %s", strings.TrimSpace(pskResult))
			setKeyMgmtCmd := fmt.Sprintf("%s set_network %s key_mgmt WPA-PSK", wpaCliCmd, networkID)
			keyMgmtResult, _ := executeCommand(setKeyMgmtCmd)
			log.Printf("Key management set result: %s", strings.TrimSpace(keyMgmtResult))
		} else {
			setKeyMgmtCmd := fmt.Sprintf("%s set_network %s key_mgmt NONE", wpaCliCmd, networkID)
			keyMgmtResult, _ := executeCommand(setKeyMgmtCmd)
			log.Printf("Key management (NONE) set result: %s", strings.TrimSpace(keyMgmtResult))
		}

		// Habilitar la red
		enableCmd := fmt.Sprintf("%s enable_network %s", wpaCliCmd, networkID)
		executeCommand(enableCmd)

		// Guardar configuración
		saveCmd := fmt.Sprintf("%s save_config", wpaCliCmd)
		executeCommand(saveCmd)
		log.Printf("Configuración guardada en wpa_supplicant")
	} else {
		// La red ya existe, habilitarla
		log.Printf("Habilitando red existente: %s", ssid)
		enableCmd := fmt.Sprintf("%s enable_network %s", wpaCliCmd, networkID)
		executeCommand(enableCmd)

		// Si hay una contraseña nueva, actualizarla
		if password != "" {
			setPskCmd := fmt.Sprintf("%s set_network %s psk '\"%s\"'", wpaCliCmd, networkID, password)
			executeCommand(setPskCmd)
			saveCmd := fmt.Sprintf("%s save_config", wpaCliCmd)
			executeCommand(saveCmd)
		}
	}

	// Deshabilitar todas las redes primero
	executeCommand(fmt.Sprintf("%s disable_network all", wpaCliCmd))

	// Intentar conectar
	selectCmd := fmt.Sprintf("%s select_network %s", wpaCliCmd, networkID)
	selectResult, _ := executeCommand(selectCmd)
	log.Printf("select_network result: %s", strings.TrimSpace(selectResult))

	// Habilitar la red específica
	enableCmd := fmt.Sprintf("%s enable_network %s", wpaCliCmd, networkID)
	enableResult, _ := executeCommand(enableCmd)
	log.Printf("enable_network result: %s", strings.TrimSpace(enableResult))

	// Reconectar explícitamente
	executeCommand(fmt.Sprintf("%s reconnect", wpaCliCmd))
	time.Sleep(3 * time.Second)

	// Verificar el estado de la conexión (con múltiples intentos)
	connected := false
	statusOutput := ""
	maxAttempts := 8

	for attempt := 0; attempt < maxAttempts && !connected; attempt++ {
		time.Sleep(3 * time.Second)
		statusCmd := fmt.Sprintf("%s status", wpaCliCmd)
		statusOutput, _ = executeCommand(statusCmd)
		log.Printf("Connection status (attempt %d): %s", attempt+1, strings.TrimSpace(statusOutput))

		if strings.Contains(statusOutput, "wpa_state=COMPLETED") {
			if strings.Contains(statusOutput, fmt.Sprintf("ssid=%s", ssid)) {
				connected = true
				log.Printf("WiFi conectado exitosamente: %s (intento %d)", ssid, attempt+1)
				break
			} else {
				log.Printf("wpa_state=COMPLETED pero SSID no coincide")
			}
		} else {
			// Extraer wpa_state para debugging
			re := regexp.MustCompile(`wpa_state=([^\r\n]+)`)
			matches := re.FindStringSubmatch(statusOutput)
			if len(matches) > 1 {
				log.Printf("Estado wpa_state: %s", matches[1])
			}
		}

		if attempt < maxAttempts-1 && !connected {
			log.Printf("Esperando conexión... (intento %d/%d)", attempt+1, maxAttempts)
			executeCommand(fmt.Sprintf("%s reconnect", wpaCliCmd))
		}
	}

	if connected {
		// Esperar más tiempo para que se establezca la IP
		log.Printf("wpa_supplicant reporta conexión, esperando IP...")
		ipObtained := false
		ipWaitAttempts := 10

		for ipWait := 0; ipWait < ipWaitAttempts && !ipObtained; ipWait++ {
			time.Sleep(2 * time.Second)
			ipCheckCmd := exec.Command("sh", "-c", fmt.Sprintf("ip addr show %s 2>/dev/null | grep 'inet ' | awk '{print $2}' | cut -d/ -f1 | head -1", interfaceName))
			if ipOut, err := ipCheckCmd.Output(); err == nil {
				ip := strings.TrimSpace(string(ipOut))
				if ip != "" && ip != "N/A" {
					ipObtained = true
					log.Printf("IP obtenida: %s", ip)
					result["success"] = true
					result["message"] = fmt.Sprintf("Conectado a %s (IP: %s)", ssid, ip)
					result["output"] = statusOutput
					result["ip"] = ip
					log.Printf("WiFi conectado exitosamente: %s con IP %s", ssid, ip)
				} else {
					ipWait++
					log.Printf("Esperando IP... (intento %d/%d)", ipWait, ipWaitAttempts)
					// Verificar si hay un proceso DHCP corriendo
					dhcpCheck := exec.Command("sh", "-c", fmt.Sprintf("ps aux | grep -E '[d]hclient|udhcpc' | grep %s", interfaceName))
					if dhcpOut, _ := dhcpCheck.Output(); len(dhcpOut) == 0 {
						// No hay DHCP corriendo, intentar iniciarlo
						log.Printf("No hay DHCP corriendo, intentando obtener IP...")
						executeCommand(fmt.Sprintf("sudo dhclient -v %s 2>/dev/null || sudo udhcpc -i %s 2>/dev/null || true", interfaceName, interfaceName))
					}
				}
			}
		}

		if !ipObtained {
			log.Printf("WARNING: Conectado a WiFi pero sin IP después de %d segundos", ipWaitAttempts*2)
			result["success"] = true
			result["message"] = fmt.Sprintf("Conectado a %s (obteniendo IP...)", ssid)
			result["output"] = statusOutput
			result["warning"] = "Conectado pero sin IP asignada aún"
		}
	} else {
		result["success"] = false
		result["error"] = fmt.Sprintf("No se pudo establecer la conexión después de %d intentos", maxAttempts)
		result["message"] = fmt.Sprintf("Error conectando a %s", ssid)
		result["output"] = statusOutput
		log.Printf("ERROR: Error conectando WiFi: %s - Estado: %s", ssid, statusOutput)
	}

	return result
}

// toggleWiFi habilita o deshabilita WiFi (reemplaza wifi_toggle.lua)
func toggleWiFi(interfaceName string, enable bool) map[string]interface{} {
	result := make(map[string]interface{})

	if interfaceName == "" {
		interfaceName = DefaultWiFiInterface
	}

	if enable {
		// Habilitar WiFi
		executeCommand("sudo rfkill unblock wifi 2>/dev/null || true")
		executeCommand(fmt.Sprintf("sudo ip link set %s up 2>/dev/null || true", interfaceName))
		result["success"] = true
		result["message"] = "WiFi habilitado"
		result["enabled"] = true
	} else {
		// Deshabilitar WiFi
		executeCommand("sudo rfkill block wifi 2>/dev/null || true")
		executeCommand(fmt.Sprintf("sudo ip link set %s down 2>/dev/null || true", interfaceName))
		result["success"] = true
		result["message"] = "WiFi deshabilitado"
		result["enabled"] = false
	}

	return result
}
