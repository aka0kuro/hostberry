package main

import (
	"encoding/json"
	"fmt"
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
	
	// PRIORIDAD: Templates embebidos (MÁS RÁPIDOS - en memoria)
	// Intentar usar templates embebidos primero para mejor rendimiento
	tmplFS, err := fs.Sub(templatesFS, "website/templates")
	if err == nil {
		// Verificar que hay templates embebidos
		if entries, err := fs.ReadDir(tmplFS, "."); err == nil {
			htmlFiles := 0
			var templateNames []string
			for _, entry := range entries {
				if !entry.IsDir() && strings.HasSuffix(entry.Name(), ".html") {
					htmlFiles++
					if len(templateNames) < 5 {
						templateNames = append(templateNames, entry.Name())
					}
				}
			}
			if htmlFiles > 0 {
				engine = html.NewFileSystem(http.FS(tmplFS), ".html")
				if engine != nil {
					// Configurar reload (deshabilitado para embebidos)
					engine.Reload(false)
					log.Printf("✅ Templates embebidos cargados (MÁS RÁPIDO): %d archivos .html", htmlFiles)
					log.Printf("   Templates encontrados: %v", templateNames)
					// Verificar que dashboard.html está disponible
					if testFile, err := tmplFS.Open("dashboard.html"); err == nil {
						testFile.Close()
						log.Printf("   ✅ dashboard.html verificado en FS embebido")
					} else {
						log.Printf("   ⚠️  No se pudo abrir dashboard.html: %v", err)
					}
					// Continuar para añadir funciones personalizadas
				} else {
					log.Printf("⚠️  Error: engine es nil después de NewFileSystem con embebidos")
					err = fmt.Errorf("engine es nil")
				}
			} else {
				log.Printf("⚠️  Templates embebidos vacíos, usando fallback")
				err = fmt.Errorf("templates embebidos vacíos")
			}
		} else {
			log.Printf("⚠️  Error leyendo directorio embebido: %v", err)
		}
	} else {
		log.Printf("⚠️  Error creando sub-FS de templates embebidos: %v", err)
		log.Printf("   Intentando acceder directamente al FS...")
		// Intentar acceder directamente sin sub-FS
		if entries, err := fs.ReadDir(templatesFS, "website/templates"); err == nil {
			htmlFiles := 0
			for _, entry := range entries {
				if !entry.IsDir() && strings.HasSuffix(entry.Name(), ".html") {
					htmlFiles++
				}
			}
			if htmlFiles > 0 {
				log.Printf("✅ Templates encontrados directamente en website/templates: %d archivos", htmlFiles)
				// Crear sub-FS desde website/templates
				if tmplFS2, err2 := fs.Sub(templatesFS, "website/templates"); err2 == nil {
					engine = html.NewFileSystem(http.FS(tmplFS2), ".html")
					if engine != nil {
						log.Printf("✅ Motor de templates configurado usando sub-FS directo")
					}
				}
			}
		}
	}
	
	// FALLBACK: Sistema de archivos (más lento pero más flexible)
	// Solo usar si los embebidos no están disponibles
	if engine == nil {
		log.Println("⚠️  Usando templates desde sistema de archivos (más lento pero flexible)")
		paths := []string{
			"/opt/hostberry/website/templates",  // Ruta de instalación estándar
		}
		
		// Añadir ruta del ejecutable si es diferente
		exePath, _ := os.Executable()
		if exePath != "" {
			exeDir := filepath.Dir(exePath)
			templatesPath := filepath.Join(exeDir, "website", "templates")
			// Solo añadir si es diferente a /opt/hostberry
			if templatesPath != "/opt/hostberry/website/templates" {
				paths = append(paths, templatesPath)
			}
		}
		
		// Añadir ruta relativa al final (menos confiable)
		paths = append(paths, "./website/templates")
		
		for _, path := range paths {
			if stat, err := os.Stat(path); err == nil {
				if stat.IsDir() {
					// Verificar que hay archivos .html en el directorio
					if entries, err := os.ReadDir(path); err == nil {
						htmlFiles := 0
						for _, entry := range entries {
							if !entry.IsDir() && strings.HasSuffix(entry.Name(), ".html") {
								htmlFiles++
							}
						}
						if htmlFiles > 0 {
							engine = html.New(path, ".html")
							if engine == nil {
								log.Printf("❌ Error: engine es nil después de html.New para %s", path)
								continue
							}
							engine.Reload(!appConfig.Server.Debug)
							log.Printf("✅ Templates cargados desde sistema de archivos: %s (%d archivos .html)", path, htmlFiles)
							// Listar algunos archivos para verificación
							if htmlFiles <= 5 {
								for _, entry := range entries {
									if !entry.IsDir() && strings.HasSuffix(entry.Name(), ".html") {
										log.Printf("   - %s", entry.Name())
									}
								}
							}
							break // Salir del loop, engine encontrado
						} else {
							log.Printf("⚠️  Directorio %s existe pero no contiene archivos .html", path)
						}
					}
				}
			}
		}
	}
	
	// Verificar que engine no es nil antes de agregar funciones
	if engine == nil {
		log.Fatal("❌ Error crítico: engine es nil después de todos los intentos de carga")
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
	
	// Intentar renderizar el template
	// Fiber busca el template por nombre sin extensión cuando usas .html como extensión
	templateName := name
	if !strings.HasSuffix(templateName, ".html") {
		templateName = name + ".html"
	}
	
	if err := c.Render(templateName, data); err != nil {
		log.Printf("❌ Error renderizando template '%s' (intentado: '%s'): %v", name, templateName, err)
		// Intentar sin extensión
		if strings.HasSuffix(templateName, ".html") {
			if err2 := c.Render(strings.TrimSuffix(templateName, ".html"), data); err2 == nil {
				return nil
			}
		}
		// Log detallado del error
		log.Printf("   Detalles del error: %+v", err)
		return err
	}
	return nil
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
