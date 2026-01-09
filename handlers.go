package main

import (
	"encoding/json"
	"fmt"
	"log"
	"os"
	"os/exec"
	"strings"
	"strconv"
	"time"

	"github.com/gofiber/fiber/v2"
)

// Handlers de autenticación
func loginAPIHandler(c *fiber.Ctx) error {
	// Debug: log para verificar que el handler se está ejecutando
	log.Printf("DEBUG loginAPIHandler: Handler ejecutado, path='%s', method=%s", c.Path(), c.Method())
	
	var req struct {
		Username string `json:"username"`
		Password string `json:"password"`
	}

	if err := c.BodyParser(&req); err != nil {
		return c.Status(400).JSON(fiber.Map{
			"error": "Datos inválidos",
		})
	}

	// Validar username
	if err := ValidateUsername(req.Username); err != nil {
		return err
	}

	// Validar password (solo formato, no longitud mínima para login)
	if req.Password == "" {
		return c.Status(400).JSON(fiber.Map{
			"error": "La contraseña es requerida",
		})
	}

	user, token, err := Login(req.Username, req.Password)
	if err != nil {
		return c.Status(401).JSON(fiber.Map{
			"error": err.Error(),
		})
	}

	// Log de login
	userID := user.ID
	InsertLog("INFO", "Usuario autenticado: "+user.Username, "auth", &userID)

	// Determinar si se requiere cambio de contraseña
	// Se requiere si es el primer login (LoginCount == 1 después del incremento en Login)
	// Esto significa que el usuario acaba de hacer su primer login exitoso
	passwordChangeRequired := user.LoginCount == 1

	// También setear cookie para permitir render protegido en rutas web (HttpOnly)
	c.Cookie(&fiber.Cookie{
		Name:     "access_token",
		Value:    token,
		Path:     "/",
		HTTPOnly: true,
		SameSite: "Lax",
		// Secure: true, // si sirves por HTTPS
	})

	return c.JSON(fiber.Map{
		"access_token":            token,
		"password_change_required": passwordChangeRequired,
		"user": fiber.Map{
			"id":       user.ID,
			"username": user.Username,
			"email":    user.Email,
		},
	})
}

func logoutAPIHandler(c *fiber.Ctx) error {
	// En JWT stateless, el logout es principalmente del lado del cliente
	// Pero podemos registrar el evento
	user := c.Locals("user").(*User)
	userID := user.ID
	InsertLog("INFO", "Usuario cerró sesión: "+user.Username, "auth", &userID)

	// Limpiar cookie para rutas web
	c.Cookie(&fiber.Cookie{
		Name:     "access_token",
		Value:    "",
		Path:     "/",
		HTTPOnly: true,
		MaxAge:   -1,
	})

	return c.JSON(fiber.Map{
		"message": "Sesión cerrada",
	})
}

func meHandler(c *fiber.Ctx) error {
	user := c.Locals("user").(*User)
	return c.JSON(fiber.Map{
		"id":       user.ID,
		"username": user.Username,
		"email":    user.Email,
		"first_name": user.FirstName,
		"last_name":  user.LastName,
		"role":       user.Role,
		"timezone":   user.Timezone,
	})
}

func changePasswordAPIHandler(c *fiber.Ctx) error {
	user := c.Locals("user").(*User)

	var req struct {
		CurrentPassword string `json:"current_password"`
		NewPassword     string `json:"new_password"`
	}
	if err := c.BodyParser(&req); err != nil {
		return c.Status(400).JSON(fiber.Map{"error": "Datos inválidos"})
	}
	if req.CurrentPassword == "" || req.NewPassword == "" {
		return c.Status(400).JSON(fiber.Map{"error": "Contraseñas requeridas"})
	}
	if !CheckPassword(req.CurrentPassword, user.Password) {
		return c.Status(401).JSON(fiber.Map{"error": "Contraseña actual incorrecta"})
	}

	hashed, err := HashPassword(req.NewPassword)
	if err != nil {
		return c.Status(500).JSON(fiber.Map{"error": "Error hasheando contraseña"})
	}
	user.Password = hashed
	if err := db.Save(user).Error; err != nil {
		return c.Status(500).JSON(fiber.Map{"error": "Error guardando contraseña"})
	}

	userID := user.ID
	InsertLog("INFO", "Usuario cambió contraseña", "auth", &userID)
	return c.JSON(fiber.Map{"message": "Contraseña actualizada"})
}

