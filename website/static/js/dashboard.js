// Dashboard JavaScript - Funcionalidades interactivas

// Helpers (evitar duplicación en cada refresh)
function hbSetText(id, text) {
    const el = document.getElementById(id);
    if (el) el.textContent = text;
}

function hbUpdateProgress(id, percent) {
    const el = document.getElementById(id);
    if (!el) return;
    const numeric = (typeof percent === 'number') ? percent : parseFloat(percent);
    const safePercent = Number.isFinite(numeric) ? Math.min(100, Math.max(0, numeric)) : 0;
    el.style.width = safePercent + '%';
}

function hbSafeToFixed(value, digits = 1) {
    if (value === null || value === undefined) return '0.0';
    const num = typeof value === 'number' ? value : parseFloat(value);
    if (Number.isNaN(num) || !Number.isFinite(num)) return '0.0';
    return num.toFixed(digits);
}

function hbFormatBytes(bytes) {
    if (!Number.isFinite(bytes) || bytes <= 0) return '0 GB';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    const sizeIndex = Math.max(0, Math.min(i, sizes.length - 1));
    return `${hbSafeToFixed(bytes / Math.pow(k, sizeIndex), 1)} ${sizes[sizeIndex]}`;
}

function hbFormatUptime(seconds) {
    if (typeof seconds !== 'number' || !isFinite(seconds) || seconds < 0) return '--';
    const mins = Math.floor(seconds / 60);
    const hrs = Math.floor(mins / 60);
    const days = Math.floor(hrs / 24);
    const remHrs = hrs % 24;
    const remMins = mins % 60;
    if (days > 0) return `${days}d ${remHrs}h ${remMins}m`;
    if (hrs > 0) return `${hrs}h ${remMins}m`;
    return `${remMins}m`;
}

// ---- Monitoring-like Network Stats (para dashboard) ----
let hbSelectedInterface = '';
let hbLastNetSnapshot = null;
let hbNetChart = null;
const hbNetHistory = { labels: [], download: [], upload: [] };

function hbPopulateInterfaceSelect(list) {
    const select = document.getElementById('net-interface-select');
    if (!select || !Array.isArray(list)) return;

    const existing = new Set(Array.from(select.options).map(o => o.value));
    let added = false;

    list.forEach((iface) => {
        const name = (typeof iface === 'string') ? iface : (iface?.name || iface);
        if (!name || name === 'lo') return;
        if (existing.has(name)) return;
        const opt = document.createElement('option');
        opt.value = name;
        opt.textContent = name;
        select.appendChild(opt);
        existing.add(name);
        added = true;
    });

    // Mantener selección
    if (!select.value && hbSelectedInterface) {
        select.value = hbSelectedInterface;
    }

    // Si se añadieron opciones y no hay selección explícita, no disparamos change
    // (evita bucles). La UI se actualizará en el siguiente refresh.
    return added;
}

function hbEnsureNetChart() {
    const canvas = document.getElementById('net-chart');
    if (!canvas) return null;
    if (hbNetChart) return hbNetChart;
    if (typeof Chart === 'undefined') return null;

    const t = (key, fallback) => (window.HostBerry && HostBerry.t) ? HostBerry.t(key, fallback) : (fallback || key);

    const ctx = canvas.getContext('2d');
    hbNetChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: hbNetHistory.labels,
            datasets: [
                {
                    label: t('monitoring.download', 'Download'),
                    data: hbNetHistory.download,
                    borderColor: '#0dcaf0',
                    backgroundColor: 'rgba(13, 202, 240, 0.1)',
                    tension: 0.4,
                    fill: true,
                    pointRadius: 0,
                    pointHoverRadius: 4
                },
                {
                    label: t('monitoring.upload', 'Upload'),
                    data: hbNetHistory.upload,
                    borderColor: '#198754',
                    backgroundColor: 'rgba(25, 135, 84, 0.1)',
                    tension: 0.4,
                    fill: true,
                    pointRadius: 0,
                    pointHoverRadius: 4
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            animation: { duration: 0 },
            plugins: {
                legend: { labels: { color: '#fff' }, display: true },
                tooltip: { mode: 'index', intersect: false }
            },
            scales: {
                x: {
                    ticks: { color: '#fff', maxRotation: 45, minRotation: 0 },
                    grid: { color: 'rgba(255,255,255,0.1)' }
                },
                y: {
                    ticks: {
                        color: '#fff',
                        callback: function (value) {
                            return hbFormatBytes(value) + '/s';
                        }
                    },
                    grid: { color: 'rgba(255,255,255,0.1)' },
                    beginAtZero: true
                }
            },
            interaction: { mode: 'nearest', axis: 'x', intersect: false }
        }
    });

    return hbNetChart;
}

