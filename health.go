package main

import (
	"time"

	"github.com/gofiber/fiber/v2"
)

// HealthCheckResponse estructura de respuesta del health check
type HealthCheckResponse struct {
	Status    string            `json:"status"`
	Timestamp time.Time         `json:"timestamp"`
	Version   string            `json:"version"`
	Services  map[string]string `json:"services"`
}

// healthCheckHandler maneja el endpoint de health check
func healthCheckHandler(c *fiber.Ctx) error {
	response := HealthCheckResponse{
		Status:    "healthy",
		Timestamp: time.Now(),
		Version:   "2.0.0",
		Services:  make(map[string]string),
	}

	// Verificar base de datos
	if db != nil {
		sqlDB, err := db.DB()
		if err == nil {
			if err := sqlDB.Ping(); err == nil {
				response.Services["database"] = "healthy"
			} else {
				response.Services["database"] = "unhealthy"
				response.Status = "degraded"
			}
		} else {
			response.Services["database"] = "unhealthy"
			response.Status = "degraded"
		}
	} else {
		response.Services["database"] = "not_configured"
		response.Status = "degraded"
	}

	// Lua ya no se usa - todo está en Go ahora

	// Verificar i18n
	if i18nManager != nil {
		response.Services["i18n"] = "healthy"
	} else {
		response.Services["i18n"] = "unhealthy"
		response.Status = "degraded"
	}

	statusCode := 200
	if response.Status == "degraded" {
		statusCode = 503
	}

	return c.Status(statusCode).JSON(response)
}

// readinessCheckHandler verifica si la aplicación está lista para recibir tráfico
func readinessCheckHandler(c *fiber.Ctx) error {
	if db == nil {
		return c.Status(503).JSON(fiber.Map{
			"status":  "not_ready",
			"message": "Database not initialized",
		})
	}

	// Verificar conexión a BD
	sqlDB, err := db.DB()
	if err != nil {
		return c.Status(503).JSON(fiber.Map{
			"status":  "not_ready",
			"message": "Database connection error",
		})
	}

	if err := sqlDB.Ping(); err != nil {
		return c.Status(503).JSON(fiber.Map{
			"status":  "not_ready",
			"message": "Database ping failed",
		})
	}

	return c.JSON(fiber.Map{
		"status":  "ready",
		"message": "Application is ready",
	})
}

// livenessCheckHandler verifica si la aplicación está viva
func livenessCheckHandler(c *fiber.Ctx) error {
	return c.JSON(fiber.Map{
		"status":  "alive",
		"message": "Application is running",
	})
}
