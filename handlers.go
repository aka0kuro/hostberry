package main

import (
	"encoding/json"
	"strconv"
	"time"

	"github.com/gofiber/fiber/v2"
)

// Handlers de autenticación
func loginAPIHandler(c *fiber.Ctx) error {
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
		"access_token":    token,
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
			return c.Status(500).JSON(fiber.Map{"error": err.Error()})
		}
		return c.JSON(result)
	}

	return c.Status(500).JSON(fiber.Map{
		"error": "Lua engine no disponible",
	})
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

func wireguardConfigHandler(c *fiber.Ctx) error {
	var req struct {
		Config string `json:"config"`
	}

	if err := c.BodyParser(&req); err != nil {
		return c.Status(400).JSON(fiber.Map{
			"error": "Datos inválidos",
		})
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
	return fiber.Map{
		"hostname":      "unknown",
		"os_version":    "Linux",
		"kernel":        "unknown",
		"architecture":  "unknown",
		"processor":     "unknown",
	}
}
