package main

import (
	"strconv"

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
	})
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
		"Title": T(c, "wifi.overview", "WiFi Overview"),
	})
}

func wifiScanPageHandler(c *fiber.Ctx) error {
	return renderTemplate(c, "wifi_scan", fiber.Map{
		"Title": T(c, "wifi.scan", "WiFi Scan"),
	})
}

func vpnPageHandler(c *fiber.Ctx) error {
	return renderTemplate(c, "vpn", fiber.Map{
		"Title": T(c, "vpn.overview", "VPN Overview"),
	})
}

func wireguardPageHandler(c *fiber.Ctx) error {
	return renderTemplate(c, "wireguard", fiber.Map{
		"Title": T(c, "wireguard.overview", "WireGuard Overview"),
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
	user := c.Locals("user")
	return renderTemplate(c, "profile", fiber.Map{
		"Title": T(c, "auth.profile", "Profile"),
		"user":  user,
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
