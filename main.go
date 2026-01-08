package main

import (
	"context"
	"embed"
	"encoding/json"
	"fmt"
	"io/fs"
	"log"
	"os"
	"os/exec"
	"os/signal"
	"path/filepath"
	"strconv"
	"strings"
	"syscall"
	"time"

	"github.com/gofiber/fiber/v2"
	"github.com/gofiber/fiber/v2/middleware/compress"
	"github.com/gofiber/fiber/v2/middleware/cors"
	"github.com/gofiber/fiber/v2/middleware/logger"
	"gopkg.in/yaml.v3"
)

//go:embed website/templates
var templatesFS embed.FS

//go:embed website/static
var staticFS embed.FS

// Configuración de la aplicación
type Config struct {
	Server   ServerConfig   `yaml:"server"`
	Database DatabaseConfig `yaml:"database"`
	Security SecurityConfig `yaml:"security"`
	Lua      LuaConfig      `yaml:"lua"`
}

type ServerConfig struct {
	Host         string `yaml:"host"`
	Port         int    `yaml:"port"`
	Debug        bool   `yaml:"debug"`
	ReadTimeout  int    `yaml:"read_timeout"`
	WriteTimeout int    `yaml:"write_timeout"`
}

type DatabaseConfig struct {
	Type     string `yaml:"type"` // sqlite, postgres, mysql
	Path     string `yaml:"path"` // Para SQLite
	Host     string `yaml:"host"`
	Port     int    `yaml:"port"`
	User     string `yaml:"user"`
	Password string `yaml:"password"`
	Database string `yaml:"database"`
}

type SecurityConfig struct {
	JWTSecret    string `yaml:"jwt_secret"`
	TokenExpiry  int    `yaml:"token_expiry"` // minutos
	BcryptCost   int    `yaml:"bcrypt_cost"`
	RateLimitRPS int    `yaml:"rate_limit_rps"`
}

type LuaConfig struct {
	ScriptsPath string `yaml:"scripts_path"`
	Enabled     bool   `yaml:"enabled"`
}

var appConfig Config
var luaEngine *LuaEngine

func main() {
	// Cargar configuración
	if err := loadConfig(); err != nil {
		log.Fatalf("Error cargando configuración: %v", err)
	}

	// Inicializar motor Lua
	if appConfig.Lua.Enabled {
		var err error
		luaEngine, err = NewLuaEngine(appConfig.Lua.ScriptsPath)
		if err != nil {
			log.Fatalf("Error inicializando Lua: %v", err)
		}
		defer luaEngine.Close()
	}

	// Inicializar i18n
	if err := InitI18n("locales"); err != nil {
		log.Printf("⚠️  Advertencia: Error inicializando i18n: %v", err)
	}

	// Inicializar base de datos
	if err := initDatabase(); err != nil {
		log.Fatalf("❌ Error inicializando base de datos: %v", err)
	}

	// Crear usuario admin por defecto si no existe
	log.Println("🔐 Verificando usuario admin por defecto...")
	createDefaultAdmin()

	// Crear aplicación Fiber
	app := createApp()

	// IMPORTANTE: Registrar archivos estáticos ANTES de aplicar middlewares globales
	// para evitar que cualquier middleware intercepte /static/*
	setupStaticFiles(app)

	// Configurar rutas
	setupRoutes(app)

	// Iniciar servidor
	addr := fmt.Sprintf("%s:%d", appConfig.Server.Host, appConfig.Server.Port)
	log.Printf("🚀 HostBerry iniciando en %s", addr)
	log.Printf("📋 Configuración: Debug=%v, Timeout=%ds/%ds",
		appConfig.Server.Debug,
		appConfig.Server.ReadTimeout,
		appConfig.Server.WriteTimeout)

	// Manejo graceful de shutdown
	go func() {
		sigint := make(chan os.Signal, 1)
		signal.Notify(sigint, os.Interrupt, syscall.SIGTERM)
		<-sigint
		log.Println("🛑 Deteniendo servidor...")
		ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
		defer cancel()
		if err := app.ShutdownWithContext(ctx); err != nil {
			log.Printf("Error en shutdown: %v", err)
		}
		os.Exit(0)
	}()

	log.Println("✅ Servidor listo, escuchando en", addr)
	if err := app.Listen(addr); err != nil {
		log.Fatalf("❌ Error iniciando servidor: %v", err)
	}
}

