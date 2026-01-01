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
            themeToggle.innerHTML = '<i class="bi bi-sun"></i>';
            themeToggle.title = 'Cambiar a tema claro';
        } else {
            themeToggle.innerHTML = '<i class="bi bi-moon"></i>';
            themeToggle.title = 'Cambiar a tema oscuro';
        }
    }
}

// Función para cargar el tema guardado
function loadTheme() {
    const savedTheme = localStorage.getItem('theme');
    const body = document.body;
    
    if (savedTheme === 'dark' || (!savedTheme && window.matchMedia('(prefers-color-scheme: dark)').matches)) {
        body.classList.add('dark-theme');
        updateThemeIcon('dark');
    } else {
        body.classList.remove('dark-theme');
        updateThemeIcon('light');
    }
}

// Función para detectar preferencia del sistema
function detectSystemTheme() {
    const mediaQuery = window.matchMedia('(prefers-color-scheme: dark)');
    
    mediaQuery.addEventListener('change', (e) => {
        if (!localStorage.getItem('theme')) {
            if (e.matches) {
                document.body.classList.add('dark-theme');
                updateThemeIcon('dark');
            } else {
                document.body.classList.remove('dark-theme');
                updateThemeIcon('light');
            }
        }
    });
}

// Función para inicializar el sistema de temas
function initTheme() {
    loadTheme();
    detectSystemTheme();
    
    // Agregar botón de cambio de tema al navbar si no existe
    const navbarNav = document.querySelector('.navbar-nav');
    if (navbarNav && !document.getElementById('theme-toggle')) {
        const themeToggle = document.createElement('li');
        themeToggle.className = 'nav-item';
        themeToggle.innerHTML = `
            <button class="nav-link btn btn-link" id="theme-toggle" onclick="toggleTheme()" title="Cambiar tema">
                <i class="bi bi-moon"></i>
            </button>
        `;
        navbarNav.appendChild(themeToggle);
        updateThemeIcon(localStorage.getItem('theme') || 'light');
    }
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