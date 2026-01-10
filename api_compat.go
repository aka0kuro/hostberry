package main

import (
	"encoding/json"
	"fmt"
	"log"
	"os"
	"os/exec"
	"path/filepath"
	"strconv"
	"strings"
	"time"

	"github.com/gofiber/fiber/v2"
)

// ---------- System ----------

func systemActivityHandler(c *fiber.Ctx) error {
	limitStr := c.Query("limit", "10")
	limit := 10
	if v, err := strconvAtoiSafe(limitStr); err == nil && v > 0 && v <= 100 {
		limit = v
	}

	logs, _, err := GetLogs("all", limit, 0)
	if err != nil {
		return c.Status(500).JSON(fiber.Map{"error": err.Error()})
	}

	var activities []fiber.Map
	for _, l := range logs {
		activities = append(activities, fiber.Map{
			"timestamp": l.CreatedAt.Format(time.RFC3339),
			"level":     l.Level,
			"message":   l.Message,
			"source":    l.Source,
		})
	}

	return c.JSON(activities)
}

// /api/v1/system/network (usado por monitoring.js)
func systemNetworkHandler(c *fiber.Ctx) error {
	// best-effort: leer /proc/net/dev (no requiere privilegios)
	out, err := os.ReadFile("/proc/net/dev")
	if err != nil {
		return c.Status(500).JSON(fiber.Map{"error": err.Error()})
	}
	return c.JSON(fiber.Map{"raw": string(out)})
}

func systemUpdatesHandler(c *fiber.Ctx) error {
	// Placeholder: evita 404 y permite UI (actualización real requiere implementación específica del SO)
	return c.JSON(fiber.Map{"available": false})
}

func systemBackupHandler(c *fiber.Ctx) error {
	// Placeholder: por seguridad no generamos backup automático sin path/permiso explícito
	return c.JSON(fiber.Map{"success": false, "message": "Backup no implementado aún"})
}

// ---------- Network ----------

func networkRoutingHandler(c *fiber.Ctx) error {
	out, err := exec.Command("sh", "-c", "ip route 2>/dev/null").CombinedOutput()
	if err != nil {
		log.Printf("⚠️ Error ejecutando ip route: %v, output: %s", err, string(out))
		return c.Status(500).JSON(fiber.Map{"error": strings.TrimSpace(string(out))})
	}
	var routes []fiber.Map
	lines := strings.Split(strings.TrimSpace(string(out)), "\n")
	log.Printf("🔍 Procesando %d líneas de routing table", len(lines))
	
	for _, line := range lines {
		line = strings.TrimSpace(line)
		if line == "" {
			continue
		}
		parts := strings.Fields(line)
		if len(parts) < 1 {
			continue
		}
		route := fiber.Map{"raw": line}
		route["destination"] = parts[0]
		
		// Parsear campos adicionales
		for i := 0; i < len(parts)-1; i++ {
			if parts[i] == "via" && i+1 < len(parts) {
				route["gateway"] = parts[i+1]
			}
			if parts[i] == "dev" && i+1 < len(parts) {
				route["interface"] = parts[i+1]
			}
			if parts[i] == "metric" && i+1 < len(parts) {
				route["metric"] = parts[i+1]
			}
		}
		
		// Si no hay gateway, usar "*"
		if _, hasGateway := route["gateway"]; !hasGateway {
			route["gateway"] = "*"
		}
		
		// Si no hay interfaz, usar "-"
		if _, hasInterface := route["interface"]; !hasInterface {
			route["interface"] = "-"
		}
		
		// Si no hay metric, usar "0"
		if _, hasMetric := route["metric"]; !hasMetric {
			route["metric"] = "0"
		}
		
		routes = append(routes, route)
	}
	
	log.Printf("✅ Devolviendo %d rutas", len(routes))
	return c.JSON(routes)
}

func networkFirewallToggleHandler(c *fiber.Ctx) error {
	return c.Status(501).JSON(fiber.Map{"error": "Firewall toggle no implementado"})
}

func networkConfigHandler(c *fiber.Ctx) error {
	// Si es GET, devolver configuración actual
	if c.Method() == "GET" {
		config := fiber.Map{
			"hostname": "",
			"gateway":  "",
			"dns1":     "",
			"dns2":     "",
		}

		// Obtener hostname
		hostnameCmd := exec.Command("sh", "-c", "hostnamectl --static 2>/dev/null || hostname 2>/dev/null || echo ''")
		if hostnameOut, err := hostnameCmd.Output(); err == nil {
			config["hostname"] = strings.TrimSpace(string(hostnameOut))
		}

		// Obtener gateway por defecto
		gatewayCmd := exec.Command("sh", "-c", "ip route | grep default | awk '{print $3}' | head -1")
		if gatewayOut, err := gatewayCmd.Output(); err == nil {
			gateway := strings.TrimSpace(string(gatewayOut))
			if gateway != "" {
				config["gateway"] = gateway
			}
		}

		// Obtener DNS desde nmcli (si está disponible)
		dnsCmd := exec.Command("sh", "-c", "nmcli -t -f IP4.DNS connection show $(nmcli -t -f NAME connection show --active | head -1) 2>/dev/null | head -2")
		if dnsOut, err := dnsCmd.Output(); err == nil {
			dnsLines := strings.Split(strings.TrimSpace(string(dnsOut)), "\n")
			for i, dns := range dnsLines {
				dns = strings.TrimSpace(dns)
				if dns != "" && strings.Contains(dns, ":") {
					// Formato puede ser "IP4.DNS[1]:8.8.8.8" o solo "8.8.8.8"
					parts := strings.Split(dns, ":")
					if len(parts) > 1 {
						dns = parts[len(parts)-1]
					}
					if i == 0 {
						config["dns1"] = dns
					} else if i == 1 {
						config["dns2"] = dns
					}
				} else if dns != "" && !strings.Contains(dns, ":") {
					// Si no tiene ":", es directamente la IP
					if i == 0 {
						config["dns1"] = dns
					} else if i == 1 {
						config["dns2"] = dns
					}
				}
			}
		}

		// Si no se obtuvieron DNS desde nmcli, intentar con resolvectl
		if config["dns1"] == "" {
			resolveCmd := exec.Command("sh", "-c", "resolvectl dns 2>/dev/null | grep -E '^[0-9]' | awk '{print $2}' | head -2")
			if resolveOut, err := resolveCmd.Output(); err == nil {
				resolveLines := strings.Split(strings.TrimSpace(string(resolveOut)), "\n")
				for i, dns := range resolveLines {
					dns = strings.TrimSpace(dns)
					if dns != "" {
						if i == 0 {
							config["dns1"] = dns
						} else if i == 1 {
							config["dns2"] = dns
						}
					}
				}
			}
		}

		// Si aún no hay DNS, intentar leer desde /etc/resolv.conf
		if config["dns1"] == "" {
			resolvCmd := exec.Command("sh", "-c", "grep '^nameserver' /etc/resolv.conf 2>/dev/null | awk '{print $2}' | head -2")
			if resolvOut, err := resolvCmd.Output(); err == nil {
				resolvLines := strings.Split(strings.TrimSpace(string(resolvOut)), "\n")
				for i, dns := range resolvLines {
					dns = strings.TrimSpace(dns)
					if dns != "" && dns != "127.0.0.1" && dns != "127.0.0.53" {
						if i == 0 {
							config["dns1"] = dns
						} else if i == 1 {
							config["dns2"] = dns
						}
					}
				}
			}
		}

		return c.JSON(config)
	}

	// Si es POST, aplicar configuración
	var req struct {
		Hostname string `json:"hostname"`
		DNS1     string `json:"dns1"`
		DNS2     string `json:"dns2"`
		Gateway  string `json:"gateway"`
	}

	if err := c.BodyParser(&req); err != nil {
		return c.Status(400).JSON(fiber.Map{
			"success": false,
			"error":   "Invalid request body",
		})
	}

	// Validar configuración
	errors := []string{}
	applied := []string{}
	
	// Validar y aplicar hostname
	if req.Hostname != "" {
		if len(req.Hostname) > 64 || len(req.Hostname) < 1 {
			errors = append(errors, "Hostname must be between 1 and 64 characters")
		} else if !strings.ContainsAny(req.Hostname, "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-") {
			errors = append(errors, "Hostname contains invalid characters")
		} else {
			// Aplicar hostname usando hostnamectl
			cmd := fmt.Sprintf("hostnamectl set-hostname %s", req.Hostname)
			if out, err := executeCommand(cmd); err != nil {
				errors = append(errors, fmt.Sprintf("Failed to set hostname: %v", err))
			} else {
				// Actualizar /etc/hosts para evitar el warning de sudo
				// Primero intentar actualizar la línea existente de 127.0.0.1
				hostsUpdateCmd1 := fmt.Sprintf("sed -i 's/^127\\.0\\.0\\.1[[:space:]]*localhost.*/127.0.0.1\\tlocalhost %s/' /etc/hosts 2>/dev/null", req.Hostname)
				executeCommand(hostsUpdateCmd1) // Ignorar errores
				
				// Si no existe la línea, agregarla
				hostsUpdateCmd2 := fmt.Sprintf("grep -q '^127\\.0\\.0\\.1' /etc/hosts || echo '127.0.0.1\\tlocalhost %s' >> /etc/hosts 2>/dev/null", req.Hostname)
				executeCommand(hostsUpdateCmd2) // Ignorar errores
				
				applied = append(applied, fmt.Sprintf("Hostname set to %s", req.Hostname))
				_ = out // Ignorar salida
			}
		}
	}
	
	// Validar y aplicar DNS
	dnsServers := []string{}
	if req.DNS1 != "" {
		// Validar formato IP
		cmd := exec.Command("sh", "-c", fmt.Sprintf("echo '%s' | grep -E '^([0-9]{1,3}\\.){3}[0-9]{1,3}$'", req.DNS1))
		if err := cmd.Run(); err != nil {
			errors = append(errors, "Invalid DNS1 format")
		} else {
			dnsServers = append(dnsServers, req.DNS1)
		}
	}
	
	if req.DNS2 != "" {
		cmd := exec.Command("sh", "-c", fmt.Sprintf("echo '%s' | grep -E '^([0-9]{1,3}\\.){3}[0-9]{1,3}$'", req.DNS2))
		if err := cmd.Run(); err != nil {
			errors = append(errors, "Invalid DNS2 format")
		} else {
			dnsServers = append(dnsServers, req.DNS2)
		}
	}
	
	// Aplicar DNS usando nmcli o systemd-resolved
	if len(dnsServers) > 0 {
		// Intentar con nmcli primero (más común en sistemas con NetworkManager)
		dnsStr := strings.Join(dnsServers, " ")
		cmd := fmt.Sprintf("nmcli connection modify $(nmcli -t -f NAME connection show --active | head -1) ipv4.dns '%s' 2>&1", dnsStr)
		if out, err := executeCommand(cmd); err != nil {
			// Si nmcli falla, intentar con systemd-resolved
			// systemd-resolved requiere editar /etc/systemd/resolved.conf
			// Por ahora, solo reportamos el error de nmcli
			errors = append(errors, fmt.Sprintf("Failed to set DNS: %v (output: %s)", err, out))
		} else {
			// Aplicar cambios de DNS
			applyCmd := "nmcli connection up $(nmcli -t -f NAME connection show --active | head -1) 2>&1"
			if _, err := executeCommand(applyCmd); err != nil {
				// No es crítico si falla el apply, el DNS puede aplicarse en el próximo reinicio
			}
			applied = append(applied, fmt.Sprintf("DNS set to %s", strings.Join(dnsServers, ", ")))
		}
	}
	
	// Validar y aplicar Gateway
	if req.Gateway != "" {
		cmd := exec.Command("sh", "-c", fmt.Sprintf("echo '%s' | grep -E '^([0-9]{1,3}\\.){3}[0-9]{1,3}$'", req.Gateway))
		if err := cmd.Run(); err != nil {
			errors = append(errors, "Invalid Gateway format")
		} else {
			// Aplicar gateway usando nmcli o ip route
			// Intentar con nmcli primero
			nmcliCmd := fmt.Sprintf("nmcli connection modify $(nmcli -t -f NAME connection show --active | head -1) ipv4.gateway %s 2>&1", req.Gateway)
			if out, err := executeCommand(nmcliCmd); err != nil {
				// Si nmcli falla, intentar con ip route
				ipCmd := fmt.Sprintf("ip route replace default via %s 2>&1", req.Gateway)
				if out2, err2 := executeCommand(ipCmd); err2 != nil {
					errors = append(errors, fmt.Sprintf("Failed to set gateway: %v (nmcli: %s, ip: %s)", err2, out, out2))
				} else {
					applied = append(applied, fmt.Sprintf("Gateway set to %s", req.Gateway))
				}
			} else {
				// Aplicar cambios de gateway
				applyCmd := "nmcli connection up $(nmcli -t -f NAME connection show --active | head -1) 2>&1"
				if _, err := executeCommand(applyCmd); err != nil {
					// No es crítico si falla el apply
				}
				applied = append(applied, fmt.Sprintf("Gateway set to %s", req.Gateway))
			}
		}
	}
	
	if len(errors) > 0 {
		errorMsg := strings.Join(errors, "; ")
		if len(applied) > 0 {
			errorMsg += " (Some settings were applied: " + strings.Join(applied, ", ") + ")"
		}
		return c.Status(400).JSON(fiber.Map{
			"success": false,
			"error":   errorMsg,
		})
	}

	// Si todo se aplicó correctamente
	message := "Configuration applied successfully"
	if len(applied) > 0 {
		message = strings.Join(applied, "; ")
	}
	
	return c.JSON(fiber.Map{
		"success": true,
		"message": message,
	})
}

// ---------- WiFi ----------

func wifiNetworksHandler(c *fiber.Ctx) error {
	if luaEngine == nil {
		return c.Status(500).JSON(fiber.Map{"error": "Lua engine no disponible"})
	}
	result, err := luaEngine.Execute("wifi_scan.lua", nil)
	if err != nil {
		return c.Status(500).JSON(fiber.Map{"error": err.Error()})
	}
	// wifi_scan.lua retorna { networks: [...] }
	if v, ok := result["networks"]; ok {
		return c.JSON(v)
	}
	return c.JSON([]fiber.Map{})
}

func wifiClientsHandler(c *fiber.Ctx) error {
	// No hay implementación aún: evita 404
	return c.JSON([]fiber.Map{})
}