function hbPushNetHistory(downloadBytesPerSec, uploadBytesPerSec) {
    const now = new Date();
    const label = now.toLocaleTimeString();

    const dl = (typeof downloadBytesPerSec === 'number' && isFinite(downloadBytesPerSec)) ? Math.max(0, downloadBytesPerSec) : 0;
    const ul = (typeof uploadBytesPerSec === 'number' && isFinite(uploadBytesPerSec)) ? Math.max(0, uploadBytesPerSec) : 0;

    hbNetHistory.labels.push(label);
    hbNetHistory.download.push(dl);
    hbNetHistory.upload.push(ul);

    if (hbNetHistory.labels.length > 30) {
        hbNetHistory.labels.shift();
        hbNetHistory.download.shift();
        hbNetHistory.upload.shift();
    }

    if (hbNetChart) {
        hbNetChart.data.labels = [...hbNetHistory.labels];
        hbNetChart.data.datasets[0].data = [...hbNetHistory.download];
        hbNetChart.data.datasets[1].data = [...hbNetHistory.upload];
        hbNetChart.update('none');
    }
}

function hbComputeNetworkRates(current) {
    if (!current || typeof current !== 'object') {
        return {
            download_speed: 0.0,
            upload_speed: 0.0,
            bytes_recv: 0,
            bytes_sent: 0,
            packets_sent: 0,
            packets_recv: 0,
            errors: 0,
            interface: hbSelectedInterface || '',
            ip_address: '--',
            interfaces: []
        };
    }

    const bytesRecv = (typeof current.bytes_recv === 'number' && isFinite(current.bytes_recv)) ? current.bytes_recv : 0;
    const bytesSent = (typeof current.bytes_sent === 'number' && isFinite(current.bytes_sent)) ? current.bytes_sent : 0;

    const now = Date.now();
    if (!hbLastNetSnapshot) {
        hbLastNetSnapshot = {
            time: now,
            bytes_recv: bytesRecv,
            bytes_sent: bytesSent,
            interface: current.interface || hbSelectedInterface || ''
        };
        return { ...current, download_speed: 0.0, upload_speed: 0.0, bytes_recv: bytesRecv, bytes_sent: bytesSent };
    }

    const elapsedSec = (now - hbLastNetSnapshot.time) / 1000;
    if (!isFinite(elapsedSec) || elapsedSec <= 0.1 || elapsedSec > 60) {
        hbLastNetSnapshot = {
            time: now,
            bytes_recv: bytesRecv,
            bytes_sent: bytesSent,
            interface: current.interface || hbSelectedInterface || ''
        };
        return { ...current, download_speed: 0.0, upload_speed: 0.0, bytes_recv: bytesRecv, bytes_sent: bytesSent };
    }

    const prevRecv = hbLastNetSnapshot.bytes_recv || 0;
    const prevSent = hbLastNetSnapshot.bytes_sent || 0;

    let recvDelta = bytesRecv - prevRecv;
    let sentDelta = bytesSent - prevSent;

    // Manejar reset de contadores
    if (recvDelta < 0 && Math.abs(recvDelta) > prevRecv * 0.5) recvDelta = bytesRecv;
    if (sentDelta < 0 && Math.abs(sentDelta) > prevSent * 0.5) sentDelta = bytesSent;

    const downloadSpeed = Math.max(0, recvDelta / elapsedSec); // bytes/s
    const uploadSpeed = Math.max(0, sentDelta / elapsedSec);   // bytes/s

    hbLastNetSnapshot = {
        time: now,
        bytes_recv: bytesRecv,
        bytes_sent: bytesSent,
        interface: current.interface || hbSelectedInterface || ''
    };

    return {
        ...current,
        download_speed: downloadSpeed,
        upload_speed: uploadSpeed,
        bytes_recv: bytesRecv,
        bytes_sent: bytesSent
    };
}

