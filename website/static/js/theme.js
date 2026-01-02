/**
 * HostBerry - Gestión de Tema Oscuro
 * Maneja el cambio entre tema claro y oscuro
 */

// Función para cambiar el tema
function toggleTheme() {
    const body = document.body;
    const isDark = body.classList.contains('dark-theme');
    
    if (isDark) {
        body.classList.remove('dark-theme');
        localStorage.setItem('theme', 'light');
        updateThemeIcon('light');
    } else {
        body.classList.add('dark-theme');
        localStorage.setItem('theme', 'dark');
        updateThemeIcon('dark');
    }
}

// Función para actualizar el icono del tema
function updateThemeIcon(theme) {
    const themeToggle = document.getElementById('theme-toggle');
    if (themeToggle) {
        if (theme === 'dark') {
            themeToggle.textContent = '☀️';
            themeToggle.title = 'Cambiar a tema claro';
            themeToggle.classList.remove('light');
            themeToggle.classList.add('dark');
        } else {
            themeToggle.textContent = '🌙';
            themeToggle.title = 'Cambiar a tema oscuro';
            themeToggle.classList.remove('dark');
            themeToggle.classList.add('light');
        }
    }
}

// Función para cargar el tema guardado
function loadTheme() {
    const savedTheme = localStorage.getItem('theme');
    const body = document.body;
    
    if (savedTheme === 'dark' || (!savedTheme && window.matchMedia('(prefers-color-scheme: dark)').matches)) {
        body.classList.remove('light-theme');
        body.classList.add('dark-theme');
        updateThemeIcon('dark');
    } else {
        body.classList.remove('dark-theme');
        body.classList.add('light-theme');
        updateThemeIcon('light');
    }
}

// Función para detectar preferencia del sistema
function detectSystemTheme() {
    const mediaQuery = window.matchMedia('(prefers-color-scheme: dark)');
    
    mediaQuery.addEventListener('change', (e) => {
        if (!localStorage.getItem('theme')) {
            if (e.matches) {
                document.body.classList.remove('light-theme');
                document.body.classList.add('dark-theme');
                updateThemeIcon('dark');
            } else {
                document.body.classList.remove('dark-theme');
                document.body.classList.add('light-theme');
                updateThemeIcon('light');
            }
        }
    });
}

// Función para inicializar el sistema de temas
function initTheme() {
    loadTheme();
    detectSystemTheme();
}

// Función para obtener el tema actual
function getCurrentTheme() {
    return document.body.classList.contains('dark-theme') ? 'dark' : 'light';
}

// Función para aplicar tema específico
function setTheme(theme) {
    const body = document.body;
    
    if (theme === 'dark') {
        body.classList.add('dark-theme');
        localStorage.setItem('theme', 'dark');
        updateThemeIcon('dark');
    } else {
        body.classList.remove('dark-theme');
        localStorage.setItem('theme', 'light');
        updateThemeIcon('light');
    }
}

// Función para obtener estadísticas del tema
function getThemeStats() {
    const theme = getCurrentTheme();
    const savedTheme = localStorage.getItem('theme');
    const systemPrefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
    
    return {
        current: theme,
        saved: savedTheme,
        systemPrefersDark: systemPrefersDark,
        isAuto: !savedTheme
    };
}

// Inicializar cuando el DOM esté listo
document.addEventListener('DOMContentLoaded', function() {
    initTheme();
});

// Exportar funciones para uso global
window.ThemeManager = {
    toggleTheme,
    loadTheme,
    setTheme,
    getCurrentTheme,
    getThemeStats,
    initTheme
}; 