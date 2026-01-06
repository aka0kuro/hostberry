// JS extraído desde templates/hostapd.html
(function(){
  async function loadAccessPoints(){
    try{
      const resp = await fetch('/api/v1/hostapd/access-points', { headers: { 'Authorization': `Bearer ${localStorage.getItem('access_token')}` }});
      if(resp.ok){
        const aps = await resp.json();
        const tbody = document.getElementById('accessPointsTable'); if(!tbody) return;
        tbody.innerHTML = '';
        aps.forEach(function(ap){
          const tr = document.createElement('tr');
          tr.innerHTML = '<td>'+ap.name+'</td>'+
            '<td>'+ap.ssid+'</td>'+
            '<td><span class="badge bg-'+(ap.enabled?'success':'danger')+'">'+(ap.enabled?'Active':'Inactive')+'</span></td>'+
            '<td>'+ap.clients_count+'</td>'+
            '<td><button class="btn btn-sm btn-outline-primary" onclick="configureAccessPoint(\''+ap.name+'\')"><i class="bi bi-gear"></i></button></td>';
          tbody.appendChild(tr);
        });
      }
    }catch(e){ console.error('Error loading access points:', e); }
  }

  async function loadClients(){
    try{
      const resp = await fetch('/api/v1/hostapd/clients', { headers: { 'Authorization': `Bearer ${localStorage.getItem('access_token')}` }});
      if(resp.ok){
        const clients = await resp.json();
        const tbody = document.getElementById('clientsTable'); if(!tbody) return;
        tbody.innerHTML = '';
        clients.forEach(function(client){
          const tr = document.createElement('tr');
          tr.innerHTML = '<td>'+client.mac_address+'</td><td>'+client.ip_address+'</td><td>'+client.signal+' dBm</td><td>'+client.uptime+'</td>';
          tbody.appendChild(tr);
        });
      }
    }catch(e){ console.error('Error loading clients:', e); }
  }

  async function toggleHostAPD(){
    try{
      const resp = await fetch('/api/v1/hostapd/toggle', { method:'POST', headers:{ 'Authorization': `Bearer ${localStorage.getItem('access_token')}` }});
      if(resp.ok){ HostBerry.showAlert('success', HostBerry.t('messages.operation_successful')); setTimeout(()=>window.location.reload(), 1000); }
      else { HostBerry.showAlert('danger', HostBerry.t('errors.operation_failed')); }
    }catch(_e){ HostBerry.showAlert('danger', HostBerry.t('errors.network_error')); }
  }

  async function restartHostAPD(){
    try{
      const resp = await fetch('/api/v1/hostapd/restart', { method:'POST', headers:{ 'Authorization': `Bearer ${localStorage.getItem('access_token')}` }});
      if(resp.ok){ HostBerry.showAlert('success', HostBerry.t('messages.operation_successful')); setTimeout(()=>window.location.reload(), 2000); }
      else { HostBerry.showAlert('danger', HostBerry.t('errors.operation_failed')); }
    }catch(_e){ HostBerry.showAlert('danger', HostBerry.t('errors.network_error')); }
  }

  function configureAccessPoint(apName){
    alert(HostBerry.t('hostapd.configuring_access_point','Configurando punto de acceso')+': '+apName);
  }

  const form = document.getElementById('hostapdConfigForm');
  if(form){
    form.addEventListener('submit', async function(e){
      e.preventDefault();
      const fd = new FormData(this);
      const data = { interface: fd.get('interface'), ssid: fd.get('ssid'), password: fd.get('password'), channel: parseInt(fd.get('channel')), security: fd.get('security') };
      try{
        const resp = await fetch('/api/v1/hostapd/config', { method:'POST', headers:{ 'Content-Type':'application/json', 'Authorization': `Bearer ${localStorage.getItem('access_token')}` }, body: JSON.stringify(data) });
        if(resp.ok){ HostBerry.showAlert('success', HostBerry.t('messages.changes_saved')); }
        else { HostBerry.showAlert('danger', HostBerry.t('errors.configuration_error')); }
      }catch(_e){ HostBerry.showAlert('danger', HostBerry.t('errors.network_error')); }
    });
  }

  document.addEventListener('DOMContentLoaded', function(){
    loadAccessPoints(); loadClients();
    setInterval(function(){ loadAccessPoints(); loadClients(); }, 30000);
  });

  // export para onClick
  window.toggleHostAPD = toggleHostAPD;
  window.restartHostAPD = restartHostAPD;
  window.configureAccessPoint = configureAccessPoint;
})();

