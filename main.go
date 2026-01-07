package main

import (
	"context"
	"embed"
	"encoding/json"
	"fmt"
	"io/fs"
	"log"
	"os"
	"os/signal"
	"path/filepath"
	"strconv"
	"strings"
	"syscall"
	"time"

	"github.com/gofiber/fiber/v2"
	"github.com/gofiber/fiber/v2/middleware/cors"
	"github.com/gofiber/fiber/v2/middleware/compress"
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
	JWTSecret     string `yaml:"jwt_secret"`
	TokenExpiry   int    `yaml:"token_expiry"` // minutos
	BcryptCost    int    `yaml:"bcrypt_cost"`
	RateLimitRPS  int    `yaml:"rate_limit_rps"`
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

	// Middlewares globales
	app.Use(logger.New())
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

func setupRoutes(app *fiber.App) {
	// Health check endpoints (sin autenticación)
	app.Get("/health", healthCheckHandler)
	app.Get("/health/ready", readinessCheckHandler)
	app.Get("/health/live", livenessCheckHandler)

	// Archivos estáticos embebidos
	staticSubFS, err := fs.Sub(staticFS, "website/static")
	if err != nil {
		log.Printf("⚠️  Error preparando archivos estáticos embebidos: %v", err)
		// Fallback a sistema de archivos si existe
		if _, err := os.Stat("./website/static"); err == nil {
			app.Static("/static", "./website/static", fiber.Static{
				Compress:  true,
				ByteRange: true,
			})
			log.Println("✅ Archivos estáticos cargados desde sistema de archivos")
		} else {
			log.Printf("⚠️  No se encontraron archivos estáticos ni embebidos ni en filesystem")
		}
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
			wifi.Post("/connect", wifiConnectHandler)
			wifi.Get("/networks", wifiNetworksHandler)
			wifi.Get("/clients", wifiClientsHandler)
			wifi.Post("/toggle", wifiToggleHandler)
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
			return c.Status(500).JSON(fiber.Map{
				"error": err.Error(),
			})
		}
		return c.JSON(result)
	}

	// Fallback a Go puro si Lua no está disponible
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

func wifiScanHandler(c *fiber.Ctx) error {
	if luaEngine != nil {
		result, err := luaEngine.Execute("wifi_scan.lua", nil)
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
		"cpu_usage":     0.0,
		"memory_usage": 0.0,
		"disk_usage":   0.0,
		"uptime":       0,
		"cpu_cores":    1,
		"hostname":     "unknown",
		"kernel_version": "unknown",
		"architecture": "unknown",
		"os_version":   "Linux",
	}
	
	// Intentar obtener datos reales del sistema
	// CPU usage - usar método más robusto
	if cpuOut, err := executeCommand("top -bn1 | grep 'Cpu(s)' | awk '{for(i=1;i<=NF;i++){if($i ~ /id/){split($i,a,\"%\");print 100-a[1]}}}'"); err == nil && strings.TrimSpace(cpuOut) != "" {
		if cpu, err := strconv.ParseFloat(strings.TrimSpace(cpuOut), 64); err == nil && cpu >= 0 && cpu <= 100 {
			stats["cpu_usage"] = cpu
		}
	}
	// Fallback alternativo para CPU
	if stats["cpu_usage"] == 0.0 {
		if cpuOut, err := executeCommand("grep 'cpu ' /proc/stat | awk '{usage=($2+$4)*100/($2+$3+$4+$5)} END {print usage}'"); err == nil && strings.TrimSpace(cpuOut) != "" {
			if cpu, err := strconv.ParseFloat(strings.TrimSpace(cpuOut), 64); err == nil && cpu >= 0 && cpu <= 100 {
				stats["cpu_usage"] = cpu
			}
		}
	}
	
	// Memory usage
	if memOut, err := executeCommand("free | grep Mem | awk '{printf \"%.2f\", $3/$2 * 100.0}'"); err == nil && strings.TrimSpace(memOut) != "" {
		if mem, err := strconv.ParseFloat(strings.TrimSpace(memOut), 64); err == nil && mem >= 0 && mem <= 100 {
			stats["memory_usage"] = mem
		}
	}
	
	// Disk usage - usar método más simple
	if diskOut, err := executeCommand("df / | tail -1 | awk '{print $5}' | sed 's/%//'"); err == nil && strings.TrimSpace(diskOut) != "" {
		if disk, err := strconv.ParseFloat(strings.TrimSpace(diskOut), 64); err == nil && disk >= 0 && disk <= 100 {
			stats["disk_usage"] = disk
		}
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
