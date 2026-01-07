package main

import "testing"

// Este test asegura que todos los templates (FS o embebidos) se pueden cargar/parsear
// con las funciones registradas. Evita regresiones tipo: "function \"json\" not defined".
func TestTemplatesLoad(t *testing.T) {
	// Config mínima requerida por createTemplateEngine()
	appConfig = Config{
		Server: ServerConfig{Debug: false},
	}

	engine := createTemplateEngine()
	if engine == nil {
		t.Fatal("engine de templates es nil")
	}

	// Re-cargar para forzar parseo completo (si hay algo roto, falla aquí).
	if err := engine.Load(); err != nil {
		t.Fatalf("error cargando/parsing templates: %v", err)
	}
}

