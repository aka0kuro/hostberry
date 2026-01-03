// Dashboard JavaScript - Funcionalidades interactivas

// Actualizar tiempo en tiempo real
function updateCurrentTime() {
    const now = new Date();
    const timeString = now.toLocaleTimeString('es-ES', { 
        hour12: false,
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit'
    });
    const timeElement = document.getElementById('currentTime');
    if (timeElement) {
        timeElement.textContent = timeString;
    }
}

// Inicializar actualización de tiempo
setInterval(updateCurrentTime, 1000);
updateCurrentTime();

// Actualizar datos del sistema
async function updateSystemStats() {
    try {
        const response = await fetch('/api/v1/system/stats');
        if (response.ok) {
            const stats = await response.json();
            
            // Actualizar CPU
            updateStatCard('cpu', stats.cpu_usage);
            
            // Actualizar Memoria
            updateStatCard('memory', stats.memory_usage);
            
            // Actualizar Disco
            updateStatCard('disk', stats.disk_usage);
            
            // Actualizar Temperatura
            updateStatCard('temp', stats.cpu_temperature);
        }
    } catch (error) {
        console.error('Error updating system stats:', error);
    }
}

// Actualizar tarjeta de estadísticas
function updateStatCard(type, value) {
    const card = document.querySelector(`.${type}-card`);
    if (!card) return;
    
    const valueElement = card.querySelector('.status-info h3');
    const progressBar = card.querySelector(`.${type}-progress`);
    
    if (valueElement) {
        if (type === 'temp') {
            valueElement.textContent = `${value}°C`;
            // Para temperatura, calcular porcentaje basado en 100°C como máximo
            const tempPercent = Math.min((value / 100) * 100, 100);
            if (progressBar) {
                progressBar.style.width = `${tempPercent}%`;
            }
        } else {
            valueElement.textContent = `${value}%`;
            if (progressBar) {
                progressBar.style.width = `${value}%`;
            }
        }
    }
    
    // Actualizar estado de salud
    updateHealthStatus(type, value);
}

// Actualizar estado de salud
function updateHealthStatus(type, value) {
    const card = document.querySelector(`.${type}-card`);
    if (!card) return;
    
    const statusText = card.querySelector('.status-text');
    if (!statusText) return;
    
    let status = 'system.healthy';
    let statusClass = 'status-healthy';
    
    // Umbrales para cada tipo
    const thresholds = {
        cpu: { warning: 70, critical: 90 },
        memory: { warning: 75, critical: 90 },
        disk: { warning: 80, critical: 95 },
        temp: { warning: 60, critical: 80 }
    };
    
    const threshold = thresholds[type];
    if (value >= threshold.critical) {
        status = 'system.critical';
        statusClass = 'status-critical';
    } else if (value >= threshold.warning) {
        status = 'system.warning';
        statusClass = 'status-warning';
    }
    
    // Actualizar texto (usar traducciones si están disponibles)
    const statusTexts = {
        'system.healthy': 'Saludable',
        'system.warning': 'Advertencia',
        'system.critical': 'Crítico'
    };
    
    statusText.textContent = statusTexts[status] || status;
    statusText.className = `status-text ${statusClass}`;
}

// Actualizar servicios
async function updateServices() {
    try {
        const response = await fetch('/api/v1/system/services');
        if (response.ok) {
            const data = await response.json();
            const services = data.services;
            
            Object.keys(services).forEach(serviceName => {
                updateServiceStatus(serviceName, services[serviceName].status);
            });
        }
    } catch (error) {
        console.error('Error updating services:', error);
    }
}