func loadConfig() error {
	// Intentar cargar desde config.yaml, si no existe usar defaults
	data, err := os.ReadFile("config.yaml")
	if err != nil {
		// Configuración por defecto
		appConfig = Config{
			Server: ServerConfig{
				Host:         "0.0.0.0",
				Port:         8000,
				Debug:        false,
				ReadTimeout:  30,
				WriteTimeout: 30,
			},
			Database: DatabaseConfig{
				Type: "sqlite",
				Path: "data/hostberry.db",
			},
			Security: SecurityConfig{
				JWTSecret:    "change-me-in-production",
				TokenExpiry:  1440, // 24 horas
				BcryptCost:   10,
				RateLimitRPS: 10,
			},
			Lua: LuaConfig{
				ScriptsPath: "lua/scripts",
				Enabled:     true,
			},
		}
		return nil
	}

	return yaml.Unmarshal(data, &appConfig)
}

func createApp() *fiber.App {
	// Configurar templates
	engine := createTemplateEngine()
	if engine == nil {
		log.Fatal("❌ Error crítico: No se pudo crear el engine de templates")
	}

	log.Printf("✅ Engine de templates creado, asignando a Fiber app...")

	app := fiber.New(fiber.Config{
		Views:        engine,
		ReadTimeout:  time.Duration(appConfig.Server.ReadTimeout) * time.Second,
		WriteTimeout: time.Duration(appConfig.Server.WriteTimeout) * time.Second,
		ErrorHandler: errorHandler,
	})

	// Verificar que el engine se asignó correctamente
	if app.Config().Views == nil {
		log.Fatal("❌ Error crítico: Views no se asignó correctamente a la app")
	}
	log.Println("✅ Engine de templates asignado correctamente a Fiber app")

	// IMPORTANTE: Registrar archivos estáticos ANTES de aplicar middlewares globales
	// para evitar que cualquier middleware intercepte /static/*
	setupStaticFiles(app)

	// Middlewares globales
	// Configurar logger con formato más legible
	app.Use(logger.New(logger.Config{
		Format:     "${time} | ${status} | ${latency} | ${ip} | ${method} | ${path}\n",
		TimeFormat: "15:04:05",
		TimeZone:   "Local",
		Output:     os.Stdout,
		// Filtrar archivos estáticos para reducir ruido
		Next: func(c *fiber.Ctx) bool {
			path := c.Path()
			// Omitir logs de archivos estáticos comunes
			return strings.HasPrefix(path, "/static/") &&
				(strings.HasSuffix(path, ".css") ||
					strings.HasSuffix(path, ".js") ||
					strings.HasSuffix(path, ".png") ||
					strings.HasSuffix(path, ".jpg") ||
					strings.HasSuffix(path, ".jpeg") ||
					strings.HasSuffix(path, ".gif") ||
					strings.HasSuffix(path, ".ico") ||
					strings.HasSuffix(path, ".svg") ||
					strings.HasSuffix(path, ".woff") ||
					strings.HasSuffix(path, ".woff2") ||
					strings.HasSuffix(path, ".ttf") ||
					strings.HasSuffix(path, ".eot"))
		},
	}))
	app.Use(compress.New())
	app.Use(cors.New(cors.Config{
		AllowOrigins:     "*",
		AllowCredentials: true,
		AllowMethods:     "GET,POST,PUT,DELETE,OPTIONS",
		AllowHeaders:     "*",
		MaxAge:           3600,
	}))

	// Middleware de seguridad
	app.Use(securityMiddleware)

	// Middleware de logging
	app.Use(loggingMiddleware)

	// Middleware de idioma (debe ir antes de las rutas)
	app.Use(LanguageMiddleware)

	// Middleware de Request ID para tracing
	app.Use(requestIDMiddleware)

	// Rate limiting (solo para APIs)
	app.Use("/api/", rateLimitMiddleware)

	return app
}

