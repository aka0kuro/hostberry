// JS extraído desde templates/system.html
(function(){
  async function restartSystem(){
    if(confirm(HostBerry.t('system.restart_confirmation'))){
      try{
        await HostBerry.apiRequest('/api/v1/system/restart', { method: 'POST' });
        HostBerry.showAlert('success', HostBerry.t('system.restart_in_progress'));
        setTimeout(function(){ window.location.reload(); }, 5000);
      }catch(_e){ HostBerry.showAlert('danger', HostBerry.t('errors.system_error')); }
    }
  }

  async function shutdownSystem(){
    if(confirm(HostBerry.t('system.shutdown_confirmation'))){
      try{
        await HostBerry.apiRequest('/api/v1/system/shutdown', { method: 'POST' });
        HostBerry.showAlert('warning', HostBerry.t('system.shutdown_in_progress'));
      }catch(_e){ HostBerry.showAlert('danger', HostBerry.t('errors.system_error')); }
    }
  }

  async function backupSystem(){
    try{
      await HostBerry.apiRequest('/api/v1/system/backup', { method: 'POST' });
      HostBerry.showAlert('success', HostBerry.t('messages.backup_created'));
    }catch(_e){ HostBerry.showAlert('danger', HostBerry.t('errors.backup_error')); }
  }

  async function checkUpdates(){
    try{
      const updatesResp = await HostBerry.apiRequest('/api/v1/system/updates');
      const updates = typeof updatesResp.json === 'function' ? await updatesResp.json() : updatesResp;
      if(updates && updates.available){ HostBerry.showAlert('info', HostBerry.t('messages.update_available')); }
      else { HostBerry.showAlert('success', HostBerry.t('messages.system_optimized')); }
    }catch(_e){ HostBerry.showAlert('danger', HostBerry.t('errors.update_error')); }
  }

  async function loadLogs(){
    try{
      const resp = await HostBerry.apiRequest('/api/v1/system/logs');
      const logs = typeof resp.json === 'function' ? await resp.json() : (Array.isArray(resp) ? resp : []);
      const tbody = document.getElementById('logsTable');
      if(!tbody) return;
      tbody.innerHTML = '';
      (logs || []).slice(0,10).forEach(function(log){
        const tr = document.createElement('tr');
        tr.innerHTML = '<td>'+log.timestamp+'</td>'+
          '<td><span class="badge bg-'+(HostBerry.getStatusColor?HostBerry.getStatusColor(log.level):'secondary')+'">'+log.level+'</span></td>'+
          '<td>'+log.message+'</td>';
        tbody.appendChild(tr);
      });
    }catch(e){ console.error('Error loading logs:', e); }
  }

  function refreshLogs(){ loadLogs(); }

  document.addEventListener('DOMContentLoaded', function(){
    loadLogs();
    setInterval(loadLogs, 30000);
  });

  // Exportar a global para onClick en HTML
  window.restartSystem = restartSystem;
  window.shutdownSystem = shutdownSystem;
  window.backupSystem = backupSystem;
  window.checkUpdates = checkUpdates;
  window.refreshLogs = refreshLogs;
})();

