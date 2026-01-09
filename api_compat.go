package main

import (
	"encoding/json"
	"fmt"
	"log"
	"os"
	"os/exec"
	"path/filepath"
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
		return c.Status(500).JSON(fiber.Map{"error": strings.TrimSpace(string(out))})
	}
	var routes []fiber.Map
	for _, line := range strings.Split(string(out), "\n") {
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
		for i := 0; i < len(parts)-1; i++ {
			if parts[i] == "via" {
				route["gateway"] = parts[i+1]
			}
			if parts[i] == "dev" {
				route["interface"] = parts[i+1]
			}
			if parts[i] == "metric" {
				route["metric"] = parts[i+1]
			}
		}
		routes = append(routes, route)
	}
	return c.JSON(routes)
}

func networkFirewallToggleHandler(c *fiber.Ctx) error {
	return c.Status(501).JSON(fiber.Map{"error": "Firewall toggle no implementado"})
}

func networkConfigHandler(c *fiber.Ctx) error {
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

	// Fallback: Intentar métodos directos
	// Método 1: Intentar con nmcli
	out, err := execCommand("nmcli -t -f WIFI g 2>/dev/null").CombinedOutput()
	state := strings.TrimSpace(string(out))
	if err == nil && state != "" {
		var cmd string
		var wasEnabled bool
		if strings.Contains(strings.ToLower(state), "enabled") || strings.Contains(strings.ToLower(state), "on") {
			cmd = "nmcli radio wifi off"
			wasEnabled = true
		} else {
			cmd = "nmcli radio wifi on"
			wasEnabled = false
		}
		_, err2 := execCommand(cmd + " 2>/dev/null").CombinedOutput()
		if err2 == nil {
			// Si se activó WiFi, también activar la interfaz específica
			if !wasEnabled {
				time.Sleep(1 * time.Second)
				
				// Detectar y activar la interfaz WiFi específica
				ifaceCmd := execCommand("nmcli -t -f DEVICE,TYPE dev status 2>/dev/null | grep wifi | head -1 | cut -d: -f1")
				ifaceOut, ifaceErr := ifaceCmd.Output()
				if ifaceErr == nil {
					iface := strings.TrimSpace(string(ifaceOut))
					if iface != "" {
						// Activar la interfaz específica
						execCommand(fmt.Sprintf("nmcli device set %s managed yes 2>/dev/null", iface)).Run()
						execCommand(fmt.Sprintf("nmcli device connect %s 2>/dev/null", iface)).Run()
						time.Sleep(1 * time.Second)
					}
				}
				
				// Verificar que se activó correctamente
				verifyOut, verifyErr := execCommand("nmcli -t -f WIFI g 2>/dev/null").CombinedOutput()
				if verifyErr == nil {
					verifyState := strings.ToLower(strings.TrimSpace(string(verifyOut)))
					if strings.Contains(verifyState, "enabled") || strings.Contains(verifyState, "on") {
						InsertLog("INFO", fmt.Sprintf("WiFi activado exitosamente usando nmcli con sudo (usuario: %s)", user.Username), "wifi", &userID)
						return c.JSON(fiber.Map{"success": true, "message": "WiFi activado exitosamente"})
					}
				}
			}
			InsertLog("INFO", fmt.Sprintf("WiFi toggle exitoso usando nmcli con sudo (usuario: %s)", user.Username), "wifi", &userID)
			return c.JSON(fiber.Map{"success": true, "message": "WiFi toggle exitoso"})
		}
	}

	// Método 2: Intentar con rfkill
	rfkillOut, rfkillErr := execCommand("rfkill list wifi 2>/dev/null | grep -i 'wifi' | head -1").CombinedOutput()
	if rfkillErr == nil && strings.Contains(strings.ToLower(string(rfkillOut)), "wifi") {
		// Obtener estado actual
		statusOut, _ := execCommand("rfkill list wifi 2>/dev/null | grep -i 'soft blocked'").CombinedOutput()
		isBlocked := strings.Contains(strings.ToLower(string(statusOut)), "yes")
		
		var rfkillCmd string
		if isBlocked {
			rfkillCmd = "rfkill unblock wifi"
		} else {
			rfkillCmd = "rfkill block wifi"
		}
		
		_, rfkillToggleErr := execCommand(rfkillCmd + " 2>/dev/null").CombinedOutput()
		if rfkillToggleErr == nil {
			InsertLog("INFO", fmt.Sprintf("WiFi toggle exitoso usando rfkill con sudo (usuario: %s)", user.Username), "wifi", &userID)
			return c.JSON(fiber.Map{"success": true, "message": "WiFi toggle exitoso"})
		}
	}

	// Método 3: Intentar con iwconfig/ifconfig
	// Primero intentar detectar interfaz con nmcli
	ifaceCmd := execCommand("nmcli -t -f DEVICE,TYPE dev status 2>/dev/null | grep wifi | head -1 | cut -d: -f1")
	ifaceOut, ifaceErr := ifaceCmd.Output()
	var iface string
	if ifaceErr == nil {
		iface = strings.TrimSpace(string(ifaceOut))
	}
	
	// Si no se encontró con nmcli, intentar con iwconfig
	if iface == "" {
		iwOut, iwErr := execCommand("iwconfig 2>/dev/null | grep -i 'wlan' | head -1 | awk '{print $1}'").CombinedOutput()
		if iwErr == nil {
			iface = strings.TrimSpace(string(iwOut))
		}
	}
	
	// Si no se encontró, intentar con ip link (sin sudo, solo lectura)
	if iface == "" {
		ipOut, ipErr := exec.Command("sh", "-c", "ip -o link show | awk -F': ' '{print $2}' | grep -E '^wlan|^wl' | head -1").Output()
		if ipErr == nil {
			iface = strings.TrimSpace(string(ipOut))
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
	errorMsg := "No se pudo cambiar el estado de WiFi. Verifica que tengas permisos sudo configurados (NOPASSWD) o que nmcli/rfkill estén disponibles. Para configurar sudo sin contraseña, ejecuta: sudo visudo y agrega: usuario ALL=(ALL) NOPASSWD: /usr/bin/nmcli, /usr/sbin/rfkill, /sbin/ifconfig"
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

func hostapdAccessPointsHandler(c *fiber.Ctx) error { return c.JSON([]fiber.Map{}) }
func hostapdClientsHandler(c *fiber.Ctx) error     { return c.JSON([]fiber.Map{}) }
func hostapdToggleHandler(c *fiber.Ctx) error      { return c.Status(501).JSON(fiber.Map{"error": "HostAPD toggle no implementado"}) }
func hostapdRestartHandler(c *fiber.Ctx) error     { return c.Status(501).JSON(fiber.Map{"error": "HostAPD restart no implementado"}) }
func hostapdConfigHandler(c *fiber.Ctx) error      { return c.Status(501).JSON(fiber.Map{"error": "HostAPD config no implementado"}) }

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
		// Si no está bloqueado, verificar explícitamente si está habilitado
		// Re-verificar con nmcli para asegurar el estado
		wifiCheck2 := execCommand("nmcli -t -f WIFI g 2>/dev/null")
		wifiOut2, err2 := wifiCheck2.Output()
		if err2 == nil {
			// Filtrar mensajes de error de sudo
			wifiState2 := strings.ToLower(strings.TrimSpace(filterSudoErrors(wifiOut2)))
			if strings.Contains(wifiState2, "enabled") || strings.Contains(wifiState2, "on") {
				enabled = true
			} else if strings.Contains(wifiState2, "disabled") || strings.Contains(wifiState2, "off") {
				enabled = false
			}
		}
	}
	
	// Si nmcli no está disponible y rfkill no muestra bloqueo, verificar con iwconfig
	if !enabled && !hardBlocked && !softBlocked {
		iwOut, _ := execCommand("iwconfig 2>/dev/null | grep -i 'wlan' | head -1").CombinedOutput()
		// Filtrar mensajes de error de sudo
		cleanIwOut := filterSudoErrors(iwOut)
		if len(cleanIwOut) > 0 {
			// Si hay una interfaz WiFi, verificar si está activa
			iwStatus, _ := execCommand("iwconfig 2>/dev/null | grep -i 'wlan' | head -1 | grep -i 'unassociated'").CombinedOutput()
			// Filtrar también la salida de iwStatus
			cleanIwStatus := filterSudoErrors(iwStatus)
			if len(cleanIwStatus) == 0 {
				// No está "unassociated", verificar también con nmcli
				wifiCheck3 := execCommand("nmcli -t -f WIFI g 2>/dev/null")
				wifiOut3, err3 := wifiCheck3.Output()
				if err3 == nil {
					// Filtrar mensajes de error de sudo
					wifiState3 := strings.ToLower(strings.TrimSpace(filterSudoErrors(wifiOut3)))
					if strings.Contains(wifiState3, "enabled") || strings.Contains(wifiState3, "on") {
						enabled = true
					}
				} else {
					// Si nmcli no funciona, asumir habilitado si no está unassociated
					enabled = true
				}
			}
		}
	}
	
	// Obtener SSID actual si está conectado
	ssidOut, _ := execCommand("nmcli -t -f ACTIVE,SSID dev wifi 2>/dev/null | grep '^yes:' | head -1 | cut -d: -f2").CombinedOutput()
	ssid := strings.TrimSpace(filterSudoErrors(ssidOut))
	connected := ssid != ""
	
	// Si no hay SSID con nmcli, intentar con iwconfig
	if !connected {
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
	
	// Obtener información detallada de la conexión si está conectado
	var connectionInfo fiber.Map = nil
	if connected && ssid != "" {
		connectionInfo = fiber.Map{
			"ssid": ssid,
		}
		
		// Obtener señal (signal strength)
		signalOut, _ := execCommand("nmcli -t -f ACTIVE,SIGNAL dev wifi 2>/dev/null | grep '^yes:' | head -1 | cut -d: -f2").CombinedOutput()
		if signalStr := strings.TrimSpace(string(signalOut)); signalStr != "" {
			connectionInfo["signal"] = signalStr
		}
		
		// Obtener seguridad
		securityOut, _ := execCommand("nmcli -t -f ACTIVE,SECURITY dev wifi 2>/dev/null | grep '^yes:' | head -1 | cut -d: -f2").CombinedOutput()
		if securityStr := strings.TrimSpace(string(securityOut)); securityStr != "" {
			connectionInfo["security"] = securityStr
		}
		
		// Obtener canal
		channelOut, _ := execCommand("nmcli -t -f ACTIVE,CHAN dev wifi 2>/dev/null | grep '^yes:' | head -1 | cut -d: -f2").CombinedOutput()
		if channelStr := strings.TrimSpace(string(channelOut)); channelStr != "" {
			connectionInfo["channel"] = channelStr
		}
		
		// Obtener IP address de la interfaz WiFi
		ifaceCmd := execCommand("nmcli -t -f DEVICE,TYPE dev status 2>/dev/null | grep wifi | head -1 | cut -d: -f1")
		if ifaceOut, err := ifaceCmd.Output(); err == nil {
			iface := strings.TrimSpace(string(ifaceOut))
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
		"connected":        connected,
		"current_connection": ssid,
		"ssid":             ssid,
		"hard_blocked":     hardBlocked,
		"soft_blocked":     softBlocked,
		"connection_info":  connectionInfo,
	})
}

func wifiLegacyStoredNetworksHandler(c *fiber.Ctx) error {
	return c.JSON(fiber.Map{"success": true, "networks": []fiber.Map{}, "last_connected": []string{}})
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