func wifiToggleHandler(c *fiber.Ctx) error {
	user := c.Locals("user").(*User)
	userID := user.ID

	// Intentar usar el motor Lua primero (tiene mejor manejo de permisos)
	if luaEngine != nil {
		result, err := luaEngine.Execute("wifi_toggle.lua", fiber.Map{
			"user": user.Username,
		})
		if err == nil && result != nil {
			if success, ok := result["success"].(bool); ok && success {
				InsertLog("INFO", fmt.Sprintf("WiFi toggle exitoso usando Lua (usuario: %s)", user.Username), "wifi", &userID)
				return c.JSON(fiber.Map{"success": true, "message": "WiFi toggle exitoso"})
			}
			if errorMsg, ok := result["error"].(string); ok && errorMsg != "" {
				InsertLog("ERROR", fmt.Sprintf("Error en WiFi toggle (usuario: %s): %s", user.Username, errorMsg), "wifi", &userID)
				return c.Status(500).JSON(fiber.Map{"success": false, "error": errorMsg})
			}
		} else if err != nil {
			// Si hay un error ejecutando el script Lua, continuar con fallback
			InsertLog("WARN", fmt.Sprintf("Error ejecutando script Lua, usando fallback (usuario: %s): %v", user.Username, err), "wifi", &userID)
		}
	}

	// Fallback: Intentar métodos directos usando rfkill e ip (sin nmcli)
	// Método 1: Usar rfkill para habilitar/deshabilitar WiFi
	rfkillOut, rfkillErr := execCommand("rfkill list wifi 2>/dev/null | grep -i 'wifi' | head -1").CombinedOutput()
	if rfkillErr == nil && strings.Contains(strings.ToLower(string(rfkillOut)), "wifi") {
		// Obtener estado actual
		statusOut, _ := execCommand("rfkill list wifi 2>/dev/null | grep -i 'soft blocked'").CombinedOutput()
		isBlocked := strings.Contains(strings.ToLower(string(statusOut)), "yes")
		
		var rfkillCmd string
		var wasEnabled bool
		if isBlocked {
			rfkillCmd = "rfkill unblock wifi"
			wasEnabled = false
		} else {
			rfkillCmd = "rfkill block wifi"
			wasEnabled = true
		}
		
		_, rfkillToggleErr := execCommand(rfkillCmd + " 2>/dev/null").CombinedOutput()
		if rfkillToggleErr == nil {
			// Si se activó WiFi, también activar la interfaz específica
			if !wasEnabled {
				time.Sleep(1 * time.Second)
				
				// Detectar y activar la interfaz WiFi específica usando ip
				ifaceCmd := exec.Command("sh", "-c", "ip -o link show | awk -F': ' '{print $2}' | grep -E '^wlan|^wl' | head -1")
				ifaceOut, ifaceErr := ifaceCmd.Output()
				if ifaceErr == nil {
					iface := strings.TrimSpace(string(ifaceOut))
					if iface != "" {
						// Activar la interfaz específica
						execCommand(fmt.Sprintf("ip link set %s up 2>/dev/null", iface)).Run()
						time.Sleep(1 * time.Second)
					}
				}
			}
			InsertLog("INFO", fmt.Sprintf("WiFi toggle exitoso usando rfkill con sudo (usuario: %s)", user.Username), "wifi", &userID)
			return c.JSON(fiber.Map{"success": true, "message": "WiFi toggle exitoso"})
		}
	}

	// Método 2: Intentar con ip/ifconfig (sin nmcli)
	// Detectar interfaz usando ip
	var iface string
	ipOut, ipErr := exec.Command("sh", "-c", "ip -o link show | awk -F': ' '{print $2}' | grep -E '^wlan|^wl' | head -1").Output()
	if ipErr == nil {
		iface = strings.TrimSpace(string(ipOut))
	}
	
	// Si no se encontró con ip, intentar con iwconfig
	if iface == "" {
		iwOut, iwErr := execCommand("iwconfig 2>/dev/null | grep -i 'wlan' | head -1 | awk '{print $1}'").CombinedOutput()
		if iwErr == nil {
			iface = strings.TrimSpace(string(iwOut))
		}
	}
	
	if iface != "" {
		// Verificar estado actual de la interfaz (sin sudo, solo lectura)
		statusOut, _ := exec.Command("sh", "-c", fmt.Sprintf("ip link show %s 2>/dev/null | grep -i 'state'", iface)).CombinedOutput()
		isDown := strings.Contains(strings.ToLower(string(statusOut)), "down") || strings.Contains(strings.ToLower(string(statusOut)), "disabled")
		
		if isDown {
			// Activar interfaz: primero desbloquear con rfkill, luego activar con ip/ifconfig
			execCommand("rfkill unblock wifi 2>/dev/null").Run()
			execCommand(fmt.Sprintf("ip link set %s up 2>/dev/null", iface)).Run()
			execCommand(fmt.Sprintf("ifconfig %s up 2>/dev/null", iface)).Run()
			time.Sleep(1 * time.Second)
			InsertLog("INFO", fmt.Sprintf("WiFi activado usando ifconfig/ip en interfaz %s (usuario: %s)", iface, user.Username), "wifi", &userID)
			return c.JSON(fiber.Map{"success": true, "message": fmt.Sprintf("WiFi activado en interfaz %s", iface)})
		} else {
			iwCmd := fmt.Sprintf("ifconfig %s down", iface)
			execCommand(iwCmd + " 2>/dev/null").Run()
			InsertLog("INFO", fmt.Sprintf("WiFi desactivado usando ifconfig en interfaz %s (usuario: %s)", iface, user.Username), "wifi", &userID)
			return c.JSON(fiber.Map{"success": true, "message": fmt.Sprintf("WiFi desactivado en interfaz %s", iface)})
		}
	}

	// Si todos los métodos fallan
	errorMsg := "No se pudo cambiar el estado de WiFi. Verifica que tengas permisos sudo configurados (NOPASSWD) o que rfkill/ip estén disponibles. Para configurar sudo sin contraseña, ejecuta: sudo visudo y agrega: usuario ALL=(ALL) NOPASSWD: /usr/sbin/rfkill, /sbin/ip, /sbin/ifconfig"
	InsertLog("ERROR", fmt.Sprintf("Error en WiFi toggle (usuario: %s): %s", user.Username, errorMsg), "wifi", &userID)
	return c.Status(500).JSON(fiber.Map{"success": false, "error": errorMsg})
}

func wifiUnblockHandler(c *fiber.Ctx) error {
	user := c.Locals("user").(*User)
	userID := user.ID

	success := false
	method := ""
	var lastError error

	// Verificar si rfkill está disponible
	rfkillCheck := exec.Command("sh", "-c", "command -v rfkill 2>/dev/null")
	if rfkillCheck.Run() == nil {
		// Verificar si hay WiFi bloqueado
		rfkillOut, rfkillErr := execCommand("rfkill list wifi 2>/dev/null | grep -i 'wifi' | head -1").CombinedOutput()
		if rfkillErr == nil && strings.Contains(strings.ToLower(string(rfkillOut)), "wifi") {
			// Desbloquear
			rfkillCmd := "rfkill unblock wifi"
			rfkillOutSudo, rfkillUnblockErr := execCommand(rfkillCmd + " 2>&1").CombinedOutput()
			if rfkillUnblockErr == nil {
				success = true
				method = "rfkill (con sudo)"
			} else {
				lastError = fmt.Errorf("rfkill error: %s", string(rfkillOutSudo))
			}
		}
	}

	// Método 2: Intentar con nmcli
	if !success {
		nmcliCheck := exec.Command("sh", "-c", "command -v nmcli 2>/dev/null")
		if nmcliCheck.Run() == nil {
			// Intentar habilitar
			nmcliCmd := "nmcli radio wifi on"
			nmcliOut, nmcliErr := execCommand(nmcliCmd + " 2>&1").CombinedOutput()
			if nmcliErr == nil {
				success = true
				method = "nmcli (con sudo)"
			} else {
				if lastError == nil {
					lastError = fmt.Errorf("nmcli error: %s", string(nmcliOut))
				}
			}
		}
	}

	// Si rfkill funcionó, también intentar habilitar con nmcli
	if success && method == "rfkill (con sudo)" {
		nmcliCheck := exec.Command("sh", "-c", "command -v nmcli 2>/dev/null")
		if nmcliCheck.Run() == nil {
			// Intentar habilitar
			execCommand("nmcli radio wifi on 2>/dev/null").Run()
		}
	}

	if success {
		// Esperar un momento para que el cambio se aplique
		time.Sleep(1 * time.Second)
		
		InsertLog("INFO", fmt.Sprintf("WiFi desbloqueado exitosamente usando %s (usuario: %s)", method, user.Username), "wifi", &userID)
		return c.JSON(fiber.Map{"success": true, "message": "WiFi desbloqueado exitosamente"})
	}

	// Si todos los métodos fallan, proporcionar información útil
	errorDetails := "No se pudo desbloquear WiFi."
	if lastError != nil {
		errorDetails += fmt.Sprintf(" Último error: %v", lastError)
	}
	
	// Verificar qué comandos están disponibles
	availableCmds := []string{}
	if exec.Command("sh", "-c", "command -v rfkill 2>/dev/null").Run() == nil {
		availableCmds = append(availableCmds, "rfkill")
	}
	if exec.Command("sh", "-c", "command -v nmcli 2>/dev/null").Run() == nil {
		availableCmds = append(availableCmds, "nmcli")
	}
	
	if len(availableCmds) == 0 {
		errorDetails += " No se encontraron comandos rfkill ni nmcli instalados."
	} else {
		errorDetails += fmt.Sprintf(" Comandos disponibles: %s. Verifica permisos sudo (NOPASSWD) ejecutando: sudo fix_wifi_permissions.sh", strings.Join(availableCmds, ", "))
	}
	
	InsertLog("ERROR", fmt.Sprintf("Error desbloqueando WiFi (usuario: %s): %s", user.Username, errorDetails), "wifi", &userID)
	return c.Status(500).JSON(fiber.Map{"error": errorDetails})
}

func wifiSoftwareSwitchHandler(c *fiber.Ctx) error {
	user := c.Locals("user").(*User)
	userID := user.ID

	// Verificar si rfkill está disponible
	rfkillCheck := exec.Command("sh", "-c", "command -v rfkill 2>/dev/null")
	if rfkillCheck.Run() != nil {
		errorMsg := "rfkill no está disponible en el sistema"
		InsertLog("ERROR", fmt.Sprintf("Error en software switch (usuario: %s): %s", user.Username, errorMsg), "wifi", &userID)
		return c.Status(500).JSON(fiber.Map{"success": false, "error": errorMsg})
	}

	// Obtener estado actual del switch de software (usando execCommand que maneja sudo automáticamente)
	statusOut, _ := execCommand("rfkill list wifi 2>/dev/null | grep -i 'soft blocked'").CombinedOutput()
	statusStr := strings.ToLower(string(statusOut))
	isBlocked := strings.Contains(statusStr, "yes")

	var cmd string
	var action string
	if isBlocked {
		// Desbloquear switch de software
		cmd = "rfkill unblock wifi"
		action = "desbloqueado"
	} else {
		// Bloquear switch de software
		cmd = "rfkill block wifi"
		action = "bloqueado"
	}

	output, err := execCommand(cmd + " 2>&1").CombinedOutput()
	if err != nil {
		errorMsg := fmt.Sprintf("Error ejecutando rfkill: %s", string(output))
		InsertLog("ERROR", fmt.Sprintf("Error en software switch (usuario: %s): %s", user.Username, errorMsg), "wifi", &userID)
		return c.Status(500).JSON(fiber.Map{"success": false, "error": errorMsg})
	}

	// Esperar un momento para que el cambio se aplique
	time.Sleep(1 * time.Second)

	// Verificar el nuevo estado
	newStatusOut, _ := execCommand("rfkill list wifi 2>/dev/null | grep -i 'soft blocked'").CombinedOutput()
	newStatusStr := strings.ToLower(string(newStatusOut))
	newIsBlocked := strings.Contains(newStatusStr, "yes")

	// Verificar que el cambio se aplicó correctamente
	if isBlocked == newIsBlocked {
		errorMsg := "El switch de software no cambió de estado"
		InsertLog("WARN", fmt.Sprintf("Switch de software no cambió (usuario: %s): %s", user.Username, errorMsg), "wifi", &userID)
		return c.Status(500).JSON(fiber.Map{"success": false, "error": errorMsg})
	}

	message := fmt.Sprintf("Switch de software %s exitosamente", action)
	InsertLog("INFO", fmt.Sprintf("Switch de software %s (usuario: %s)", action, user.Username), "wifi", &userID)
	return c.JSON(fiber.Map{
		"success": true,
		"message": message,
		"blocked": newIsBlocked,
	})
}

func wifiConfigHandler(c *fiber.Ctx) error {
	user := c.Locals("user").(*User)
	userID := user.ID
	
	var req struct {
		SSID     string `json:"ssid"`
		Password string `json:"password"`
		Security string `json:"security"`
		Region   string `json:"region"`
	}
	if err := c.BodyParser(&req); err != nil {
		return c.Status(400).JSON(fiber.Map{"error": "Datos inválidos"})
	}
	
	// Si se proporciona región, cambiar la región WiFi
	if req.Region != "" {
		// Validar código de región (2 letras mayúsculas)
		if len(req.Region) != 2 {
			return c.Status(400).JSON(fiber.Map{"error": "Código de región inválido. Debe ser de 2 letras (ej: US, ES, GB)"})
		}
		
		// Convertir a mayúsculas
		req.Region = strings.ToUpper(req.Region)
		
		// Método 1: Intentar cambiar región usando iw reg set (más directo)
		iwCheck := exec.Command("sh", "-c", "command -v iw 2>/dev/null")
		if iwCheck.Run() == nil {
			// Usar iw reg set con captura de salida para debug
			cmd := exec.Command("sh", "-c", fmt.Sprintf("sudo iw reg set %s 2>&1", req.Region))
			out, err := cmd.CombinedOutput()
			output := strings.TrimSpace(string(out))
			
			if err == nil {
				// Verificar que realmente se cambió
				verifyCmd := exec.Command("sh", "-c", "iw reg get 2>&1")
				verifyOut, _ := verifyCmd.CombinedOutput()
				verifyOutput := strings.TrimSpace(string(verifyOut))
				
				if strings.Contains(verifyOutput, req.Region) || output == "" {
					InsertLog("INFO", fmt.Sprintf("Región WiFi cambiada a %s usando iw (usuario: %s)", req.Region, user.Username), "wifi", &userID)
					return c.JSON(fiber.Map{"success": true, "message": "Región WiFi cambiada exitosamente a " + req.Region})
				}
			}
			
			// Si falla, intentar escribir directamente en el archivo de configuración
			// Método alternativo: escribir en /etc/default/crda o crear archivo de configuración
			crdaCmd := exec.Command("sh", "-c", fmt.Sprintf("echo 'REGDOMAIN=%s' | sudo tee /etc/default/crda >/dev/null 2>&1", req.Region))
			if crdaCmd.Run() == nil {
				InsertLog("INFO", fmt.Sprintf("Región WiFi configurada a %s en crda (usuario: %s)", req.Region, user.Username), "wifi", &userID)
				// Intentar aplicar el cambio reiniciando WiFi
				exec.Command("sh", "-c", "sudo nmcli radio wifi off 2>/dev/null").Run()
				time.Sleep(1 * time.Second)
				exec.Command("sh", "-c", "sudo nmcli radio wifi on 2>/dev/null").Run()
				return c.JSON(fiber.Map{"success": true, "message": "Región WiFi configurada exitosamente. WiFi reiniciado para aplicar cambios."})
			}
			
			// Método 3: Intentar escribir en /etc/conf.d/wireless-regdom (Gentoo/Arch)
			regdomCmd := exec.Command("sh", "-c", fmt.Sprintf("echo '%s' | sudo tee /etc/conf.d/wireless-regdom >/dev/null 2>&1", req.Region))
			if regdomCmd.Run() == nil {
				InsertLog("INFO", fmt.Sprintf("Región WiFi configurada a %s en wireless-regdom (usuario: %s)", req.Region, user.Username), "wifi", &userID)
				return c.JSON(fiber.Map{"success": true, "message": "Región WiFi configurada. Reinicia WiFi o el sistema para aplicar cambios."})
			}
		}
		
		// Si iw no está disponible, intentar solo con archivos de configuración
		crdaCmd2 := exec.Command("sh", "-c", fmt.Sprintf("echo 'REGDOMAIN=%s' | sudo tee /etc/default/crda >/dev/null 2>&1", req.Region))
		if crdaCmd2.Run() == nil {
			InsertLog("INFO", fmt.Sprintf("Región WiFi configurada a %s (usuario: %s)", req.Region, user.Username), "wifi", &userID)
			return c.JSON(fiber.Map{"success": true, "message": "Región WiFi configurada. Reinicia WiFi para aplicar cambios."})
		}
		
		// Si todos los métodos fallan, retornar error con instrucciones
		errorMsg := fmt.Sprintf("No se pudo cambiar la región WiFi automáticamente. Verifica que 'iw' esté instalado (sudo apt-get install iw) y que tengas permisos sudo configurados. Puedes configurarlo manualmente ejecutando: sudo iw reg set %s", req.Region)
		InsertLog("ERROR", fmt.Sprintf("Error cambiando región WiFi a %s (usuario: %s): %s", req.Region, user.Username, errorMsg), "wifi", &userID)
		return c.Status(500).JSON(fiber.Map{"error": errorMsg})
	}
	
	// Si se proporciona SSID, conectar a la red
	if req.SSID != "" {
		// Reusar el handler existente conectando
		c.Request().Header.SetContentType(fiber.MIMEApplicationJSON)
		body, _ := json.Marshal(fiber.Map{"ssid": req.SSID, "password": req.Password})
		c.Request().SetBody(body)
		return wifiConnectHandler(c)
	}
	
	return c.Status(400).JSON(fiber.Map{"error": "Se requiere ssid o region"})
}

// ---------- VPN ----------

func vpnConnectionsHandler(c *fiber.Ctx) error {
	// Derivar desde vpn_status.lua (OpenVPN/WireGuard)
	if luaEngine == nil {
		return c.JSON([]fiber.Map{})
	}
	result, err := luaEngine.Execute("vpn_status.lua", nil)
	if err != nil {
		return c.Status(500).JSON(fiber.Map{"error": err.Error()})
	}

	var conns []fiber.Map
	// openvpn
	if ov, ok := result["openvpn"].(map[string]interface{}); ok {
		status := fmt.Sprintf("%v", ov["status"])
		conns = append(conns, fiber.Map{"name": "openvpn", "type": "openvpn", "status": mapActiveStatus(status), "bandwidth": "-"})
	}
	// wireguard
	if wg, ok := result["wireguard"].(map[string]interface{}); ok {
		active := fmt.Sprintf("%v", wg["active"])
		conns = append(conns, fiber.Map{"name": "wireguard", "type": "wireguard", "status": mapBoolStatus(active), "bandwidth": "-"})
	}
	return c.JSON(conns)
}