// Actualizar tiempo en tiempo real
function updateCurrentTime() {
    const now = new Date();
    const timeString = (window.HostBerry && typeof window.HostBerry.formatTime === 'function')
        ? window.HostBerry.formatTime(now)
        : now.toLocaleTimeString();
    const timeElement = document.getElementById('currentTime');
    if (timeElement) {
        timeElement.textContent = timeString;
    }
}

function updateDashboardLastUpdate() {
    const now = new Date();
    const timeString = (window.HostBerry && typeof window.HostBerry.formatTime === 'function')
        ? window.HostBerry.formatTime(now)
        : now.toLocaleTimeString();
    const el = document.getElementById('dashboard-last-update');
    if (el) el.textContent = timeString;
}

// Inicializar actualización de tiempo
setInterval(updateCurrentTime, 1000);
updateCurrentTime();

// Actualizar datos del sistema
async function updateSystemStats() {
    try {
        if (!window.HostBerry || typeof window.HostBerry.apiRequest !== 'function') {
            return;
        }
        const response = await HostBerry.apiRequest('/api/v1/system/stats');
        if (response.ok) {
            const stats = await response.json();

            // Uptime (si existe en la respuesta)
            try {
                const uptimeSeconds = (stats.uptime_seconds !== undefined ? stats.uptime_seconds : stats.uptime);
                hbSetText('uptime-value', hbFormatUptime(uptimeSeconds));
            } catch (_e) {}

            // Actualizar CPU
            const cpuUsage = (stats.cpu_percent !== undefined ? stats.cpu_percent : stats.cpu_usage);
            const cpuValue = (cpuUsage !== null && cpuUsage !== undefined) ? (typeof cpuUsage === 'number' ? cpuUsage : parseFloat(cpuUsage)) : 0;
            hbSetText('cpu-usage', `${hbSafeToFixed(cpuValue)}%`);
            hbUpdateProgress('cpu-progress', cpuValue || 0);
            if (stats.cpu_cores !== undefined) hbSetText('cpu-cores', String(stats.cpu_cores));
            const cpuTemp = (stats.temperature !== undefined ? stats.temperature : stats.cpu_temperature);
            if (typeof cpuTemp === 'number' && isFinite(cpuTemp)) hbSetText('cpu-temp', `${cpuTemp.toFixed(1)}°C`);
            else hbSetText('cpu-temp', '--°C');

            // Actualizar Memoria
            const memUsage = (stats.memory_percent !== undefined ? stats.memory_percent : stats.memory_usage);
            const memValue = (memUsage !== null && memUsage !== undefined) ? (typeof memUsage === 'number' ? memUsage : parseFloat(memUsage)) : 0;
            hbSetText('mem-usage', `${hbSafeToFixed(memValue)}%`);
            hbUpdateProgress('mem-progress', memValue || 0);
            hbSetText('mem-total', hbFormatBytes(stats.memory_total || 0));
            hbSetText('mem-free', hbFormatBytes(stats.memory_free || 0));

            // Actualizar Disco
            const diskUsage = (stats.disk_percent !== undefined ? stats.disk_percent : stats.disk_usage);
            const diskValue = (diskUsage !== null && diskUsage !== undefined) ? (typeof diskUsage === 'number' ? diskUsage : parseFloat(diskUsage)) : 0;
            hbSetText('disk-usage', `${hbSafeToFixed(diskValue)}%`);
            hbUpdateProgress('disk-progress', diskValue || 0);
            hbSetText('disk-used', hbFormatBytes(stats.disk_used || 0));
            hbSetText('disk-total', hbFormatBytes(stats.disk_total || 0));

            // System Info (monitoring-like)
            hbSetText('sys-hostname', stats.hostname || '--');
            hbSetText('sys-os', stats.os_version || '--');
            hbSetText('sys-kernel', stats.kernel_version || '--');
            hbSetText('sys-arch', stats.architecture || '--');
            hbSetText('sys-processor', stats.processor || '--');
            const loadAvg = stats.load_average;
            if (loadAvg) {
                const parts = String(loadAvg).split(',').map(s => s.trim());
                if (parts.length === 3) {
                    hbSetText('sys-load', `${parts[0]} (1m), ${parts[1]} (5m), ${parts[2]} (15m)`);
                } else {
                    hbSetText('sys-load', String(loadAvg));
                }
            } else {
                hbSetText('sys-load', '--');
            }

            updateDashboardLastUpdate();
        }
    } catch (error) {
        console.error('Error updating system stats:', error);
    }
}

