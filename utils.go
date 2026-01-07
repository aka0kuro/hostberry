package main

import (
	"log"
	"os/exec"
	"strings"
)

// createDefaultAdmin crea un usuario administrador por defecto
func createDefaultAdmin() {
	var count int64
	if err := db.Model(&User{}).Count(&count).Error; err != nil {
		log.Printf("⚠️  Error contando usuarios: %v", err)
		return
	}
	
	log.Printf("📊 Usuarios en BD: %d", count)
	
	if count == 0 {
		log.Println("🔧 Creando usuario admin por defecto...")
		// Crear usuario admin por defecto
		admin, err := Register("admin", "admin", "admin@hostberry.local")
		if err != nil {
			log.Printf("❌ Error creando usuario admin: %v", err)
			log.Printf("⚠️  Intenta crear el usuario manualmente o elimina la BD y reinicia")
		} else {
			log.Printf("✅ Usuario admin creado exitosamente")
			log.Printf("   Usuario: admin")
			log.Printf("   Contraseña: admin")
			log.Printf("   Email: admin@hostberry.local")
			log.Printf("⚠️  IMPORTANTE: Cambia la contraseña después del primer inicio")
			_ = admin
		}
	} else {
		log.Printf("ℹ️  Ya existen %d usuarios en la BD, no se crea admin por defecto", count)
	}
}

// executeCommand ejecuta un comando del sistema de forma segura
func executeCommand(cmd string) (string, error) {
	// Lista blanca de comandos permitidos
	allowedCommands := []string{
		"hostname", "uname", "cat", "grep", "awk", "sed", "cut", "head",
		"top", "free", "df", "nproc",
		"iwlist", "nmcli",
		"ip", "wg", "wg-quick", "systemctl", "pgrep",
		"sudo",
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
		return "", exec.ErrNotFound // Devolver error para que Lua/handlers lo reporten
	}
	
	// Ejecutar comando
	out, err := exec.Command("sh", "-c", cmd).CombinedOutput()
	if err != nil {
		return "", err
	}
	
	return strings.TrimSpace(string(out)), nil
}