func vpnServersHandler(c *fiber.Ctx) error  { return c.JSON([]fiber.Map{}) }
func vpnClientsHandler(c *fiber.Ctx) error  { return c.JSON([]fiber.Map{}) }
func vpnToggleHandler(c *fiber.Ctx) error   { return c.Status(501).JSON(fiber.Map{"error": "VPN toggle no implementado"}) }
func vpnConfigHandler(c *fiber.Ctx) error   { return c.Status(501).JSON(fiber.Map{"error": "VPN config no implementado"}) }
func vpnConnectionToggleHandler(c *fiber.Ctx) error {
	return c.Status(501).JSON(fiber.Map{"error": "VPN connection toggle no implementado"})
}
func vpnCertificatesGenerateHandler(c *fiber.Ctx) error {
	return c.Status(501).JSON(fiber.Map{"error": "VPN certificates no implementado"})
}

// ---------- HostAPD ----------

func hostapdAccessPointsHandler(c *fiber.Ctx) error {
	var aps []fiber.Map
	
	// Verificar si hostapd está corriendo (múltiples métodos para mayor confiabilidad)
	hostapdActive := false
	hostapdTransmitting := false // Verificar si realmente está transmitiendo
	
	// Método 1: Verificar con systemctl
	systemctlOut, _ := exec.Command("sh", "-c", "systemctl is-active hostapd 2>/dev/null").CombinedOutput()
	systemctlStatus := strings.TrimSpace(string(systemctlOut))
	if systemctlStatus == "active" {
		hostapdActive = true
	}
	
	// Método 2: Verificar si el proceso está corriendo
	if !hostapdActive {
		pgrepOut, _ := exec.Command("sh", "-c", "pgrep hostapd > /dev/null 2>&1 && echo active || echo inactive").CombinedOutput()
		pgrepStatus := strings.TrimSpace(string(pgrepOut))
		if pgrepStatus == "active" {
			hostapdActive = true
		}
	}
	
	// Método 3: Verificar si realmente está transmitiendo (verificar modo AP)
	// Esto es más confiable que solo verificar el proceso
	if hostapdActive {
		// Intentar obtener la interfaz desde la configuración primero
		// En modo AP+STA, la interfaz será ap0 (virtual), no wlan0
		interfaceName := "ap0" // default para modo AP+STA
		if configContent, err := os.ReadFile("/etc/hostapd/hostapd.conf"); err == nil {
			lines := strings.Split(string(configContent), "\n")
			for _, line := range lines {
				line = strings.TrimSpace(line)
				if strings.HasPrefix(line, "interface=") {
					parts := strings.SplitN(line, "=", 2)
					if len(parts) == 2 {
						interfaceName = strings.TrimSpace(parts[1])
						break
					}
				}
			}
		}
		
		// Verificar con iw si la interfaz está en modo AP
		iwOut, _ := exec.Command("sh", "-c", fmt.Sprintf("iw dev %s info 2>/dev/null | grep -i 'type AP' || iwconfig %s 2>/dev/null | grep -i 'mode:master' || echo ''", interfaceName, interfaceName)).CombinedOutput()
		iwStatus := strings.TrimSpace(string(iwOut))
		if iwStatus != "" {
			hostapdTransmitting = true
		}
		
		// Verificar también con hostapd_cli si está disponible
		if !hostapdTransmitting {
			cliStatusOut, _ := exec.Command("sh", "-c", fmt.Sprintf("hostapd_cli -i %s status 2>/dev/null | grep -i 'state=ENABLED' || echo ''", interfaceName)).CombinedOutput()
			cliStatus := strings.TrimSpace(string(cliStatusOut))
			if cliStatus != "" {
				hostapdTransmitting = true
			}
		}
		
		// Si no está transmitiendo, verificar logs para errores
		if !hostapdTransmitting {
			journalOut, _ := exec.Command("sh", "-c", "sudo journalctl -u hostapd -n 30 --no-pager 2>/dev/null | tail -20").CombinedOutput()
			journalLogs := strings.ToLower(string(journalOut))
			// Verificar errores comunes
			if strings.Contains(journalLogs, "could not configure driver") ||
				strings.Contains(journalLogs, "nl80211: could not") ||
				strings.Contains(journalLogs, "interface") && strings.Contains(journalLogs, "not found") ||
				strings.Contains(journalLogs, "failed to initialize") {
				// Hay errores, el servicio no está transmitiendo realmente
				hostapdTransmitting = false
			}
		}
	}
	
	// Leer configuración de hostapd
	configPath := "/etc/hostapd/hostapd.conf"
	config := make(map[string]string)
	
	if configContent, err := os.ReadFile(configPath); err == nil {
		// Parsear configuración
		lines := strings.Split(string(configContent), "\n")
		for _, line := range lines {
			line = strings.TrimSpace(line)
			if line == "" || strings.HasPrefix(line, "#") {
				continue
			}
			parts := strings.SplitN(line, "=", 2)
			if len(parts) == 2 {
				key := strings.TrimSpace(parts[0])
				value := strings.TrimSpace(parts[1])
				config[key] = value
			}
		}
	}
	
	// Si hostapd está activo o hay configuración, mostrar el punto de acceso
	if hostapdActive || len(config) > 0 {
		ssid := config["ssid"]
		if ssid == "" {
			ssid = "hostberry-ap" // Valor por defecto
		}
		
		interfaceName := config["interface"]
		if interfaceName == "" {
			interfaceName = "wlan0" // Valor por defecto
		}
		
		channel := config["channel"]
		if channel == "" {
			channel = "6" // Valor por defecto
		}
		
		// Determinar seguridad
		security := "WPA2"
		if config["auth_algs"] == "0" {
			security = "Open"
		} else if strings.Contains(config["wpa_key_mgmt"], "SHA256") {
			security = "WPA3"
		} else if config["wpa"] == "2" {
			security = "WPA2"
		}
		
		// Obtener número de clientes conectados
		clientsCount := 0
		if hostapdActive {
			// Intentar obtener clientes usando hostapd_cli
			cliOut, err := exec.Command("sh", "-c", fmt.Sprintf("hostapd_cli -i %s all_sta 2>/dev/null | grep -c '^sta=' || echo 0", interfaceName)).CombinedOutput()
			if err == nil {
				if count, err := strconvAtoiSafe(strings.TrimSpace(string(cliOut))); err == nil {
					clientsCount = count
				}
			}
		}
		
		// El punto de acceso está realmente activo solo si está transmitiendo
		// Si el servicio está corriendo pero no transmite, mostrar como inactivo
		actuallyActive := hostapdActive && hostapdTransmitting
		
		aps = append(aps, fiber.Map{
			"name":          interfaceName,
			"ssid":          ssid,
			"interface":     interfaceName,
			"channel":       channel,
			"security":      security,
			"enabled":       actuallyActive, // Solo true si realmente está transmitiendo
			"active":        actuallyActive, // Solo true si realmente está transmitiendo
			"status":        func() string {
				if actuallyActive {
					return "active"
				} else if hostapdActive {
					return "error" // Servicio corriendo pero no transmite
				}
				return "inactive"
			}(),
			"transmitting":  hostapdTransmitting, // Nuevo campo para diagnóstico
			"service_running": hostapdActive,     // Servicio corriendo (pero puede no transmitir)
			"clients_count": clientsCount,
		})
	}
	
	return c.JSON(aps)
}

func hostapdClientsHandler(c *fiber.Ctx) error {
	// Intentar leer clientes conectados desde hostapd
	// Por ahora, devolver un array vacío
	// En el futuro, se podría leer desde /var/lib/hostapd/ o usando hostapd_cli
	var clients []fiber.Map
	
	// Verificar si hostapd está corriendo
	hostapdOut, _ := exec.Command("sh", "-c", "systemctl is-active hostapd 2>/dev/null || pgrep hostapd > /dev/null && echo active || echo inactive").CombinedOutput()
	hostapdStatus := strings.TrimSpace(string(hostapdOut))
	
	if hostapdStatus == "active" {
		// Intentar usar hostapd_cli para obtener clientes
		cliOut, err := exec.Command("hostapd_cli", "-i", "wlan0", "all_sta").CombinedOutput()
		if err == nil && len(cliOut) > 0 {
			// Parsear salida de hostapd_cli (formato simple)
			lines := strings.Split(strings.TrimSpace(string(cliOut)), "\n")
			for _, line := range lines {
				line = strings.TrimSpace(line)
				if line != "" && strings.HasPrefix(line, "sta=") {
					mac := strings.TrimPrefix(line, "sta=")
					clients = append(clients, fiber.Map{
						"mac_address": mac,
						"ip_address":  "-",
						"signal":      "-",
						"uptime":      "-",
					})
				}
			}
		}
	}
	
	return c.JSON(clients)
}