// Actualizar servicios
async function updateServices() {
    try {
        if (!window.HostBerry || typeof window.HostBerry.apiRequest !== 'function') {
            return;
        }
        const response = await HostBerry.apiRequest('/api/v1/system/services');
        if (response.ok) {
            const data = await response.json();
            const services = data.services || data;
            
            // Limpiar contenedor de servicios
            // Soporta el nuevo layout (contenedor interno) y el antiguo (body directo)
            const servicesBody = document.querySelector('#dashboardServicesContainer') || document.querySelector('.services-card-body');
            if (!servicesBody) return;
            
            // Si no hay servicios, mostrar mensaje
            if (!services || Object.keys(services).length === 0) {
                servicesBody.innerHTML = `
                    <div class="text-center py-4 text-muted">
                        <i class="bi bi-inbox"></i>
                        <p class="mb-0 mt-2">${HostBerry.t?.('system.no_services', 'No services to display') || 'No services to display'}</p>
                    </div>
                `;
                return;
            }
            
            // Reconstruir lista de servicios
            servicesBody.innerHTML = '';
            
            Object.keys(services).forEach(serviceName => {
                const service = services[serviceName];
                const status = service.status || service;
                const statusLower = (typeof status === 'string' ? status : 'unknown').toLowerCase();
                const isRunning = statusLower === 'running' || statusLower === 'active' || statusLower === 'online' || statusLower === 'connected';
                
                const serviceItem = document.createElement('div');
                serviceItem.className = 'service-item';
                
                // Iconos por servicio
                const serviceIcons = {
                    'hostberry': 'bi-gear-fill hostberry-icon',
                    'nginx': 'bi-shield-check nginx-icon',
                    'fail2ban': 'bi-shield-fill fail2ban-icon',
                    'ufw': 'bi-shield-lock ufw-icon',
                    'wifi': 'bi-wifi wifi-icon',
                    'ssh': 'bi-terminal ssh-icon',
                    'hostapd': 'bi-wifi wifi-icon',
                    'openvpn': 'bi-shield-check openvpn-icon',
                    'wireguard': 'bi-shield-lock wireguard-icon',
                    'wg-quick': 'bi-shield-lock wireguard-icon',
                    'wg': 'bi-shield-lock wireguard-icon',
                    'dnsmasq': 'bi-diagram-3 dns-icon',
                    'dns': 'bi-diagram-3 dns-icon',
                    'adblock': 'bi-shield-x adblock-icon',
                    'pihole': 'bi-shield-x adblock-icon'
                };
                
                const normalizedName = serviceName.toLowerCase().replace(/[_-]/g, '');
                const iconClass = serviceIcons[normalizedName] || serviceIcons[serviceName.toLowerCase()] || 'bi-gear-fill default-icon';
                
                let statusText = 'Unknown';
                if (statusLower === 'active' || statusLower === 'running') {
                    statusText = HostBerry.t?.('system.running', 'Running') || 'Running';
                } else if (statusLower === 'connected') {
                    statusText = HostBerry.t?.('system.connected', 'Connected') || 'Connected';
                } else if (statusLower === 'online') {
                    statusText = HostBerry.t?.('system.online', 'Online') || 'Online';
                } else if (statusLower === 'stopped' || statusLower === 'inactive') {
                    statusText = HostBerry.t?.('system.stopped', 'Stopped') || 'Stopped';
                } else if (statusLower === 'disconnected') {
                    statusText = HostBerry.t?.('system.disconnected', 'Disconnected') || 'Disconnected';
                } else if (statusLower === 'offline') {
                    statusText = HostBerry.t?.('system.offline', 'Offline') || 'Offline';
                }
                
                serviceItem.innerHTML = `
                    <div class="service-info">
                        <i class="bi ${iconClass} service-icon"></i>
                        <span class="service-name">${serviceName}</span>
                    </div>
                    <div class="service-status">
                        <span class="status-badge ${isRunning ? 'status-running' : 'status-stopped'}">${statusText}</span>
                    </div>
                `;
                
                servicesBody.appendChild(serviceItem);
            });
        }
    } catch (error) {
        console.error('Error updating services:', error);
        const servicesBody = document.querySelector('#dashboardServicesContainer') || document.querySelector('.services-card-body');
        if (servicesBody) {
            servicesBody.innerHTML = `
                <div class="text-center py-4 text-danger">
                    <i class="bi bi-exclamation-triangle"></i>
                    <p class="mb-0 mt-2">${HostBerry.t?.('system.services_error', 'Error loading services') || 'Error loading services'}</p>
                </div>
            `;
        }
    }
}