// setupStaticFiles registra los archivos estáticos ANTES de cualquier middleware
// para asegurar que /static/* siempre se sirva correctamente sin interceptación
func setupStaticFiles(app *fiber.App) {
	// Archivos estáticos: preferir filesystem (para poder actualizar JS/CSS sin recompilar),
	// fallback a embebidos si no existe ./website/static.
	if _, err := os.Stat("./website/static"); err == nil {
		app.Static("/static", "./website/static", fiber.Static{
			Compress:  true,
			ByteRange: true,
		})
		log.Println("✅ Archivos estáticos cargados desde sistema de archivos")
	} else {
		// Fallback: estáticos embebidos
		staticSubFS, err := fs.Sub(staticFS, "website/static")
		if err != nil {
			log.Printf("⚠️  Error preparando archivos estáticos embebidos: %v", err)
			log.Printf("⚠️  No se encontraron archivos estáticos ni en filesystem ni embebidos")
		} else {
			// Usar handler personalizado para archivos embebidos
			app.Get("/static/*", func(c *fiber.Ctx) error {
				path := c.Params("*")
				file, err := staticSubFS.Open(path)
				if err != nil {
					return c.Status(404).SendString("Not found")
				}
				defer file.Close()

				stat, err := file.Stat()
				if err != nil {
					return c.Status(500).SendString("Error reading file")
				}

				c.Type(filepath.Ext(path))
				return c.SendStream(file, int(stat.Size()))
			})
			log.Println("✅ Archivos estáticos cargados desde archivos embebidos")
		}
	}
}

func setupRoutes(app *fiber.App) {
	// Health check endpoints (sin autenticación)
	app.Get("/health", healthCheckHandler)
	app.Get("/health/ready", readinessCheckHandler)
	app.Get("/health/live", livenessCheckHandler)

	// Rutas web
	web := app.Group("/")
	{
		web.Get("/login", loginHandler)
		web.Get("/first-login", firstLoginPageHandler)
		web.Get("/", indexHandler)

		// Páginas protegidas (requieren token por cookie o query ?token=)
		protected := web.Group("/", requireAuth)
		protected.Get("/dashboard", dashboardHandler)
		protected.Get("/settings", settingsHandler)
		protected.Get("/network", networkPageHandler)
		protected.Get("/wifi", wifiPageHandler)
		protected.Get("/wifi-scan", wifiScanPageHandler)
		protected.Get("/vpn", vpnPageHandler)
		protected.Get("/wireguard", wireguardPageHandler)
		protected.Get("/adblock", adblockPageHandler)
		protected.Get("/hostapd", hostapdPageHandler)
		protected.Get("/profile", profilePageHandler)
		protected.Get("/system", systemPageHandler)
		protected.Get("/monitoring", monitoringPageHandler)
		protected.Get("/update", updatePageHandler)
	}

	// API v1
	api := app.Group("/api/v1")
	{
		// Autenticación
		auth := api.Group("/auth")
		{
			auth.Post("/login", loginAPIHandler)
			auth.Post("/logout", requireAuth, logoutAPIHandler)
			auth.Get("/me", requireAuth, meHandler)
			auth.Post("/change-password", requireAuth, changePasswordAPIHandler)
			auth.Post("/first-login/change", firstLoginChangeAPIHandler)
			auth.Post("/profile", requireAuth, updateProfileAPIHandler)
			auth.Post("/preferences", requireAuth, updatePreferencesAPIHandler)
		}

		// Sistema
		system := api.Group("/system", requireAuth)
		{
			system.Get("/stats", systemStatsHandler)
			system.Get("/info", systemInfoHandler)
			system.Get("/logs", systemLogsHandler)
			system.Get("/activity", systemActivityHandler)
			system.Get("/network", systemNetworkHandler)
			system.Get("/updates", systemUpdatesHandler)
			system.Get("/services", systemServicesHandler)
			system.Post("/backup", systemBackupHandler)
			system.Post("/config", systemConfigHandler)
			system.Post("/restart", systemRestartHandler)
			system.Post("/shutdown", systemShutdownHandler)
		}

		// Red
		network := api.Group("/network", requireAuth)
		{
			network.Get("/status", networkStatusHandler)
			network.Get("/interfaces", networkInterfacesHandler)
			network.Get("/routing", networkRoutingHandler)
			network.Post("/firewall/toggle", networkFirewallToggleHandler)
			network.Post("/config", networkConfigHandler)
		}

		// WiFi
		wifi := api.Group("/wifi", requireAuth)
		{
			wifi.Get("/scan", wifiScanHandler)
			wifi.Post("/scan", wifiScanHandler)
			wifi.Get("/interfaces", wifiInterfacesHandler)
			wifi.Post("/connect", wifiConnectHandler)
			wifi.Get("/networks", wifiNetworksHandler)
			wifi.Get("/clients", wifiClientsHandler)
			wifi.Post("/toggle", wifiToggleHandler)
			wifi.Post("/unblock", wifiUnblockHandler)
			wifi.Post("/software-switch", wifiSoftwareSwitchHandler)
			wifi.Post("/config", wifiConfigHandler)
		}

		// VPN
		vpn := api.Group("/vpn", requireAuth)
		{
			vpn.Get("/status", vpnStatusHandler)
			vpn.Post("/connect", vpnConnectHandler)
			vpn.Get("/connections", vpnConnectionsHandler)
			vpn.Get("/servers", vpnServersHandler)
			vpn.Get("/clients", vpnClientsHandler)
			vpn.Post("/toggle", vpnToggleHandler)
			vpn.Post("/config", vpnConfigHandler)
			vpn.Post("/connections/:name/toggle", vpnConnectionToggleHandler)
			vpn.Post("/certificates/generate", vpnCertificatesGenerateHandler)
		}

		// HostAPD
		hostapd := api.Group("/hostapd", requireAuth)
		{
			hostapd.Get("/access-points", hostapdAccessPointsHandler)
			hostapd.Get("/clients", hostapdClientsHandler)
			hostapd.Post("/toggle", hostapdToggleHandler)
			hostapd.Post("/restart", hostapdRestartHandler)
			hostapd.Post("/config", hostapdConfigHandler)
		}

		// Help
		help := api.Group("/help", requireAuth)
		{
			help.Post("/contact", helpContactHandler)
		}

		// Translations (para carga dinámica)
		api.Get("/translations/:lang", translationsHandler)

		// WireGuard
		wireguard := api.Group("/wireguard", requireAuth)
		{
			wireguard.Get("/status", wireguardStatusHandler)
			wireguard.Get("/interfaces", wireguardInterfacesHandler)
			wireguard.Get("/peers", wireguardPeersHandler)
			wireguard.Get("/config", wireguardGetConfigHandler)
			wireguard.Post("/config", wireguardConfigHandler)
			wireguard.Post("/toggle", wireguardToggleHandler)
			wireguard.Post("/restart", wireguardRestartHandler)
		}

		// AdBlock
		adblock := api.Group("/adblock", requireAuth)
		{
			adblock.Get("/status", adblockStatusHandler)
			adblock.Post("/enable", adblockEnableHandler)
			adblock.Post("/disable", adblockDisableHandler)
		}
	}

	// Compat legacy: /api/wifi/* usado por wifi_scan.js
	// IMPORTANTE: NO usar app.Group("/api", ...) porque intercepta /api/v1/*
	wifiLegacy := app.Group("/api/wifi", requireAuth)
	wifiLegacy.Get("/status", wifiLegacyStatusHandler)
	wifiLegacy.Get("/stored_networks", wifiLegacyStoredNetworksHandler)
	wifiLegacy.Get("/autoconnect", wifiLegacyAutoconnectHandler)
	wifiLegacy.Get("/scan", wifiLegacyScanHandler)
	wifiLegacy.Post("/disconnect", wifiLegacyDisconnectHandler)
}