func hostapdToggleHandler(c *fiber.Ctx) error {
	log.Printf("HostAPD toggle request received")
	
	// Verificar estado actual
	hostapdOut, _ := exec.Command("sh", "-c", "systemctl is-active hostapd 2>/dev/null || pgrep hostapd > /dev/null && echo active || echo inactive").CombinedOutput()
	hostapdStatus := strings.TrimSpace(string(hostapdOut))
	isActive := hostapdStatus == "active"
	
	log.Printf("Current HostAPD status: %s (isActive: %v)", hostapdStatus, isActive)
	
	var cmdStr string
	var enableCmd string
	var action string
	
	if isActive {
		// Detener hostapd y dnsmasq
		action = "disable"
		executeCommand("sudo systemctl stop dnsmasq 2>/dev/null || true")
		cmdStr = "sudo systemctl stop hostapd"
		enableCmd = "sudo systemctl disable hostapd 2>/dev/null || true"
		
		// En modo AP+STA, no eliminamos ap0 al detener porque puede ser recreada automáticamente
		// La interfaz virtual ap0 puede mantenerse para facilitar el reinicio
	} else {
		// Habilitar y iniciar hostapd y dnsmasq
		action = "enable"
		
		// Verificar si existe el archivo de configuración
		configPath := "/etc/hostapd/hostapd.conf"
		if _, err := os.Stat(configPath); os.IsNotExist(err) {
			log.Printf("HostAPD configuration file not found: %s", configPath)
			return c.Status(400).JSON(fiber.Map{
				"error":         "HostAPD configuration not found. Please configure HostAPD first using the configuration form below.",
				"success":       false,
				"config_missing": true,
				"config_path":   configPath,
			})
		}
		
		// Verificar que el archivo de configuración no esté vacío
		configContent, err := os.ReadFile(configPath)
		if err != nil || len(configContent) == 0 {
			log.Printf("HostAPD configuration file is empty or unreadable: %s", configPath)
			return c.Status(400).JSON(fiber.Map{
				"error":         "HostAPD configuration file is empty or invalid. Please configure HostAPD first using the configuration form below.",
				"success":       false,
				"config_missing": true,
				"config_path":   configPath,
			})
		}
		
		// En modo AP+STA, verificar y crear interfaz ap0 si no existe
		ap0CheckCmd := "ip link show ap0 2>/dev/null"
		ap0Exists := false
		if out, err := executeCommand(ap0CheckCmd); err == nil && strings.TrimSpace(out) != "" {
			ap0Exists = true
			log.Printf("Interface ap0 already exists")
		} else {
			log.Printf("Interface ap0 does not exist, creating it...")
			// Leer la configuración para obtener la interfaz física
			phyInterface := "wlan0"
			if configContent, err := os.ReadFile(configPath); err == nil {
				lines := strings.Split(string(configContent), "\n")
				for _, line := range lines {
					line = strings.TrimSpace(line)
					if strings.HasPrefix(line, "interface=") {
						// Si la interfaz en la config es ap0, necesitamos obtener la interfaz física
						// Por defecto usamos wlan0
						break
					}
				}
			}
			
			// Asegurar que la interfaz física esté activa
			executeCommand(fmt.Sprintf("sudo ip link set %s up 2>/dev/null || true", phyInterface))
			time.Sleep(500 * time.Millisecond)
			
			// Obtener el phy de la interfaz física (múltiples métodos)
			phyName := ""
			
			// Método 1: Desde iw dev info
			phyCmd := fmt.Sprintf("iw dev %s info 2>/dev/null | grep 'wiphy' | awk '{print $2}'", phyInterface)
			phyOut, _ := executeCommand(phyCmd)
			phyName = strings.TrimSpace(phyOut)
			
			// Método 2: Desde /sys/class/net
			if phyName == "" {
				phyCmd2 := fmt.Sprintf("cat /sys/class/net/%s/phy80211/name 2>/dev/null", phyInterface)
				phyOut2, _ := executeCommand(phyCmd2)
				phyName = strings.TrimSpace(phyOut2)
			}
			
			// Método 3: Desde iw list
			if phyName == "" {
				phyCmd3 := "iw list 2>/dev/null | grep -A 1 'Wiphy' | tail -1 | awk '{print $2}'"
				phyOut3, _ := executeCommand(phyCmd3)
				phyName = strings.TrimSpace(phyOut3)
			}
			
			// Método 4: Valor por defecto
			if phyName == "" {
				phyName = "phy0"
				log.Printf("Warning: Could not detect phy name, using default: %s", phyName)
			}
			
			log.Printf("Creating ap0 interface using phy %s from interface %s...", phyName, phyInterface)
			
			// Eliminar ap0 si existe antes de crearla
			executeCommand("sudo iw dev ap0 del 2>/dev/null || true")
			time.Sleep(1 * time.Second)
			
			// Crear interfaz ap0 usando phy
			createApCmd := fmt.Sprintf("sudo iw phy %s interface add ap0 type __ap", phyName)
			createOut, createErr := executeCommand(createApCmd)
			if createErr != nil {
				log.Printf("Warning: Could not create ap0 interface with phy %s: %s", phyName, strings.TrimSpace(createOut))
				// Intentar método alternativo
				createApCmd2 := fmt.Sprintf("sudo iw dev %s interface add ap0 type __ap", phyInterface)
				createOut2, createErr2 := executeCommand(createApCmd2)
				if createErr2 != nil {
					log.Printf("Warning: Alternative method also failed: %s", strings.TrimSpace(createOut2))
				} else {
					log.Printf("Successfully created ap0 interface using alternative method (from %s)", phyInterface)
					ap0Exists = true
				}
			} else {
				log.Printf("Successfully created ap0 interface using phy %s", phyName)
				ap0Exists = true
			}
			
			// Verificar que la interfaz se creó
			if ap0Exists {
				verifyCmd := "ip link show ap0 2>/dev/null"
				verifyOut, verifyErr := executeCommand(verifyCmd)
				if verifyErr == nil && strings.TrimSpace(verifyOut) != "" {
					log.Printf("Interface ap0 verified: %s", strings.TrimSpace(verifyOut))
					// Activar la interfaz ap0
					executeCommand("sudo ip link set ap0 up 2>/dev/null || true")
					log.Printf("Activated ap0 interface")
				} else {
					log.Printf("Warning: ap0 was created but verification failed")
				}
			}
		}
		
		// Verificar si el servicio está masked y desbloquearlo si es necesario
		maskedCheck, _ := exec.Command("sh", "-c", "systemctl is-enabled hostapd 2>&1").CombinedOutput()
		maskedStatus := strings.TrimSpace(string(maskedCheck))
		if strings.Contains(maskedStatus, "masked") {
			log.Printf("HostAPD service is masked, unmasking...")
			executeCommand("sudo systemctl unmask hostapd 2>/dev/null || true")
		}
		
		// Leer la configuración para obtener la interfaz y el gateway
		configLines := strings.Split(string(configContent), "\n")
		var interfaceName, gatewayIP string
		for _, line := range configLines {
			line = strings.TrimSpace(line)
			if line == "" || strings.HasPrefix(line, "#") {
				continue
			}
			if strings.HasPrefix(line, "interface=") {
				interfaceName = strings.TrimPrefix(line, "interface=")
			}
		}
		
		// Verificar que tenemos al menos la interfaz configurada
		if interfaceName == "" {
			log.Printf("HostAPD configuration file missing interface setting: %s", configPath)
			return c.Status(400).JSON(fiber.Map{
				"error":         "HostAPD configuration file is missing required 'interface' setting. Please configure HostAPD first using the configuration form below.",
				"success":       false,
				"config_missing": true,
				"config_path":   configPath,
			})
		}
		
		// Si tenemos la interfaz, verificar y configurar la IP antes de iniciar
		if interfaceName != "" {
			// Intentar obtener el gateway de la configuración (si está en dnsmasq o en otro lugar)
			// Por defecto usamos 192.168.4.1
			gatewayIP = "192.168.4.1"
			
			// Verificar si la interfaz tiene una IP configurada
			ipCheckCmd := fmt.Sprintf("ip addr show %s 2>/dev/null | grep 'inet ' | awk '{print $2}' | cut -d/ -f1", interfaceName)
			ipOut, _ := exec.Command("sh", "-c", ipCheckCmd).CombinedOutput()
			currentIP := strings.TrimSpace(string(ipOut))
			
			if currentIP == "" {
				// Configurar la IP en la interfaz
				log.Printf("Configuring IP %s on interface %s", gatewayIP, interfaceName)
				ipCmd := fmt.Sprintf("sudo ip addr add %s/24 dev %s 2>/dev/null || sudo ip addr replace %s/24 dev %s", gatewayIP, interfaceName, gatewayIP, interfaceName)
				if out, err := executeCommand(ipCmd); err != nil {
					log.Printf("Warning: Error setting IP on interface: %s", strings.TrimSpace(out))
				}
				
				// Activar la interfaz
				if out, err := executeCommand(fmt.Sprintf("sudo ip link set %s up", interfaceName)); err != nil {
					log.Printf("Warning: Error bringing interface up: %s", strings.TrimSpace(out))
				}
			}
		}
		
		// Asegurarse de que el servicio no esté masked antes de habilitarlo
		executeCommand("sudo systemctl unmask hostapd 2>/dev/null || true")
		executeCommand("sudo systemctl unmask dnsmasq 2>/dev/null || true")
		
		// Recargar systemd para asegurar que los cambios en el override se apliquen
		executeCommand("sudo systemctl daemon-reload 2>/dev/null || true")
		
		// Habilitar servicios
		enableCmd = "sudo systemctl enable hostapd 2>/dev/null || true"
		executeCommand("sudo systemctl enable dnsmasq 2>/dev/null || true")
		
		// Verificar que el archivo de configuración existe y tiene contenido (systemd lo verifica)
		// Asegurar permisos correctos
		executeCommand(fmt.Sprintf("sudo chmod 644 %s 2>/dev/null || true", configPath))
		
		cmdStr = "sudo systemctl start hostapd"
		// Iniciar dnsmasq después de hostapd
		executeCommand("sudo systemctl start dnsmasq 2>/dev/null || true")
	}
	
	log.Printf("Action: %s, Command: %s", action, cmdStr)
	
	// Ejecutar comando de habilitación/deshabilitación
	if enableCmd != "" {
		if out, err := executeCommand(enableCmd); err != nil {
			log.Printf("Warning: Error enabling/disabling hostapd: %s", strings.TrimSpace(out))
			// No fallar aquí, continuar con el start/stop
		} else {
			log.Printf("Enable/disable command executed successfully: %s", strings.TrimSpace(out))
		}
	}
	
	// Ejecutar comando de inicio/detención
	out, err := executeCommand(cmdStr)
	if err != nil {
		log.Printf("Error executing %s command: %s", action, strings.TrimSpace(out))
		
		// Si es un error de inicio, obtener más información de los logs
		var errorDetails string
		if action == "enable" {
			// Obtener logs del servicio
			journalOut, _ := exec.Command("sh", "-c", "sudo journalctl -u hostapd -n 20 --no-pager 2>/dev/null | tail -10").CombinedOutput()
			journalLogs := strings.TrimSpace(string(journalOut))
			if journalLogs != "" {
				// Extraer solo las líneas de error más relevantes
				lines := strings.Split(journalLogs, "\n")
				errorLines := []string{}
				for _, line := range lines {
					line = strings.TrimSpace(line)
					if line != "" && (strings.Contains(strings.ToLower(line), "error") || 
						strings.Contains(strings.ToLower(line), "failed") ||
						strings.Contains(strings.ToLower(line), "fail")) {
						errorLines = append(errorLines, line)
					}
				}
				if len(errorLines) > 0 {
					errorDetails = fmt.Sprintf(" Recent errors: %s", strings.Join(errorLines, "; "))
				} else {
					errorDetails = fmt.Sprintf(" Last logs: %s", strings.Join(lines[len(lines)-3:], "; "))
				}
			} else {
				// Intentar obtener el estado del servicio
				statusOut, _ := exec.Command("sh", "-c", "sudo systemctl status hostapd --no-pager 2>/dev/null | head -15").CombinedOutput()
				statusInfo := strings.TrimSpace(string(statusOut))
				if statusInfo != "" {
					errorDetails = fmt.Sprintf(" Service status: %s", statusInfo)
				}
			}
		}
		
		return c.Status(500).JSON(fiber.Map{
			"error":   fmt.Sprintf("Failed to %s hostapd: %s%s", action, strings.TrimSpace(out), errorDetails),
			"success": false,
		})
	}
	
	log.Printf("HostAPD %s command executed. Output: %s", action, strings.TrimSpace(out))
	
	// Verificar el estado después de la operación
	// Dar más tiempo al servicio para iniciar si es enable
	if action == "enable" {
		time.Sleep(1500 * time.Millisecond) // Más tiempo para que hostapd inicie
	} else {
		time.Sleep(500 * time.Millisecond)
	}
	
	// Verificar estado del servicio
	hostapdOut2, _ := exec.Command("sh", "-c", "systemctl is-active hostapd 2>/dev/null || pgrep hostapd > /dev/null && echo active || echo inactive").CombinedOutput()
	hostapdStatus2 := strings.TrimSpace(string(hostapdOut2))
	actuallyActive := hostapdStatus2 == "active"
	
	// Si intentamos habilitar pero sigue inactivo, obtener más información
	if action == "enable" && !actuallyActive {
		log.Printf("HostAPD failed to start. Checking logs...")
		// Verificar si el servicio está habilitado pero falló
		enabledOut, _ := exec.Command("sh", "-c", "systemctl is-enabled hostapd 2>/dev/null || echo disabled").CombinedOutput()
		enabledStatus := strings.TrimSpace(string(enabledOut))
		
		// Obtener logs recientes
		journalOut, _ := exec.Command("sh", "-c", "sudo journalctl -u hostapd -n 15 --no-pager 2>/dev/null | tail -8").CombinedOutput()
		journalLogs := strings.TrimSpace(string(journalOut))
		
		// Obtener estado detallado
		statusOut, _ := exec.Command("sh", "-c", "sudo systemctl status hostapd --no-pager 2>/dev/null | head -20").CombinedOutput()
		statusInfo := strings.TrimSpace(string(statusOut))
		
		var errorMsg string
		if journalLogs != "" {
			// Buscar líneas de error
			lines := strings.Split(journalLogs, "\n")
			errorLines := []string{}
			for _, line := range lines {
				line = strings.TrimSpace(line)
				if line != "" {
					lowerLine := strings.ToLower(line)
					if strings.Contains(lowerLine, "error") || strings.Contains(lowerLine, "failed") || 
						strings.Contains(lowerLine, "fail") || strings.Contains(lowerLine, "cannot") {
						errorLines = append(errorLines, line)
					}
				}
			}
			if len(errorLines) > 0 {
				maxLines := 3
				if len(errorLines) < maxLines {
					maxLines = len(errorLines)
				}
				errorMsg = strings.Join(errorLines[:maxLines], "; ")
			} else if len(lines) > 0 {
				maxLines := 3
				if len(lines) < maxLines {
					maxLines = len(lines)
				}
				errorMsg = strings.Join(lines[len(lines)-maxLines:], "; ")
			}
		}
		
		if errorMsg == "" && statusInfo != "" {
			// Extraer información relevante del status
			statusLines := strings.Split(statusInfo, "\n")
			for _, line := range statusLines {
				if strings.Contains(strings.ToLower(line), "active:") || 
					strings.Contains(strings.ToLower(line), "failed") ||
					strings.Contains(strings.ToLower(line), "error") {
					errorMsg = strings.TrimSpace(line)
					break
				}
			}
		}
		
		if errorMsg != "" {
			return c.Status(500).JSON(fiber.Map{
				"error":   fmt.Sprintf("Failed to enable HostAPD. Service status: %s (enabled: %s). %s", hostapdStatus2, enabledStatus, errorMsg),
				"success": false,
				"status":  hostapdStatus2,
				"enabled": false,
			})
		} else {
			return c.Status(500).JSON(fiber.Map{
				"error":   fmt.Sprintf("Failed to enable HostAPD. Service status: %s (enabled: %s). Check configuration and logs.", hostapdStatus2, enabledStatus),
				"success": false,
				"status":  hostapdStatus2,
				"enabled": false,
			})
		}
	}
	
	log.Printf("HostAPD status after %s: %s (actuallyActive: %v)", action, hostapdStatus2, actuallyActive)
	
	return c.JSON(fiber.Map{
		"success": true,
		"output":  strings.TrimSpace(out),
		"enabled": actuallyActive,
		"action":  action,
		"status":  hostapdStatus2,
	})
}

func hostapdRestartHandler(c *fiber.Ctx) error {
	// Detener hostapd
	out1, err1 := executeCommand("sudo systemctl stop hostapd")
	
	// Esperar un momento
	time.Sleep(500 * time.Millisecond)
	
	// Iniciar hostapd
	out2, err2 := executeCommand("sudo systemctl start hostapd")
	
	if err1 != nil || err2 != nil {
		return c.Status(500).JSON(fiber.Map{
			"error":  "Error reiniciando HostAPD",
			"stop":   strings.TrimSpace(out1),
			"start":   strings.TrimSpace(out2),
			"stopOk":  err1 == nil,
			"startOk": err2 == nil,
			"success": false,
		})
	}
	
	return c.JSON(fiber.Map{
		"success": true,
		"output":  "HostAPD restarted successfully",
	})
}

func hostapdDiagnosticsHandler(c *fiber.Ctx) error {
	diagnostics := make(map[string]interface{})
	
	// 1. Verificar estado del servicio
	systemctlOut, _ := exec.Command("sh", "-c", "systemctl is-active hostapd 2>/dev/null").CombinedOutput()
	systemctlStatus := strings.TrimSpace(string(systemctlOut))
	pgrepOut, _ := exec.Command("sh", "-c", "pgrep hostapd > /dev/null 2>&1 && echo active || echo inactive").CombinedOutput()
	pgrepStatus := strings.TrimSpace(string(pgrepOut))
	
	serviceRunning := systemctlStatus == "active" || pgrepStatus == "active"
	diagnostics["service_running"] = serviceRunning
	diagnostics["systemctl_status"] = systemctlStatus
	diagnostics["process_running"] = pgrepStatus == "active"
	
	// 2. Leer configuración para obtener la interfaz
	interfaceName := "wlan0"
	configPath := "/etc/hostapd/hostapd.conf"
	if configContent, err := os.ReadFile(configPath); err == nil {
		lines := strings.Split(string(configContent), "\n")
		for _, line := range lines {
			line = strings.TrimSpace(line)
			if strings.HasPrefix(line, "interface=") {
				parts := strings.SplitN(line, "=", 2)
				if len(parts) == 2 {
					interfaceName = strings.TrimSpace(parts[1])
					break
				}
			}
		}
	}
	diagnostics["interface"] = interfaceName
	
	// 3. Verificar si la interfaz está en modo AP
	iwOut, _ := exec.Command("sh", "-c", fmt.Sprintf("iw dev %s info 2>/dev/null | grep -i 'type AP' || iwconfig %s 2>/dev/null | grep -i 'mode:master' || echo ''", interfaceName, interfaceName)).CombinedOutput()
	iwStatus := strings.TrimSpace(string(iwOut))
	transmitting := iwStatus != ""
	
	// Verificar también con hostapd_cli
	if !transmitting && serviceRunning {
		cliStatusOut, _ := exec.Command("sh", "-c", fmt.Sprintf("hostapd_cli -i %s status 2>/dev/null | grep -i 'state=ENABLED' || echo ''", interfaceName)).CombinedOutput()
		cliStatus := strings.TrimSpace(string(cliStatusOut))
		if cliStatus != "" {
			transmitting = true
		}
	}
	
	diagnostics["transmitting"] = transmitting
	diagnostics["interface_in_ap_mode"] = iwStatus != ""
	
	// 4. Verificar logs de errores
	journalOut, _ := exec.Command("sh", "-c", "sudo journalctl -u hostapd -n 50 --no-pager 2>/dev/null | tail -30").CombinedOutput()
	journalLogs := string(journalOut)
	diagnostics["recent_logs"] = journalLogs
	
	// Buscar errores comunes
	errors := []string{}
	journalLower := strings.ToLower(journalLogs)
	if strings.Contains(journalLower, "could not configure driver") {
		errors = append(errors, "Driver configuration error")
	}
	if strings.Contains(journalLower, "nl80211: could not") {
		errors = append(errors, "nl80211 driver error")
	}
	if strings.Contains(journalLower, "interface") && strings.Contains(journalLower, "not found") {
		errors = append(errors, "Interface not found")
	}
	if strings.Contains(journalLower, "failed to initialize") {
		errors = append(errors, "Initialization failed")
	}
	if strings.Contains(journalLower, "could not set channel") {
		errors = append(errors, "Channel configuration error")
	}
	
	diagnostics["errors"] = errors
	diagnostics["has_errors"] = len(errors) > 0
	
	// 5. Verificar estado de la interfaz
	ipOut, _ := exec.Command("sh", "-c", fmt.Sprintf("ip addr show %s 2>/dev/null | grep -i 'state UP' || echo ''", interfaceName)).CombinedOutput()
	interfaceUp := strings.Contains(strings.ToLower(string(ipOut)), "state up")
	diagnostics["interface_up"] = interfaceUp
	
	// 6. Verificar si dnsmasq está corriendo (necesario para DHCP)
	dnsmasqOut, _ := exec.Command("sh", "-c", "systemctl is-active dnsmasq 2>/dev/null || echo inactive").CombinedOutput()
	dnsmasqStatus := strings.TrimSpace(string(dnsmasqOut))
	diagnostics["dnsmasq_running"] = dnsmasqStatus == "active"
	
	// 7. Estado general
	diagnostics["status"] = func() string {
		if !serviceRunning {
			return "service_stopped"
		}
		if !transmitting {
			return "service_running_not_transmitting"
		}
		return "ok"
	}()
	
	return c.JSON(diagnostics)
}

func hostapdGetConfigHandler(c *fiber.Ctx) error {
	configPath := "/etc/hostapd/hostapd.conf"
	
	// Verificar si el archivo existe
	if _, err := os.Stat(configPath); os.IsNotExist(err) {
		return c.JSON(fiber.Map{
			"success": false,
			"error":   "Configuration file not found",
			"config":  nil,
		})
	}
	
	// Leer el archivo de configuración
	configContent, err := os.ReadFile(configPath)
	if err != nil {
		return c.Status(500).JSON(fiber.Map{
			"success": false,
			"error":   fmt.Sprintf("Error reading config file: %v", err),
			"config":  nil,
		})
	}
	
	// Parsear la configuración
	config := make(map[string]string)
	lines := strings.Split(string(configContent), "\n")
	for _, line := range lines {
		line = strings.TrimSpace(line)
		if line == "" || strings.HasPrefix(line, "#") {
			continue
		}
		parts := strings.SplitN(line, "=", 2)
		if len(parts) == 2 {
			key := strings.TrimSpace(parts[0])
			value := strings.TrimSpace(parts[1])
			config[key] = value
		}
	}
	
	// Extraer valores relevantes
	// En modo AP+STA, la interfaz en la config será ap0, pero mostramos wlan0 al usuario
	interfaceForDisplay := config["interface"]
	if interfaceForDisplay == "ap0" {
		// Si es ap0, mostrar wlan0 en el formulario (la interfaz física)
		interfaceForDisplay = "wlan0"
	}
	
	result := fiber.Map{
		"success": true,
		"config": fiber.Map{
			"interface": interfaceForDisplay, // Mostrar interfaz física al usuario
			"ssid":      config["ssid"],
			"channel":   config["channel"],
			"password":  config["wpa_passphrase"], // Devolver la contraseña para que el usuario pueda verla/editarla
		},
	}
	
	// Determinar el tipo de seguridad
	if config["auth_algs"] == "0" {
		result["config"].(fiber.Map)["security"] = "open"
	} else if strings.Contains(config["wpa_key_mgmt"], "SHA256") {
		result["config"].(fiber.Map)["security"] = "wpa3"
	} else if config["wpa"] == "2" {
		result["config"].(fiber.Map)["security"] = "wpa2"
	} else {
		result["config"].(fiber.Map)["security"] = "wpa2" // Por defecto
	}
	
	// Leer configuración de dnsmasq para obtener gateway y DHCP range
	dnsmasqPath := "/etc/dnsmasq.conf"
	if dnsmasqContent, err := os.ReadFile(dnsmasqPath); err == nil {
		dnsmasqLines := strings.Split(string(dnsmasqContent), "\n")
		for _, line := range dnsmasqLines {
			line = strings.TrimSpace(line)
			if strings.HasPrefix(line, "dhcp-option=3,") {
				gateway := strings.TrimPrefix(line, "dhcp-option=3,")
				result["config"].(fiber.Map)["gateway"] = gateway
			} else if strings.HasPrefix(line, "dhcp-range=") {
				rangeStr := strings.TrimPrefix(line, "dhcp-range=")
				parts := strings.Split(rangeStr, ",")
				if len(parts) >= 2 {
					result["config"].(fiber.Map)["dhcp_range_start"] = parts[0]
					result["config"].(fiber.Map)["dhcp_range_end"] = parts[1]
					if len(parts) >= 4 {
						result["config"].(fiber.Map)["lease_time"] = parts[3]
					}
				}
			}
		}
	}
	
	// Valores por defecto si no se encontraron
	configMap := result["config"].(fiber.Map)
	if configMap["gateway"] == nil || configMap["gateway"] == "" {
		configMap["gateway"] = "192.168.4.1"
	}
	if configMap["dhcp_range_start"] == nil || configMap["dhcp_range_start"] == "" {
		configMap["dhcp_range_start"] = "192.168.4.2"
	}
	if configMap["dhcp_range_end"] == nil || configMap["dhcp_range_end"] == "" {
		configMap["dhcp_range_end"] = "192.168.4.254"
	}
	if configMap["lease_time"] == nil || configMap["lease_time"] == "" {
		configMap["lease_time"] = "12h"
	}
	if configMap["channel"] == nil || configMap["channel"] == "" {
		configMap["channel"] = "6"
	}
	
	// Obtener country code
	countryCode := config["country_code"]
	if countryCode == "" {
		countryCode = config["country"] // Algunas configuraciones usan "country" en lugar de "country_code"
	}
	if countryCode == "" {
		countryCode = "US" // Valor por defecto
	}
	configMap["country"] = countryCode
	
	return c.JSON(result)
}