// Actualizar estado de un servicio
function updateServiceStatus(serviceName, status) {
    const serviceItems = document.querySelectorAll('.service-item');
    
    serviceItems.forEach(item => {
        const serviceNameElement = item.querySelector('.service-name');
        if (serviceNameElement && serviceNameElement.textContent.toLowerCase().includes(serviceName.toLowerCase())) {
            const statusBadge = item.querySelector('.status-badge');
            if (statusBadge) {
                if (status === 'running') {
                    statusBadge.className = 'status-badge status-running';
                    statusBadge.textContent = 'Activo';
                } else {
                    statusBadge.className = 'status-badge status-stopped';
                    statusBadge.textContent = 'Detenido';
                }
            }
        }
    });
}

// Actualizar estado de red
async function updateNetworkStatus() {
    try {
        const response = await fetch('/api/v1/system/network/status');
        if (response.ok) {
            const data = await response.json();
            const networkData = data.interfaces;
            
            // Actualizar interfaces de red
            updateNetworkInterface('eth0', networkData.eth0);
            updateNetworkInterface('wlan0', networkData.wlan0);
        }
    } catch (error) {
        console.error('Error updating network status:', error);
    }
}

// Actualizar interfaz de red
function updateNetworkInterface(interfaceName, data) {
    const interfaces = document.querySelectorAll('.network-interface');
    
    interfaces.forEach(interface => {
        const interfaceHeader = interface.querySelector('.interface-header h6');
        if (interfaceHeader && interfaceHeader.textContent === interfaceName) {
            const statusElement = interface.querySelector('.interface-status');
            const details = interface.querySelectorAll('.network-item');
            
            if (statusElement) {
                statusElement.textContent = data.connected ? 'Conectado' : 'Desconectado';
            }
            
            // Actualizar detalles si están disponibles
            if (data.ip_address && details[0]) {
                details[0].querySelector('.network-value').textContent = data.ip_address;
            }
            if (data.gateway && details[1]) {
                details[1].querySelector('.network-value').textContent = data.gateway;
            }
            if (data.ssid && details[2]) {
                details[2].querySelector('.network-value').textContent = data.ssid;
            }
            if (data.signal_strength && details[2]) {
                details[2].querySelector('.network-value').textContent = `${data.signal_strength}%`;
            }
        }
    });
}

// Actualizar logs
async function updateLogs() {
    try {
        const levelSelect = document.getElementById('logLevel');
        const level = levelSelect ? levelSelect.value : 'all';
        // Add timestamp to prevent caching
        const timestamp = new Date().getTime();
        const response = await fetch(`/api/v1/system/logs?level=${level}&limit=10&_t=${timestamp}`);
        if (response.ok) {
            const data = await response.json();
            renderLogs(data.logs);
        }
    } catch (error) {
        console.error('Error updating logs:', error);
    }
}

// Renderizar logs
function renderLogs(logs) {
    const logsContainer = document.querySelector('.logs-container');
    if (!logsContainer) return;
    
    logsContainer.innerHTML = '';
    
    logs.forEach(log => {
        const logItem = document.createElement('div');
        logItem.className = `log-item log-${log.level.toLowerCase()}`;
        
        const time = new Date(log.timestamp).toLocaleTimeString('es-ES', { 
            hour12: false,
            hour: '2-digit',
            minute: '2-digit',
            second: '2-digit'
        });
        
        logItem.innerHTML = `
            <span class="log-time">${time}</span>
            <span class="log-level ${log.level.toLowerCase()}">${log.level}</span>
            <span class="log-message">${log.message}</span>
        `;
        
        logsContainer.appendChild(logItem);
    });
}

// Actualizar actividad reciente
async function updateRecentActivity() {
    try {
        const response = await fetch('/api/v1/system/activity?limit=5');
        if (response.ok) {
            const data = await response.json();
            renderActivities(data.activities);
        }
    } catch (error) {
        console.error('Error updating recent activity:', error);
    }
}