// Handlers básicos
func indexHandler(c *fiber.Ctx) error {
	// Intentar obtener token de cookie o query
	token := c.Cookies("access_token")
	if token == "" {
		token = c.Query("token")
	}

	// Si hay token, validarlo
	if token != "" {
		claims, err := ValidateToken(token)
		if err == nil {
			// Token válido, verificar usuario
			var user User
			if err := db.First(&user, claims.UserID).Error; err == nil && user.IsActive {
				// Usuario válido y activo, redirigir a dashboard
				return c.Redirect("/dashboard")
			}
		}
	}

	// No hay token válido o usuario no válido, redirigir a login
	return c.Redirect("/login")
}

func dashboardHandler(c *fiber.Ctx) error {
	return renderTemplate(c, "dashboard", fiber.Map{
		"Title": T(c, "dashboard.title", "Dashboard"),
	})
}

func loginHandler(c *fiber.Ctx) error {
	return renderTemplate(c, "login", fiber.Map{
		"Title": T(c, "auth.login", "Login"),
	})
}

func settingsHandler(c *fiber.Ctx) error {
	configs, _ := GetAllConfigs()

	// Asegurar valores por defecto si no existen
	if _, exists := configs["max_login_attempts"]; !exists || configs["max_login_attempts"] == "" {
		configs["max_login_attempts"] = "3"
	}
	if _, exists := configs["session_timeout"]; !exists || configs["session_timeout"] == "" {
		configs["session_timeout"] = "60"
	}
	if _, exists := configs["cache_enabled"]; !exists || configs["cache_enabled"] == "" {
		configs["cache_enabled"] = "true"
	}
	if _, exists := configs["cache_size"]; !exists || configs["cache_size"] == "" {
		configs["cache_size"] = "75"
	}

	configsJSON, _ := json.Marshal(configs)

	return renderTemplate(c, "settings", fiber.Map{
		"Title":         T(c, "navigation.settings", "Settings"),
		"settings":      configs,
		"settings_json": string(configsJSON),
	})
}

