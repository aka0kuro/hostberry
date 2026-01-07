package main

import (
	"fmt"
	"log"
	"strings"
	"time"

	"github.com/gofiber/fiber/v2"
)

// requireAuth middleware que requiere autenticación
func requireAuth(c *fiber.Ctx) error {
	// Rutas públicas que NO requieren autenticación
	publicPaths := []string{
		"/api/v1/auth/login",
		"/api/v1/translations/",
		"/health",
		"/health/ready",
		"/health/live",
	}
	
	path := c.Path()
	for _, publicPath := range publicPaths {
		if path == publicPath || strings.HasPrefix(path, publicPath) {
			// Esta ruta es pública, permitir sin autenticación
			return c.Next()
		}
	}
	
	var token string
	
	// Para APIs, obtener token del header Authorization
	if strings.HasPrefix(c.Path(), "/api/") {
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
		token = parts[1]
	} else {
		// Para rutas web, intentar obtener token de cookie o query parameter
		// (el frontend puede enviarlo en cookie o el JS lo maneja con localStorage)
		token = c.Cookies("access_token")
		if token == "" {
			token = c.Query("token")
		}
		
		// Si no hay token, redirigir a login
		if token == "" {
			return c.Redirect("/login")
		}
	}

	// Validar token
	claims, err := ValidateToken(token)
	if err != nil {
		if strings.HasPrefix(c.Path(), "/api/") {
			return c.Status(401).JSON(fiber.Map{
				"error": "Token inválido o expirado",
			})
		}
		// Para web, redirigir a login
		return c.Redirect("/login")
	}

	// Obtener usuario de la base de datos
	var user User
	if err := db.First(&user, claims.UserID).Error; err != nil {
		if strings.HasPrefix(c.Path(), "/api/") {
			return c.Status(401).JSON(fiber.Map{
				"error": "Usuario no encontrado",
			})
		}
		return c.Redirect("/login")
	}

	if !user.IsActive {
		if strings.HasPrefix(c.Path(), "/api/") {
			return c.Status(401).JSON(fiber.Map{
				"error": "Usuario inactivo",
			})
		}
		return c.Redirect("/login")
	}

	// Agregar usuario al contexto
	c.Locals("user", &user)
	c.Locals("user_id", user.ID)

	return c.Next()
}

// rateLimitMiddleware está definido en rate_limiter.go

// loggingMiddleware middleware de logging de requests
func loggingMiddleware(c *fiber.Ctx) error {
	start := time.Now()

	// Continuar con el request
	err := c.Next()

	// Log después de procesar
	duration := time.Since(start)
	
	// Capturar valores del contexto ANTES de la goroutine
	// (el contexto no es seguro para usar en goroutines)
	method := c.Method()
	path := c.Path()
	ip := c.IP()
	
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
			method+" "+path+" - "+ip+" - "+duration.String(),
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

	// Capturar valores del contexto ANTES de la goroutine
	// (el contexto no es seguro para usar en goroutines)
	method := c.Method()
	path := c.Path()
	errMsg := err.Error()
	
	userID := c.Locals("user_id")
	var userIDPtr *int
	if userID != nil {
		id := userID.(int)
		userIDPtr = &id
	}

	// Solo registrar errores del servidor (500+) como ERROR
	// Los errores de validación (400-499) son esperados y no se registran como ERROR
	if code >= 500 {
		// Log detallado del error del servidor
		log.Printf("❌ Error en %s %s: %v", method, path, err)
		
		go func() {
			InsertLog(
				"ERROR",
				"Error en "+path+": "+errMsg,
				"http",
				userIDPtr,
			)
		}()
	}

	// Si es una petición de API, retornar JSON
	if strings.HasPrefix(c.Path(), "/api/") {
		return c.Status(code).JSON(fiber.Map{
			"error":   message,
			"path":    c.Path(),
			"method":  c.Method(),
			"details": err.Error(),
		})
	}

	// Si es una página web, intentar renderizar página de error
	// Si falla el render, retornar error simple
	if renderErr := renderTemplate(c, "error", fiber.Map{
		"Title":   "Error",
		"Code":    code,
		"Message": message,
		"Details": err.Error(),
	}); renderErr != nil {
		log.Printf("❌ Error al renderizar página de error: %v", renderErr)
		// Fallback: retornar HTML simple
		return c.Status(code).SendString(fmt.Sprintf(
			"<html><body><h1>Error %d</h1><p>%s</p><p>%s</p></body></html>",
			code, message, err.Error(),
		))
	}
	return nil
}