// Renderizar actividades
function renderActivities(activities) {
    const activityList = document.querySelector('.activity-list');
    if (!activityList) return;
    
    activityList.innerHTML = '';
    
    activities.forEach(activity => {
        const activityItem = document.createElement('div');
        activityItem.className = 'activity-item';
        
        const iconClass = getActivityIconClass(activity.type);
        const timeAgo = getTimeAgo(activity.timestamp);
        
        activityItem.innerHTML = `
            <div class="activity-icon ${iconClass}">
                <i class="bi ${getActivityIcon(activity.type)}"></i>
            </div>
            <div class="activity-content">
                <h6>${activity.title}</h6>
                <p>${activity.description}</p>
                <span class="activity-time">${timeAgo}</span>
            </div>
        `;
        
        activityList.appendChild(activityItem);
    });
}

// Obtener clase de icono de actividad
function getActivityIconClass(type) {
    const iconClasses = {
        'login': 'login-activity',
        'system': 'system-activity',
        'network': 'network-activity',
        'security': 'security-activity',
        'error': 'security-activity'
    };
    return iconClasses[type] || 'system-activity';
}

// Obtener icono de actividad
function getActivityIcon(type) {
    const icons = {
        'login': 'bi-box-arrow-in-right',
        'system': 'bi-arrow-clockwise',
        'network': 'bi-wifi',
        'security': 'bi-shield-check',
        'error': 'bi-exclamation-triangle'
    };
    return icons[type] || 'bi-info-circle';
}

// Calcular tiempo relativo
function getTimeAgo(timestamp) {
    const now = new Date();
    const time = new Date(timestamp);
    const diff = Math.floor((now - time) / 1000); // diferencia en segundos
    
    if (diff < 60) return 'Ahora';
    if (diff < 3600) return `Hace ${Math.floor(diff / 60)} minutos`;
    if (diff < 86400) return `Hace ${Math.floor(diff / 3600)} horas`;
    return `Hace ${Math.floor(diff / 86400)} días`;
}

// Funciones de acción rápida
async function restartSystem() {
    if (!confirm('¿Estás seguro de que quieres reiniciar el sistema?')) return;
    
    try {
        const response = await fetch('/api/v1/system/restart', { method: 'POST' });
        if (response.ok) {
            showNotification('Sistema reiniciándose...', 'info');
            setTimeout(() => {
                window.location.reload();
            }, 5000);
        } else {
            showNotification('Error al reiniciar el sistema', 'error');
        }
    } catch (error) {
        showNotification('Error de conexión', 'error');
    }
}

async function shutdownSystem() {
    if (!confirm('¿Estás seguro de que quieres apagar el sistema?')) return;
    
    try {
        const response = await fetch('/api/v1/system/shutdown', { method: 'POST' });
        if (response.ok) {
            showNotification('Sistema apagándose...', 'info');
        } else {
            showNotification('Error al apagar el sistema', 'error');
        }
    } catch (error) {
        showNotification('Error de conexión', 'error');
    }
}

async function backupSystem() {
    try {
        showNotification('Iniciando backup...', 'info');
        const response = await fetch('/api/v1/system/backup', { method: 'POST' });
        if (response.ok) {
            const result = await response.json();
            showNotification('Backup completado exitosamente', 'success');
        } else {
            showNotification('Error al crear backup', 'error');
        }
    } catch (error) {
        showNotification('Error de conexión', 'error');
    }
}

async function checkUpdates() {
    try {
        showNotification('Buscando actualizaciones...', 'info');
        const response = await fetch('/api/v1/system/updates', { method: 'POST' });
        if (response.ok) {
            const result = await response.json();
            if (result.updates_available) {
                showNotification(`${result.update_count} actualizaciones disponibles`, 'warning');
            } else {
                showNotification('Sistema actualizado', 'success');
            }
        } else {
            showNotification('Error al buscar actualizaciones', 'error');
        }
    } catch (error) {
        showNotification('Error de conexión', 'error');
    }
}

function openMonitoring() {
    window.location.href = '/monitoring';
}

function openSecurity() {
    window.location.href = '/security';
}

