// JS extraído desde templates/settings.html
(function(){
  function bindForm(formId, endpoint){
    const form = document.getElementById(formId);
    if(!form) return;
    form.addEventListener('submit', async function(e){
      e.preventDefault();
      const fd = new FormData(this);
      // Convertir valores según tipo
      const obj = {};
      fd.forEach((v,k)=>{ obj[k] = v; });
      // Normalizaciones básicas
      ['max_login_attempts','session_timeout','cache_size','backup_interval'].forEach(function(k){ if(obj[k]!==undefined) obj[k] = parseInt(obj[k]); });
      ['auto_backup','firewall_enabled','ssl_enabled','cache_enabled','compression_enabled','email_notifications','system_alerts'].forEach(function(k){ if(obj[k]!==undefined) obj[k] = (obj[k] === 'on'); });
      try{
        const resp = await fetch(endpoint, {
          method: 'POST',
          headers: { 'Content-Type':'application/json', 'Authorization': `Bearer ${localStorage.getItem('access_token')}` },
          body: JSON.stringify(obj)
        });
        if(resp.ok){
          HostBerry.showAlert('success', HostBerry.t('messages.changes_saved'));
          if(formId==='generalConfigForm') setTimeout(()=>window.location.reload(), 1000);
        }else{
          HostBerry.showAlert('danger', HostBerry.t('errors.configuration_error'));
        }
      }catch(_e){ HostBerry.showAlert('danger', HostBerry.t('errors.network_error')); }
    });
  }

  bindForm('generalConfigForm','/api/v1/settings/general');
  bindForm('systemConfigForm','/api/v1/settings/system');
  bindForm('networkConfigForm','/api/v1/settings/network');
  bindForm('securityConfigForm','/api/v1/settings/security');
  bindForm('performanceConfigForm','/api/v1/settings/performance');
  bindForm('notificationConfigForm','/api/v1/settings/notifications');
})();

