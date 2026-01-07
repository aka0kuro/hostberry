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
  function getSecurityColor(security){
    const s = String(security||'').toLowerCase();
    if(s==='wpa3') return 'success'; if(s==='wpa2') return 'primary'; if(s==='wep') return 'warning'; if(s==='open') return 'danger'; return 'secondary';
  }
  async function toggleWiFi(){
    try{ 
      const resp = await fetch('/api/v1/wifi/toggle', { method:'POST', headers:{ 'Authorization': `Bearer ${localStorage.getItem('access_token')}` } });
      const data = await resp.json();
      if(resp.ok && data.success){ 
        const showAlert = (window.HostBerry && window.HostBerry.showAlert) || function(type, msg) { alert(msg); };
        const t = (window.HostBerry && window.HostBerry.t) || function(key, def) { return def || key; };
        showAlert('success', t('messages.operation_successful', 'Operación exitosa')); 
        setTimeout(()=>window.location.reload(), 1000); 
      }
      else { 
        const showAlert = (window.HostBerry && window.HostBerry.showAlert) || function(type, msg) { alert(msg); };
        const t = (window.HostBerry && window.HostBerry.t) || function(key, def) { return def || key; };
        const errorMsg = data.error || t('errors.operation_failed', 'Operación fallida');
        showAlert('danger', errorMsg); 
      }
    }catch(e){ 
      const showAlert = (window.HostBerry && window.HostBerry.showAlert) || function(type, msg) { alert(msg); };
      const t = (window.HostBerry && window.HostBerry.t) || function(key, def) { return def || key; };
      showAlert('danger', t('errors.network_error', 'Error de red')); 
      console.error('Error en toggleWiFi:', e);
    }
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

