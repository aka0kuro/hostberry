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
// Usa execCommand internamente para manejar sudo automáticamente
func executeCommand(cmd string) (string, error) {
	// Lista blanca de comandos permitidos
	allowedCommands := []string{
		"hostname", "hostnamectl", "uname", "cat", "grep", "awk", "sed", "cut", "head", "tail",
		"top", "free", "df", "nproc",
		"iwlist", "nmcli", "iw",
		"ip", "wg", "wg-quick", "systemctl", "pgrep",
		"sudo", "sh", "reboot", "shutdown", "poweroff",
		"rfkill", "ifconfig", "iwconfig",
	}
	
	// Comandos que NO necesitan sudo (pueden ejecutarse directamente)
	noSudoCommands := []string{
		"hostname", "uname", "cat", "grep", "awk", "sed", "cut", "head", "tail",
		"free", "df", "nproc", "pgrep",
	}
	
	// Validar comando (extraer el comando base, ignorando sudo si está presente)
	parts := strings.Fields(cmd)
	if len(parts) == 0 {
		return "", nil
	}
	
	// Si el primer argumento es "sudo", usar el segundo como comando
	commandIndex := 0
	hasSudo := false
	if len(parts) > 1 && parts[0] == "sudo" {
		commandIndex = 1
		hasSudo = true
	}
	
	if commandIndex >= len(parts) {
		return "", exec.ErrNotFound
	}
	
	command := parts[commandIndex]
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
	
	// Si el comando no necesita sudo y no se especificó sudo, ejecutar directamente
	needsSudo := true
	for _, noSudoCmd := range noSudoCommands {
		if command == noSudoCmd {
			needsSudo = false
			break
		}
	}
	
	// Si el comando no necesita sudo, remover sudo del comando
	if !needsSudo && hasSudo {
		cmd = strings.Join(parts[1:], " ")
	}
	
	// Usar execCommand para manejar sudo automáticamente
	// execCommand remueve "sudo" si está presente y lo agrega si es necesario
	cmdObj := execCommand(cmd)
	
	// Configurar variables de entorno para evitar logs de sudo en sistemas read-only
	cmdObj.Env = append(os.Environ(),
		"SUDO_ASKPASS=/bin/false",
		"SUDO_LOG_FILE=", // Deshabilitar log de sudo
	)
	
	out, err := cmdObj.CombinedOutput()
	outputStr := string(out)
	
	// Filtrar mensajes de error de sudo relacionados con read-only file system
	lines := strings.Split(outputStr, "\n")
	filteredLines := make([]string, 0, len(lines))
	for _, line := range lines {
		line = strings.TrimSpace(line)
		// Ignorar líneas de error de sudo sobre logs
		if strings.Contains(line, "sudo: unable to open log file") ||
			strings.Contains(line, "Read-only file system") ||
			strings.Contains(line, "sudo: unable to stat") {
			continue
		}
		if line != "" {
			filteredLines = append(filteredLines, line)
		}
	}
	
	outputStr = strings.Join(filteredLines, "\n")
	
	// Si hay error pero la salida filtrada tiene contenido válido, usar la salida
	if err != nil && outputStr != "" {
		// Verificar si el error es solo por los mensajes de log de sudo
		errStr := err.Error()
		if strings.Contains(errStr, "exit status") && outputStr != "" {
			// El comando puede haber funcionado pero sudo reportó un error de log
			// Intentar usar la salida si parece válida
			return strings.TrimSpace(outputStr), nil
		}
	}
	
	if err != nil {
		return "", err
	}
	
	return strings.TrimSpace(outputStr), nil
}

// filterSudoErrors filtra mensajes de error de sudo relacionados con read-only file system
func filterSudoErrors(output []byte) string {
	lines := strings.Split(string(output), "\n")
	var cleanLines []string
	for _, line := range lines {
		line = strings.TrimSpace(line)
		if line != "" && 
		   !strings.Contains(line, "sudo: unable to open log file") &&
		   !strings.Contains(line, "Read-only file system") &&
		   !strings.Contains(line, "sudo: unable to stat") {
			cleanLines = append(cleanLines, line)
		}
	}
	return strings.Join(cleanLines, "\n")
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
