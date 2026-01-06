package main

import (
	"log"
	"os/exec"
	"strings"
)

// createDefaultAdmin crea un usuario administrador por defecto
func createDefaultAdmin() {
	var count int64
	db.Model(&User{}).Count(&count)
	
	if count == 0 {
		// Crear usuario admin por defecto
		admin, err := Register("admin", "admin", "admin@hostberry.local")
		if err != nil {
			log.Printf("⚠️  Error creando usuario admin: %v", err)
		} else {
			log.Printf("✅ Usuario admin creado: admin/admin")
		}
		_ = admin
	}
}

// executeCommand ejecuta un comando del sistema de forma segura
func executeCommand(cmd string) (string, error) {
	// Lista blanca de comandos permitidos
	allowedCommands := []string{
		"hostname", "uname", "cat", "grep", "awk", "sed",
		"top", "free", "df", "nproc", "iwlist", "nmcli",
	}
	
	// Validar comando
	parts := strings.Fields(cmd)
	if len(parts) == 0 {
		return "", nil
	}
	
	command := parts[0]
	allowed := false
	for _, allowedCmd := range allowedCommands {
		if command == allowedCmd {
			allowed = true
			break
		}
	}
	
	if !allowed {
		return "", nil // Silenciosamente rechazar comandos no permitidos
	}
	
	// Ejecutar comando
	out, err := exec.Command("sh", "-c", cmd).CombinedOutput()
	if err != nil {
		return "", err
	}
	
	return strings.TrimSpace(string(out)), nil
}