func firstLoginChangeAPIHandler(c *fiber.Ctx) error {
	// Obtener token del header Authorization o de la cookie
	tokenString := c.Get("Authorization")
	if tokenString != "" {
		// Remover "Bearer " si está presente
		tokenString = strings.TrimPrefix(tokenString, "Bearer ")
	} else {
		// Intentar obtener de la cookie
		tokenString = c.Cookies("access_token")
	}

	if tokenString == "" {
		return c.Status(401).JSON(fiber.Map{
			"error": "Token requerido",
		})
	}

	// Validar token
	claims, err := ValidateToken(tokenString)
	if err != nil {
		return c.Status(401).JSON(fiber.Map{
			"error": "Token inválido",
		})
	}

	// Obtener usuario
	var user User
	if err := db.Where("id = ? AND is_active = ?", claims.UserID, true).First(&user).Error; err != nil {
		return c.Status(404).JSON(fiber.Map{
			"error": "Usuario no encontrado",
		})
	}

	// Verificar que es el primer login (LoginCount == 1)
	if user.LoginCount != 1 {
		return c.Status(403).JSON(fiber.Map{
			"error": "Este endpoint solo está disponible en el primer login",
		})
	}

	// Parsear request
	var req struct {
		NewUsername string `json:"new_username"`
		NewPassword string `json:"new_password"`
	}
	if err := c.BodyParser(&req); err != nil {
		return c.Status(400).JSON(fiber.Map{
			"error": "Datos inválidos",
		})
	}

	// Validar nuevo username
	if req.NewUsername != "" {
		if err := ValidateUsername(req.NewUsername); err != nil {
			return err
		}
		// Verificar que el nuevo username no esté en uso (si es diferente al actual)
		if req.NewUsername != user.Username {
			var existingUser User
			if err := db.Where("username = ?", req.NewUsername).First(&existingUser).Error; err == nil {
				return c.Status(400).JSON(fiber.Map{
					"error": "El nombre de usuario ya está en uso",
				})
			}
			user.Username = req.NewUsername
		}
	}

	// Validar nueva contraseña
	if req.NewPassword == "" {
		return c.Status(400).JSON(fiber.Map{
			"error": "La nueva contraseña es requerida",
		})
	}
	if err := ValidatePassword(req.NewPassword); err != nil {
		return err
	}

	// Hashear nueva contraseña
	hashed, err := HashPassword(req.NewPassword)
	if err != nil {
		return c.Status(500).JSON(fiber.Map{
			"error": "Error hasheando contraseña",
		})
	}
	user.Password = hashed

	// Incrementar LoginCount para que no pueda volver a usar este endpoint
	user.LoginCount++

	// Guardar cambios
	if err := db.Save(&user).Error; err != nil {
		return c.Status(500).JSON(fiber.Map{
			"error": "Error guardando credenciales",
		})
	}

	userID := user.ID
	InsertLog("INFO", "Usuario cambió credenciales en primer login: "+user.Username, "auth", &userID)
	
	return c.JSON(fiber.Map{
		"message": "Credenciales actualizadas. Por favor, inicia sesión nuevamente.",
	})
}

func updateProfileAPIHandler(c *fiber.Ctx) error {
	user := c.Locals("user").(*User)

	var req struct {
		Email     string `json:"email"`
		FirstName string `json:"first_name"`
		LastName  string `json:"last_name"`
		Timezone  string `json:"timezone"`
	}
	if err := c.BodyParser(&req); err != nil {
		return c.Status(400).JSON(fiber.Map{"error": "Datos inválidos"})
	}

	// Campos opcionales
	user.Email = req.Email
	user.FirstName = req.FirstName
	user.LastName = req.LastName
	if req.Timezone != "" {
		user.Timezone = req.Timezone
	}

	if err := db.Save(user).Error; err != nil {
		return c.Status(500).JSON(fiber.Map{"error": "Error guardando perfil"})
	}

	userID := user.ID
	InsertLog("INFO", "Usuario actualizó su perfil", "auth", &userID)
	return c.JSON(fiber.Map{"message": "Perfil actualizado"})
}

