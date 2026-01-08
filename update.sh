#!/bin/bash

# HostBerry - Script de Actualización Rápida
# Este script es un wrapper que llama a install.sh --update
# Verifica actualizaciones en GitHub y crea backup antes de actualizar

set -e

# Colores
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKUP_DIR="${SCRIPT_DIR}/backups"
GITHUB_REPO="https://github.com/aka0kuro/Hostberry.git"

print_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[OK]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Crear backup del proyecto
create_backup() {
    local backup_name="hostberry-backup-$(date +%Y%m%d-%H%M%S)"
    local backup_path="${BACKUP_DIR}/${backup_name}"
    
    print_info "Creando backup del proyecto..."
    
    # Crear directorio de backups si no existe
    mkdir -p "${BACKUP_DIR}"
    
    # Crear backup excluyendo ciertos directorios
    if [ -d "${SCRIPT_DIR}/.git" ]; then
        # Si es un repositorio git, hacer backup de los archivos importantes
        print_info "Creando backup de archivos del proyecto..."
        mkdir -p "${backup_path}"
        
        # Copiar archivos importantes
        local important_files=(
            "*.go"
            "*.sh"
            "*.yaml"
            "*.json"
            "*.lua"
            "*.html"
            "*.js"
            "*.css"
            "*.mod"
            "*.sum"
            "Makefile"
            "go.mod"
            "go.sum"
            "website"
            "lua"
            "locales"
        )
        
        for pattern in "${important_files[@]}"; do
            if ls "${SCRIPT_DIR}/${pattern}" 1> /dev/null 2>&1 || [ -d "${SCRIPT_DIR}/${pattern}" ]; then
                cp -r "${SCRIPT_DIR}/${pattern}" "${backup_path}/" 2>/dev/null || true
            fi
        done
        
        # Guardar el commit actual
        if command -v git &> /dev/null && [ -d "${SCRIPT_DIR}/.git" ]; then
            git rev-parse HEAD > "${backup_path}/.git-commit" 2>/dev/null || true
        fi
    else
        # Si no es git, hacer backup completo
        print_info "Creando backup completo del proyecto..."
        cp -r "${SCRIPT_DIR}" "${backup_path}" 2>/dev/null || {
            print_error "Error al crear backup"
            return 1
        }
    fi
    
    # Comprimir backup
    print_info "Comprimiendo backup..."
    cd "${BACKUP_DIR}"
    tar -czf "${backup_name}.tar.gz" "${backup_name}" 2>/dev/null && {
        rm -rf "${backup_name}"
        print_success "Backup creado: ${backup_name}.tar.gz"
        echo "${backup_path}.tar.gz"
        return 0
    } || {
        print_warning "No se pudo comprimir el backup, pero se guardó en: ${backup_path}"
        echo "${backup_path}"
        return 0
    }
}

# Verificar si hay actualizaciones disponibles
check_for_updates() {
    if ! command -v git &> /dev/null; then
        print_warning "Git no está instalado, no se puede verificar actualizaciones"
        return 2
    fi
    
    if [ ! -d "${SCRIPT_DIR}/.git" ]; then
        print_warning "No es un repositorio git, no se puede verificar actualizaciones"
        return 2
    fi
    
    print_info "Verificando actualizaciones en GitHub..."
    
    # Obtener el remote URL si existe
    local remote_url=$(git -C "${SCRIPT_DIR}" remote get-url origin 2>/dev/null || echo "")
    
    # Si no hay remote configurado, intentar agregarlo
    if [ -z "${remote_url}" ]; then
        print_info "Configurando remote de GitHub..."
        git -C "${SCRIPT_DIR}" remote add origin "${GITHUB_REPO}" 2>/dev/null || {
            git -C "${SCRIPT_DIR}" remote set-url origin "${GITHUB_REPO}" 2>/dev/null || true
        }
    fi
    
    # Obtener información del repositorio remoto
    print_info "Obteniendo información del repositorio remoto..."
    git -C "${SCRIPT_DIR}" fetch origin 2>/dev/null || {
        print_error "No se pudo conectar con GitHub. Verifica tu conexión a internet."
        return 1
    }
    
    # Comparar commits locales con remotos
    local local_commit=$(git -C "${SCRIPT_DIR}" rev-parse HEAD 2>/dev/null)
    local remote_commit=$(git -C "${SCRIPT_DIR}" rev-parse origin/main 2>/dev/null || git -C "${SCRIPT_DIR}" rev-parse origin/master 2>/dev/null)
    
    if [ -z "${remote_commit}" ]; then
        print_warning "No se pudo determinar la rama remota (main/master)"
        return 2
    fi
    
    if [ "${local_commit}" = "${remote_commit}" ]; then
        print_success "Ya tienes la última versión. No hay actualizaciones disponibles."
        return 0
    else
        print_info "Hay actualizaciones disponibles en GitHub"
        print_info "Commit local:  ${local_commit:0:7}"
        print_info "Commit remoto: ${remote_commit:0:7}"
        return 1
    fi
}