// Función para refrescar servicios manualmente
function refreshServices() {
    updateServices();
    showNotification(HostBerry.t?.('system.services_refreshed', 'Services refreshed') || 'Services refreshed', 'info');
}

// Actualizar estado de un servicio
function updateServiceStatus(serviceName, status) {
    const serviceItems = document.querySelectorAll('.service-item');
    
    serviceItems.forEach(item => {
        const serviceNameElement = item.querySelector('.service-name');
        if (serviceNameElement && serviceNameElement.textContent.toLowerCase().includes(serviceName.toLowerCase())) {
            const statusBadge = item.querySelector('.status-badge');
            if (statusBadge) {
                const statusLower = (status || '').toLowerCase();
                const isRunning = statusLower === 'running' || statusLower === 'active' || statusLower === 'online' || statusLower === 'connected';
                
                if (isRunning) {
                    statusBadge.className = 'status-badge status-running';
                    // Usar traducción correcta
                    if (statusLower === 'active') {
                        statusBadge.textContent = HostBerry.t('system.running', 'Running');
                    } else if (statusLower === 'connected') {
                        statusBadge.textContent = HostBerry.t('system.connected', 'Connected');
                    } else if (statusLower === 'online') {
                        statusBadge.textContent = HostBerry.t('system.online', 'Online');
                    } else {
                        statusBadge.textContent = HostBerry.t('system.running', 'Running');
                    }
                } else {
                    statusBadge.className = 'status-badge status-stopped';
                    // Usar traducción correcta
                    if (statusLower === 'disconnected') {
                        statusBadge.textContent = HostBerry.t('system.disconnected', 'Disconnected');
                    } else if (statusLower === 'offline') {
                        statusBadge.textContent = HostBerry.t('system.offline', 'Offline');
                    } else {
                        statusBadge.textContent = HostBerry.t('system.stopped', 'Stopped');
                    }
                }
            }
        }
    });
}

// Actualizar estado de red
async function updateNetworkStatus() {
    try {
        if (!window.HostBerry || typeof window.HostBerry.apiRequest !== 'function') {
            return;
        }
        const response = await HostBerry.apiRequest('/api/v1/system/network/status');
        if (response.ok) {
            const data = await response.json();
            const networkData = data.interfaces;
            
            // Actualizar interfaces de red
            updateNetworkInterface('eth0', networkData?.eth0 || {});
            updateNetworkInterface('wlan0', networkData?.wlan0 || {});

            updateDashboardLastUpdate();
        }
    } catch (error) {
        console.error('Error updating network status:', error);
    }
}

