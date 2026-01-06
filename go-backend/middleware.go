package main

import (
	"strings"
	"time"

	"github.com/gofiber/fiber/v2"
)

// requireAuth middleware que requiere autenticación
func requireAuth(c *fiber.Ctx) error {
	// Obtener token del header Authorization
	authHeader := c.Get("Authorization")
	if authHeader == "" {
		return c.Status(401).JSON(fiber.Map{
			"error": "No autorizado - token requerido",
		})
	}

	// Extraer token (formato: "Bearer <token>")
	parts := strings.Split(authHeader, " ")
	if len(parts) != 2 || parts[0] != "Bearer" {
		return c.Status(401).JSON(fiber.Map{
			"error": "Formato de token inválido",
		})
	}

	token := parts[1]

	// Validar token
	claims, err := ValidateToken(token)
	if err != nil {
		return c.Status(401).JSON(fiber.Map{
			"error": "Token inválido o expirado",
		})
	}

	// Obtener usuario de la base de datos
	var user User
	if err := db.First(&user, claims.UserID).Error; err != nil {
		return c.Status(401).JSON(fiber.Map{
			"error": "Usuario no encontrado",
		})
	}

	if !user.IsActive {
		return c.Status(401).JSON(fiber.Map{
			"error": "Usuario inactivo",
		})
	}

	// Agregar usuario al contexto
	c.Locals("user", &user)
	c.Locals("user_id", user.ID)

	return c.Next()
}

// rateLimitMiddleware middleware de rate limiting básico
func rateLimitMiddleware(c *fiber.Ctx) error {
	// Implementación básica de rate limiting
	// En producción, usar redis o similar
	// Por ahora, solo pasar al siguiente middleware
	return c.Next()
}

// loggingMiddleware middleware de logging de requests
func loggingMiddleware(c *fiber.Ctx) error {
	start := time.Now()

	// Continuar con el request
	err := c.Next()

	// Log después de procesar
	duration := time.Since(start)
	
	userID := c.Locals("user_id")
	var userIDPtr *int
	if userID != nil {
		id := userID.(int)
		userIDPtr = &id
	}

	// Insertar log en BD (async, no bloquea)
	go func() {
		InsertLog(
			"INFO",
			c.Method()+" "+c.Path()+" - "+c.IP()+" - "+duration.String(),
			"http",
			userIDPtr,
		)
	}()

	return err
}

// errorHandler maneja errores de la aplicación
func errorHandler(c *fiber.Ctx, err error) error {
	code := fiber.StatusInternalServerError
	message := "Error interno del servidor"

	if e, ok := err.(*fiber.Error); ok {
		code = e.Code
		message = e.Message
	}

	// Log del error
	userID := c.Locals("user_id")
	var userIDPtr *int
	if userID != nil {
		id := userID.(int)
		userIDPtr = &id
	}

	go func() {
		InsertLog(
			"ERROR",
			"Error en "+c.Path()+": "+err.Error(),
			"http",
			userIDPtr,
		)
	}()

	// Si es una petición de API, retornar JSON
	if strings.HasPrefix(c.Path(), "/api/") {
		return c.Status(code).JSON(fiber.Map{
			"error":   message,
			"path":    c.Path(),
			"method":  c.Method(),
		})
	}

	// Si es una página web, renderizar página de error
	return renderTemplate(c, "error", fiber.Map{
		"Title":   "Error",
		"Code":    code,
		"Message": message,
	})
}
