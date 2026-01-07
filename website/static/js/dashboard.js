// Dashboard JavaScript
(function() {
    const setText = (id, value) => {
        const el = document.getElementById(id);
        if (el) el.textContent = value;
    };

    const setProgress = (id, percent) => {
        const bar = document.getElementById(id);
        if (bar && Number.isFinite(percent)) {
            const clamped = Math.min(100, Math.max(0, percent));
            bar.style.width = clamped + '%';
        }
    };

    const formatUptime = (seconds) => {
        if (!Number.isFinite(seconds) || seconds < 0) return '--';
        const days = Math.floor(seconds / 86400);
        const hours = Math.floor((seconds % 86400) / 3600);
        const minutes = Math.floor((seconds % 3600) / 60);
        if (days > 0) return days + 'd ' + hours + 'h';
        if (hours > 0) return hours + 'h ' + minutes + 'm';
        return minutes + 'm';
    };

    const updateTime = () => {
        const now = new Date();
        const timeStr = now.toLocaleTimeString();
        setText('dashboard-time', timeStr);
    };

    const updateHealth = (type, value, thresholds) => {
        const dot = document.getElementById('health-' + type);
        const text = document.getElementById('health-' + type + '-text');
        if (!dot || !text) return;

        let status = 'healthy';
        let statusText = (window.HostBerry && window.HostBerry.t) ? window.HostBerry.t('dashboard.healthy', 'Healthy') : 'Healthy';
        
        if (value >= thresholds.critical) {
            status = 'danger';
            statusText = (window.HostBerry && window.HostBerry.t) ? window.HostBerry.t('dashboard.critical', 'Critical') : 'Critical';
        } else if (value >= thresholds.warning) {
            status = 'warning';
            statusText = (window.HostBerry && window.HostBerry.t) ? window.HostBerry.t('dashboard.warning', 'Warning') : 'Warning';
        }

        dot.className = 'health-dot health-dot-' + status;
        text.textContent = statusText;
    };

    async function fetchDashboardData() {
        try {
            const apiRequestFn = window.HostBerry && window.HostBerry.apiRequest 
                ? window.HostBerry.apiRequest 
                : async function(url) {
                    const token = localStorage.getItem('access_token');
                    const headers = { 'Content-Type': 'application/json' };
                    if (token) {
                        headers['Authorization'] = 'Bearer ' + token;
                    }
                    return fetch(url, { headers: headers });
                };
            
            // Obtener stats e info en paralelo
            const [statsResp, infoResp] = await Promise.all([
                apiRequestFn('/api/v1/system/stats'),
                apiRequestFn('/api/v1/system/info')
            ]);
            
            if (!statsResp.ok) {
                console.error('Stats request failed:', statsResp.status, statsResp.statusText);
                throw new Error('Stats request failed: ' + statsResp.status);
            }
            
            if (!infoResp.ok) {
                console.error('Info request failed:', infoResp.status, infoResp.statusText);
            }
            
            const statsPayload = await statsResp.json();
            const infoPayload = infoResp.ok ? await infoResp.json() : {};
            
            console.log('Dashboard stats response:', statsPayload);
            console.log('Dashboard info response:', infoPayload);
            
            // Manejar diferentes formatos de respuesta
            let stats = statsPayload;
            if (statsPayload.data) {
                stats = statsPayload.data;
            } else if (statsPayload.stats) {
                stats = statsPayload.stats;
            }
            
            let info = infoPayload;
            if (infoPayload.data) {
                info = infoPayload.data;
            } else if (infoPayload.info) {
                info = infoPayload.info;
            }

            // CPU - intentar diferentes nombres de campo
            const cpuUsage = stats.cpu_usage || stats.cpu_percent || stats.cpu || 0;
            setText('stat-cpu', cpuUsage.toFixed(1) + '%');
            setProgress('stat-cpu-bar', cpuUsage);
            updateHealth('cpu', cpuUsage, { warning: 70, critical: 90 });

            // Memory - intentar diferentes nombres de campo
            const memUsage = stats.memory_usage || stats.memory_percent || stats.memory || 0;
            setText('stat-memory', memUsage.toFixed(1) + '%');
            setProgress('stat-memory-bar', memUsage);
            updateHealth('memory', memUsage, { warning: 75, critical: 90 });

            // Disk - intentar diferentes nombres de campo
            const diskUsage = stats.disk_usage || stats.disk_percent || stats.disk || 0;
            setText('stat-disk', diskUsage.toFixed(1) + '%');
            setProgress('stat-disk-bar', diskUsage);
            updateHealth('disk', diskUsage, { warning: 80, critical: 95 });

            // Uptime
            const uptimeSeconds = info.uptime_seconds || stats.uptime || stats.uptime_seconds || 0;
            const uptimeFormatted = formatUptime(uptimeSeconds);
            setText('stat-uptime', uptimeFormatted);

            // System Info - combinar datos de stats e info
            setText('info-hostname', info.hostname || stats.hostname || stats.host_name || '--');
            setText('info-os', info.os_version || stats.os_version || stats.os || '--');
            setText('info-kernel', info.kernel_version || stats.kernel_version || stats.kernel || '--');
            setText('info-arch', info.architecture || stats.architecture || stats.arch || '--');
            setText('info-uptime', formatUptime(info.uptime_seconds || stats.uptime || stats.uptime_seconds || 0));
            setText('info-cores', stats.cpu_cores || stats.cores || stats.cpu_count || info.cpu_cores || '--');

        } catch (error) {
            console.error('Error fetching dashboard data:', error);
            // Mostrar mensaje de error al usuario
            if (window.HostBerry && window.HostBerry.showAlert) {
                window.HostBerry.showAlert('warning', 'Unable to load dashboard data. Please refresh the page.');
            }
        }
    }

    async function loadActivity() {
        const container = document.getElementById('activity-list');
        if (!container) return;
        
        try {
            const apiRequestFn = window.HostBerry && window.HostBerry.apiRequest 
                ? window.HostBerry.apiRequest 
                : async function(url) {
                    const token = localStorage.getItem('access_token');
                    const headers = { 'Content-Type': 'application/json' };
                    if (token) {
                        headers['Authorization'] = 'Bearer ' + token;
                    }
                    return fetch(url, { headers: headers });
                };
            
            const resp = await apiRequestFn('/api/v1/system/activity?limit=10');
            
            if (!resp.ok) {
                console.error('Activity request failed:', resp.status, resp.statusText);
                throw new Error('Activity request failed: ' + resp.status);
            }
            
            const activities = await resp.json();
            console.log('Activity response:', activities);
            
            // El endpoint devuelve un array directamente, no envuelto
            const activitiesList = Array.isArray(activities) ? activities : (activities.activities || activities.data || []);

            if (!activitiesList.length) {
                const noActivityText = (window.HostBerry && window.HostBerry.t) ? window.HostBerry.t('dashboard.no_activity', 'No recent activity') : 'No recent activity';
                container.innerHTML = '<div class="activity-item"><div class="activity-content"><div class="activity-text">' + noActivityText + '</div></div></div>';
                return;
            }

            container.innerHTML = '';
            activitiesList.forEach(function(activity) {
                const item = document.createElement('div');
                item.className = 'activity-item';
                
                // Usar level en lugar de type
                const level = (activity.level || '').toLowerCase();
                const icon = level === 'error' ? 'bi-exclamation-triangle' : 
                           level === 'warning' ? 'bi-exclamation-circle' : 
                           level === 'info' ? 'bi-info-circle' : 'bi-check-circle';
                
                const time = activity.timestamp ? new Date(activity.timestamp).toLocaleString() : '';
                const message = activity.message || activity.description || activity.content || '';
                const source = activity.source ? ' [' + activity.source + ']' : '';
                const timeHtml = time ? '<div class="activity-time">' + time + '</div>' : '';
                
                item.innerHTML = '<div class="activity-icon"><i class="bi ' + icon + '"></i></div><div class="activity-content"><div class="activity-text">' + message + source + '</div>' + timeHtml + '</div>';
                container.appendChild(item);
            });
        } catch (error) {
            console.error('Error loading activity:', error);
            const errorText = (window.HostBerry && window.HostBerry.t) ? window.HostBerry.t('errors.unknown_error', 'Error loading activity') : 'Error loading activity';
            if (container) {
                container.innerHTML = '<div class="activity-item"><div class="activity-content"><div class="activity-text text-danger">' + errorText + '</div></div></div>';
            }
        }
    }

    document.addEventListener('DOMContentLoaded', function() {
        updateTime();
        setInterval(updateTime, 1000);
        
        fetchDashboardData();
        loadActivity();
        
        const refreshSystemInfo = document.getElementById('refresh-system-info');
        if (refreshSystemInfo) {
            refreshSystemInfo.addEventListener('click', fetchDashboardData);
        }
        
        const refreshActivity = document.getElementById('refresh-activity');
        if (refreshActivity) {
            refreshActivity.addEventListener('click', loadActivity);
        }
        
        setInterval(fetchDashboardData, 30000);
        setInterval(loadActivity, 60000);
    });
})();