// Handlers de API que usan Lua
func systemStatsHandler(c *fiber.Ctx) error {
	if luaEngine != nil {
		// Ejecutar script Lua para obtener estadísticas
		result, err := luaEngine.Execute("system_stats.lua", nil)
		if err != nil {
			log.Printf("⚠️  Error ejecutando script Lua, usando fallback: %v", err)
			// Fallback a Go puro si Lua falla
			stats := getSystemStats()
			return c.JSON(stats)
		}
		// Verificar que el resultado tenga datos válidos
		if result != nil {
			// Si todos los valores son 0, usar fallback
			cpu, _ := result["cpu_usage"].(float64)
			mem, _ := result["memory_usage"].(float64)
			disk, _ := result["disk_usage"].(float64)
			if cpu == 0.0 && mem == 0.0 && disk == 0.0 {
				log.Printf("⚠️  Script Lua devolvió valores en 0, usando fallback")
				stats := getSystemStats()
				return c.JSON(stats)
			}
		}
		return c.JSON(result)
	}

	// Fallback a Go puro si Lua no está disponible
	log.Printf("ℹ️  Motor Lua no disponible, usando fallback")
	stats := getSystemStats()
	return c.JSON(stats)
}

func systemRestartHandler(c *fiber.Ctx) error {
	if luaEngine != nil {
		// Ejecutar script Lua para reiniciar el sistema
		user := c.Locals("user").(*User)
		result, err := luaEngine.Execute("system_restart.lua", fiber.Map{
			"user": user.Username,
		})
		if err != nil {
			return c.Status(500).JSON(fiber.Map{
				"error": err.Error(),
			})
		}
		return c.JSON(result)
	}

	return c.Status(500).JSON(fiber.Map{
		"error": "Lua engine no disponible",
	})
}

// detectWiFiInterface detecta automáticamente la interfaz WiFi
func detectWiFiInterface() string {
	// Intentar con nmcli primero (con sudo)
	cmd := exec.Command("sh", "-c", "sudo nmcli -t -f DEVICE,TYPE dev status 2>/dev/null | grep wifi | head -1 | cut -d: -f1")
	out, err := cmd.Output()
	if err == nil {
		iface := strings.TrimSpace(string(out))
		if iface != "" {
			return iface
		}
	}

	// Fallback: buscar interfaces wlan*
	cmd2 := exec.Command("sh", "-c", "ip -o link show | awk -F': ' '{print $2}' | grep -E '^wlan|^wl' | head -1")
	out2, err2 := cmd2.Output()
	if err2 == nil {
		iface := strings.TrimSpace(string(out2))
		if iface != "" {
			return iface
		}
	}

	// Último fallback: wlan0
	return "wlan0"
}

// wifiInterfacesHandler devuelve las interfaces WiFi disponibles
func wifiInterfacesHandler(c *fiber.Ctx) error {
	var interfaces []fiber.Map

	// Método 1: nmcli (con sudo)
	cmd := exec.Command("sh", "-c", "sudo nmcli -t -f DEVICE,TYPE,STATE dev status 2>/dev/null | grep wifi")
	out, err := cmd.Output()
	if err == nil {
		lines := strings.Split(strings.TrimSpace(string(out)), "\n")
		for _, line := range lines {
			parts := strings.Split(line, ":")
			if len(parts) >= 2 {
				iface := fiber.Map{
					"name":  parts[0],
					"type":  parts[1],
					"state": "unknown",
				}
				if len(parts) >= 3 {
					iface["state"] = parts[2]
				}
				interfaces = append(interfaces, iface)
			}
		}
	}

	// Fallback: buscar interfaces wlan* manualmente
	if len(interfaces) == 0 {
		cmd2 := exec.Command("sh", "-c", "ip -o link show | awk -F': ' '{print $2}' | grep -E '^wlan|^wl'")
		out2, err2 := cmd2.Output()
		if err2 == nil {
			lines := strings.Split(strings.TrimSpace(string(out2)), "\n")
			for _, ifaceName := range lines {
				ifaceName = strings.TrimSpace(ifaceName)
				if ifaceName != "" {
					// Verificar estado
					stateCmd := exec.Command("sh", "-c", fmt.Sprintf("cat /sys/class/net/%s/operstate 2>/dev/null", ifaceName))
					stateOut, _ := stateCmd.Output()
					state := strings.TrimSpace(string(stateOut))
					if state == "" {
						state = "unknown"
					}

					interfaces = append(interfaces, fiber.Map{
						"name":  ifaceName,
						"type":  "wifi",
						"state": state,
					})
				}
			}
		}
	}

	// Si no hay interfaces, agregar wlan0 como opción por defecto
	if len(interfaces) == 0 {
		interfaces = append(interfaces, fiber.Map{
			"name":  "wlan0",
			"type":  "wifi",
			"state": "unknown",
		})
	}

	return c.JSON(fiber.Map{
		"success":   true,
		"interfaces": interfaces,
	})
}

