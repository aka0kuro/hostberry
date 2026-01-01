// JS extraído desde templates/wifi.html
(function(){
  async function loadNetworks(){
    try{
      const resp = await fetch('/api/v1/wifi/networks', { headers:{ 'Authorization': `Bearer ${localStorage.getItem('access_token')}` } });
      if(resp.ok){
        const networks = await resp.json();
        const tbody = document.getElementById('networksTable'); if(!tbody) return; tbody.innerHTML='';
        networks.forEach(function(network){
          const tr = document.createElement('tr');
          tr.innerHTML = '<td>'+network.ssid+'</td>'+
            '<td><span class="badge bg-'+getSecurityColor(network.security)+'">'+network.security+'</span></td>'+
            '<td>'+network.signal+' dBm</td>'+
            '<td>'+network.channel+'</td>'+
            '<td><button class="btn btn-sm btn-outline-primary" onclick="connectToNetwork(\''+network.ssid+'\')"><i class="bi bi-wifi"></i></button></td>';
          tbody.appendChild(tr);
        });
      }
    }catch(e){ console.error('Error loading networks:', e); }
  }
  async function loadClients(){
    try{
      const resp = await fetch('/api/v1/wifi/clients', { headers:{ 'Authorization': `Bearer ${localStorage.getItem('access_token')}` } });
      if(resp.ok){
        const clients = await resp.json();
        const tbody = document.getElementById('clientsTable'); if(!tbody) return; tbody.innerHTML='';
        clients.forEach(function(client){
          const tr = document.createElement('tr');
          tr.innerHTML = '<td>'+client.mac_address+'</td><td>'+client.ip_address+'</td><td>'+client.signal+' dBm</td><td>'+client.uptime+'</td>';
          tbody.appendChild(tr);
        });
      }
    }catch(e){ console.error('Error loading clients:', e); }
  }
  function getSecurityColor(security){
    const s = String(security||'').toLowerCase();
    if(s==='wpa3') return 'success'; if(s==='wpa2') return 'primary'; if(s==='wep') return 'warning'; if(s==='open') return 'danger'; return 'secondary';
  }
  async function toggleWiFi(){
    try{ const resp = await fetch('/api/v1/wifi/toggle', { method:'POST', headers:{ 'Authorization': `Bearer ${localStorage.getItem('access_token')}` } });
      if(resp.ok){ HostBerry.showAlert('success', HostBerry.t('messages.operation_successful')); setTimeout(()=>window.location.reload(), 1000); }
      else { HostBerry.showAlert('danger', HostBerry.t('errors.operation_failed')); }
    }catch(_e){ HostBerry.showAlert('danger', HostBerry.t('errors.network_error')); }
  }
  async function scanNetworks(){
    try{ const resp = await fetch('/api/v1/wifi/scan', { method:'POST', headers:{ 'Authorization': `Bearer ${localStorage.getItem('access_token')}` } });
      if(resp.ok){ HostBerry.showAlert('info', HostBerry.t('wifi.scanning_networks')); setTimeout(loadNetworks, 5000); }
      else { HostBerry.showAlert('danger', HostBerry.t('errors.operation_failed')); }
    }catch(_e){ HostBerry.showAlert('danger', HostBerry.t('errors.network_error')); }
  }
  function connectToNetwork(ssid){ alert(HostBerry.t('wifi.connecting_to_network','Conectando a red')+': '+ssid); }
  const wifiConfigForm = document.getElementById('wifiConfigForm');
  if(wifiConfigForm){
    wifiConfigForm.addEventListener('submit', async function(e){
      e.preventDefault(); const fd = new FormData(this);
      const data = { ssid: fd.get('ssid'), password: fd.get('password'), security: fd.get('security'), channel: parseInt(fd.get('channel')), bandwidth: parseInt(fd.get('bandwidth')) };
      try{ const resp = await fetch('/api/v1/wifi/config', { method:'POST', headers:{ 'Content-Type':'application/json', 'Authorization': `Bearer ${localStorage.getItem('access_token')}` }, body: JSON.stringify(data) });
        if(resp.ok){ HostBerry.showAlert('success', HostBerry.t('messages.changes_saved')); }
        else { HostBerry.showAlert('danger', HostBerry.t('errors.configuration_error')); }
      }catch(_e){ HostBerry.showAlert('danger', HostBerry.t('errors.network_error')); }
    });
  }
  document.addEventListener('DOMContentLoaded', function(){ loadNetworks(); loadClients(); setInterval(function(){ loadNetworks(); loadClients(); }, 30000); });
  window.toggleWiFi = toggleWiFi; window.scanNetworks = scanNetworks; window.connectToNetwork = connectToNetwork;
})();