// Monitoring-like Network Stats (selector + chart) - Solo si los elementos existen
async function updateNetworkMonitoring() {
    // Si no existe el selector de interfaz, no hacer nada
    if (!document.getElementById('net-interface-select')) {
        return;
    }
    try {
        if (!window.HostBerry || typeof window.HostBerry.apiRequest !== 'function') {
            return;
        }

        const url = hbSelectedInterface
            ? `/api/v1/system/network?interface=${encodeURIComponent(hbSelectedInterface)}&_t=${Date.now()}`
            : `/api/v1/system/network?_t=${Date.now()}`;

        const resp = await HostBerry.apiRequest(url);
        if (!resp || !resp.ok) return;

        const payload = await resp.json();
        const raw = (payload && typeof payload === 'object' && payload.data !== undefined) ? payload.data : payload;

        const computed = hbComputeNetworkRates(raw);

        if (computed.interfaces && Array.isArray(computed.interfaces)) {
            hbPopulateInterfaceSelect(computed.interfaces);
        } else if (raw && raw.interfaces && Array.isArray(raw.interfaces)) {
            hbPopulateInterfaceSelect(raw.interfaces);
        }

        // Solo actualizar si los elementos existen
        const netInterface = document.getElementById('net-interface');
        const netIp = document.getElementById('net-ip');
        const netDownload = document.getElementById('net-download');
        const netUpload = document.getElementById('net-upload');
        const netBytesRecv = document.getElementById('net-bytes-recv');
        const netBytesSent = document.getElementById('net-bytes-sent');
        const netPackets = document.getElementById('net-packets');
        const netErrors = document.getElementById('net-errors');

        if (netInterface) hbSetText('net-interface', computed.interface || raw?.interface || '--');
        if (netIp) hbSetText('net-ip', computed.ip_address || raw?.ip_address || '--');

        const dl = computed.download_speed || 0;
        const ul = computed.upload_speed || 0;
        if (netDownload) hbSetText('net-download', dl > 0 ? `${hbFormatBytes(dl)}/s` : '0 B/s');
        if (netUpload) hbSetText('net-upload', ul > 0 ? `${hbFormatBytes(ul)}/s` : '0 B/s');

        const bytesRecv = computed.bytes_recv || raw?.bytes_recv || 0;
        const bytesSent = computed.bytes_sent || raw?.bytes_sent || 0;
        if (netBytesRecv) hbSetText('net-bytes-recv', hbFormatBytes(bytesRecv));
        if (netBytesSent) hbSetText('net-bytes-sent', hbFormatBytes(bytesSent));

        const packetsSent = computed.packets_sent || raw?.packets_sent || 0;
        const packetsRecv = computed.packets_recv || raw?.packets_recv || 0;
        if (netPackets) hbSetText('net-packets', `${packetsSent} / ${packetsRecv}`);

        const errors = (computed.errors || 0) + (raw?.errors || 0) + (raw?.drop || 0);
        if (netErrors) hbSetText('net-errors', String(errors || 0));

        hbEnsureNetChart();
        hbPushNetHistory(dl, ul);

        updateDashboardLastUpdate();
    } catch (e) {
        console.error('Error updating network monitoring:', e);
    }
}

// Actualizar interfaz de red
function updateNetworkInterface(interfaceName, data) {
    const container =
        document.querySelector(`.network-interface[data-interface="${interfaceName}"]`) ||
        Array.from(document.querySelectorAll('.network-interface')).find(el => {
            const h6 = el.querySelector('.interface-header h6');
            return h6 && h6.textContent === interfaceName;
        });
    if (!container) return;

    const statusElement = container.querySelector('.interface-status');
    const isConnected = !!data?.connected;
    if (statusElement) {
        statusElement.textContent = isConnected
            ? HostBerry.t('network.connected', 'Connected')
            : HostBerry.t('network.disconnected', 'Disconnected');
    }

    const setField = (field, value) => {
        const el = container.querySelector(`.network-value[data-field="${field}"]`);
        if (!el) return;
        el.textContent = (value === null || value === undefined || value === '') ? '--' : String(value);
    };

    setField('ip_address', data?.ip_address);
    setField('gateway', data?.gateway);
    setField('dns', data?.dns || (Array.isArray(data?.dns_servers) ? data.dns_servers.join(', ') : undefined));
    setField('ssid', data?.ssid);
    setField('signal_strength', (data?.signal_strength !== undefined && data?.signal_strength !== null) ? `${data.signal_strength}%` : undefined);
}