func wifiScanHandler(c *fiber.Ctx) error {
	// Obtener interfaz del query o body
	interfaceName := c.Query("interface", "")
	if interfaceName == "" {
		var req struct {
			Interface string `json:"interface"`
		}
		if err := c.BodyParser(&req); err == nil {
			interfaceName = req.Interface
		}
	}

	// Si no se especifica interfaz, detectar automáticamente
	if interfaceName == "" {
		interfaceName = detectWiFiInterface()
	}

	if luaEngine != nil {
		result, err := luaEngine.Execute("wifi_scan.lua", fiber.Map{
			"interface": interfaceName,
		})
		if err != nil {
			log.Printf("⚠️  Error ejecutando wifi_scan.lua, usando fallback: %v", err)
			// Fallback: intentar escanear directamente con comandos del sistema
			return wifiScanFallback(c, interfaceName)
		}
		// Verificar que el resultado tenga networks
		if result != nil {
			if networks, ok := result["networks"]; ok {
				return c.JSON(fiber.Map{
					"success":  true,
					"networks": networks,
				})
			}
		}
		// Si no hay networks, usar fallback
		return wifiScanFallback(c, interfaceName)
	}

	return c.Status(500).JSON(fiber.Map{
		"error": "Lua engine no disponible",
	})
}

