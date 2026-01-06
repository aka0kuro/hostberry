package main

import (
	"crypto/rand"
	"encoding/hex"

	"github.com/gofiber/fiber/v2"
)

// requestIDMiddleware agrega un ID único a cada request para tracing
func requestIDMiddleware(c *fiber.Ctx) error {
	// Intentar obtener ID del header (para requests entre servicios)
	requestID := c.Get("X-Request-ID")
	
	// Si no existe, generar uno nuevo
	if requestID == "" {
		bytes := make([]byte, 16)
		if _, err := rand.Read(bytes); err == nil {
			requestID = hex.EncodeToString(bytes)
		} else {
			// Fallback simple
			requestID = generateSimpleID()
		}
	}

	// Agregar al contexto
	c.Locals("request_id", requestID)
	
	// Agregar al header de respuesta
	c.Set("X-Request-ID", requestID)

	return c.Next()
}

func generateSimpleID() string {
	// Generar ID simple basado en timestamp y random
	return hex.EncodeToString([]byte{byte(time.Now().Unix() % 256)})
}