function refreshNetwork() {
    // Solo refrescar si los elementos de red existen
    if (document.getElementById('net-interface-select')) {
        updateNetworkMonitoring();
        showNotification(HostBerry.t?.('system.network_refreshed', 'Network refreshed') || 'Network refreshed', 'info');
    } else if (document.querySelector('.network-interface')) {
        updateNetworkStatus();
        showNotification(HostBerry.t?.('system.network_refreshed', 'Network refreshed') || 'Network refreshed', 'info');
    }
    // Si no hay elementos de red, no hacer nada
}

// Actualizar logs
async function updateLogs() {
    const logsContainer = document.querySelector('.logs-container');
    try {
        if (!window.HostBerry || typeof window.HostBerry.apiRequest !== 'function') {
            return;
        }
        const levelSelect = document.getElementById('logLevel');
        let level = levelSelect ? levelSelect.value : 'all';
        
        // Ensure level is valid
        if (!level || level === 'undefined' || level === 'null') {
            level = 'all';
        }
        
        const response = await HostBerry.apiRequest(`/api/v1/system/logs?level=${encodeURIComponent(level)}&limit=20`);
        
        if (response.ok) {
            const data = await response.json();
            renderLogs(data.logs);
            updateDashboardLastUpdate();
        } else {
            console.error('Server returned error:', response.status);
            if (logsContainer) {
                logsContainer.innerHTML = `
                    <div class="text-center py-4 text-muted">
                        <i class="bi bi-exclamation-circle text-danger"></i>
                        <p class="mb-0 mt-2">${HostBerry.t?.('system.logs_error', `Error loading logs (${response.status})`) || `Error loading logs (${response.status})`}</p>
                    </div>
                `;
            }
        }
    } catch (error) {
        console.error('Error updating logs:', error);
        if (logsContainer) {
            logsContainer.innerHTML = `
                <div class="text-center py-4 text-muted">
                    <i class="bi bi-wifi-off text-danger"></i>
                    <p class="mb-0 mt-2">${HostBerry.t?.('system.connection_error', 'Connection error') || 'Connection error'}</p>
                </div>
            `;
        }
    }
}

// Renderizar logs
function renderLogs(logs) {
    const logsContainer = document.querySelector('.logs-container');
    if (!logsContainer) return;
    
    logsContainer.innerHTML = '';
    
    if (!logs || !Array.isArray(logs) || logs.length === 0) {
        logsContainer.innerHTML = `
            <div class="text-center py-4 text-muted">
                <i class="bi bi-journal-x"></i>
                <p class="mb-0 mt-2">No hay logs disponibles</p>
            </div>
        `;
        return;
    }
    
    logs.forEach(log => {
        const logItem = document.createElement('div');
        const logLevel = (log.level || 'INFO').toLowerCase();
        logItem.className = `log-item log-${logLevel}`;
        
        let timeStr = '';
        try {
            timeStr = (window.HostBerry && typeof window.HostBerry.formatTime === 'function')
                ? window.HostBerry.formatTime(log.timestamp)
                : new Date(log.timestamp).toLocaleTimeString();
        } catch (e) {
            timeStr = '--:--:--';
        }
        
        logItem.innerHTML = `
            <span class="log-time">${timeStr}</span>
            <span class="log-level ${logLevel}">${log.level || 'INFO'}</span>
            <span class="log-source">${log.source || 'system'}</span>
            <span class="log-message" title="${log.message || ''}">${log.message || ''}</span>
        `;
        
        logsContainer.appendChild(logItem);
    });
}