func hostapdConfigHandler(c *fiber.Ctx) error {
	var req struct {
		Interface      string `json:"interface"`
		SSID           string `json:"ssid"`
		Password       string `json:"password"`
		Channel        int    `json:"channel"`
		Security       string `json:"security"`
		Gateway        string `json:"gateway"`
		DHCPRangeStart string `json:"dhcp_range_start"`
		DHCPRangeEnd   string `json:"dhcp_range_end"`
		LeaseTime      string `json:"lease_time"`
		Country        string `json:"country"`
	}
	
	if err := c.BodyParser(&req); err != nil {
		return c.Status(400).JSON(fiber.Map{
			"error":   "Invalid request body",
			"success": false,
		})
	}
	
	// Validar campos requeridos
	if req.Interface == "" || req.SSID == "" || req.Channel < 1 || req.Channel > 13 {
		return c.Status(400).JSON(fiber.Map{
			"error":   "Missing required fields: interface, ssid, channel",
			"success": false,
		})
	}
	
	// Valores por defecto
	if req.Gateway == "" {
		req.Gateway = "192.168.4.1"
	}
	if req.DHCPRangeStart == "" {
		req.DHCPRangeStart = "192.168.4.2"
	}
	if req.DHCPRangeEnd == "" {
		req.DHCPRangeEnd = "192.168.4.254"
	}
	if req.LeaseTime == "" {
		req.LeaseTime = "12h"
	}
	if req.Country == "" {
		req.Country = "US" // Valor por defecto
	}
	
	// Validar country code (debe ser 2 letras mayúsculas)
	if len(req.Country) != 2 {
		req.Country = "US"
	}
	req.Country = strings.ToUpper(req.Country)
	
	// Validar security
	if req.Security != "wpa2" && req.Security != "wpa3" && req.Security != "open" {
		req.Security = "wpa2"
	}
	
	// Modo AP+STA: Crear interfaz virtual ap0 para el punto de acceso
	// Esto permite que wlan0 funcione como estación (STA) mientras ap0 funciona como AP
	apInterface := "ap0"
	phyInterface := req.Interface // wlan0 o la interfaz física
	
	log.Printf("Configuring AP+STA mode: creating virtual interface %s from %s", apInterface, phyInterface)
	
	// 1. Asegurar que la interfaz física esté activa antes de crear la virtual
	executeCommand(fmt.Sprintf("sudo ip link set %s up 2>/dev/null || true", phyInterface))
	time.Sleep(500 * time.Millisecond)
	
	// 2. Obtener el nombre del phy de la interfaz física
	// Método 1: Desde /sys/class/net (más confiable)
	phyName := ""
	phyCmd2 := fmt.Sprintf("cat /sys/class/net/%s/phy80211/name 2>/dev/null", phyInterface)
	phyOut2, _ := executeCommand(phyCmd2)
	phyName = strings.TrimSpace(phyOut2)
	
	// Método 2: Desde iw dev info
	if phyName == "" {
		phyCmd := fmt.Sprintf("iw dev %s info 2>/dev/null | grep 'wiphy' | awk '{print $2}'", phyInterface)
		phyOut, _ := executeCommand(phyCmd)
		phyName = strings.TrimSpace(phyOut)
	}
	
	// Método 3: Desde iw phy (listar todos los phy y encontrar el que tiene esta interfaz)
	if phyName == "" {
		phyCmd3 := fmt.Sprintf("iw phy | grep -B 5 '%s' | grep 'Wiphy' | awk '{print $2}' | head -1", phyInterface)
		phyOut3, _ := executeCommand(phyCmd3)
		phyName = strings.TrimSpace(phyOut3)
	}
	
	// Método 4: Desde iw list (último recurso)
	if phyName == "" {
		phyCmd4 := "iw list 2>/dev/null | grep 'Wiphy' | head -1 | awk '{print $2}'"
		phyOut4, _ := executeCommand(phyCmd4)
		phyName = strings.TrimSpace(phyOut4)
	}
	
	// Método 5: Intentar detectar desde el número de la interfaz
	if phyName == "" {
		// Si la interfaz es wlan0, wlan1, etc., intentar phy0, phy1, etc.
		if strings.HasPrefix(phyInterface, "wlan") {
			if numStr := strings.TrimPrefix(phyInterface, "wlan"); numStr != "" {
				phyName = "phy" + numStr
				log.Printf("Trying phy name based on interface number: %s", phyName)
			}
		}
	}
	
	// Método 6: Valor por defecto
	if phyName == "" {
		phyName = "phy0"
		log.Printf("Warning: Could not detect phy name, using default: %s", phyName)
	}
	
	log.Printf("Detected phy name: %s for interface %s", phyName, phyInterface)
	
	// Obtener MAC address de la interfaz física para la regla udev
	macAddress := ""
	macCmd := exec.Command("sh", "-c", fmt.Sprintf("cat /sys/class/net/%s/address 2>/dev/null", phyInterface))
	if macOut, err := macCmd.Output(); err == nil {
		macAddress = strings.TrimSpace(string(macOut))
	}
	if macAddress == "" {
		log.Printf("Warning: Could not get MAC address for %s", phyInterface)
		macAddress = "00:00:00:00:00:00" // Valor por defecto
	}
	
	log.Printf("Using phy: %s (MAC: %s) for virtual interface creation from %s", phyName, macAddress, phyInterface)
	
	// 2.5. Crear regla udev para crear ap0 automáticamente (basado en el script ap_sta_config.sh)
	if apInterface == "ap0" {
		log.Printf("Creating udev rule for automatic ap0 interface creation")
		udevRuleContent := fmt.Sprintf(`SUBSYSTEM=="ieee80211", ACTION=="add|change", ATTR{macaddress}=="%s", KERNEL=="%s", \
RUN+="/sbin/iw phy %s interface add ap0 type __ap", \
RUN+="/bin/ip link set ap0 address %s"
`, macAddress, phyName, phyName, macAddress)
		
		udevRulePath := "/etc/udev/rules.d/70-persistent-net.rules"
		tmpUdevFile := "/tmp/70-persistent-net.rules.tmp"
		if err := os.WriteFile(tmpUdevFile, []byte(udevRuleContent), 0644); err == nil {
			executeCommand(fmt.Sprintf("sudo cp %s %s && sudo chmod 644 %s", tmpUdevFile, udevRulePath, udevRulePath))
			os.Remove(tmpUdevFile)
			log.Printf("Created udev rule for automatic ap0 creation")
			// Recargar reglas udev
			executeCommand("sudo udevadm control --reload-rules 2>/dev/null || true")
			executeCommand("sudo udevadm trigger 2>/dev/null || true")
		} else {
			log.Printf("Warning: Could not create udev rule: %v", err)
		}
	}
	
	// 3. Verificar si la interfaz ap0 ya existe
	checkApCmd := fmt.Sprintf("ip link show %s 2>/dev/null", apInterface)
	apExists := false
	checkOut, checkErr := executeCommand(checkApCmd)
	if checkErr == nil && strings.TrimSpace(checkOut) != "" {
		apExists = true
		log.Printf("Interface %s already exists, reusing it", apInterface)
		// Si existe pero está down, activarla
		executeCommand(fmt.Sprintf("sudo ip link set %s up 2>/dev/null || true", apInterface))
	}
	
	// 4. Si no existe, eliminar cualquier interfaz ap0 anterior y crear una nueva
	if !apExists {
		log.Printf("Interface %s does not exist, creating it...", apInterface)
		
		// Eliminar interfaz virtual ap0 si ya existe (para recrearla limpia)
		delOut, delErr := executeCommand(fmt.Sprintf("sudo iw dev %s del 2>/dev/null || true", apInterface))
		if delErr == nil {
			log.Printf("Removed existing %s interface (if it existed): %s", apInterface, strings.TrimSpace(delOut))
		}
		time.Sleep(1 * time.Second)
		
		// Crear interfaz virtual ap0 en modo AP usando phy
		log.Printf("Creating virtual interface %s using phy %s...", apInterface, phyName)
		
		// Primero verificar que el phy existe
		phyExistsCmd := fmt.Sprintf("iw phy %s info 2>/dev/null", phyName)
		phyExistsOut, phyExistsErr := executeCommand(phyExistsCmd)
		if phyExistsErr != nil || strings.TrimSpace(phyExistsOut) == "" {
			log.Printf("Warning: phy %s may not exist, output: %s", phyName, strings.TrimSpace(phyExistsOut))
		} else {
			log.Printf("phy %s exists and is accessible", phyName)
		}
		
		// Verificar que el phy soporta AP mode
		phyCheckCmd := fmt.Sprintf("iw phy %s info 2>/dev/null | grep -i 'AP'", phyName)
		phyCheckOut, _ := executeCommand(phyCheckCmd)
		if strings.TrimSpace(phyCheckOut) == "" {
			log.Printf("Warning: phy %s may not support AP mode, but attempting anyway", phyName)
		} else {
			log.Printf("phy %s supports AP mode: %s", phyName, strings.TrimSpace(phyCheckOut))
		}
		
		// Verificar que la interfaz física no esté en modo AP (debe estar en managed)
		iwInfoCmd := fmt.Sprintf("iw dev %s info 2>/dev/null", phyInterface)
		iwInfoOut, _ := executeCommand(iwInfoCmd)
		if strings.Contains(iwInfoOut, "type AP") {
			log.Printf("Warning: Physical interface %s is in AP mode, changing to managed first", phyInterface)
			executeCommand(fmt.Sprintf("sudo iw dev %s set type managed 2>/dev/null", phyInterface))
			time.Sleep(1 * time.Second)
		}
		
		// Asegurar que la interfaz física esté activa
		executeCommand(fmt.Sprintf("sudo ip link set %s up 2>/dev/null || true", phyInterface))
		time.Sleep(500 * time.Millisecond)
		
		// Intentar crear la interfaz con logging detallado
		createApCmd := fmt.Sprintf("sudo iw phy %s interface add %s type __ap 2>&1", phyName, apInterface)
		log.Printf("Executing: %s", createApCmd)
		createOut, createErr := executeCommand(createApCmd)
		if createOut != "" {
			log.Printf("Command output: %s", strings.TrimSpace(createOut))
		}
		
		if createErr != nil {
			log.Printf("Error creating virtual interface %s with phy %s: %s", apInterface, phyName, strings.TrimSpace(createOut))
			log.Printf("Error details: %v", createErr)
			log.Printf("Trying alternative method 1: using interface %s directly...", phyInterface)
			
			// Método alternativo 1: usar el nombre de la interfaz directamente
			createApCmd2 := fmt.Sprintf("sudo iw dev %s interface add %s type __ap 2>&1", phyInterface, apInterface)
			log.Printf("Executing: %s", createApCmd2)
			createOut2, createErr2 := executeCommand(createApCmd2)
			if createOut2 != "" {
				log.Printf("Method 1 output: %s", strings.TrimSpace(createOut2))
			}
			
			if createErr2 != nil {
				log.Printf("Error with alternative method 1: %s", strings.TrimSpace(createOut2))
				log.Printf("Trying alternative method 2: using iw phy without sudo...")
				
				// Método alternativo 2: intentar sin sudo (puede funcionar si el usuario tiene permisos)
				createApCmd3 := fmt.Sprintf("iw phy %s interface add %s type __ap 2>&1", phyName, apInterface)
				log.Printf("Executing: %s", createApCmd3)
				createOut3, createErr3 := executeCommand(createApCmd3)
				if createOut3 != "" {
					log.Printf("Method 2 output: %s", strings.TrimSpace(createOut3))
				}
				
				if createErr3 != nil {
					log.Printf("Error with alternative method 2: %s", strings.TrimSpace(createOut3))
					log.Printf("Trying alternative method 3: using mac80211_hwsim if available...")
					
					// Método alternativo 3: verificar si hay otro phy disponible
					phyListCmd := "iw phy 2>/dev/null | grep 'Wiphy' | awk '{print $2}'"
					phyListOut, _ := executeCommand(phyListCmd)
					log.Printf("Available phys: %s", strings.TrimSpace(phyListOut))
					altPhyName := strings.TrimSpace(phyListOut)
					if altPhyName != "" && altPhyName != phyName {
						// Tomar el primer phy disponible
						phyLines := strings.Split(altPhyName, "\n")
						if len(phyLines) > 0 {
							altPhyName = strings.TrimSpace(phyLines[0])
						}
						if altPhyName != "" && altPhyName != phyName {
							log.Printf("Trying with alternative phy: %s", altPhyName)
							createApCmd4 := fmt.Sprintf("sudo iw phy %s interface add %s type __ap 2>&1", altPhyName, apInterface)
							log.Printf("Executing: %s", createApCmd4)
							createOut4, createErr4 := executeCommand(createApCmd4)
							if createOut4 != "" {
								log.Printf("Method 3 output: %s", strings.TrimSpace(createOut4))
							}
						if createErr4 == nil {
							log.Printf("Successfully created interface %s using alternative phy %s", apInterface, altPhyName)
							apExists = true
							phyName = altPhyName // Actualizar phyName para uso posterior
						} else {
							log.Printf("Error with alternative phy: %s", strings.TrimSpace(createOut4))
							// Si todo falla, usar la interfaz física directamente (modo no concurrente)
							apInterface = phyInterface
							log.Printf("Falling back to using physical interface %s directly (non-concurrent mode)", apInterface)
						}
					} else {
						// Si todo falla, usar la interfaz física directamente (modo no concurrente)
						apInterface = phyInterface
						log.Printf("Falling back to using physical interface %s directly (non-concurrent mode)", apInterface)
					}
				} else {
					log.Printf("Successfully created interface %s using method 2 (without sudo)", apInterface)
					apExists = true
				}
			} else {
				log.Printf("Successfully created interface %s using alternative method 1 (from %s)", apInterface, phyInterface)
				apExists = true
			}
		} else {
			log.Printf("Successfully created interface %s using phy %s", apInterface, phyName)
			apExists = true
		}
		
		// Verificar que la interfaz se creó correctamente (con retry)
		if apExists && apInterface == "ap0" {
			// Esperar un momento para que el sistema registre la interfaz
			time.Sleep(2 * time.Second)
			
			// Intentar verificar varias veces con múltiples métodos
			verified := false
			for i := 0; i < 5; i++ {
				// Método 1: ip link show
				verifyCmd := fmt.Sprintf("ip link show %s 2>/dev/null", apInterface)
				verifyOut, verifyErr := executeCommand(verifyCmd)
				if verifyErr == nil && strings.TrimSpace(verifyOut) != "" {
					log.Printf("Interface %s verified successfully with ip link (attempt %d)", apInterface, i+1)
					verified = true
					break
				}
				
				// Método 2: ls /sys/class/net
				lsCmd := fmt.Sprintf("ls /sys/class/net/ 2>/dev/null | grep -q '^%s$' && echo 'exists'", apInterface)
				lsOut, _ := executeCommand(lsCmd)
				if strings.TrimSpace(lsOut) == "exists" {
					log.Printf("Interface %s verified successfully with ls /sys/class/net (attempt %d)", apInterface, i+1)
					verified = true
					break
				}
				
				// Método 3: iw dev list
				iwListCmd := fmt.Sprintf("iw dev 2>/dev/null | grep -q 'Interface %s' && echo 'exists'", apInterface)
				iwListOut, _ := executeCommand(iwListCmd)
				if strings.TrimSpace(iwListOut) == "exists" {
					log.Printf("Interface %s verified successfully with iw dev (attempt %d)", apInterface, i+1)
					verified = true
					break
				}
				
				if i < 4 {
					log.Printf("Verification attempt %d failed, retrying...", i+1)
					time.Sleep(1 * time.Second)
				}
			}
			
			if !verified {
				log.Printf("ERROR: Interface %s was NOT created successfully after all attempts", apInterface)
				log.Printf("Diagnostics:")
				log.Printf("  - phy name: %s", phyName)
				log.Printf("  - physical interface: %s", phyInterface)
				log.Printf("  - MAC address: %s", macAddress)
				
				// Intentar crear manualmente como último recurso
				log.Printf("Attempting manual creation as last resort...")
				manualCmd := fmt.Sprintf("sudo iw phy %s interface add %s type __ap 2>&1; sleep 1; ip link show %s 2>&1", phyName, apInterface, apInterface)
				manualOut, _ := executeCommand(manualCmd)
				log.Printf("Manual creation result: %s", strings.TrimSpace(manualOut))
			} else {
				log.Printf("SUCCESS: Interface %s created and verified", apInterface)
			}
		}
	}
	
	// 4. Configurar IP de la interfaz virtual ap0
	ipCmd := fmt.Sprintf("sudo ip addr add %s/24 dev %s 2>/dev/null || sudo ip addr replace %s/24 dev %s", req.Gateway, apInterface, req.Gateway, apInterface)
	if out, err := executeCommand(ipCmd); err != nil {
		log.Printf("Warning: Error setting IP on interface %s: %s", apInterface, strings.TrimSpace(out))
	}
	
	// 5. Activar interfaz virtual ap0
	if out, err := executeCommand(fmt.Sprintf("sudo ip link set %s up", apInterface)); err != nil {
		log.Printf("Warning: Error bringing interface %s up: %s", apInterface, strings.TrimSpace(out))
	} else {
		log.Printf("Successfully created and activated virtual interface %s", apInterface)
		// Verificar que la interfaz existe
		checkCmd := fmt.Sprintf("ip link show %s", apInterface)
		if checkOut, checkErr := executeCommand(checkCmd); checkErr == nil {
			log.Printf("Interface %s verified: %s", apInterface, strings.TrimSpace(checkOut))
		}
	}
	
	// 6. Generar configuración de hostapd usando la interfaz virtual ap0
	configPath := "/etc/hostapd/hostapd.conf"
	
	// Asegurar que el directorio existe
	executeCommand("sudo mkdir -p /etc/hostapd 2>/dev/null || true")
	
	configContent := fmt.Sprintf(`interface=%s
driver=nl80211
ssid=%s
hw_mode=g
channel=%d
country_code=%s
`, apInterface, req.SSID, req.Channel, req.Country)
	
	if req.Security == "open" {
		configContent += "auth_algs=0\n"
	} else if req.Security == "wpa2" {
		if req.Password == "" {
			return c.Status(400).JSON(fiber.Map{
				"error":   "Password required for WPA2/WPA3",
				"success": false,
			})
		}
		configContent += fmt.Sprintf(`wpa=2
wpa_passphrase=%s
wpa_key_mgmt=WPA-PSK
wpa_pairwise=TKIP
rsn_pairwise=CCMP
`, req.Password)
	} else if req.Security == "wpa3" {
		if req.Password == "" {
			return c.Status(400).JSON(fiber.Map{
				"error":   "Password required for WPA2/WPA3",
				"success": false,
			})
		}
		configContent += fmt.Sprintf(`wpa=2
wpa_passphrase=%s
wpa_key_mgmt=WPA-PSK-SHA256
wpa_pairwise=CCMP
rsn_pairwise=CCMP
`, req.Password)
	}
	
	// Guardar configuración de hostapd usando un archivo temporal
	// Crear archivo temporal
	tmpFile := "/tmp/hostapd.conf.tmp"
	log.Printf("Creating temporary config file: %s", tmpFile)
	if err := os.WriteFile(tmpFile, []byte(configContent), 0644); err != nil {
		log.Printf("Error creating temporary config file: %v", err)
		return c.Status(500).JSON(fiber.Map{
			"error":   fmt.Sprintf("Error creating temporary config file: %v", err),
			"success": false,
		})
	}
	
	// Verificar que el archivo temporal se creó correctamente
	if _, err := os.Stat(tmpFile); os.IsNotExist(err) {
		log.Printf("Temporary file was not created: %s", tmpFile)
		return c.Status(500).JSON(fiber.Map{
			"error":   "Failed to create temporary config file",
			"success": false,
		})
	}
	
	log.Printf("Temporary file created successfully, size: %d bytes", len(configContent))
	
	// Verificar que el archivo temporal existe justo antes de copiarlo
	if _, err := os.Stat(tmpFile); os.IsNotExist(err) {
		log.Printf("Temporary file does not exist before copy: %s", tmpFile)
		return c.Status(500).JSON(fiber.Map{
			"error":   "Temporary file was not created or was deleted",
			"success": false,
		})
	}
	
	// Verificar que podemos leer el archivo temporal
	if fileInfo, err := os.Stat(tmpFile); err == nil {
		log.Printf("Temporary file exists, size: %d bytes, mode: %v", fileInfo.Size(), fileInfo.Mode())
	} else {
		log.Printf("Cannot stat temporary file: %v", err)
		return c.Status(500).JSON(fiber.Map{
			"error":   fmt.Sprintf("Cannot access temporary file: %v", err),
			"success": false,
		})
	}
	
	// Copiar archivo temporal a la ubicación final con sudo
	// Primero asegurar que el directorio existe y tiene permisos correctos
	log.Printf("Ensuring /etc/hostapd directory exists...")
	if out, err := executeCommand("sudo mkdir -p /etc/hostapd"); err != nil {
		log.Printf("Warning: Error creating /etc/hostapd directory: %v, output: %s", err, out)
	}
	if out, err := executeCommand("sudo chmod 755 /etc/hostapd"); err != nil {
		log.Printf("Warning: Error setting permissions on /etc/hostapd: %v, output: %s", err, out)
	}
	
	// Verificar que el directorio existe y es accesible
	if _, err := os.Stat("/etc/hostapd"); os.IsNotExist(err) {
		log.Printf("Error: /etc/hostapd directory does not exist after creation attempt")
		return c.Status(500).JSON(fiber.Map{
			"error":   "Failed to create /etc/hostapd directory. Please run: sudo mkdir -p /etc/hostapd && sudo chmod 755 /etc/hostapd",
			"success": false,
		})
	}
	
	// Copiar archivo temporal a la ubicación final usando sudo cp
	// Primero asegurar que el archivo temporal tiene permisos de lectura
	os.Chmod(tmpFile, 0644)
	
	cmdStr := fmt.Sprintf("sudo cp %s %s", tmpFile, configPath)
	log.Printf("Executing: %s", cmdStr)
	out, err := executeCommand(cmdStr)
	if err != nil {
		log.Printf("Error copying config file: %v, output: '%s'", err, out)
		os.Remove(tmpFile) // Limpiar archivo temporal
		errorMsg := strings.TrimSpace(out)
		if errorMsg == "" {
			errorMsg = err.Error()
		}
		return c.Status(500).JSON(fiber.Map{
			"error":   fmt.Sprintf("Error saving hostapd configuration: %s. Please check sudo permissions for cp command.", errorMsg),
			"success": false,
		})
	}
	log.Printf("File copied successfully, output: '%s'", strings.TrimSpace(out))
	
	// Establecer permisos
	chmodCmd := fmt.Sprintf("sudo chmod 644 %s", configPath)
	log.Printf("Setting permissions: %s", chmodCmd)
	if out, err := executeCommand(chmodCmd); err != nil {
		log.Printf("Warning: Error setting permissions: %v, output: %s", err, strings.TrimSpace(out))
		// No fallar aquí, continuar
	}
	
	// Verificar que el archivo se creó correctamente
	if _, err := os.Stat(configPath); os.IsNotExist(err) {
		os.Remove(tmpFile)
		log.Printf("Config file was not created at: %s", configPath)
		return c.Status(500).JSON(fiber.Map{
			"error":   fmt.Sprintf("Config file was not created at %s", configPath),
			"success": false,
		})
	}
	
	log.Printf("HostAPD config file created successfully at: %s", configPath)
	
	// Limpiar archivo temporal
	os.Remove(tmpFile)
	
	// 3. Configurar dnsmasq para DHCP (mejorado basado en ap_sta_config.sh)
	dnsmasqConfigPath := "/etc/dnsmasq.conf"
	// Hacer backup de configuración existente
	executeCommand(fmt.Sprintf("sudo cp %s %s.backup 2>/dev/null || true", dnsmasqConfigPath, dnsmasqConfigPath))
	
	// Configuración mejorada: bind-interfaces y no-dhcp-interface son importantes para AP+STA
	// Esto evita que dnsmasq intente servir DHCP en wlan0 (STA) y solo lo haga en ap0 (AP)
	dnsmasqContent := fmt.Sprintf(`interface=lo,%s
no-dhcp-interface=lo,%s
bind-interfaces
server=8.8.8.8
server=8.8.4.4
domain-needed
bogus-priv
dhcp-range=%s,%s,255.255.255.0,%s
dhcp-option=3,%s
dhcp-option=6,%s
`, apInterface, phyInterface, req.DHCPRangeStart, req.DHCPRangeEnd, req.LeaseTime, req.Gateway, req.Gateway)
	
	// Guardar configuración de dnsmasq usando un archivo temporal
	tmpDnsmasqFile := "/tmp/dnsmasq.conf.tmp"
	if err := os.WriteFile(tmpDnsmasqFile, []byte(dnsmasqContent), 0644); err != nil {
		log.Printf("Error creating temporary dnsmasq config file: %v", err)
		return c.Status(500).JSON(fiber.Map{
			"error":   fmt.Sprintf("Error creating temporary dnsmasq config file: %v", err),
			"success": false,
		})
	}
	
	// Copiar archivo temporal a la ubicación final usando sudo cp
	os.Chmod(tmpDnsmasqFile, 0644)
	cmdStr2 := fmt.Sprintf("sudo cp %s %s && sudo chmod 644 %s", tmpDnsmasqFile, dnsmasqConfigPath, dnsmasqConfigPath)
	if out, err := executeCommand(cmdStr2); err != nil {
		os.Remove(tmpDnsmasqFile) // Limpiar archivo temporal
		log.Printf("Error writing dnsmasq config file: %s, output: %s", err, strings.TrimSpace(out))
		return c.Status(500).JSON(fiber.Map{
			"error":   fmt.Sprintf("Error saving dnsmasq configuration: %s", strings.TrimSpace(out)),
			"success": false,
		})
	}
	
	// Limpiar archivo temporal
	os.Remove(tmpDnsmasqFile)
	
	// 4. Configurar NAT con iptables (mejorado basado en ap_sta_config.sh)
	// Habilitar forwarding IP de forma persistente
	executeCommand("echo 1 | sudo tee /proc/sys/net/ipv4/ip_forward > /dev/null")
	executeCommand("sudo sysctl -w net.ipv4.ip_forward=1 > /dev/null 2>&1")
	
	// Hacer que el forwarding sea persistente en /etc/sysctl.conf
	sysctlCheckCmd := "grep -q '^net.ipv4.ip_forward=1' /etc/sysctl.conf || echo 'net.ipv4.ip_forward=1' | sudo tee -a /etc/sysctl.conf > /dev/null"
	executeCommand(sysctlCheckCmd)
	
	// Obtener interfaz principal (no la de hostapd)
	mainInterface := "eth0"
	if out, _ := executeCommand("ip route | grep default | awk '{print $5}' | head -1"); strings.TrimSpace(out) != "" {
		mainInterface = strings.TrimSpace(out)
	}
	
	// Calcular rango de red para ap0 (basado en gateway)
	apIPBegin := req.Gateway
	if lastDot := strings.LastIndex(req.Gateway, "."); lastDot > 0 {
		apIPBegin = req.Gateway[:lastDot]
	}
	
	// Configurar NAT (si hay interfaz principal)
	// En modo AP+STA, ap0 es la interfaz del AP y mainInterface puede ser eth0 o wlan0 (si está conectado como STA)
	if mainInterface != "" && mainInterface != apInterface {
		// Limpiar reglas antiguas para evitar duplicados
		executeCommand(fmt.Sprintf("sudo iptables -t nat -D POSTROUTING -s %s.0/24 ! -d %s.0/24 -j MASQUERADE 2>/dev/null || true", apIPBegin, apIPBegin))
		executeCommand(fmt.Sprintf("sudo iptables -t nat -D POSTROUTING -o %s -j MASQUERADE 2>/dev/null || true", mainInterface))
		executeCommand(fmt.Sprintf("sudo iptables -D FORWARD -i %s -o %s -j ACCEPT 2>/dev/null || true", apInterface, mainInterface))
		executeCommand(fmt.Sprintf("sudo iptables -D FORWARD -i %s -o %s -m state --state RELATED,ESTABLISHED -j ACCEPT 2>/dev/null || true", mainInterface, apInterface))
		
		// Añadir nueva regla NAT (usando el formato del script ap_sta_config.sh)
		// Esta regla es más específica: solo hace NAT para tráfico que sale de la red ap0
		executeCommand(fmt.Sprintf("sudo iptables -t nat -A POSTROUTING -s %s.0/24 ! -d %s.0/24 -j MASQUERADE", apIPBegin, apIPBegin))
		// También mantener la regla genérica como fallback
		executeCommand(fmt.Sprintf("sudo iptables -t nat -A POSTROUTING -o %s -j MASQUERADE", mainInterface))
		// Permitir forwarding entre ap0 y la interfaz principal
		executeCommand(fmt.Sprintf("sudo iptables -A FORWARD -i %s -o %s -j ACCEPT", apInterface, mainInterface))
		executeCommand(fmt.Sprintf("sudo iptables -A FORWARD -i %s -o %s -m state --state RELATED,ESTABLISHED -j ACCEPT", mainInterface, apInterface))
	}
	
	// 5. Configurar systemd para usar el archivo de configuración
	// Crear archivo de servicio override si no existe
	overrideDir := "/etc/systemd/system/hostapd.service.d"
	executeCommand(fmt.Sprintf("sudo mkdir -p %s 2>/dev/null || true", overrideDir))
	overrideContent := fmt.Sprintf(`[Service]
ExecStart=
ExecStart=/usr/sbin/hostapd -B %s
`, configPath)
	// Guardar override usando un archivo temporal
	tmpOverrideFile := "/tmp/hostapd-override.conf.tmp"
	if err := os.WriteFile(tmpOverrideFile, []byte(overrideContent), 0644); err != nil {
		log.Printf("Warning: Error creating temporary override file: %v", err)
	} else {
		overridePath := fmt.Sprintf("%s/override.conf", overrideDir)
		os.Chmod(tmpOverrideFile, 0644)
		cmdStr3 := fmt.Sprintf("sudo cp %s %s && sudo chmod 644 %s", tmpOverrideFile, overridePath, overridePath)
		if out, err := executeCommand(cmdStr3); err != nil {
			log.Printf("Warning: Error writing override file: %s, output: %s", err, strings.TrimSpace(out))
		} else {
			log.Printf("Override file created successfully")
		}
		os.Remove(tmpOverrideFile)
	}
	executeCommand("sudo systemctl daemon-reload")
	
	// 5.5. Crear scripts de gestión basados en ap_sta_config.sh
	// Script para limpiar /var/run/hostapd/ap0 si está colgado (manage-ap0-iface.sh)
	manageAp0Script := `#!/bin/bash
# check if hostapd service success to start or not
# in our case, it cannot start when /var/run/hostapd/ap0 exist
# so we have to delete it
echo 'Check if hostapd.service is hang cause ap0 exist...'
hostapd_is_running=$(service hostapd status | grep -c "Active: active (running)")
if test 1 -ne "${hostapd_is_running}"; then
    rm -rf /var/run/hostapd/ap0 || echo "ap0 interface does not exist, the failure is elsewhere"
fi
`
	manageAp0Path := "/bin/manage-ap0-iface.sh"
	tmpManageAp0 := "/tmp/manage-ap0-iface.sh.tmp"
	if err := os.WriteFile(tmpManageAp0, []byte(manageAp0Script), 0755); err == nil {
		executeCommand(fmt.Sprintf("sudo cp %s %s && sudo chmod +x %s", tmpManageAp0, manageAp0Path, manageAp0Path))
		os.Remove(tmpManageAp0)
		log.Printf("Created manage-ap0-iface.sh script")
	}
	
	// Script para reiniciar interfaces WiFi (rpi-wifi.sh)
	// Calcular rango de red para ap0 (basado en gateway) - reutilizar variable ya declarada
	apIPBeginForScript := req.Gateway
	if lastDot := strings.LastIndex(req.Gateway, "."); lastDot > 0 {
		apIPBeginForScript = req.Gateway[:lastDot]
	}
	rpiWifiScript := fmt.Sprintf(`#!/bin/bash
echo 'Starting Wifi AP and STA client...'
/usr/sbin/ifdown --force %s 2>/dev/null || true
/usr/sbin/ifdown --force %s 2>/dev/null || true
/usr/sbin/ifup --force %s 2>/dev/null || true
/usr/sbin/ifup --force %s 2>/dev/null || true
/usr/sbin/sysctl -w net.ipv4.ip_forward=1 > /dev/null 2>&1
/usr/sbin/iptables -t nat -A POSTROUTING -s %s.0/24 ! -d %s.0/24 -j MASQUERADE 2>/dev/null || true
/usr/bin/systemctl restart dnsmasq 2>/dev/null || true
echo 'WPA Supplicant reconfigure in 5sec...'
/usr/bin/sleep 5
wpa_cli -i %s reconfigure 2>/dev/null || true
`, phyInterface, apInterface, apInterface, phyInterface, apIPBeginForScript, apIPBeginForScript, phyInterface)
	rpiWifiPath := "/bin/rpi-wifi.sh"
	tmpRpiWifi := "/tmp/rpi-wifi.sh.tmp"
	if err := os.WriteFile(tmpRpiWifi, []byte(rpiWifiScript), 0755); err == nil {
		executeCommand(fmt.Sprintf("sudo cp %s %s && sudo chmod +x %s", tmpRpiWifi, rpiWifiPath, rpiWifiPath))
		os.Remove(tmpRpiWifi)
		log.Printf("Created rpi-wifi.sh script")
	}
	
	// Habilitar hostapd para que inicie al arrancar
	executeCommand("sudo systemctl enable hostapd 2>/dev/null || true")
	executeCommand("sudo systemctl enable dnsmasq 2>/dev/null || true")
	
	// Reiniciar dnsmasq
	if out, err := executeCommand("sudo systemctl restart dnsmasq"); err != nil {
		log.Printf("Warning: Error restarting dnsmasq: %s", strings.TrimSpace(out))
	}
	
	// Reiniciar hostapd
	if out, err := executeCommand("sudo systemctl restart hostapd"); err != nil {
		return c.Status(500).JSON(fiber.Map{
			"error":   fmt.Sprintf("Configuration saved but failed to restart hostapd: %s", strings.TrimSpace(out)),
			"success": false,
		})
	}
	
	return c.JSON(fiber.Map{
		"success": true,
		"message": "Configuration saved and services restarted",
	})
}

// ---------- Help ----------

func helpContactHandler(c *fiber.Ctx) error {
	// Aceptar cualquier payload y registrar en logs
	user := c.Locals("user").(*User)
	userID := user.ID
	InsertLog("INFO", "Contacto/help recibido", "help", &userID)
	return c.JSON(fiber.Map{"success": true})
}

// ---------- Translations ----------

func translationsHandler(c *fiber.Ctx) error {
	lang := c.Params("lang", "en")
	if lang != "en" && lang != "es" {
		lang = "en"
	}
	path := filepath.Join("locales", lang+".json")
	b, err := os.ReadFile(path)
	if err != nil {
		// fallback embebido (en install) o error
		return c.Status(500).JSON(fiber.Map{"error": err.Error()})
	}
	var out interface{}
	if err := json.Unmarshal(b, &out); err != nil {
		return c.Status(500).JSON(fiber.Map{"error": "JSON inválido en locales"})
	}
	return c.JSON(out)
}

// ---------- Legacy /api/wifi/* ----------

// wifiStatusHandler es el handler para /api/v1/wifi/status
func wifiStatusHandler(c *fiber.Ctx) error {
	return wifiLegacyStatusHandler(c)
}

func wifiLegacyStatusHandler(c *fiber.Ctx) error {
	// Verificar estado real del WiFi
	var enabled bool = false
	var hardBlocked bool = false
	var softBlocked bool = false
	
	// Método 1: Verificar con nmcli (más confiable)
	wifiCheck := execCommand("nmcli -t -f WIFI g 2>/dev/null")
	wifiOut, err := wifiCheck.Output()
	if err == nil {
		// Filtrar mensajes de error de sudo
		wifiState := strings.ToLower(strings.TrimSpace(filterSudoErrors(wifiOut)))
		if strings.Contains(wifiState, "enabled") || strings.Contains(wifiState, "on") {
			enabled = true
		} else if strings.Contains(wifiState, "disabled") || strings.Contains(wifiState, "off") {
			enabled = false
		}
	}
	
	// Método 2: Verificar con rfkill para obtener información de bloqueo
	rfkillOut, _ := execCommand("rfkill list wifi 2>/dev/null").CombinedOutput()
	// Filtrar mensajes de error de sudo
	rfkillStr := strings.ToLower(filterSudoErrors(rfkillOut))
	if strings.Contains(rfkillStr, "hard blocked: yes") {
		hardBlocked = true
		enabled = false
	} else if strings.Contains(rfkillStr, "soft blocked: yes") {
		softBlocked = true
		enabled = false
	} else {
		// Si no está bloqueado, verificar explícitamente si está habilitado usando iwconfig/ip
		// Verificar con iwconfig si la interfaz está activa
		iwOut, _ := execCommand("iwconfig 2>/dev/null | grep -i 'wlan' | head -1").CombinedOutput()
		// Filtrar mensajes de error de sudo
		cleanIwOut := filterSudoErrors(iwOut)
		if len(cleanIwOut) > 0 {
			// Si hay una interfaz WiFi, verificar si está activa
			iwStatus, _ := execCommand("iwconfig 2>/dev/null | grep -i 'wlan' | head -1 | grep -i 'unassociated'").CombinedOutput()
			// Filtrar también la salida de iwStatus
			cleanIwStatus := filterSudoErrors(iwStatus)
			if len(cleanIwStatus) == 0 {
				// No está "unassociated", asumir habilitado
				enabled = true
			}
		} else {
			// Verificar con ip si la interfaz está UP
			ipCheck := exec.Command("sh", "-c", "ip link show | grep -E '^[0-9]+: wlan' | grep -i 'state UP'")
			if ipOut, err := ipCheck.Output(); err == nil && len(ipOut) > 0 {
				enabled = true
			}
		}
	}
	
	// Obtener SSID actual si está conectado usando wpa_cli o iw
	ssid := ""
	connected := false
	iface := "wlan0"
	
	// Detectar interfaz WiFi
	ipIfaceCmd := exec.Command("sh", "-c", "ip -o link show | awk -F': ' '{print $2}' | grep -E '^wlan|^wl' | head -1")
	if ipIfaceOut, err := ipIfaceCmd.Output(); err == nil {
		if ipIfaceStr := strings.TrimSpace(string(ipIfaceOut)); ipIfaceStr != "" {
			iface = ipIfaceStr
		}
	}
	
	// Método 1: Intentar con wpa_cli (si está usando wpa_supplicant)
	wpaStatusCmd := exec.Command("sh", "-c", fmt.Sprintf("sudo wpa_cli -i %s status 2>/dev/null", iface))
	wpaStatusOut, wpaErr := wpaStatusCmd.CombinedOutput()
	if wpaErr == nil && len(wpaStatusOut) > 0 {
		wpaStatus := string(wpaStatusOut)
		for _, line := range strings.Split(wpaStatus, "\n") {
			line = strings.TrimSpace(line)
			if strings.HasPrefix(line, "ssid=") {
				ssid = strings.TrimPrefix(line, "ssid=")
				if ssid != "" {
					// Verificar si está realmente conectado
					if strings.Contains(wpaStatus, "wpa_state=COMPLETED") {
						connected = true
					}
				}
				break
			}
		}
	}
	
	// Método 2: Si wpa_cli no funcionó, intentar con iw
	if !connected || ssid == "" {
		iwLinkCmd := exec.Command("sh", "-c", fmt.Sprintf("iw dev %s link 2>/dev/null", iface))
		iwLinkOut, iwErr := iwLinkCmd.CombinedOutput()
		if iwErr == nil && len(iwLinkOut) > 0 {
			iwLink := string(iwLinkOut)
			for _, line := range strings.Split(iwLink, "\n") {
				line = strings.TrimSpace(line)
				if strings.HasPrefix(line, "Connected to ") {
					// Formato: "Connected to aa:bb:cc:dd:ee:ff (on wlan0)"
					// O buscar SSID en otra línea
					connected = true
				} else if strings.Contains(line, "SSID:") {
					ssid = strings.TrimSpace(strings.TrimPrefix(line, "SSID:"))
					if ssid != "" {
						connected = true
					}
				}
			}
		}
	}
	
	// Método 3: Fallback a iwconfig si está disponible
	if !connected || ssid == "" {
		iwOut, _ := execCommand("iwconfig 2>/dev/null | grep -i 'essid' | grep -v 'off/any' | head -1").CombinedOutput()
		iwStr := filterSudoErrors(iwOut)
		if strings.Contains(iwStr, "ESSID:") {
			// Extraer SSID
			parts := strings.Split(iwStr, "ESSID:")
			if len(parts) > 1 {
				ssid = strings.TrimSpace(strings.Trim(parts[1], "\""))
				if ssid != "" && ssid != "off/any" {
					connected = true
				}
			}
		}
	}
	
	// Verificar realmente si está conectado - no solo si tiene SSID
	// Debe tener wpa_state=COMPLETED Y una IP asignada
	reallyConnected := false
	if connected && ssid != "" {
		// Verificar que realmente tenga una IP (no solo que wpa_cli diga COMPLETED)
		ipCheckCmd := exec.Command("sh", "-c", fmt.Sprintf("ip addr show %s 2>/dev/null | grep 'inet ' | awk '{print $2}' | cut -d/ -f1 | head -1", iface))
		ipOut, ipErr := ipCheckCmd.Output()
		if ipErr == nil {
			ip := strings.TrimSpace(string(ipOut))
			if ip != "" && ip != "N/A" {
				reallyConnected = true
				log.Printf("WiFi realmente conectado: SSID=%s, IP=%s", ssid, ip)
			} else {
				log.Printf("WiFi tiene SSID pero no IP: SSID=%s, IP=%s", ssid, ip)
				// Verificar si está obteniendo IP
				dhcpCheck := exec.Command("sh", "-c", fmt.Sprintf("ps aux | grep -E '[d]hclient|udhcpc' | grep %s", iface))
				if dhcpOut, _ := dhcpCheck.Output(); len(dhcpOut) > 0 {
					log.Printf("WiFi está obteniendo IP (DHCP en proceso)")
					reallyConnected = false // Aún no está completamente conectado
				}
			}
		}
	}
	
	// Obtener información detallada de la conexión si está realmente conectado
	var connectionInfo fiber.Map = nil
	if reallyConnected && ssid != "" {
		connectionInfo = fiber.Map{
			"ssid": ssid,
		}
		
		// Detectar interfaz WiFi (wlan0 por defecto)
		// Usar solo ip/iw, sin nmcli
		iface := "wlan0"
		ipIfaceCmd := exec.Command("sh", "-c", "ip -o link show | awk -F': ' '{print $2}' | grep -E '^wlan|^wl' | head -1")
		if ipIfaceOut, err := ipIfaceCmd.Output(); err == nil {
			if ipIfaceStr := strings.TrimSpace(string(ipIfaceOut)); ipIfaceStr != "" {
				iface = ipIfaceStr
			}
		}
		
		// Obtener señal, seguridad y canal usando wpa_cli o iw
		// Método 1: Intentar con wpa_cli (si está usando wpa_supplicant)
		wpaStatusCmd := exec.Command("sh", "-c", fmt.Sprintf("sudo wpa_cli -i %s status 2>/dev/null", iface))
		wpaStatusOut, wpaErr := wpaStatusCmd.CombinedOutput()
		if wpaErr == nil && len(wpaStatusOut) > 0 {
			wpaStatus := string(wpaStatusOut)
			log.Printf("wpa_cli status output for %s: %s", iface, wpaStatus)
			// Parsear salida de wpa_cli status
			for _, line := range strings.Split(wpaStatus, "\n") {
				line = strings.TrimSpace(line)
				if strings.HasPrefix(line, "signal=") {
					signalStr := strings.TrimPrefix(line, "signal=")
					signalStr = strings.TrimSpace(signalStr)
					if signalStr != "" && signalStr != "0" {
						// wpa_cli puede devolver la señal como número negativo o positivo
						// Convertir a entero para verificar que sea válido
						if signalInt, err := strconv.Atoi(signalStr); err == nil && signalInt != 0 {
							// Asegurar que sea negativo (dBm siempre es negativo)
							if signalInt > 0 {
								signalInt = -signalInt
								signalStr = strconv.Itoa(signalInt)
							}
							connectionInfo["signal"] = signalStr
							log.Printf("Found signal from wpa_cli: %s dBm", signalStr)
						}
					}
				} else if strings.HasPrefix(line, "key_mgmt=") {
					keyMgmt := strings.TrimPrefix(line, "key_mgmt=")
					keyMgmt = strings.TrimSpace(keyMgmt)
					if keyMgmt != "" {
						if strings.Contains(keyMgmt, "WPA2") || strings.Contains(keyMgmt, "WPA-PSK") {
							connectionInfo["security"] = "WPA2"
						} else if strings.Contains(keyMgmt, "WPA3") || strings.Contains(keyMgmt, "SAE") {
							connectionInfo["security"] = "WPA3"
						} else if strings.Contains(keyMgmt, "NONE") {
							connectionInfo["security"] = "Open"
						} else {
							connectionInfo["security"] = keyMgmt
						}
						log.Printf("Found security from wpa_cli: %s", connectionInfo["security"])
					}
				} else if strings.HasPrefix(line, "freq=") {
					freqStr := strings.TrimPrefix(line, "freq=")
					freqStr = strings.TrimSpace(freqStr)
					if freq, err := strconv.Atoi(freqStr); err == nil && freq > 0 {
						// Convertir frecuencia a canal
						var channel int
						if freq >= 2412 && freq <= 2484 {
							channel = (freq-2412)/5 + 1
						} else if freq >= 5000 && freq <= 5825 {
							channel = (freq - 5000) / 5
						} else if freq >= 5955 && freq <= 7115 {
							// 6 GHz band
							channel = (freq - 5955) / 5
						}
						if channel > 0 {
							connectionInfo["channel"] = strconv.Itoa(channel)
							log.Printf("Found channel from wpa_cli: %d (from freq %d)", channel, freq)
						}
					}
				}
			}
		} else {
			log.Printf("wpa_cli failed or returned empty for %s: %v", iface, wpaErr)
		}
		
		// Método 2: Si wpa_cli no funcionó o falta información, usar iw para obtener información
		if connectionInfo["signal"] == nil || connectionInfo["signal"] == "" || connectionInfo["signal"] == "0" ||
			connectionInfo["channel"] == nil || connectionInfo["channel"] == "" ||
			connectionInfo["security"] == nil || connectionInfo["security"] == "" {
			log.Printf("Getting additional info from iw for interface %s", iface)
			// Intentar con sudo primero
			iwLinkCmd := exec.Command("sh", "-c", fmt.Sprintf("sudo iw dev %s link 2>/dev/null", iface))
			iwLinkOut, iwErr := iwLinkCmd.CombinedOutput()
			if iwErr != nil || len(iwLinkOut) == 0 {
				// Si falla con sudo, intentar sin sudo
				iwLinkCmd = exec.Command("sh", "-c", fmt.Sprintf("iw dev %s link 2>/dev/null", iface))
				iwLinkOut, iwErr = iwLinkCmd.CombinedOutput()
			}
			if iwErr == nil && len(iwLinkOut) > 0 {
				iwLink := string(iwLinkOut)
				log.Printf("iw link output for %s: %s", iface, iwLink)
				for _, line := range strings.Split(iwLink, "\n") {
					line = strings.TrimSpace(line)
					// Obtener señal
					if (connectionInfo["signal"] == nil || connectionInfo["signal"] == "" || connectionInfo["signal"] == "0") && strings.Contains(line, "signal:") {
						// Formato: "signal: -45 dBm" o "signal: -45" o "Signal: -45 dBm"
						parts := strings.Fields(line)
						for i, part := range parts {
							if (part == "signal:" || part == "Signal:") && i+1 < len(parts) {
								signalStr := strings.TrimSpace(parts[i+1])
								// Remover "dBm" si está presente
								signalStr = strings.TrimSuffix(signalStr, "dBm")
								signalStr = strings.TrimSpace(signalStr)
								// Verificar que no sea 0 o vacío
								if signalStr != "" && signalStr != "0" {
									connectionInfo["signal"] = signalStr
									log.Printf("Found signal from iw: %s", signalStr)
								}
								break
							}
						}
					}
					// Obtener frecuencia/canal
					if (connectionInfo["channel"] == nil || connectionInfo["channel"] == "") && strings.Contains(line, "freq:") {
						parts := strings.Fields(line)
						for i, part := range parts {
							if part == "freq:" && i+1 < len(parts) {
								freqStr := strings.TrimSpace(parts[i+1])
								if freq, err := strconv.Atoi(freqStr); err == nil && freq > 0 {
									// Convertir frecuencia a canal
									var channel int
									if freq >= 2412 && freq <= 2484 {
										channel = (freq-2412)/5 + 1
									} else if freq >= 5000 && freq <= 5825 {
										channel = (freq - 5000) / 5
									} else if freq >= 5955 && freq <= 7115 {
										// 6 GHz band
										channel = (freq - 5955) / 5
									}
									if channel > 0 {
										connectionInfo["channel"] = strconv.Itoa(channel)
										log.Printf("Found channel from iw: %d (from freq %d)", channel, freq)
									}
								}
								break
							}
						}
					}
					// Obtener seguridad desde iw (si no se obtuvo de wpa_cli)
					if connectionInfo["security"] == nil && strings.Contains(line, "WPA") {
						if strings.Contains(line, "WPA3") || strings.Contains(line, "SAE") {
							connectionInfo["security"] = "WPA3"
						} else if strings.Contains(line, "WPA2") || strings.Contains(line, "WPA") {
							connectionInfo["security"] = "WPA2"
						}
					}
				}
			} else {
				log.Printf("iw link command failed or returned empty: %v, output: %s", iwErr, string(iwLinkOut))
			}
		}
		
		// Método 3: Intentar con /proc/net/wireless para señal
		if connectionInfo["signal"] == nil || connectionInfo["signal"] == "" || connectionInfo["signal"] == "0" {
			log.Printf("Trying /proc/net/wireless for signal on %s", iface)
			wirelessCmd := exec.Command("sh", "-c", fmt.Sprintf("cat /proc/net/wireless 2>/dev/null | grep %s", iface))
			wirelessOut, wirelessErr := wirelessCmd.Output()
			if wirelessErr == nil && len(wirelessOut) > 0 {
				wirelessLine := strings.TrimSpace(string(wirelessOut))
				log.Printf("/proc/net/wireless output: %s", wirelessLine)
				// Formato: "wlan0: 0000 123. 456. 0.000 0.000 0 0 0 0 0 0"
				// Campo 3 es signal level (multiplicado por 10, negativo)
				parts := strings.Fields(wirelessLine)
				if len(parts) >= 3 {
					if signalLevel, err := strconv.Atoi(strings.TrimSuffix(parts[2], ".")); err == nil && signalLevel > 0 {
						// Convertir de formato /proc/net/wireless (multiplicado por 10) a dBm
						signalDbm := signalLevel / 10
						// El valor en /proc/net/wireless es positivo pero representa dBm negativo
						// Por ejemplo, 45 significa -45 dBm
						if signalDbm > 0 {
							connectionInfo["signal"] = fmt.Sprintf("-%d", signalDbm)
							log.Printf("Found signal from /proc/net/wireless: -%d dBm", signalDbm)
						}
					}
				}
			}
		}
		
		// Método 4: Intentar con iwconfig como último recurso
		if (connectionInfo["signal"] == nil || connectionInfo["signal"] == "" || connectionInfo["signal"] == "0") ||
			(connectionInfo["channel"] == nil || connectionInfo["channel"] == "") {
			log.Printf("Trying iwconfig as last resort for interface %s", iface)
			iwconfigCmd := exec.Command("sh", "-c", fmt.Sprintf("iwconfig %s 2>/dev/null", iface))
			iwconfigOut, iwconfigErr := iwconfigCmd.CombinedOutput()
			if iwconfigErr == nil && len(iwconfigOut) > 0 {
				iwconfigStr := string(iwconfigOut)
				log.Printf("iwconfig output: %s", iwconfigStr)
				// Buscar señal (formato: "Signal level=-45 dBm")
				if connectionInfo["signal"] == nil || connectionInfo["signal"] == "" || connectionInfo["signal"] == "0" {
					if strings.Contains(iwconfigStr, "Signal level=") {
						parts := strings.Split(iwconfigStr, "Signal level=")
						if len(parts) > 1 {
							signalPart := strings.Fields(parts[1])[0]
							signalStr := strings.TrimSpace(signalPart)
							// Remover "dBm" si está presente
							signalStr = strings.TrimSuffix(signalStr, "dBm")
							signalStr = strings.TrimSpace(signalStr)
							if signalStr != "" && signalStr != "0" {
								connectionInfo["signal"] = signalStr
								log.Printf("Found signal from iwconfig: %s", signalStr)
							}
						}
					}
				}
				// Buscar canal (formato: "Channel:6")
				if connectionInfo["channel"] == nil || connectionInfo["channel"] == "" {
					if strings.Contains(iwconfigStr, "Channel:") {
						parts := strings.Split(iwconfigStr, "Channel:")
						if len(parts) > 1 {
							channelPart := strings.Fields(parts[1])[0]
							channelStr := strings.TrimSpace(channelPart)
							if channelStr != "" {
								connectionInfo["channel"] = channelStr
								log.Printf("Found channel from iwconfig: %s", channelStr)
							}
						}
					}
				}
			}
		}
		
		// Establecer valores por defecto si no se encontró información
		if connectionInfo["signal"] == nil || connectionInfo["signal"] == "" || connectionInfo["signal"] == "0" {
			log.Printf("Warning: Could not determine signal strength for %s", iface)
		}
		if connectionInfo["channel"] == nil || connectionInfo["channel"] == "" {
			log.Printf("Warning: Could not determine channel for %s", iface)
		}
		if connectionInfo["security"] == nil || connectionInfo["security"] == "" {
			// Si no se encontró seguridad, intentar inferir desde wpa_supplicant config
			log.Printf("Warning: Could not determine security for %s, defaulting to WPA2", iface)
			connectionInfo["security"] = "WPA2" // Valor por defecto común
		}
		
		// No usar nmcli - solo wpa_cli e iw
		
		// Obtener IP address de la interfaz WiFi
		if iface != "" {
			// Obtener IP
			ipCmd := exec.Command("sh", "-c", fmt.Sprintf("ip addr show %s 2>/dev/null | grep 'inet ' | awk '{print $2}' | cut -d/ -f1 | head -1", iface))
			ipOut, _ := ipCmd.Output()
			if ipStr := strings.TrimSpace(string(ipOut)); ipStr != "" {
				connectionInfo["ip"] = ipStr
			}
			
			// Obtener MAC
			macCmd := exec.Command("sh", "-c", fmt.Sprintf("cat /sys/class/net/%s/address 2>/dev/null", iface))
			macOut, _ := macCmd.Output()
			if macStr := strings.TrimSpace(string(macOut)); macStr != "" {
				connectionInfo["mac"] = macStr
			}
			
			// Obtener velocidad
			speedCmd := exec.Command("sh", "-c", fmt.Sprintf("cat /sys/class/net/%s/speed 2>/dev/null", iface))
			speedOut, _ := speedCmd.Output()
			if speedStr := strings.TrimSpace(string(speedOut)); speedStr != "" && speedStr != "-1" {
				connectionInfo["speed"] = speedStr + " Mbps"
			}
		}
	}
	
	// Si WiFi está habilitado pero no conectado, intentar obtener información básica de la interfaz
	if !connected && enabled {
		ifaceCmd := execCommand("nmcli -t -f DEVICE,TYPE dev status 2>/dev/null | grep wifi | head -1 | cut -d: -f1")
		if ifaceOut, err := ifaceCmd.Output(); err == nil {
			iface := strings.TrimSpace(string(ifaceOut))
			if iface != "" {
				if connectionInfo == nil {
					connectionInfo = fiber.Map{}
				}
				// Obtener MAC aunque no esté conectado
				macCmd := exec.Command("sh", "-c", fmt.Sprintf("cat /sys/class/net/%s/address 2>/dev/null", iface))
				macOut, _ := macCmd.Output()
				if macStr := strings.TrimSpace(string(macOut)); macStr != "" {
					connectionInfo["mac"] = macStr
				}
			}
		}
	}
	
	return c.JSON(fiber.Map{
		"enabled":          enabled,
		"connected":        reallyConnected,
		"current_connection": ssid,
		"ssid":             ssid,
		"hard_blocked":     hardBlocked,
		"soft_blocked":     softBlocked,
		"connection_info":  connectionInfo,
	})
}

func wifiLegacyStoredNetworksHandler(c *fiber.Ctx) error {
	// Leer redes guardadas desde wpa_supplicant
	var networks []fiber.Map
	var lastConnected []string
	
	// Intentar leer desde wpa_supplicant usando wpa_cli
	interfaceName := "wlan0"
	
	// Listar redes guardadas
	listCmd := exec.Command("sh", "-c", fmt.Sprintf("sudo wpa_cli -i %s list_networks 2>/dev/null", interfaceName))
	listOut, err := listCmd.CombinedOutput()
	
	if err == nil && len(listOut) > 0 {
		lines := strings.Split(string(listOut), "\n")
		for i, line := range lines {
			if i == 0 || strings.TrimSpace(line) == "" {
				continue // Saltar encabezado y líneas vacías
			}
			
			fields := strings.Fields(line)
			if len(fields) >= 2 {
				networkID := fields[0]
				ssid := fields[1]
				
				if ssid != "" && ssid != "--" {
					// Limpiar SSID (puede venir con comillas)
					ssid = strings.Trim(ssid, "\"")
					
					network := fiber.Map{
						"id":     networkID,
						"ssid":   ssid,
						"status": "saved",
					}
					
					// Verificar si está habilitada
					enabledCmd := exec.Command("sh", "-c", fmt.Sprintf("sudo wpa_cli -i %s get_network %s disabled 2>/dev/null", interfaceName, networkID))
					enabledOut, _ := enabledCmd.CombinedOutput()
					if strings.TrimSpace(string(enabledOut)) == "0" {
						network["enabled"] = true
						lastConnected = append(lastConnected, ssid)
					} else {
						network["enabled"] = false
					}
					
					networks = append(networks, network)
				}
			}
		}
	}
	
	return c.JSON(fiber.Map{
		"success":        true,
		"networks":       networks,
		"last_connected": lastConnected,
	})
}

func wifiLegacyAutoconnectHandler(c *fiber.Ctx) error {
	return c.JSON(fiber.Map{"success": false})
}

func wifiLegacyScanHandler(c *fiber.Ctx) error {
	// Reusar el scan Lua
	if luaEngine == nil {
		return c.JSON(fiber.Map{"success": true, "networks": []fiber.Map{}})
	}
	result, err := luaEngine.Execute("wifi_scan.lua", nil)
	if err != nil {
		return c.Status(500).JSON(fiber.Map{"error": err.Error()})
	}
	return c.JSON(fiber.Map{"success": true, "networks": result["networks"]})
}

func wifiLegacyDisconnectHandler(c *fiber.Ctx) error {
	user := c.Locals("user").(*User)
	userID := user.ID

	// Obtener la conexión WiFi activa
	activeConnCmd := execCommand("nmcli -t -f NAME,TYPE,DEVICE connection show --active | grep -i wifi")
	activeConnOut, err := activeConnCmd.Output()
	
	var connectionName string
	if err == nil && len(activeConnOut) > 0 {
		// Extraer el nombre de la conexión (primera columna)
		lines := strings.Split(strings.TrimSpace(string(activeConnOut)), "\n")
		if len(lines) > 0 {
			parts := strings.Split(lines[0], ":")
			if len(parts) > 0 {
				connectionName = strings.TrimSpace(parts[0])
			}
		}
	}

	// Si encontramos una conexión activa, desconectarla
	if connectionName != "" {
		// Método 1: Desconectar la conexión específica
		disconnectCmd := execCommand(fmt.Sprintf("nmcli connection down '%s'", connectionName))
		disconnectOut, disconnectErr := disconnectCmd.CombinedOutput()
		
		if disconnectErr == nil {
			InsertLog("INFO", fmt.Sprintf("WiFi desconectado: %s (usuario: %s)", connectionName, user.Username), "wifi", &userID)
			return c.JSON(fiber.Map{"success": true, "message": "Disconnected from " + connectionName})
		}
		
		// Si falla, intentar desconectar el dispositivo WiFi directamente
		log.Printf("Error desconectando conexión %s: %s, intentando desconectar dispositivo", connectionName, string(disconnectOut))
	}

	// Método 2: Desconectar el dispositivo WiFi directamente
	// Obtener el dispositivo WiFi activo
	wifiDeviceCmd := execCommand("nmcli -t -f DEVICE,TYPE device status | grep -i wifi | head -1 | cut -d: -f1")
	wifiDeviceOut, err := wifiDeviceCmd.Output()
	
	if err == nil && len(wifiDeviceOut) > 0 {
		deviceName := strings.TrimSpace(string(wifiDeviceOut))
		if deviceName != "" {
			deviceDisconnectCmd := execCommand(fmt.Sprintf("nmcli device disconnect '%s'", deviceName))
			deviceDisconnectOut, deviceDisconnectErr := deviceDisconnectCmd.CombinedOutput()
			
			if deviceDisconnectErr == nil {
				InsertLog("INFO", fmt.Sprintf("Dispositivo WiFi desconectado: %s (usuario: %s)", deviceName, user.Username), "wifi", &userID)
				return c.JSON(fiber.Map{"success": true, "message": "Disconnected from WiFi device " + deviceName})
			}
			
			log.Printf("Error desconectando dispositivo %s: %s", deviceName, string(deviceDisconnectOut))
		}
	}

	// Método 3: Fallback - apagar y encender el networking (método anterior)
	networkingOffCmd := execCommand("nmcli networking off")
	networkingOffOut, networkingOffErr := networkingOffCmd.CombinedOutput()
	
	if networkingOffErr != nil {
		errorMsg := fmt.Sprintf("Error desconectando WiFi: %s", strings.TrimSpace(string(networkingOffOut)))
		InsertLog("ERROR", fmt.Sprintf("Error en desconexión WiFi (usuario: %s): %s", user.Username, errorMsg), "wifi", &userID)
		return c.Status(500).JSON(fiber.Map{"success": false, "error": errorMsg})
	}

	// Esperar un momento antes de reactivar
	time.Sleep(1 * time.Second)
	
	networkingOnCmd := execCommand("nmcli networking on")
	networkingOnOut, networkingOnErr := networkingOnCmd.CombinedOutput()
	
	if networkingOnErr != nil {
		errorMsg := fmt.Sprintf("Error reactivando networking: %s", strings.TrimSpace(string(networkingOnOut)))
		InsertLog("ERROR", fmt.Sprintf("Error reactivando networking (usuario: %s): %s", user.Username, errorMsg), "wifi", &userID)
		return c.Status(500).JSON(fiber.Map{"success": false, "error": errorMsg})
	}

	InsertLog("INFO", fmt.Sprintf("WiFi desconectado mediante fallback (usuario: %s)", user.Username), "wifi", &userID)
	return c.JSON(fiber.Map{"success": true, "message": "Disconnected from WiFi"})
}

// ---------- helpers ----------

func strconvAtoiSafe(s string) (int, error) {
	n := 0
	for _, r := range s {
		if r < '0' || r > '9' {
			return 0, fmt.Errorf("invalid int")
		}
		n = n*10 + int(r-'0')
	}
	return n, nil
}

func mapActiveStatus(status string) string {
	status = strings.ToLower(strings.TrimSpace(status))
	if status == "active" {
		return "connected"
	}
	return "disconnected"
}

func mapBoolStatus(v string) string {
	v = strings.ToLower(strings.TrimSpace(v))
	if v == "true" || v == "1" || v == "yes" {
		return "connected"
	}
	return "disconnected"
}

