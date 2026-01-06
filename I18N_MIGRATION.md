# Migración de i18n y Templates

## Sistema de i18n Migrado

### Archivos Creados
- `i18n.go` - Sistema completo de internacionalización
- `templates.go` - Helper para renderizado de templates
- `go-backend/locales/` - Archivos JSON de traducciones (copiados)

### Características

1. **Detección automática de idioma**:
   - Query parameter `?lang=es`
   - Cookie `lang`
   - Header `Accept-Language`
   - Fallback a español por defecto

2. **Funciones en templates**:
   - `{{ call .t "key" "default" }}` - Obtener traducción
   - `{{ .language }}` - Idioma actual
   - `{{ .common }}`, `{{ .navigation }}`, etc. - Secciones de traducciones

3. **Soporte para JavaScript**:
   - Variable `translations_json` con todas las traducciones
   - Compatible con el código JavaScript existente

## Templates Migrados

### Sintaxis Jinja2 → Go Templates

| Jinja2 | Go Templates |
|--------|--------------|
| `{{ variable }}` | `{{ .variable }}` |
| `{% block name %}` | `{{ define "name" }}` |
| `{% extends "base.html" %}` | `{{ template "base.html" . }}` |
| `{% if condition %}` | `{{ if .condition }}` |
| `{{ 'ES' if lang == 'es' else 'EN' }}` | `{{ if eq .lang "es" }}ES{{ else }}EN{{ end }}` |
| `{{ t('key', 'default') }}` | `{{ call .t "key" "default" }}` |

### Templates Creados

1. **base.html** - Template base con navbar, selector de idioma, etc.
2. **login.html** - Página de login
3. **dashboard.html** - Dashboard principal

### Ejemplo de Uso

```go
// En handler
func dashboardHandler(c *fiber.Ctx) error {
    return renderTemplate(c, "dashboard", fiber.Map{
        "Title": T(c, "dashboard.title", "Dashboard"),
    })
}
```

```html
<!-- En template -->
<h1>{{ call .t "dashboard.title" "Dashboard" }}</h1>
<p>{{ call .t "dashboard.subtitle" "Control Panel" }}</p>
```

## Próximos Pasos

1. **Migrar más templates**:
   - settings.html
   - network.html
   - wifi.html
   - vpn.html
   - wireguard.html
   - adblock.html

2. **Optimizar**:
   - Cache de traducciones
   - Lazy loading de templates
   - Minificación de HTML

3. **Testing**:
   - Probar cambio de idioma
   - Verificar todas las traducciones
   - Validar JavaScript con traducciones

## Compatibilidad

- ✅ Mismos archivos JSON de traducciones
- ✅ Misma estructura de claves
- ✅ Compatible con JavaScript existente
- ✅ Mismo comportamiento de detección de idioma