// wifiScanFallback escanea WiFi usando comandos del sistema directamente
func wifiScanFallback(c *fiber.Ctx, interfaceName string) error {
	var networks []fiber.Map

	// Si no se especifica interfaz, detectar automáticamente
	if interfaceName == "" {
		interfaceName = detectWiFiInterface()
	}

	// Verificar que WiFi esté habilitado (con sudo)
	wifiCheck := exec.Command("sh", "-c", "sudo nmcli -t -f WIFI g 2>/dev/null")
	wifiOut, _ := wifiCheck.Output()
	wifiState := strings.ToLower(strings.TrimSpace(string(wifiOut)))
	if !strings.Contains(wifiState, "enabled") && !strings.Contains(wifiState, "on") {
		log.Printf("⚠️  WiFi no está habilitado")
		return c.JSON(fiber.Map{
			"success":  false,
			"error":    "WiFi no está habilitado. Por favor, habilita WiFi primero.",
			"networks": []fiber.Map{},
		})
	}

	// Método 1: Intentar con nmcli (formato mejorado, con sudo)
	cmd := exec.Command("sh", "-c", "sudo nmcli -t -f SSID,SIGNAL,SECURITY,CHAN dev wifi list 2>&1")
	out, err := cmd.CombinedOutput()
	output := strings.TrimSpace(string(out))

	if err == nil && len(output) > 0 && !strings.Contains(output, "Error") && !strings.Contains(output, "permission") {
		log.Printf("📡 Escaneando con nmcli...")
		lines := strings.Split(output, "\n")
		for _, line := range lines {
			line = strings.TrimSpace(line)
			if line == "" || line == "--" || strings.HasPrefix(line, "Error") {
				continue
			}
			parts := strings.Split(line, ":")
			if len(parts) >= 2 {
				ssid := parts[0]
				signalStr := parts[1]
				security := "Open"
				channel := ""
				if len(parts) >= 3 {
					security = parts[2]
				}
				if len(parts) >= 4 {
					channel = parts[3]
				}
				if ssid != "" && ssid != "--" {
					signal := 0
					if s, err := strconv.Atoi(signalStr); err == nil {
						signal = s
					}
					networks = append(networks, fiber.Map{
						"ssid":     ssid,
						"signal":   signal,
						"security": security,
						"channel":  channel,
					})
				}
			}
		}
		if len(networks) > 0 {
			log.Printf("✅ Encontradas %d redes con nmcli", len(networks))
			return c.JSON(fiber.Map{
				"success":  true,
				"networks": networks,
			})
		}
	}

	// Método 2: Intentar con iw si nmcli no funcionó
	log.Printf("📡 Intentando escanear con iw en interfaz %s...", interfaceName)
	iwCmd := exec.Command("sh", "-c", fmt.Sprintf("sudo iw dev %s scan 2>&1 | grep -E 'SSID|signal|freq' | head -30", interfaceName))
	iwOut, iwErr := iwCmd.CombinedOutput()
	if iwErr == nil && len(iwOut) > 0 {
		lines := strings.Split(string(iwOut), "\n")
		currentNetwork := make(map[string]interface{})
		for _, line := range lines {
			line = strings.TrimSpace(line)
			if strings.Contains(line, "SSID:") {
				if ssid, ok := currentNetwork["ssid"].(string); ok && ssid != "" {
					networks = append(networks, fiber.Map{
						"ssid":     currentNetwork["ssid"],
						"signal":   currentNetwork["signal"],
						"security": currentNetwork["security"],
						"channel":  currentNetwork["channel"],
					})
				}
				currentNetwork = make(map[string]interface{})
				ssid := strings.TrimSpace(strings.TrimPrefix(line, "SSID:"))
				if ssid != "" {
					currentNetwork["ssid"] = ssid
					currentNetwork["security"] = "Unknown"
					currentNetwork["signal"] = 0
					currentNetwork["channel"] = ""
				}
			} else if strings.Contains(line, "signal:") {
				parts := strings.Fields(line)
				for i, part := range parts {
					if part == "signal:" && i+1 < len(parts) {
						if s, err := strconv.Atoi(parts[i+1]); err == nil {
							currentNetwork["signal"] = s
						}
						break
					}
				}
			} else if strings.Contains(line, "freq:") {
				parts := strings.Fields(line)
				for i, part := range parts {
					if part == "freq:" && i+1 < len(parts) {
						if f, err := strconv.Atoi(parts[i+1]); err == nil {
							// Convertir frecuencia a canal
							if f >= 2412 && f <= 2484 {
								channel := (f-2412)/5 + 1
								currentNetwork["channel"] = strconv.Itoa(channel)
							} else if f >= 5000 && f <= 5825 {
								channel := (f - 5000) / 5
								currentNetwork["channel"] = strconv.Itoa(channel)
							}
						}
						break
					}
				}
			}
		}
		if ssid, ok := currentNetwork["ssid"].(string); ok && ssid != "" {
			networks = append(networks, fiber.Map{
				"ssid":     currentNetwork["ssid"],
				"signal":   currentNetwork["signal"],
				"security": currentNetwork["security"],
				"channel":  currentNetwork["channel"],
			})
		}
		if len(networks) > 0 {
			log.Printf("✅ Encontradas %d redes con iw", len(networks))
			return c.JSON(fiber.Map{
				"success":  true,
				"networks": networks,
			})
		}
	}

	// Si no hay redes encontradas, retornar array vacío con mensaje
	log.Printf("⚠️  No se encontraron redes WiFi")
	return c.JSON(fiber.Map{
		"success":  true,
		"error":    "No se encontraron redes WiFi. Verifica que WiFi esté habilitado y que haya redes disponibles en el área.",
		"networks": []fiber.Map{},
	})
}

