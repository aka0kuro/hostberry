package main

import (
	"fmt"
	"log"
	"os"
	"os/exec"
	"path/filepath"
	"strings"

	"github.com/gofiber/fiber/v2"
)

// systemConfigHandler maneja la actualización de configuraciones del sistema
func systemConfigHandler(c *fiber.Ctx) error {
	var req map[string]interface{}
	if err := c.BodyParser(&req); err != nil {
		return c.Status(400).JSON(fiber.Map{
			"error": "Datos inválidos",
		})
	}

	user := c.Locals("user").(*User)
	userID := user.ID
	
	updatedKeys := []string{}
	errors := []string{}
	
	// Procesar cada clave de configuración
	for key, value := range req {
		// Convertir valor a string
		var valueStr string
		switch v := value.(type) {
		case string:
			valueStr = v
		case float64:
			valueStr = fmt.Sprintf("%v", v) // Para números JSON
		case bool:
			valueStr = fmt.Sprintf("%v", v)
		case nil:
			continue
		default:
			valueStr = fmt.Sprintf("%v", v)
		}
		
		// Guardar en BD
		if err := SetConfig(key, valueStr); err != nil {
			log.Printf("⚠️ Error guardando configuración %s: %v", key, err)
			errors = append(errors, fmt.Sprintf("Error guardando %s", key))
		}
		
		// Aplicar cambios del sistema
		if key == "timezone" && valueStr != "" {
			tz := strings.TrimSpace(valueStr)
			
			// Validar timezone (básico)
			if strings.Contains(tz, "..") || strings.Contains(tz, ";") {
				errors = append(errors, "Zona horaria inválida")
				continue
			}
			
			zonePath := filepath.Join("/usr/share/zoneinfo", tz)
			if _, err := os.Stat(zonePath); os.IsNotExist(err) {
				errors = append(errors, "Zona horaria no encontrada")
				continue
			}
			
			// Ejecutar comando
			cmd := exec.Command("sudo", "/usr/local/sbin/hostberry-safe/set-timezone", tz)
			output, err := cmd.CombinedOutput()
			if err != nil {
				combined := strings.TrimSpace(string(output))
				log.Printf("⚠️ Error aplicando timezone: %v, Output: %s", err, combined)
				
				baseMsg := "No se pudo aplicar la zona horaria al sistema"
				if combined != "" {
					// Detectar error de sudo
					if strings.Contains(strings.ToLower(combined), "sudo") && 
					   (strings.Contains(strings.ToLower(combined), "password") || strings.Contains(strings.ToLower(combined), "required")) {
						errors = append(errors, "Permisos insuficientes (sudo requerido)")
					} else {
						errors = append(errors, fmt.Sprintf("%s: %s", baseMsg, combined[:min(len(combined), 200)]))
					}
				} else {
					errors = append(errors, fmt.Sprintf("%s (rc=%v)", baseMsg, err))
				}
			} else {
				log.Printf("✅ Timezone aplicado exitosamente: %s", tz)
			}
		}
		
		updatedKeys = append(updatedKeys, key)
	}

	// Construir respuesta
	response := fiber.Map{
		"message":      "Configuración guardada",
		"updated_keys": updatedKeys,
	}
	
	if len(errors) > 0 {
		response["errors"] = errors
		// Si hubo errores, el mensaje debería reflejarlo parcialmente
		response["message"] = fmt.Sprintf("Configuración guardada con advertencias (Algunos errores: %s)", strings.Join(errors, ", "))
	} else {
		response["message"] = "Configuración actualizada exitosamente"
	}
	
	InsertLog("INFO", fmt.Sprintf("Configuración actualizada por %s: %v", user.Username, updatedKeys), "system", &userID)

	return c.JSON(response)
}

func min(a, b int) int {
	if a < b {
		return a
	}
	return b
}
