package main

import (
	"encoding/json"
	"fmt"
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
	// Placeholder: evita 404; aplicar config de red requiere validación y privilegios
	return c.JSON(fiber.Map{"success": false, "message": "Config de red no implementada"})
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

func wifiLegacyStatusHandler(c *fiber.Ctx) error {
	// Verificar estado real del WiFi
	var enabled bool = false
	var hardBlocked bool = false
	var softBlocked bool = false
	
	// Método 1: Verificar con nmcli (más confiable)
	wifiCheck := execCommand("nmcli -t -f WIFI g 2>/dev/null")
	wifiOut, err := wifiCheck.Output()
	if err == nil {
		wifiState := strings.ToLower(strings.TrimSpace(string(wifiOut)))
		if strings.Contains(wifiState, "enabled") || strings.Contains(wifiState, "on") {
			enabled = true
		} else if strings.Contains(wifiState, "disabled") || strings.Contains(wifiState, "off") {
			enabled = false
		}
	}
	
	// Método 2: Verificar con rfkill para obtener información de bloqueo
	rfkillOut, _ := execCommand("rfkill list wifi 2>/dev/null").CombinedOutput()
	rfkillStr := strings.ToLower(string(rfkillOut))
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
			wifiState2 := strings.ToLower(strings.TrimSpace(string(wifiOut2)))
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
		if len(iwOut) > 0 {
			// Si hay una interfaz WiFi, verificar si está activa
			iwStatus, _ := execCommand("iwconfig 2>/dev/null | grep -i 'wlan' | head -1 | grep -i 'unassociated'").CombinedOutput()
			if len(iwStatus) == 0 {
				// No está "unassociated", verificar también con nmcli
				wifiCheck3 := execCommand("nmcli -t -f WIFI g 2>/dev/null")
				wifiOut3, err3 := wifiCheck3.Output()
				if err3 == nil {
					wifiState3 := strings.ToLower(strings.TrimSpace(string(wifiOut3)))
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
	
	// Obtener SSID actual si está conectado (con sudo)
	ssidOut, _ := exec.Command("sh", "-c", "sudo nmcli -t -f ACTIVE,SSID dev wifi 2>/dev/null | grep '^yes:' | head -1 | cut -d: -f2").CombinedOutput()
	ssid := strings.TrimSpace(string(ssidOut))
	connected := ssid != ""
	
	// Si no hay SSID con nmcli, intentar con iwconfig (con sudo)
	if !connected {
		iwOut, _ := exec.Command("sh", "-c", "sudo iwconfig 2>/dev/null | grep -i 'essid' | grep -v 'off/any' | head -1").CombinedOutput()
		iwStr := string(iwOut)
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
	
	return c.JSON(fiber.Map{
		"enabled":          enabled,
		"connected":        connected,
		"current_connection": ssid,
		"ssid":             ssid,
		"hard_blocked":     hardBlocked,
		"soft_blocked":     softBlocked,
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
	// best-effort
	_, _ = exec.Command("sh", "-c", "nmcli networking off; nmcli networking on").CombinedOutput()
	return c.JSON(fiber.Map{"success": true})
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

