package main

import (
	"encoding/json"
	"fmt"
	"html/template"
	"log"
	"os"
	"path/filepath"
	"strings"
)

func main() {
	templateDir := "website/templates"
	files, err := filepath.Glob(filepath.Join(templateDir, "*.html"))
	if err != nil {
		log.Fatal(err)
	}

	if len(files) == 0 {
		log.Fatal("No templates found")
	}

	fmt.Printf("Found %d templates. Testing parsing...\n", len(files))

	funcMap := template.FuncMap{
		"t": func(key string, defaultValue ...string) string { return key },
		"json": func(v interface{}) template.HTML {
			return template.HTML("{}")
		},
		"eq": func(a, b interface{}) bool { return a == b },
		"ne": func(a, b interface{}) bool { return a != b },
		"contains": func(s, substr string) bool { return strings.Contains(s, substr) },
		"Seq": func(start, end int) []int { return []int{} },
	}

	// Test 1: Parse all at once (simulates Fiber)
	tmpl := template.New("").Funcs(funcMap)
	_, err = tmpl.ParseGlob(filepath.Join(templateDir, "*.html"))
	if err != nil {
		fmt.Printf("\n❌ GLOBAL PARSE ERROR:\n%v\n", err)
		
		// Test 2: Parse individually to isolate the culprit
		fmt.Println("\n🔍 Isolating problematic file...")
		for _, file := range files {
			t := template.New(filepath.Base(file)).Funcs(funcMap)
			content, _ := os.ReadFile(file)
			_, err := t.Parse(string(content))
			if err != nil {
				fmt.Printf("❌ ERROR in %s:\n   %v\n", file, err)
			} else {
				fmt.Printf("✅ %s OK\n", filepath.Base(file))
			}
		}
	} else {
		fmt.Println("\n✅ All templates parsed successfully!")
	}
}