// Middlewares
func securityMiddleware(c *fiber.Ctx) error {
	// Headers de seguridad
	c.Set("X-Content-Type-Options", "nosniff")
	c.Set("X-Frame-Options", "DENY")
	c.Set("X-XSS-Protection", "1; mode=block")
	c.Set("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
	return c.Next()
}

func getSystemStats() fiber.Map {
	stats := fiber.Map{
		"cpu_usage":      0.0,
		"memory_usage":   0.0,
		"disk_usage":     0.0,
		"uptime":         0,
		"cpu_cores":      1,
		"hostname":       "unknown",
		"kernel_version": "unknown",
		"architecture":   "unknown",
		"os_version":     "Linux",
	}

	// Intentar obtener datos reales del sistema
	// CPU usage - usar /proc/stat (más confiable)
	cpuOut, cpuErr := executeCommand("grep 'cpu ' /proc/stat | awk '{usage=($2+$4)*100/($2+$3+$4+$5)} END {print usage}'")
	if cpuErr == nil && strings.TrimSpace(cpuOut) != "" {
		// Normalizar: reemplazar coma por punto para locales que usan coma
		cpuOut = strings.ReplaceAll(strings.TrimSpace(cpuOut), ",", ".")
		if cpu, err := strconv.ParseFloat(cpuOut, 64); err == nil && cpu >= 0 && cpu <= 100 {
			stats["cpu_usage"] = cpu
			log.Printf("✅ CPU usage obtenido: %.2f%%", cpu)
		} else {
			log.Printf("⚠️  Error parseando CPU: %v, output: %s", err, cpuOut)
		}
	} else {
		log.Printf("⚠️  Error ejecutando comando CPU: %v", cpuErr)
	}

	// Fallback alternativo para CPU usando top
	if stats["cpu_usage"] == 0.0 {
		cpuOut2, cpuErr2 := executeCommand("top -bn1 | grep 'Cpu(s)' | awk -F'id,' '{split($1,a,\"%\"); for(i in a){if(a[i] ~ /^[0-9]/){print 100-a[i];break}}}'")
		if cpuErr2 == nil && strings.TrimSpace(cpuOut2) != "" {
			cpuOut2 = strings.ReplaceAll(strings.TrimSpace(cpuOut2), ",", ".")
			if cpu, err := strconv.ParseFloat(cpuOut2, 64); err == nil && cpu >= 0 && cpu <= 100 {
				stats["cpu_usage"] = cpu
				log.Printf("✅ CPU usage obtenido (fallback): %.2f%%", cpu)
			}
		}
	}

	// Memory usage
	memOut, memErr := executeCommand("free | grep Mem | awk '{printf \"%.2f\", $3/$2 * 100.0}'")
	if memErr == nil && strings.TrimSpace(memOut) != "" {
		// Normalizar: reemplazar coma por punto
		memOut = strings.ReplaceAll(strings.TrimSpace(memOut), ",", ".")
		if mem, err := strconv.ParseFloat(memOut, 64); err == nil && mem >= 0 && mem <= 100 {
			stats["memory_usage"] = mem
			log.Printf("✅ Memory usage obtenido: %.2f%%", mem)
		} else {
			log.Printf("⚠️  Error parseando Memory: %v, output: %s", err, memOut)
		}
	} else {
		log.Printf("⚠️  Error ejecutando comando Memory: %v", memErr)
	}

	// Disk usage - usar método más simple
	diskOut, diskErr := executeCommand("df / | tail -1 | awk '{print $5}' | sed 's/%//'")
	if diskErr == nil && strings.TrimSpace(diskOut) != "" {
		if disk, err := strconv.ParseFloat(strings.TrimSpace(diskOut), 64); err == nil && disk >= 0 && disk <= 100 {
			stats["disk_usage"] = disk
			log.Printf("✅ Disk usage obtenido: %.2f%%", disk)
		} else {
			log.Printf("⚠️  Error parseando Disk: %v, output: %s", err, diskOut)
		}
	} else {
		log.Printf("⚠️  Error ejecutando comando Disk: %v", diskErr)
	}

	// Uptime
	if uptimeOut, err := executeCommand("cat /proc/uptime | awk '{print int($1)}'"); err == nil {
		if uptime, err := strconv.Atoi(strings.TrimSpace(uptimeOut)); err == nil {
			stats["uptime"] = uptime
		}
	}

	// CPU cores
	if coresOut, err := executeCommand("nproc"); err == nil {
		if cores, err := strconv.Atoi(strings.TrimSpace(coresOut)); err == nil && cores > 0 {
			stats["cpu_cores"] = cores
		}
	}

	// Hostname
	if hostname, err := executeCommand("hostname"); err == nil && hostname != "" {
		stats["hostname"] = hostname
	}

	// Kernel version
	if kernel, err := executeCommand("uname -r"); err == nil && kernel != "" {
		stats["kernel_version"] = kernel
	}

	// Architecture
	if arch, err := executeCommand("uname -m"); err == nil && arch != "" {
		stats["architecture"] = arch
	}

	// OS version
	if osRelease, err := os.ReadFile("/etc/os-release"); err == nil {
		lines := strings.Split(string(osRelease), "\n")
		for _, line := range lines {
			if strings.HasPrefix(line, "PRETTY_NAME=") {
				osVersion := strings.TrimPrefix(line, "PRETTY_NAME=")
				osVersion = strings.Trim(osVersion, "\"")
				if osVersion != "" {
					stats["os_version"] = osVersion
				}
				break
			}
		}
	}

	return stats
}
