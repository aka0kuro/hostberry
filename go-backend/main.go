package main

import (
	"context"
	"embed"
	"encoding/json"
	"fmt"
	"log"
	"net/http"
	"os"
	"os/signal"
	"syscall"
	"time"

	"github.com/gofiber/fiber/v2"
	"github.com/gofiber/fiber/v2/middleware/cors"
	"github.com/gofiber/fiber/v2/middleware/compress"
	"github.com/gofiber/fiber/v2/middleware/logger"
	"github.com/gofiber/template/html/v2"
	"gopkg.in/yaml.v3"
)

//go:embed website/templates/*.html
var templatesFS embed.FS

//go:embed website/static/*
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
		log.Fatalf("Error inicializando base de datos: %v", err)
	}

	// Crear usuario admin por defecto si no existe
	createDefaultAdmin()

	// Crear aplicación Fiber
	app := createApp()

	// Configurar rutas
	setupRoutes(app)

	// Iniciar servidor
	addr := fmt.Sprintf("%s:%d", appConfig.Server.Host, appConfig.Server.Port)
	log.Printf("🚀 HostBerry iniciando en %s", addr)

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
	}()

	if err := app.Listen(addr); err != nil {
		log.Fatalf("Error iniciando servidor: %v", err)
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
	engine := html.NewFileSystem(http.FS(templatesFS), ".html")
	engine.Reload(true) // Solo en desarrollo

	app := fiber.New(fiber.Config{
		Views:        engine,
		ReadTimeout:  time.Duration(appConfig.Server.ReadTimeout) * time.Second,
		WriteTimeout: time.Duration(appConfig.Server.WriteTimeout) * time.Second,
		ErrorHandler: errorHandler,
	})

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

	return app
}

func setupRoutes(app *fiber.App) {
	// Archivos estáticos
	app.Static("/static", "./website/static", fiber.Static{
		Compress:  true,
		ByteRange: true,
	})

	// Rutas web
	web := app.Group("/")
	{
		web.Get("/", indexHandler)
		web.Get("/dashboard", dashboardHandler)
		web.Get("/login", loginHandler)
		web.Get("/settings", settingsHandler)
		// ... más rutas web
	}

	// API v1
	api := app.Group("/api/v1")
	{
		// Autenticación
		auth := api.Group("/auth")
		{
			auth.Post("/login", loginAPIHandler)
			auth.Post("/logout", logoutAPIHandler)
			auth.Get("/me", meHandler)
		}

		// Sistema
		system := api.Group("/system", requireAuth)
		{
			system.Get("/stats", systemStatsHandler)
			system.Get("/info", systemInfoHandler)
			system.Get("/logs", systemLogsHandler)
			system.Post("/restart", systemRestartHandler)
			system.Post("/shutdown", systemShutdownHandler)
		}

		// Red
		network := api.Group("/network", requireAuth)
		{
			network.Get("/status", networkStatusHandler)
			network.Get("/interfaces", networkInterfacesHandler)
		}

		// WiFi
		wifi := api.Group("/wifi", requireAuth)
		{
			wifi.Get("/scan", wifiScanHandler)
			wifi.Post("/connect", wifiConnectHandler)
		}

		// VPN
		vpn := api.Group("/vpn", requireAuth)
		{
			vpn.Get("/status", vpnStatusHandler)
			vpn.Post("/connect", vpnConnectHandler)
		}

		// WireGuard
		wireguard := api.Group("/wireguard", requireAuth)
		{
			wireguard.Get("/status", wireguardStatusHandler)
			wireguard.Post("/config", wireguardConfigHandler)
		}

		// AdBlock
		adblock := api.Group("/adblock", requireAuth)
		{
			adblock.Get("/status", adblockStatusHandler)
			adblock.Post("/enable", adblockEnableHandler)
			adblock.Post("/disable", adblockDisableHandler)
		}
	}
}

// Handlers básicos
func indexHandler(c *fiber.Ctx) error {
	return c.Redirect("/dashboard")
}

func dashboardHandler(c *fiber.Ctx) error {
	language := GetCurrentLanguage(c)
	i18nFuncs := TemplateFuncs(c)
	
	// Convertir traducciones a JSON para JavaScript
	translationsJSON, _ := json.Marshal(i18nFuncs["translations"])
	
	data := fiber.Map{
		"Title":         T(c, "dashboard.title", "Dashboard"),
		"language":      language,
		"current_user": c.Locals("user"),
		"translations_json": string(translationsJSON),
	}
	
	// Agregar funciones i18n
	for k, v := range i18nFuncs {
		data[k] = v
	}
	
	return c.Render("dashboard", data)
}

func loginHandler(c *fiber.Ctx) error {
	language := GetCurrentLanguage(c)
	i18nFuncs := TemplateFuncs(c)
	
	data := fiber.Map{
		"Title":    T(c, "auth.login", "Login"),
		"language": language,
	}
	
	// Agregar funciones i18n
	for k, v := range i18nFuncs {
		data[k] = v
	}
	
	return c.Render("login", data)
}

func settingsHandler(c *fiber.Ctx) error {
	language := GetCurrentLanguage(c)
	i18nFuncs := TemplateFuncs(c)
	
	// Convertir traducciones a JSON para JavaScript
	translationsJSON, _ := json.Marshal(i18nFuncs["translations"])
	
	data := fiber.Map{
		"Title":            T(c, "navigation.settings", "Settings"),
		"language":         language,
		"current_user":     c.Locals("user"),
		"translations_json": string(translationsJSON),
	}
	
	// Agregar funciones i18n
	for k, v := range i18nFuncs {
		data[k] = v
	}
	
	return c.Render("settings", data)
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
	// Obtener estadísticas del sistema (fallback sin Lua)
	return fiber.Map{
		"cpu_usage":    0.0,
		"memory_usage": 0.0,
		"disk_usage":   0.0,
		"uptime":       0,
	}
}
