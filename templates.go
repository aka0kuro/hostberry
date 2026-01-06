package main

import (
	"encoding/json"
	"html/template"
	"io"
	"io/fs"
	"log"
	"net/http"
	"os"
	"path/filepath"
	"strings"

	"github.com/gofiber/fiber/v2"
	"github.com/gofiber/template/html/v2"
)

// createTemplateEngine crea el motor de templates con funciones personalizadas
func createTemplateEngine() *html.Engine {
	var engine *html.Engine
	
	// Intentar usar templates embebidos primero
	// Crear sub-FS para templates
	tmplFS, err := fs.Sub(templatesFS, "website/templates")
	if err == nil {
		engine = html.NewFileSystem(http.FS(tmplFS), ".html")
		// Listar templates disponibles para debug
		if entries, err := fs.ReadDir(tmplFS, "."); err == nil {
			log.Printf("✅ Templates embebidos encontrados: %d archivos", len(entries))
			for _, entry := range entries {
				log.Printf("   - %s", entry.Name())
			}
		}
	} else {
		log.Printf("⚠️  Error cargando templates embebidos: %v", err)
		// Fallback a sistema de archivos si los embebidos fallan
		if _, err := os.Stat("./website/templates"); err == nil {
			engine = html.New("./website/templates", ".html")
			// Configurar reload solo en desarrollo
			engine.Reload(!appConfig.Server.Debug)
			log.Println("✅ Templates cargados desde sistema de archivos")
		} else {
			// Intentar ruta absoluta desde el ejecutable
			exePath, _ := os.Executable()
			exeDir := filepath.Dir(exePath)
			templatesPath := filepath.Join(exeDir, "website", "templates")
			if _, err := os.Stat(templatesPath); err == nil {
				engine = html.New(templatesPath, ".html")
				log.Printf("✅ Templates cargados desde: %s", templatesPath)
			} else {
				// Intentar ruta de instalación
				installPath := "/opt/hostberry/website/templates"
				if _, err := os.Stat(installPath); err == nil {
					engine = html.New(installPath, ".html")
					log.Printf("✅ Templates cargados desde: %s", installPath)
				} else {
					log.Printf("❌ Error: No se encontraron templates en ninguna ubicación")
					log.Printf("   Intentado: ./website/templates, %s, %s", templatesPath, installPath)
					// Crear engine vacío para evitar crash, pero mostrará errores
					engine = html.New(".", ".html")
				}
			}
		}
	}
	
	// Agregar funciones personalizadas a los templates
	engine.AddFunc("t", func(key string, defaultValue ...string) string {
		// Esta función se sobrescribirá en cada request con el contexto correcto
		if len(defaultValue) > 0 {
			return defaultValue[0]
		}
		return key
	})
	
	engine.AddFunc("json", func(v interface{}) template.HTML {
		b, err := json.Marshal(v)
		if err != nil {
			return template.HTML("{}")
		}
		return template.HTML(b)
	})
	
	engine.AddFunc("eq", func(a, b interface{}) bool {
		return a == b
	})
	
	engine.AddFunc("ne", func(a, b interface{}) bool {
		return a != b
	})
	
	engine.AddFunc("contains", func(s, substr string) bool {
		return strings.Contains(s, substr)
	})
	
	return engine
}

// renderTemplate renderiza un template con datos i18n
func renderTemplate(c *fiber.Ctx, name string, data fiber.Map) error {
	// Obtener idioma actual
	language := GetCurrentLanguage(c)
	
	// Obtener funciones i18n
	i18nFuncs := TemplateFuncs(c)
	
	// Agregar datos base
	if data == nil {
		data = fiber.Map{}
	}
	
	// Agregar funciones i18n al contexto
	data["language"] = language
	data["t"] = i18nFuncs["t"]
	data["common"] = i18nFuncs["common"]
	data["navigation"] = i18nFuncs["navigation"]
	data["dashboard"] = i18nFuncs["dashboard"]
	data["auth"] = i18nFuncs["auth"]
	data["system"] = i18nFuncs["system"]
	data["network"] = i18nFuncs["network"]
	data["wifi"] = i18nFuncs["wifi"]
	data["vpn"] = i18nFuncs["vpn"]
	data["wireguard"] = i18nFuncs["wireguard"]
	data["adblock"] = i18nFuncs["adblock"]
	data["settings"] = i18nFuncs["settings"]
	data["errors"] = i18nFuncs["errors"]
	
	// Convertir traducciones a JSON para JavaScript
	if translations, ok := i18nFuncs["translations"].(map[string]interface{}); ok {
		if translationsJSON, err := json.Marshal(translations); err == nil {
			data["translations"] = translations
			data["translations_json"] = string(translationsJSON)
		}
	}
	
	// Agregar usuario actual si está autenticado
	if user := c.Locals("user"); user != nil {
		data["current_user"] = user
	}
	
	return c.Render(name, data)
}

// copyStaticFiles copia archivos estáticos al directorio de Go
func copyStaticFiles() error {
	sourceDir := "website/static"
	targetDir := "go-backend/website/static"
	
	// Verificar si el directorio fuente existe
	if _, err := os.Stat(sourceDir); os.IsNotExist(err) {
		return nil // No hay archivos estáticos que copiar
	}
	
	// Crear directorio destino
	if err := os.MkdirAll(targetDir, 0755); err != nil {
		return err
	}
	
	// Copiar archivos recursivamente
	return filepath.Walk(sourceDir, func(path string, info os.FileInfo, err error) error {
		if err != nil {
			return err
		}
		
		// Calcular ruta relativa
		relPath, err := filepath.Rel(sourceDir, path)
		if err != nil {
			return err
		}
		
		targetPath := filepath.Join(targetDir, relPath)
		
		if info.IsDir() {
			return os.MkdirAll(targetPath, info.Mode())
		}
		
		// Copiar archivo
		source, err := os.Open(path)
		if err != nil {
			return err
		}
		defer source.Close()
		
		target, err := os.Create(targetPath)
		if err != nil {
			return err
		}
		defer target.Close()
		
		_, err = io.Copy(target, source)
		return err
	})
}