// Funciones de refresco
function refreshActivity() {
    updateRecentActivity();
    showNotification('Actividad actualizada', 'info');
}

function refreshLogs() {
    updateLogs();
    showNotification('Logs actualizados', 'info');
}

// Sistema de notificaciones
function showNotification(message, type = 'info') {
    // Crear elemento de notificación
    const notification = document.createElement('div');
    notification.className = `notification notification-${type}`;
    notification.innerHTML = `
        <div class="notification-content">
            <span class="notification-message">${message}</span>
            <button class="notification-close" onclick="this.parentElement.parentElement.remove()">×</button>
        </div>
    `;
    
    // Añadir estilos si no existen
    if (!document.querySelector('#notification-styles')) {
        const style = document.createElement('style');
        style.id = 'notification-styles';
        style.textContent = `
            .notification {
                position: fixed;
                top: 20px;
                right: 20px;
                z-index: 9999;
                min-width: 300px;
                padding: 1rem;
                border-radius: 12px;
                background: rgba(255, 255, 255, 0.1);
                backdrop-filter: blur(10px);
                border: 1px solid rgba(255, 255, 255, 0.2);
                box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
                animation: slideInRight 0.3s ease;
            }
            
            .notification-content {
                display: flex;
                justify-content: space-between;
                align-items: center;
                color: #fff;
            }
            
            .notification-close {
                background: none;
                border: none;
                color: #fff;
                font-size: 1.2rem;
                cursor: pointer;
                padding: 0;
                margin-left: 1rem;
            }
            
            .notification-success { border-left: 4px solid #198754; }
            .notification-error { border-left: 4px solid #dc3545; }
            .notification-warning { border-left: 4px solid #ffc107; }
            .notification-info { border-left: 4px solid #0dcaf0; }
            
            @keyframes slideInRight {
                from { transform: translateX(100%); opacity: 0; }
                to { transform: translateX(0); opacity: 1; }
            }
        `;
        document.head.appendChild(style);
    }
    
    // Añadir al DOM
    document.body.appendChild(notification);
    
    // Auto-eliminar después de 5 segundos
    setTimeout(() => {
        if (notification.parentElement) {
            notification.remove();
        }
    }, 5000);
}

// Inicialización
document.addEventListener('DOMContentLoaded', function() {
    // Cargar datos iniciales
    updateSystemStats();
    updateServices();
    updateNetworkStatus();
    updateLogs();
    updateRecentActivity();
    
    // Configurar actualizaciones periódicas
    setInterval(updateSystemStats, 30000); // Cada 30 segundos
    setInterval(updateServices, 60000);   // Cada minuto
    setInterval(updateNetworkStatus, 30000); // Cada 30 segundos
    setInterval(updateLogs, 30000);       // Cada 30 segundos
    setInterval(updateRecentActivity, 60000); // Cada minuto
    
    // Event listener para cambio de nivel de logs
    const logLevelSelect = document.getElementById('logLevel');
    if (logLevelSelect) {
        logLevelSelect.addEventListener('change', updateLogs);
    }
    
    // Animación de entrada para las tarjetas
    const cards = document.querySelectorAll('.status-card, .info-card, .services-card, .network-card, .activity-card, .logs-card, .actions-card');
    cards.forEach((card, index) => {
        card.style.opacity = '0';
        card.style.transform = 'translateY(20px)';
        setTimeout(() => {
            card.style.transition = 'all 0.5s ease';
            card.style.opacity = '1';
            card.style.transform = 'translateY(0)';
        }, index * 100);
    });
});

// Exportar funciones para uso global
window.dashboard = {
    updateSystemStats,
    updateServices,
    updateNetworkStatus,
    updateLogs,
    updateRecentActivity,
    refreshActivity,
    refreshLogs,
    restartSystem,
    shutdownSystem,
    backupSystem,
    checkUpdates,
    openMonitoring,
    openSecurity,
    showNotification
};
