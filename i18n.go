package main

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"strings"
	"sync"

	"github.com/gofiber/fiber/v2"
)

// I18nManager gestiona las traducciones
type I18nManager struct {
	translations     map[string]map[string]interface{}
	defaultLanguage  string
	supportedLanguages []string
	mu               sync.RWMutex
}

var i18nManager *I18nManager

// InitI18n inicializa el sistema de i18n
func InitI18n(localesPath string) error {
	i18nManager = &I18nManager{
		translations:      make(map[string]map[string]interface{}),
		defaultLanguage:   "es",
		supportedLanguages: []string{"es", "en"},
	}

	// Intentar múltiples rutas
	paths := []string{
		localesPath,
		"locales",
		"/opt/hostberry/locales",
		filepath.Join(filepath.Dir(os.Args[0]), "locales"),
	}

	var foundPath string
	for _, path := range paths {
		if _, err := os.Stat(path); err == nil {
			foundPath = path
			break
		}
	}

	if foundPath == "" {
		return fmt.Errorf("directorio de locales no encontrado")
	}

	// Cargar traducciones
	for _, lang := range i18nManager.supportedLanguages {
		langFile := filepath.Join(foundPath, lang+".json")
		if err := i18nManager.loadLanguage(lang, langFile); err != nil {
			fmt.Printf("⚠️  Advertencia: No se pudo cargar %s: %v\n", langFile, err)
		}
	}

	return nil
}

// loadLanguage carga las traducciones de un idioma
func (i *I18nManager) loadLanguage(lang, filePath string) error {
	data, err := os.ReadFile(filePath)
	if err != nil {
		return err
	}

	var translations map[string]interface{}
	if err := json.Unmarshal(data, &translations); err != nil {
		return err
	}

	i.mu.Lock()
	i.translations[lang] = translations
	i.mu.Unlock()

	return nil
}

// GetText obtiene una traducción por clave
func (i *I18nManager) GetText(key, language string, defaultValue string) string {
	if language == "" {
		language = i.defaultLanguage
	}

	i.mu.RLock()
	defer i.mu.RUnlock()

	// Obtener traducciones del idioma
	langTranslations, ok := i.translations[language]
	if !ok {
		langTranslations = i.translations[i.defaultLanguage]
	}

	// Buscar clave anidada (ej: "common.save")
	value := i.getNestedValue(langTranslations, key)
	if value != "" {
		return value
	}

	// Fallback a idioma por defecto si no se encuentra
	if language != i.defaultLanguage {
		defaultTranslations := i.translations[i.defaultLanguage]
		value = i.getNestedValue(defaultTranslations, key)
		if value != "" {
			return value
		}
	}

	// Si no se encuentra, usar valor por defecto o la clave
	if defaultValue != "" {
		return defaultValue
	}
	return key
}

// getNestedValue obtiene un valor anidado de un mapa
func (i *I18nManager) getNestedValue(data map[string]interface{}, key string) string {
	keys := strings.Split(key, ".")
	current := data

	for i, k := range keys {
		if val, ok := current[k]; ok {
			if i == len(keys)-1 {
				// Última clave, retornar string
				if str, ok := val.(string); ok {
					return str
				}
				return ""
			}
			// Continuar navegando
			if nested, ok := val.(map[string]interface{}); ok {
				current = nested
			} else {
				return ""
			}
		} else {
			return ""
		}
	}

	return ""
}

// GetTranslations obtiene todas las traducciones de un idioma
func (i *I18nManager) GetTranslations(language string) map[string]interface{} {
	if language == "" {
		language = i.defaultLanguage
	}

	i.mu.RLock()
	defer i.mu.RUnlock()

	translations, ok := i.translations[language]
	if !ok {
		translations = i.translations[i.defaultLanguage]
	}

	return translations
}

// GetCurrentLanguage obtiene el idioma actual del contexto
func GetCurrentLanguage(c *fiber.Ctx) string {
	// Intentar obtener del query parameter
	if lang := c.Query("lang"); lang != "" {
		if isLanguageSupported(lang) {
			return lang
		}
	}

	// Intentar obtener de cookie
	if lang := c.Cookies("lang"); lang != "" {
		if isLanguageSupported(lang) {
			return lang
		}
	}

	// Intentar obtener del header Accept-Language
	acceptLang := c.Get("Accept-Language", "")
	if acceptLang != "" {
		// Parsear Accept-Language (formato: "es,en;q=0.9")
		langs := strings.Split(acceptLang, ",")
		if len(langs) > 0 {
			lang := strings.TrimSpace(strings.Split(langs[0], ";")[0])
			if len(lang) >= 2 {
				lang = lang[:2]
				if isLanguageSupported(lang) {
					return lang
				}
			}
		}
	}

	// Usar idioma por defecto
	return i18nManager.defaultLanguage
}

// isLanguageSupported verifica si un idioma está soportado
func isLanguageSupported(lang string) bool {
	for _, supported := range i18nManager.supportedLanguages {
		if lang == supported {
			return true
		}
	}
	return false
}

// T es un helper para obtener traducciones en templates
func T(c *fiber.Ctx, key string, defaultValue string) string {
	language := GetCurrentLanguage(c)
	return i18nManager.GetText(key, language, defaultValue)
}

// TemplateFuncs retorna funciones para usar en templates
func TemplateFuncs(c *fiber.Ctx) fiber.Map {
	language := GetCurrentLanguage(c)
	translations := i18nManager.GetTranslations(language)

	return fiber.Map{
		"t": func(key string, defaultValue ...string) string {
			def := ""
			if len(defaultValue) > 0 {
				def = defaultValue[0]
			}
			return i18nManager.GetText(key, language, def)
		},
		"language": language,
		"translations": translations,
		"common": getSection(translations, "common"),
		"navigation": getSection(translations, "navigation"),
		"dashboard": getSection(translations, "dashboard"),
		"auth": getSection(translations, "auth"),
		"system": getSection(translations, "system"),
		"network": getSection(translations, "network"),
		"wifi": getSection(translations, "wifi"),
		"vpn": getSection(translations, "vpn"),
		"wireguard": getSection(translations, "wireguard"),
		"adblock": getSection(translations, "adblock"),
		"settings": getSection(translations, "settings"),
		"errors": getSection(translations, "errors"),
	}
}

// getSection obtiene una sección específica de las traducciones
func getSection(translations map[string]interface{}, section string) map[string]interface{} {
	if val, ok := translations[section]; ok {
		if sectionMap, ok := val.(map[string]interface{}); ok {
			return sectionMap
		}
	}
	return make(map[string]interface{})
}

// LanguageMiddleware middleware para detectar y establecer idioma
func LanguageMiddleware(c *fiber.Ctx) error {
	language := GetCurrentLanguage(c)
	c.Locals("language", language)
	c.Locals("i18n", TemplateFuncs(c))
	return c.Next()
}