// Actualizar actividad reciente
async function updateRecentActivity() {
    try {
        if (!window.HostBerry || typeof window.HostBerry.apiRequest !== 'function') {
            return;
        }
        const response = await HostBerry.apiRequest('/api/v1/system/activity?limit=5');
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
    
    if (diff < 60) return HostBerry.t('time.just_now', 'Just now');
    
    if (diff < 3600) {
        const minutes = Math.floor(diff / 60);
        return HostBerry.t('time.minutes_ago', `Hace ${minutes} minutos`).replace('{minutes}', minutes);
    }
    
    if (diff < 86400) {
        const hours = Math.floor(diff / 3600);
        return HostBerry.t('time.hours_ago', `Hace ${hours} horas`).replace('{hours}', hours);
    }
    
    const days = Math.floor(diff / 86400);
    return HostBerry.t('time.days_ago', `Hace ${days} días`).replace('{days}', days);
}

// Funciones de acción rápida
async function restartSystem() {
    if (!confirm(HostBerry.t?.('system.restart_confirm', 'Are you sure you want to restart the system?') || 'Are you sure you want to restart the system?')) return;
    
    try {
        const response = await HostBerry.apiRequest('/api/v1/system/restart', { method: 'POST' });
        if (response.ok) {
            showNotification(HostBerry.t?.('system.restarting', 'System restarting...') || 'System restarting...', 'info');
            setTimeout(() => {
                window.location.reload();
            }, 5000);
        } else {
            showNotification(HostBerry.t?.('system.restart_error', 'Error restarting system') || 'Error restarting system', 'error');
        }
    } catch (error) {
        showNotification(HostBerry.t?.('system.connection_error', 'Connection error') || 'Connection error', 'error');
    }
}

async function shutdownSystem() {
    if (!confirm(HostBerry.t?.('system.shutdown_confirm', 'Are you sure you want to shutdown the system?') || 'Are you sure you want to shutdown the system?')) return;
    
    try {
        const response = await HostBerry.apiRequest('/api/v1/system/shutdown', { method: 'POST' });
        if (response.ok) {
            showNotification(HostBerry.t?.('system.shutting_down', 'System shutting down...') || 'System shutting down...', 'info');
        } else {
            showNotification(HostBerry.t?.('system.shutdown_error', 'Error shutting down system') || 'Error shutting down system', 'error');
        }
    } catch (error) {
        showNotification(HostBerry.t?.('system.connection_error', 'Connection error') || 'Connection error', 'error');
    }
}

async function backupSystem() {
    try {
        showNotification('Iniciando backup...', 'info');
        const response = await HostBerry.apiRequest('/api/v1/system/backup', { method: 'POST' });
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
        const response = await HostBerry.apiRequest('/api/v1/system/updates', { method: 'POST' });
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

function openUpdate() {
    window.location.href = '/update';
}

// Funciones de refresco
function refreshActivity() {
    updateRecentActivity();
    showNotification('Actividad actualizada', 'info');
}

function refreshLogs() {
    updateLogs();
    showNotification(HostBerry.t?.('system.logs_refreshed', 'Logs refreshed') || 'Logs refreshed', 'info');
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
    // Las funciones de red solo se ejecutan si los elementos existen (ya están protegidas)
    updateLogs();
    updateRecentActivity();
    
    // Configurar actualizaciones periódicas
    setInterval(updateSystemStats, 5000); // más parecido a Monitoring
    setInterval(updateServices, 60000);   // Cada minuto
    setInterval(updateLogs, 10000);       // Cada 10 segundos
    setInterval(updateRecentActivity, 60000); // Cada minuto
    
    // Event listener para cambio de nivel de logs
    const logLevelSelect = document.getElementById('logLevel');
    if (logLevelSelect) {
        logLevelSelect.addEventListener('change', updateLogs);
    }
    
    // Animación de entrada para las tarjetas
    const cards = document.querySelectorAll('.status-card, .info-card, .services-card, .network-card, .activity-card, .logs-card, .actions-card, .glass-card');
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
    updateNetworkMonitoring,
    updateLogs,
    updateRecentActivity,
    refreshActivity,
    refreshLogs,
    refreshServices,
    refreshNetwork,
    restartSystem,
    shutdownSystem,
    backupSystem,
    checkUpdates,
    openMonitoring,
    openUpdate,
    showNotification
};
