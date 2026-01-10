package main

import (
	"log"
	"os"
	"os/exec"
	"strings"
)

// getAdBlockStatus obtiene el estado de AdBlock (reemplaza adblock_status.lua)
func getAdBlockStatus() map[string]interface{} {
	result := make(map[string]interface{})

	// Verificar dnsmasq
	dnsmasqCmd := exec.Command("sh", "-c", "systemctl is-active dnsmasq 2>/dev/null || echo inactive")
	dnsmasqOut, _ := dnsmasqCmd.Output()
	dnsmasqStatus := strings.TrimSpace(string(dnsmasqOut))
	if dnsmasqStatus == "" {
		dnsmasqStatus = "inactive"
	}

	// Verificar pihole
	piholeCmd := exec.Command("sh", "-c", "systemctl is-active pihole-FTL 2>/dev/null || echo inactive")
	piholeOut, _ := piholeCmd.Output()
	piholeStatus := strings.TrimSpace(string(piholeOut))
	if piholeStatus == "" {
		piholeStatus = "inactive"
	}

	result["active"] = dnsmasqStatus == "active" || piholeStatus == "active"
	result["type"] = "none"

	if dnsmasqStatus == "active" {
		result["type"] = "dnsmasq"
	} else if piholeStatus == "active" {
		result["type"] = "pihole"
	}

	// Verificar si hay listas de bloqueo configuradas
	if result["active"] == true {
		if hostsContent, err := os.ReadFile("/etc/hosts"); err == nil {
			blockedCount := strings.Count(string(hostsContent), "0.0.0.0")
			result["blocked_domains"] = blockedCount
		} else {
			result["blocked_domains"] = 0
		}
	} else {
		result["blocked_domains"] = 0
	}

	result["success"] = true
	return result
}

// enableAdBlock habilita AdBlock (reemplaza adblock_enable.lua)
func enableAdBlock(user string) map[string]interface{} {
	result := make(map[string]interface{})

	if user == "" {
		user = "unknown"
	}

	log.Printf("Habilitando AdBlock (usuario: %s)", user)

	// Intentar iniciar dnsmasq
	dnsmasqCmd := "sudo systemctl start dnsmasq"
	if _, err := executeCommand(dnsmasqCmd); err != nil {
		// Intentar con pihole
		piholeCmd := "sudo systemctl start pihole-FTL"
		if out2, err2 := executeCommand(piholeCmd); err2 != nil {
			result["success"] = false
			result["error"] = err2.Error()
			if out2 != "" {
				result["error"] = strings.TrimSpace(out2)
			}
			result["message"] = "Error iniciando servicio AdBlock"
			log.Printf("ERROR: Error habilitando AdBlock: %v", err2)
			return result
		}
	}

	result["success"] = true
	result["message"] = "AdBlock habilitado"
	log.Printf("INFO: AdBlock habilitado exitosamente")
	return result
}

// disableAdBlock deshabilita AdBlock (reemplaza adblock_disable.lua)
func disableAdBlock(user string) map[string]interface{} {
	result := make(map[string]interface{})

	if user == "" {
		user = "unknown"
	}

	log.Printf("Deshabilitando AdBlock (usuario: %s)", user)

	// Detener dnsmasq
	executeCommand("sudo systemctl stop dnsmasq")

	// Detener pihole si está activo
	executeCommand("sudo systemctl stop pihole-FTL")

	result["success"] = true
	result["message"] = "AdBlock deshabilitado"
	log.Printf("INFO: AdBlock deshabilitado exitosamente")
	return result
}