# Actualizar desde GitHub
update_from_github() {
    print_info "Actualizando desde GitHub..."
    
    # Guardar cambios locales si existen
    local has_changes=false
    if git -C "${SCRIPT_DIR}" diff --quiet 2>/dev/null && git -C "${SCRIPT_DIR}" diff --cached --quiet 2>/dev/null; then
        has_changes=false
    else
        has_changes=true
        print_warning "Hay cambios locales sin commitear"
        print_info "Guardando cambios locales en stash..."
        git -C "${SCRIPT_DIR}" stash push -m "Auto-stash antes de actualizar $(date +%Y%m%d-%H%M%S)" 2>/dev/null || {
            print_error "No se pudieron guardar los cambios locales. Por favor, haz commit o descarta los cambios antes de actualizar."
            return 1
        }
    fi
    
    # Hacer pull
    if git -C "${SCRIPT_DIR}" pull origin main 2>/dev/null || git -C "${SCRIPT_DIR}" pull origin master 2>/dev/null; then
        print_success "Código actualizado desde GitHub"
        
        # Intentar aplicar cambios guardados si existían
        if [ "${has_changes}" = true ]; then
            print_info "Intentando aplicar cambios locales guardados..."
            git -C "${SCRIPT_DIR}" stash pop 2>/dev/null || {
                print_warning "Hubo conflictos al aplicar cambios locales. Revisa con: git stash list"
            }
        fi
        
        return 0
    else
        print_error "Error al actualizar desde GitHub"
        return 1
    fi
}

# Limpiar backups antiguos (mantener solo los últimos 5)
cleanup_old_backups() {
    if [ -d "${BACKUP_DIR}" ]; then
        print_info "Limpiando backups antiguos (manteniendo los últimos 5)..."
        cd "${BACKUP_DIR}"
        ls -t *.tar.gz 2>/dev/null | tail -n +6 | xargs rm -f 2>/dev/null || true
        ls -t */ 2>/dev/null | tail -n +6 | xargs rm -rf 2>/dev/null || true
    fi
}

main() {
    print_info "Iniciando actualización de HostBerry..."
    
    cd "${SCRIPT_DIR}"
    
    # Verificar si es un repositorio git
    if [ -d ".git" ]; then
        # Verificar actualizaciones
        check_for_updates
        local update_status=$?
        
        if [ ${update_status} -eq 0 ]; then
            # No hay actualizaciones
            print_info "No es necesario actualizar. Ejecutando instalador para verificar dependencias..."
        elif [ ${update_status} -eq 1 ]; then
            # Hay actualizaciones disponibles
            print_info "Se encontraron actualizaciones disponibles"
            
            # Crear backup antes de actualizar
            local backup_path=$(create_backup)
            if [ -z "${backup_path}" ]; then
                print_error "No se pudo crear el backup. Abortando actualización por seguridad."
                exit 1
            fi
            
            # Actualizar desde GitHub
            if ! update_from_github; then
                print_error "Error al actualizar. El backup está disponible en: ${backup_path}"
                print_info "Para restaurar: tar -xzf ${backup_path} -C ${SCRIPT_DIR}"
                exit 1
            fi
            
            # Limpiar backups antiguos
            cleanup_old_backups
        else
            # No se pudo verificar (git no instalado o no es repo git)
            print_warning "No se pudo verificar actualizaciones, pero continuando..."
        fi
    else
        print_warning "No es un repositorio git. No se puede actualizar desde GitHub."
        print_info "Para habilitar actualizaciones desde GitHub, inicializa git:"
        print_info "  git init"
        print_info "  git remote add origin ${GITHUB_REPO}"
        print_info "  git fetch origin"
        print_info "  git reset --hard origin/main"
    fi
    
    # Ejecutar el instalador en modo actualización
    # El instalador preservará automáticamente la base de datos
    if [ -f "${SCRIPT_DIR}/install.sh" ]; then
        print_info "Ejecutando instalador en modo actualización..."
        print_info "La base de datos será preservada automáticamente"
        exec "${SCRIPT_DIR}/install.sh" --update
    else
        print_error "install.sh no encontrado en ${SCRIPT_DIR}"
        exit 1
    fi
}

main "$@"