func updatePreferencesAPIHandler(c *fiber.Ctx) error {
	user := c.Locals("user").(*User)

	var req struct {
		EmailNotifications bool `json:"email_notifications"`
		SystemAlerts       bool `json:"system_alerts"`
		SecurityAlerts     bool `json:"security_alerts"`
		ShowActivity       bool `json:"show_activity"`
		DataCollection     bool `json:"data_collection"`
		Analytics          bool `json:"analytics"`
	}
	if err := c.BodyParser(&req); err != nil {
		return c.Status(400).JSON(fiber.Map{"error": "Datos inválidos"})
	}

	user.EmailNotifications = req.EmailNotifications
	user.SystemAlerts = req.SystemAlerts
	user.SecurityAlerts = req.SecurityAlerts
	user.ShowActivity = req.ShowActivity
	user.DataCollection = req.DataCollection
	user.Analytics = req.Analytics

	if err := db.Save(user).Error; err != nil {
		return c.Status(500).JSON(fiber.Map{"error": "Error guardando preferencias"})
	}

	userID := user.ID
	InsertLog("INFO", "Usuario actualizó sus preferencias", "auth", &userID)
	return c.JSON(fiber.Map{"message": "Preferencias actualizadas"})
}

// Handlers del sistema
func systemInfoHandler(c *fiber.Ctx) error {
	if luaEngine != nil {
		result, err := luaEngine.Execute("system_info.lua", nil)
		if err != nil {
			return c.Status(500).JSON(fiber.Map{"error": err.Error()})
		}
		return c.JSON(result)
	}

	// Fallback
	info := getSystemInfo()
	return c.JSON(info)
}

func systemShutdownHandler(c *fiber.Ctx) error {
	user := c.Locals("user").(*User)
	userID := user.ID

	if luaEngine != nil {
		result, err := luaEngine.Execute("system_shutdown.lua", fiber.Map{
			"user": user.Username,
		})
		if err != nil {
			InsertLog("ERROR", "Error en shutdown: "+err.Error(), "system", &userID)
			return c.Status(500).JSON(fiber.Map{"error": err.Error()})
		}

		InsertLog("INFO", "Sistema apagado por: "+user.Username, "system", &userID)
		return c.JSON(result)
	}

	return c.Status(500).JSON(fiber.Map{
		"error": "Lua engine no disponible",
	})
}

// Handlers de red
func networkStatusHandler(c *fiber.Ctx) error {
	if luaEngine != nil {
		result, err := luaEngine.Execute("network_status.lua", nil)
		if err != nil {
			return c.Status(500).JSON(fiber.Map{"error": err.Error()})
		}
		return c.JSON(result)
	}

	return c.Status(500).JSON(fiber.Map{
		"error": "Lua engine no disponible",
	})
}

