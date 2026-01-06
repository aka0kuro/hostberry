#!/usr/bin/env python3
"""Script para convertir templates Jinja2 a Go templates"""
import re
import os
import sys

def convert_template(content):
    """Convierte sintaxis Jinja2 a Go templates"""
    
    # {% extends "base.html" %} -> {{ template "base.html" . }}
    content = re.sub(r'\{%\s*extends\s+"([^"]+)"\s*%\}', r'{{ template "\1" . }}', content)
    
    # {% block name %} -> {{ define "name" }}
    content = re.sub(r'\{%\s*block\s+(\w+)\s*%\}', r'{{ define "\1" }}', content)
    
    # {% endblock %} -> {{ end }}
    content = re.sub(r'\{%\s*endblock\s*%\}', r'{{ end }}', content)
    
    # {{ t('key', 'default') }} -> {{ call .t "key" "default" }}
    content = re.sub(r'\{\{\s*t\([\'"]([^\'"]+)[\'"],\s*[\'"]([^\'"]*)[\'"]\)\s*\}\}', r'{{ call .t "\1" "\2" }}', content)
    
    # {{ variable }} -> {{ .variable }} (solo si no es una llamada a función)
    # Primero proteger las llamadas a funciones
    content = re.sub(r'\{\{\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*\}\}', r'{{ .\1 }}', content)
    
    # {{ item | default('value') }} -> {{ or .item "value" }}
    content = re.sub(r'\{\{\s*([a-zA-Z_][a-zA-Z0-9_.]*)\s*\|\s*default\([\'"]([^\'"]*)[\'"]\)\s*\}\}', r'{{ or .\1 "\2" }}', content)
    
    # {{ item | tojson }} -> {{ .item_json }}
    content = re.sub(r'\{\{\s*([a-zA-Z_][a-zA-Z0-9_.]*)\s*\|\s*tojson\s*\}\}', r'{{ .\1_json }}', content)
    
    # {% if condition %} -> {{ if condition }}
    # Necesita conversión manual de condiciones
    content = re.sub(r'\{%\s*if\s+([^%]+)\s*%\}', lambda m: '{{ if ' + convert_condition(m.group(1)) + ' }}', content)
    
    # {% endif %} -> {{ end }}
    content = re.sub(r'\{%\s*endif\s*%\}', r'{{ end }}', content)
    
    # {% for item in items %} -> {{ range .items }}
    content = re.sub(r'\{%\s*for\s+(\w+)\s+in\s+(\w+)\s*%\}', r'{{ range .\2 }}', content)
    
    # {% endfor %} -> {{ end }}
    content = re.sub(r'\{%\s*endfor\s*%\}', r'{{ end }}', content)
    
    # {% set var = value %} -> Necesita ser manejado en el handler
    # Por ahora lo comentamos
    content = re.sub(r'\{%\s*set\s+([^=]+)=\s*([^%]+)\s*%\}', r'{{/* set \1 = \2 */}}', content)
    
    # {% else %} -> {{ else }}
    content = re.sub(r'\{%\s*else\s*%\}', r'{{ else }}', content)
    
    return content

def convert_condition(cond):
    """Convierte condiciones de Jinja2 a Go"""
    cond = cond.strip()
    
    # == -> eq
    cond = re.sub(r'\s+==\s+', ' eq ', cond)
    # != -> ne
    cond = re.sub(r'\s+!=\s+', ' ne ', cond)
    # and -> &&
    cond = re.sub(r'\s+and\s+', ' && ', cond)
    # or -> ||
    cond = re.sub(r'\s+or\s+', ' || ', cond)
    # not -> !
    cond = re.sub(r'\bnot\s+', '!', cond)
    
    # Variables simples -> .variable
    # Pero no tocar si ya tiene punto
    cond = re.sub(r'\b([a-zA-Z_][a-zA-Z0-9_]*)\b(?!\.)', r'.\1', cond)
    
    return cond

if __name__ == '__main__':
    if len(sys.argv) < 3:
        print("Uso: python3 convert_templates.py <archivo_entrada> <archivo_salida>")
        sys.exit(1)
    
    input_file = sys.argv[1]
    output_file = sys.argv[2]
    
    with open(input_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    converted = convert_template(content)
    
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(converted)
    
    print(f"Convertido: {input_file} -> {output_file}")
