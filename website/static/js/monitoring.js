// Monitoring dashboard interactions
(function(){
  const setText = (id, value) => {
    const el = document.getElementById(id);
    if(el) el.textContent = value;
  };

  function safeToFixed(value, digits = 1){
    if(typeof value !== 'number' || Number.isNaN(value)) return '0.0';
    return value.toFixed(digits);
  }

  function formatUptime(seconds){
    if(!Number.isFinite(seconds) || seconds < 0) return '--';
    const days = Math.floor(seconds / 86400);
    const hours = Math.floor((seconds % 86400) / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    return `${days}d ${hours}h ${minutes}m`;
  }

  function formatBytes(bytes){
    if(!Number.isFinite(bytes)) return '0 MB';
    const mb = bytes / (1024 * 1024);
    return `${safeToFixed(mb, 1)} MB`;
  }

  async function fetchJson(url){
    const resp = await HostBerry.apiRequest(url);
    if(!resp.ok){
      const errText = await resp.text();
      throw new Error(`Request failed ${resp.status}: ${errText}`);
    }
    return resp.json();
  }

  function updateProgress(id, percent){
    const bar = document.getElementById(id);
    if(bar && Number.isFinite(percent)){
      const clamped = Math.min(100, Math.max(0, percent));
      bar.style.width = `${clamped}%`;
    }
  }

  async function updateStats(){
    try{
      const [systemStats, networkStats] = await Promise.all([
        fetchJson('/api/v1/system/stats'),
        fetchJson('/api/v1/system/network')
      ]);

      setText('uptime-value', formatUptime(systemStats.uptime));
      setText('cpu-usage', `${safeToFixed(systemStats.cpu_usage)}%`);
      updateProgress('cpu-progress', systemStats.cpu_usage);
      if(typeof systemStats.cpu_temperature === 'number'){
        setText('cpu-temp', `${safeToFixed(systemStats.cpu_temperature)}°C`);
      }
      setText('cpu-cores', systemStats.cpu_cores ? String(systemStats.cpu_cores) : '-');

      setText('mem-usage', `${safeToFixed(systemStats.memory_usage)}%`);
      updateProgress('mem-progress', systemStats.memory_usage);
      if(systemStats.memory_total){
        setText('mem-total', `${safeToFixed(systemStats.memory_total / (1024 ** 3),1)} GB`);
      }
      if(systemStats.memory_free){
        setText('mem-free', `${safeToFixed(systemStats.memory_free / (1024 ** 3),1)} GB`);
      }

      setText('disk-usage', `${safeToFixed(systemStats.disk_usage)}%`);
      updateProgress('disk-progress', systemStats.disk_usage);
      if(systemStats.disk_total){
        setText('disk-total', `${safeToFixed(systemStats.disk_total / (1024 ** 3),1)} GB`);
      }
      if(systemStats.disk_used){
        setText('disk-used', `${safeToFixed(systemStats.disk_used / (1024 ** 3),1)} GB`);
      }

      setText('net-interface', networkStats.interface || '-');
      setText('net-ip', networkStats.ip_address || '--');
      setText('net-download', `${safeToFixed(networkStats.download_speed || 0, 2)} KB/s`);
      setText('net-upload', `${safeToFixed(networkStats.upload_speed || 0, 2)} KB/s`);
      setText('net-bytes-recv', formatBytes(networkStats.bytes_recv || 0));
      setText('net-bytes-sent', formatBytes(networkStats.bytes_sent || 0));
      setText('net-packets', `${networkStats.packets_sent || 0} / ${networkStats.packets_recv || 0}`);

      setText('monitoring-last-update', new Date().toLocaleTimeString());
    }catch(error){
      console.error('Error updating monitoring stats:', error);
      HostBerry.showAlert?.('danger', HostBerry.t?.('errors.monitoring_stats', 'Unable to refresh monitoring stats') || 'Unable to refresh monitoring stats');
    }
  }

  async function loadBackups(){
    await Promise.all([refreshBackupList(), fetchBackupStatus()]);
  }

  async function refreshBackupList(){
    const list = document.getElementById('monitoring-backup-list');
    if(!list) return;
    try{
      const resp = await HostBerry.apiRequest('/api/v1/security/backups');
      const payload = await resp.json();
      const backups = payload.data?.backups || [];
      document.getElementById('backup-count')?.textContent = backups.length;
      if(!backups.length){
        list.innerHTML = `
          <div class="text-center py-4 text-white-50">
            <i class="bi bi-archive"></i>
            <p class="mb-0 mt-2">${HostBerry.t?.('monitoring.backup_empty', 'No backups recorded yet')}</p>
          </div>`;
        updateBackupSummary(null);
        return;
      }
      list.innerHTML = '';
      backups.slice(0,5).forEach(backup => {
        const item = document.createElement('div');
        item.className = 'backup-item text-white';
        const status = backup.status || 'success';
        item.innerHTML = `
          <div class="d-flex justify-content-between align-items-center">
            <div>
              <strong>${backup.name || backup.filename || 'backup'}</strong>
              <div class="text-white-50 small">${backup.created_at || ''}</div>
            </div>
            <span class="badge bg-${status === 'success' ? 'success' : (status === 'warning' ? 'warning text-dark' : 'danger')}">${status}</span>
          </div>
          <div class="text-white-50 small mt-1">${backup.size || ''}</div>`;
        list.appendChild(item);
      });
      updateBackupSummary(backups[0]);
    }catch(error){
      console.error('Error loading backups', error);
      list.innerHTML = `
        <div class="text-center py-4 text-danger">
          <i class="bi bi-exclamation-triangle"></i>
          <p class="mb-0 mt-2">${HostBerry.t?.('monitoring.backup_error', 'Unable to load backups')}</p>
        </div>`;
    }
  }

  function updateBackupSummary(latest){
    const lastRunEl = document.getElementById('backup-last-run');
    const lastSizeEl = document.getElementById('backup-last-size');
    const pill = document.getElementById('backup-status-pill');
    if(!latest){
      if(lastRunEl) lastRunEl.textContent = '--';
      if(lastSizeEl) lastSizeEl.textContent = '--';
      if(pill){
        pill.className = 'status-pill bg-dark text-white';
        pill.textContent = HostBerry.t?.('monitoring.backup_status_unknown', 'Unknown');
      }
      return;
    }
    if(lastRunEl) lastRunEl.textContent = latest.created_at || '--';
    if(lastSizeEl) lastSizeEl.textContent = latest.size || '--';
    if(pill){
      const ok = (latest.status || '').toLowerCase() === 'success';
      pill.className = `status-pill ${ok ? 'bg-success text-white' : 'bg-warning text-dark'}`;
      pill.textContent = ok ? HostBerry.t?.('monitoring.backup_ok', 'Healthy') : HostBerry.t?.('monitoring.backup_attention', 'Needs attention');
    }
  }

  async function fetchBackupStatus(){
    try{
      await refreshBackupList();
    }catch(error){
      console.error('Error refreshing backup status', error);
    }
  }

  async function runBackup(){
    const btn = document.getElementById('monitoringBackupRun');
    if(btn){
      btn.disabled = true;
      btn.innerHTML = `<span class="spinner-border spinner-border-sm me-2"></span>${HostBerry.t?.('monitoring.backup_running', 'Creating backup...')}`;
    }
    try{
      const resp = await HostBerry.apiRequest('/api/v1/security/backup?include_logs=true&include_uploads=true', { method: 'POST' });
      const payload = await resp.json();
      HostBerry.showAlert?.('success', payload.message || HostBerry.t?.('monitoring.backup_success', 'Backup created successfully'));
      await refreshBackupList();
    }catch(error){
      console.error('Backup creation failed', error);
      HostBerry.showAlert?.('danger', HostBerry.t?.('monitoring.backup_failed', 'Unable to create backup'));
    }finally{
      if(btn){
        btn.disabled = false;
        btn.innerHTML = `<i class="bi bi-hdd-network me-2"></i>${HostBerry.t?.('monitoring.backup_run_now', 'Create encrypted backup')}`;
      }
    }
  }

  async function loadLogs(){
    const container = document.getElementById('monitoring-logs');
    if(!container) return;
    const levelSelect = document.getElementById('monitoringLogLevel');
    const level = levelSelect ? levelSelect.value : 'all';
    try{
      const params = new URLSearchParams({ limit: '20' });
      if(level && level !== 'all'){ params.set('level', level); }
      const data = await fetchJson(`/api/v1/system/logs?${params.toString()}`);
      const logs = Array.isArray(data.logs) ? data.logs : [];
      if(!logs.length){
        container.innerHTML = `
          <div class="text-center py-4 text-white-50">
            <i class="bi bi-journal-x"></i>
            <p class="mb-0 mt-2">${HostBerry.t?.('monitoring.no_logs', 'No logs available') || 'No logs available'}</p>
          </div>`;
        return;
      }
      container.innerHTML = '';
      logs.forEach((log)=>{
        const item = document.createElement('div');
        const levelLabel = (log.level || 'INFO').toUpperCase();
        const timestamp = log.timestamp ? new Date(log.timestamp).toLocaleTimeString() : '--:--:--';
        item.className = 'log-item';
        item.innerHTML = `
          <span class="log-time text-white-50 small">${timestamp}</span>
          <span class="badge bg-${getLevelColor(levelLabel)} log-level">${levelLabel}</span>
          <span class="text-white flex-grow-1">${log.message || ''}</span>
        `;
        container.appendChild(item);
      });
    }catch(error){
      console.error('Error loading monitoring logs:', error);
      container.innerHTML = `
        <div class="text-center py-4 text-danger">
          <i class="bi bi-exclamation-triangle"></i>
          <p class="mb-0 mt-2">${HostBerry.t?.('monitoring.logs_error', 'Unable to load logs') || 'Unable to load logs'}</p>
        </div>`;
    }
  }

  function getLevelColor(level){
    switch(level){
      case 'ERROR': return 'danger';
      case 'WARNING': return 'warning text-dark';
      case 'INFO': return 'info';
      default: return 'secondary';
    }
  }

  function initMonitoring(){
    updateStats();
    loadLogs();
    loadBackups();
    setInterval(updateStats, 60000);
    setInterval(loadLogs, 60000);
    setInterval(loadBackups, 60000);
    const refreshBtn = document.getElementById('monitoringLogsRefresh');
    if(refreshBtn){ refreshBtn.addEventListener('click', loadLogs); }
    const logLevelSelect = document.getElementById('monitoringLogLevel');
    if(logLevelSelect){ logLevelSelect.addEventListener('change', loadLogs); }
    document.getElementById('monitoringBackupRefresh')?.addEventListener('click', loadBackups);
    document.getElementById('monitoringBackupRun')?.addEventListener('click', runBackup);
  }

  document.addEventListener('DOMContentLoaded', initMonitoring);
})();