func networkInterfacesHandler(c *fiber.Ctx) error {
	if luaEngine != nil {
		result, err := luaEngine.Execute("network_interfaces.lua", nil)
		if err != nil {
			log.Printf("⚠️ Error ejecutando Lua script: %v", err)
			// Continuar con fallback
		} else if result != nil {
			// Asegurar que el resultado tenga el formato correcto
			if _, ok := result["interfaces"]; ok {
				// Si ya tiene interfaces, devolverlo tal cual
				return c.JSON(result)
			} else {
				// Si no tiene interfaces, crear un array vacío
				return c.JSON(fiber.Map{
					"interfaces": []interface{}{},
					"success":   true,
					"count":     0,
				})
			}
		}
	}

	// Fallback: obtener interfaces directamente
	interfaces := []map[string]interface{}{}
	
	// Obtener lista de interfaces
	cmd := exec.Command("sh", "-c", "ip -o link show | awk -F': ' '{print $2}'")
	output, err := cmd.Output()
	if err != nil {
		log.Printf("⚠️ Error obteniendo interfaces: %v", err)
		return c.JSON(fiber.Map{"interfaces": interfaces})
	}

	lines := strings.Split(strings.TrimSpace(string(output)), "\n")
	for _, ifaceName := range lines {
		ifaceName = strings.TrimSpace(ifaceName)
		if ifaceName == "" || ifaceName == "lo" {
			continue // Saltar loopback
		}

		iface := map[string]interface{}{
			"name": ifaceName,
			"ip":   "N/A",
			"mac":  "N/A",
			"state": "unknown",
		}

		// Obtener estado
		stateCmd := exec.Command("sh", "-c", fmt.Sprintf("cat /sys/class/net/%s/operstate 2>/dev/null", ifaceName))
		if stateOut, err := stateCmd.Output(); err == nil {
			iface["state"] = strings.TrimSpace(string(stateOut))
		}

		// Obtener IP y máscara de red
		ipCmd := exec.Command("sh", "-c", fmt.Sprintf("ip addr show %s | grep 'inet ' | awk '{print $2}'", ifaceName))
		if ipOut, err := ipCmd.Output(); err == nil {
			ipLine := strings.TrimSpace(string(ipOut))
			if ipLine != "" {
				// Formato: "192.168.1.100/24"
				parts := strings.Split(ipLine, "/")
				iface["ip"] = parts[0]
				if len(parts) > 1 {
					iface["netmask"] = parts[1]
				}
			}
		}

		// Obtener gateway para esta interfaz
		gatewayCmd := exec.Command("sh", "-c", fmt.Sprintf("ip route | grep %s | grep default | awk '{print $3}' | head -1", ifaceName))
		if gatewayOut, err := gatewayCmd.Output(); err == nil {
			gateway := strings.TrimSpace(string(gatewayOut))
			if gateway != "" {
				iface["gateway"] = gateway
			}
		}
		
		// Si no hay gateway específico, intentar obtener el gateway por defecto
		if _, hasGateway := iface["gateway"]; !hasGateway {
			defaultGatewayCmd := exec.Command("sh", "-c", "ip route | grep default | awk '{print $3}' | head -1")
			if defaultGatewayOut, err := defaultGatewayCmd.Output(); err == nil {
				defaultGateway := strings.TrimSpace(string(defaultGatewayOut))
				if defaultGateway != "" {
					iface["gateway"] = defaultGateway
				}
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

		interfaces = append(interfaces, iface)
	}

	return c.JSON(fiber.Map{"interfaces": interfaces})
}

// Handlers de WiFi
func wifiConnectHandler(c *fiber.Ctx) error {
	var req struct {
		SSID     string `json:"ssid"`
		Password string `json:"password"`
	}

	if err := c.BodyParser(&req); err != nil {
		return c.Status(400).JSON(fiber.Map{
			"error": "Datos inválidos",
		})
	}

	user := c.Locals("user").(*User)
	userID := user.ID

	if luaEngine != nil {
		result, err := luaEngine.Execute("wifi_connect.lua", fiber.Map{
			"ssid":     req.SSID,
			"password": req.Password,
			"user":     user.Username,
		})
		if err != nil {
			InsertLog("ERROR", "Error conectando WiFi: "+err.Error(), "wifi", &userID)
			return c.Status(500).JSON(fiber.Map{"error": err.Error()})
		}

		InsertLog("INFO", "WiFi conectado: "+req.SSID, "wifi", &userID)
		return c.JSON(result)
	}

	return c.Status(500).JSON(fiber.Map{
		"error": "Lua engine no disponible",
	})
}

// Handlers de VPN
func vpnStatusHandler(c *fiber.Ctx) error {
	if luaEngine != nil {
		result, err := luaEngine.Execute("vpn_status.lua", nil)
		if err != nil {
			return c.Status(500).JSON(fiber.Map{"error": err.Error()})
		}
		return c.JSON(result)
	}

	return c.Status(500).JSON(fiber.Map{
		"error": "Lua engine no disponible",
	})
}

func vpnConnectHandler(c *fiber.Ctx) error {
	var req struct {
		Config string `json:"config"`
		Type   string `json:"type"`
	}

	if err := c.BodyParser(&req); err != nil {
		return c.Status(400).JSON(fiber.Map{
			"error": "Datos inválidos",
		})
	}

	user := c.Locals("user").(*User)
	userID := user.ID

	if luaEngine != nil {
		result, err := luaEngine.Execute("vpn_connect.lua", fiber.Map{
			"config": req.Config,
			"type":   req.Type,
			"user":   user.Username,
		})
		if err != nil {
			InsertLog("ERROR", "Error conectando VPN: "+err.Error(), "vpn", &userID)
			return c.Status(500).JSON(fiber.Map{"error": err.Error()})
		}

		InsertLog("INFO", "VPN conectado: "+req.Type, "vpn", &userID)
		return c.JSON(result)
	}

	return c.Status(500).JSON(fiber.Map{
		"error": "Lua engine no disponible",
	})
}

// Handlers de WireGuard
func wireguardStatusHandler(c *fiber.Ctx) error {
	if luaEngine != nil {
		result, err := luaEngine.Execute("wireguard_status.lua", nil)
		if err != nil {
			return c.Status(500).JSON(fiber.Map{"error": err.Error()})
		}
		return c.JSON(result)
	}

	return c.Status(500).JSON(fiber.Map{
		"error": "Lua engine no disponible",
	})
}

// wireguardInterfacesHandler adapta el estado a la estructura esperada por wireguard.js
func wireguardInterfacesHandler(c *fiber.Ctx) error {
	// Intentar obtener interfaces via wg (más directo que Lua para estructura)
	out, err := exec.Command("wg", "show", "interfaces").CombinedOutput()
	if err != nil {
		// fallback a Lua status
		if luaEngine != nil {
			result, err2 := luaEngine.Execute("wireguard_status.lua", nil)
			if err2 != nil {
				return c.Status(500).JSON(fiber.Map{"error": string(out)})
			}
			_ = result
		}
		return c.Status(500).JSON(fiber.Map{"error": strings.TrimSpace(string(out))})
	}

	ifaces := strings.Fields(strings.TrimSpace(string(out)))
	var resp []fiber.Map
	for _, iface := range ifaces {
		// peers count
		detailsOut, _ := exec.Command("wg", "show", iface).CombinedOutput()
		details := string(detailsOut)
		peersCount := 0
		for _, line := range strings.Split(details, "\n") {
			if strings.HasPrefix(strings.TrimSpace(line), "peer:") {
				peersCount++
			}
		}
		resp = append(resp, fiber.Map{
			"name":        iface,
			"status":      "up",
			"address":     "", // opcional (depende de ip)
			"peers_count": peersCount,
		})
	}
	return c.JSON(resp)
}

// wireguardPeersHandler devuelve una lista simple de peers a partir de wg show wg0
func wireguardPeersHandler(c *fiber.Ctx) error {
	out, err := exec.Command("wg", "show").CombinedOutput()
	if err != nil {
		return c.Status(500).JSON(fiber.Map{"error": strings.TrimSpace(string(out))})
	}
	text := string(out)
	var peers []fiber.Map

	var curPeer string
	var handshake string
	var transfer string

	flush := func() {
		if curPeer == "" {
			return
		}
		connected := true
		if strings.Contains(handshake, "never") || handshake == "" {
			connected = false
		}
		name := curPeer
		if len(name) > 12 {
			name = name[:12] + "…"
		}
		peers = append(peers, fiber.Map{
			"name":      name,
			"connected": connected,
			"bandwidth": transfer,
			"uptime":    handshake,
		})
		curPeer, handshake, transfer = "", "", ""
	}

	for _, line := range strings.Split(text, "\n") {
		line = strings.TrimSpace(line)
		if strings.HasPrefix(line, "peer:") {
			flush()
			curPeer = strings.TrimSpace(strings.TrimPrefix(line, "peer:"))
			continue
		}
		if strings.HasPrefix(line, "latest handshake:") {
			handshake = strings.TrimSpace(strings.TrimPrefix(line, "latest handshake:"))
			continue
		}
		if strings.HasPrefix(line, "transfer:") {
			transfer = strings.TrimSpace(strings.TrimPrefix(line, "transfer:"))
			continue
		}
	}
	flush()
	return c.JSON(peers)
}

// wireguardGetConfigHandler devuelve el contenido actual de /etc/wireguard/wg0.conf (si existe)
func wireguardGetConfigHandler(c *fiber.Ctx) error {
	out, err := exec.Command("sh", "-c", "cat /etc/wireguard/wg0.conf 2>/dev/null").CombinedOutput()
	if err != nil {
		return c.Status(500).JSON(fiber.Map{"error": strings.TrimSpace(string(out))})
	}
	return c.JSON(fiber.Map{"config": string(out)})
}

func wireguardToggleHandler(c *fiber.Ctx) error {
	// Toggle basado en estado actual
	statusOut, _ := exec.Command("wg", "show").CombinedOutput()
	active := strings.TrimSpace(string(statusOut)) != ""

	var cmd *exec.Cmd
	if active {
		cmd = exec.Command("sudo", "wg-quick", "down", "wg0")
	} else {
		cmd = exec.Command("sudo", "wg-quick", "up", "wg0")
	}
	out, err := cmd.CombinedOutput()
	if err != nil {
		return c.Status(500).JSON(fiber.Map{"error": strings.TrimSpace(string(out))})
	}
	return c.JSON(fiber.Map{"success": true, "output": strings.TrimSpace(string(out))})
}

func wireguardRestartHandler(c *fiber.Ctx) error {
	out1, err1 := exec.Command("sudo", "wg-quick", "down", "wg0").CombinedOutput()
	out2, err2 := exec.Command("sudo", "wg-quick", "up", "wg0").CombinedOutput()
	if err1 != nil || err2 != nil {
		return c.Status(500).JSON(fiber.Map{
			"error":  "Error reiniciando WireGuard (requiere sudo NOPASSWD)",
			"down":   strings.TrimSpace(string(out1)),
			"up":     strings.TrimSpace(string(out2)),
			"downOk": err1 == nil,
			"upOk":   err2 == nil,
		})
	}
	return c.JSON(fiber.Map{"success": true})
}

func wireguardConfigHandler(c *fiber.Ctx) error {
	var req struct {
		Config string `json:"config"`
	}

	if err := c.BodyParser(&req); err != nil {
		return c.Status(400).JSON(fiber.Map{
			"error": "Datos inválidos",
		})
	}
	if strings.TrimSpace(req.Config) == "" {
		return c.Status(400).JSON(fiber.Map{"error": "config requerido (texto completo wg0.conf)"})
	}

	user := c.Locals("user").(*User)
	userID := user.ID

	if luaEngine != nil {
		result, err := luaEngine.Execute("wireguard_config.lua", fiber.Map{
			"config": req.Config,
			"user":   user.Username,
		})
		if err != nil {
			InsertLog("ERROR", "Error configurando WireGuard: "+err.Error(), "wireguard", &userID)
			return c.Status(500).JSON(fiber.Map{"error": err.Error()})
		}

		InsertLog("INFO", "WireGuard configurado", "wireguard", &userID)
		return c.JSON(result)
	}

	return c.Status(500).JSON(fiber.Map{
		"error": "Lua engine no disponible",
	})
}

// Handlers de AdBlock
func adblockStatusHandler(c *fiber.Ctx) error {
	if luaEngine != nil {
		result, err := luaEngine.Execute("adblock_status.lua", nil)
		if err != nil {
			return c.Status(500).JSON(fiber.Map{"error": err.Error()})
		}
		return c.JSON(result)
	}

	return c.Status(500).JSON(fiber.Map{
		"error": "Lua engine no disponible",
	})
}

func adblockEnableHandler(c *fiber.Ctx) error {
	user := c.Locals("user").(*User)
	userID := user.ID

	if luaEngine != nil {
		result, err := luaEngine.Execute("adblock_enable.lua", fiber.Map{
			"user": user.Username,
		})
		if err != nil {
			InsertLog("ERROR", "Error habilitando AdBlock: "+err.Error(), "adblock", &userID)
			return c.Status(500).JSON(fiber.Map{"error": err.Error()})
		}

		InsertLog("INFO", "AdBlock habilitado", "adblock", &userID)
		return c.JSON(result)
	}

	return c.Status(500).JSON(fiber.Map{
		"error": "Lua engine no disponible",
	})
}

func adblockDisableHandler(c *fiber.Ctx) error {
	user := c.Locals("user").(*User)
	userID := user.ID

	if luaEngine != nil {
		result, err := luaEngine.Execute("adblock_disable.lua", fiber.Map{
			"user": user.Username,
		})
		if err != nil {
			InsertLog("ERROR", "Error deshabilitando AdBlock: "+err.Error(), "adblock", &userID)
			return c.Status(500).JSON(fiber.Map{"error": err.Error()})
		}

		InsertLog("INFO", "AdBlock deshabilitado", "adblock", &userID)
		return c.JSON(result)
	}

	return c.Status(500).JSON(fiber.Map{
		"error": "Lua engine no disponible",
	})
}

// Handler de logs del sistema
// Handlers de páginas web
func networkPageHandler(c *fiber.Ctx) error {
	return renderTemplate(c, "network", fiber.Map{
		"Title": T(c, "network.title", "Network Management"),
	})
}

func wifiPageHandler(c *fiber.Ctx) error {
	return renderTemplate(c, "wifi", fiber.Map{
		"Title":         T(c, "wifi.overview", "WiFi Overview"),
		"wifi_stats":    fiber.Map{},
		"wifi_status":   fiber.Map{},
		"wifi_config":   fiber.Map{},
		"guest_network": fiber.Map{},
		"last_update":   time.Now().Unix(),
	})
}

func wifiScanPageHandler(c *fiber.Ctx) error {
	return renderTemplate(c, "wifi_scan", fiber.Map{
		"Title": T(c, "wifi.scan", "WiFi Scan"),
	})
}

func vpnPageHandler(c *fiber.Ctx) error {
	return renderTemplate(c, "vpn", fiber.Map{
		"Title":        T(c, "vpn.overview", "VPN Overview"),
		"vpn_stats":    fiber.Map{},
		"vpn_status":   fiber.Map{},
		"vpn_config":   fiber.Map{},
		"vpn_security": fiber.Map{},
		"last_update":  time.Now().Unix(),
	})
}

func wireguardPageHandler(c *fiber.Ctx) error {
	return renderTemplate(c, "wireguard", fiber.Map{
		"Title":            T(c, "wireguard.overview", "WireGuard Overview"),
		"wireguard_stats":  fiber.Map{},
		"wireguard_status": fiber.Map{},
		"wireguard_config": fiber.Map{},
		"last_update":      time.Now().Unix(),
	})
}

func adblockPageHandler(c *fiber.Ctx) error {
	return renderTemplate(c, "adblock", fiber.Map{
		"Title":          T(c, "adblock.overview", "AdBlock Overview"),
		"adblock_stats":  fiber.Map{},
		"adblock_status": fiber.Map{},
		"adblock_config": fiber.Map{},
	})
}

func hostapdPageHandler(c *fiber.Ctx) error {
	return renderTemplate(c, "hostapd", fiber.Map{
		"Title":          T(c, "hostapd.overview", "Hotspot Overview"),
		"hostapd_stats":  fiber.Map{},
		"hostapd_status": fiber.Map{},
		"hostapd_config": fiber.Map{},
		"last_update":    time.Now().Unix(),
	})
}

func profilePageHandler(c *fiber.Ctx) error {
	user := c.Locals("user").(*User)
	// Actividad real: últimos logs
	logs, _, _ := GetLogs("all", 10, 0)
	type activity struct {
		Action      string
		Timestamp   string
		Description string
		IPAddress   string
	}
	var activities []activity
	for _, l := range logs {
		activities = append(activities, activity{
			Action:      l.Source,
			Timestamp:   l.CreatedAt.Format(time.RFC3339),
			Description: l.Message,
			IPAddress:   "-",
		})
	}

	configs, _ := GetAllConfigs()
	configsJSON, _ := json.Marshal(configs)
	return renderTemplate(c, "profile", fiber.Map{
		"Title": T(c, "auth.profile", "Profile"),
		"user":  user,
		"recent_activities": activities,
		"settings":          configs,
		"settings_json":     string(configsJSON),
		"last_update":       time.Now().Unix(),
	})
}

func systemPageHandler(c *fiber.Ctx) error {
	return renderTemplate(c, "system", fiber.Map{
		"Title": T(c, "system.title", "System Manager"),
	})
}

func monitoringPageHandler(c *fiber.Ctx) error {
	return renderTemplate(c, "monitoring", fiber.Map{
		"Title": T(c, "monitoring.title", "Monitoring"),
	})
}

func updatePageHandler(c *fiber.Ctx) error {
	return renderTemplate(c, "update", fiber.Map{
		"Title": T(c, "update.title", "Updates"),
	})
}

func firstLoginPageHandler(c *fiber.Ctx) error {
	return renderTemplate(c, "first_login", fiber.Map{
		"Title": T(c, "auth.first_login", "First Login"),
	})
}

func systemLogsHandler(c *fiber.Ctx) error {
	level := c.Query("level", "all")
	limitStr := c.Query("limit", "20")
	offsetStr := c.Query("offset", "0")

	limit, _ := strconv.Atoi(limitStr)
	offset, _ := strconv.Atoi(offsetStr)

	if limit <= 0 || limit > 100 {
		limit = 20
	}

	logs, total, err := GetLogs(level, limit, offset)
	if err != nil {
		return c.Status(500).JSON(fiber.Map{
			"error": err.Error(),
		})
	}

	return c.JSON(fiber.Map{
		"logs":  logs,
		"total": total,
		"limit": limit,
		"offset": offset,
	})
}

// Funciones auxiliares
func getSystemInfo() fiber.Map {
	info := fiber.Map{
		"hostname":      "unknown",
		"os_version":    "Linux",
		"kernel_version": "unknown",
		"architecture":  "unknown",
		"processor":     "unknown",
		"uptime_seconds": 0,
	}
	
	// Intentar obtener datos reales del sistema
	if hostname, err := executeCommand("hostname"); err == nil && hostname != "" {
		info["hostname"] = hostname
	}
	
	if kernel, err := executeCommand("uname -r"); err == nil && kernel != "" {
		info["kernel_version"] = kernel
	}
	
	if arch, err := executeCommand("uname -m"); err == nil && arch != "" {
		info["architecture"] = arch
	}
	
	// Obtener procesador - intentar múltiples métodos
	processorCmd := "cat /proc/cpuinfo | grep -m1 'model name\\|Processor\\|Hardware' | cut -d ':' -f 2 | sed 's/^[[:space:]]*//'"
	if processor, err := executeCommand(processorCmd); err == nil && processor != "" && processor != "unknown" {
		info["processor"] = strings.TrimSpace(processor)
	} else {
		// Fallback: intentar con lscpu
		if lscpu, err := executeCommand("lscpu | grep 'Model name' | cut -d ':' -f 2 | sed 's/^[[:space:]]*//'"); err == nil && lscpu != "" {
			info["processor"] = strings.TrimSpace(lscpu)
		} else {
			// Fallback: usar architecture como indicador
			if arch, ok := info["architecture"].(string); ok && arch != "" {
				info["processor"] = arch + " Processor"
			} else {
				info["processor"] = "Unknown Processor"
			}
		}
	}
	
	// Obtener OS version
	if osRelease, err := os.ReadFile("/etc/os-release"); err == nil {
		lines := strings.Split(string(osRelease), "\n")
		for _, line := range lines {
			if strings.HasPrefix(line, "PRETTY_NAME=") {
				osVersion := strings.TrimPrefix(line, "PRETTY_NAME=")
				osVersion = strings.Trim(osVersion, "\"")
				if osVersion != "" {
					info["os_version"] = osVersion
				}
				break
			}
		}
	}
	
	// Obtener uptime
	if uptimeOut, err := executeCommand("cat /proc/uptime | awk '{print int($1)}'"); err == nil {
		if uptime, err := strconv.Atoi(strings.TrimSpace(uptimeOut)); err == nil {
			info["uptime_seconds"] = uptime
		}
	}
	
	return info
}

// systemServicesHandler devuelve el estado de los servicios principales del proyecto
func systemServicesHandler(c *fiber.Ctx) error {
	services := make(map[string]interface{})
	
	// Verificar WireGuard
	wgOut, _ := exec.Command("wg", "show").CombinedOutput()
	wgActive := strings.TrimSpace(string(wgOut)) != ""
	services["wireguard"] = map[string]interface{}{
		"status": wgActive,
		"active": wgActive,
	}
	
	// Verificar OpenVPN
	openvpnOut, _ := exec.Command("sh", "-c", "systemctl is-active openvpn 2>/dev/null || pgrep openvpn > /dev/null && echo active || echo inactive").CombinedOutput()
	openvpnStatus := strings.TrimSpace(string(openvpnOut))
	openvpnActive := openvpnStatus == "active"
	services["openvpn"] = map[string]interface{}{
		"status": openvpnStatus,
		"active": openvpnActive,
	}
	
	// Verificar HostAPD
	hostapdOut, _ := exec.Command("sh", "-c", "systemctl is-active hostapd 2>/dev/null || pgrep hostapd > /dev/null && echo active || echo inactive").CombinedOutput()
	hostapdStatus := strings.TrimSpace(string(hostapdOut))
	hostapdActive := hostapdStatus == "active"
	services["hostapd"] = map[string]interface{}{
		"status": hostapdStatus,
		"active": hostapdActive,
	}
	
	// Verificar AdBlock (dnsmasq o pihole)
	dnsmasqOut, _ := exec.Command("sh", "-c", "systemctl is-active dnsmasq 2>/dev/null || echo inactive").CombinedOutput()
	dnsmasqStatus := strings.TrimSpace(string(dnsmasqOut))
	piholeOut, _ := exec.Command("sh", "-c", "systemctl is-active pihole-FTL 2>/dev/null || echo inactive").CombinedOutput()
	piholeStatus := strings.TrimSpace(string(piholeOut))
	adblockActive := dnsmasqStatus == "active" || piholeStatus == "active"
	services["adblock"] = map[string]interface{}{
		"status": adblockActive,
		"active": adblockActive,
		"type": func() string {
			if dnsmasqStatus == "active" {
				return "dnsmasq"
			}
			if piholeStatus == "active" {
				return "pihole"
			}
			return "none"
		}(),
	}
	
	return c.JSON(fiber.Map{
		"services": services,
	})
}
