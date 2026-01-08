package main

import (
	"log"
	"os"
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
		"hostname", "uname", "cat", "grep", "awk", "sed", "cut", "head", "tail",
		"top", "free", "df", "nproc",
		"iwlist", "nmcli", "iw",
		"ip", "wg", "wg-quick", "systemctl", "pgrep",
		"sudo", "sh",
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

// canUseSudo verifica si el proceso puede usar sudo o si ya es root
var sudoAvailable *bool // Cache del resultado

func canUseSudo() bool {
	// Si ya tenemos el resultado en cache, usarlo
	if sudoAvailable != nil {
		return *sudoAvailable
	}
	
	result := false
	defer func() {
		sudoAvailable = &result
	}()
	
	// Si ya somos root, no necesitamos sudo
	if os.Geteuid() == 0 {
		return false // No necesitamos sudo, ya somos root
	}
	
	// Verificar si sudo está disponible
	sudoCheck := exec.Command("sh", "-c", "command -v sudo 2>/dev/null")
	if sudoCheck.Run() != nil {
		return false // Sudo no está instalado
	}
	
	// Intentar ejecutar un comando simple con sudo para verificar si funciona
	testCmd := exec.Command("sh", "-c", "sudo -n true 2>&1")
	output, err := testCmd.CombinedOutput()
	outputStr := strings.ToLower(string(output))
	
	// Si el comando funcionó (sin error), sudo está disponible y funciona
	if err == nil {
		result = true
		return true
	}
	
	// Si el error es sobre "no new privileges", no podemos usar sudo
	if strings.Contains(outputStr, "no new privileges") {
		result = false
		return false
	}
	
	// Si el error es sobre contraseña o permisos, sudo está disponible pero puede no funcionar
	// En este caso, asumimos que puede funcionar si está configurado en sudoers
	if strings.Contains(outputStr, "password") || strings.Contains(outputStr, "a password is required") {
		// Sudo está disponible pero necesita contraseña o no tiene permisos NOPASSWD
		// Intentar verificar si tenemos permisos específicos para comandos WiFi
		result = true // Asumimos que puede funcionar si está en sudoers
		return true
	}
	
	return false
}

// execCommand ejecuta un comando, usando sudo solo si es necesario y está disponible
func execCommand(cmd string) *exec.Cmd {
	// Si el comando ya incluye sudo, removerlo y usar nuestra lógica
	originalCmd := cmd
	cmd = strings.TrimSpace(cmd)
	cmd = strings.TrimPrefix(cmd, "sudo ")
	
	// Si ya somos root, ejecutar sin sudo
	if os.Geteuid() == 0 {
		return exec.Command("sh", "-c", cmd)
	}
	
	// Si podemos usar sudo, agregarlo
	if canUseSudo() {
		cmd = "sudo " + cmd
	}
	// Si no podemos usar sudo, intentar ejecutar sin sudo (puede fallar pero lo intentamos)
	
	return exec.Command("sh", "-c", cmd)
}
