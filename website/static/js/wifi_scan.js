// JS extraído desde templates/wifi_scan.html para uso offline
(function(){
  // utilidades locales
  function getCSRFToken(){
    const meta = document.querySelector('meta[name="csrf-token"]');
    return meta ? meta.getAttribute('content') : null;
  }
  function getCookie(name){
    const value = `; ${document.cookie}`;
    const parts = value.split(`; ${name}=`);
    if(parts.length === 2) return parts.pop().split(';').shift();
    return null;
  }
  function formatDate(date){
    return new Date(date).toLocaleString(undefined, { dateStyle: 'short', timeStyle: 'medium' });
  }

  window.currentSSID = null;

  async function loadStatusAndScan(){
    try{
      const resp = await fetch('/api/wifi/status');
      const data = await resp.json();
      const statusData = data.status || data;
      window.currentSSID = statusData.ssid ? statusData.ssid.trim() : (statusData.current_connection ? statusData.current_connection.trim() : null);
      updateStatusDisplay(statusData);
    }catch(e){
      console.error('Error fetching initial status:', e);
      window.currentSSID = null;
      updateStatusDisplay({ enabled:false, connected:false, current_connection:null, soft_blocked:false, hard_blocked:false });
    }
    const rescanBtn = document.getElementById('rescanBtn');
    if(rescanBtn){ rescanBtn.click(); }
  }

  async function refreshWifiStatusAndButtons(){
    try{
      const resp = await fetch('/api/wifi/status');
      const data = await resp.json();
      const statusData = data.status || data;
      const newSSID = statusData.ssid ? statusData.ssid.trim() : (statusData.current_connection ? statusData.current_connection.trim() : null);
      if(window.currentSSID !== newSSID){ window.currentSSID = newSSID; }
      updateStatusDisplay(statusData);

      document.querySelectorAll('.list-group-item').forEach(function(item){
        const itemSsid = item.getAttribute('data-ssid-name');
        const originalSecurityType = item.getAttribute('data-original-security');
        const btn = item.querySelector('.connect-btn, .disconnect-btn');
        const isConnectedItem = window.currentSSID && itemSsid && window.currentSSID === itemSsid;
        if(isConnectedItem){
          if(!btn || !btn.classList.contains('disconnect-btn')){
            const disconnectButton = document.createElement('button');
            disconnectButton.className = 'btn btn-sm btn-danger disconnect-btn';
            disconnectButton.dataset.ssid = itemSsid;
            disconnectButton.innerHTML = '<i class="fas fa-power-off me-1"></i> Disconnect';
            if(btn) btn.replaceWith(disconnectButton); else item.querySelector('.d-flex').appendChild(disconnectButton);
          }
        }else{
          if(!btn || !btn.classList.contains('connect-btn')){
            const connectButton = document.createElement('button');
            connectButton.className = 'btn btn-sm btn-outline-primary connect-btn';
            connectButton.dataset.ssid = itemSsid;
            connectButton.dataset.security = originalSecurityType || 'Open';
            connectButton.innerHTML = '<i class="fas fa-plug me-1"></i> Connect';
            if(btn) btn.replaceWith(connectButton); else item.querySelector('.d-flex').appendChild(connectButton);
          }
        }
      });

    }catch(error){
      console.error('Error in refreshWifiStatusAndButtons:', error);
      updateStatusDisplay({ enabled:false, connected:false, current_connection:null, soft_blocked:false, hard_blocked:false, error:true });
    }
  }

  function addActivity(type, details){
    const feed = document.getElementById('activity-feed');
    if(!feed) return;
    const now = new Date();
    let icon = 'fa-info-circle', color = 'info', title = 'Information';
    if(type==='scan'){ icon='fa-search'; color='info'; title='Network Scan'; }
    else if(type==='connect'){ icon='fa-plug'; color='success'; title='Connection'; }
    else if(type==='disconnect'){ icon='fa-power-off'; color='warning'; title='Disconnection'; }
    else if(type==='error'){ icon='fa-exclamation-triangle'; color='danger'; title='Error'; }

    const el = document.createElement('div');
    el.className = 'activity-item';
    el.innerHTML = '<div class="activity-badge '+color+'"><i class="fas '+icon+'"></i></div>'+
      '<div class="activity-content">'+
      '<div class="font-weight-bold">'+title+'</div>'+ 
      '<div class="text-muted small">'+formatDate(now)+'</div>'+ 
      '<div>'+details+'</div>'+ 
      '</div>';
    feed.prepend(el);
    while(feed.children.length>10){ feed.removeChild(feed.lastElementChild); }
    saveActivities();
  }

  function saveActivities(){
    const feed = document.getElementById('activity-feed');
    if(!feed) return;
    const activities = Array.from(feed.querySelectorAll('.activity-item')).map(function(item){
      return {
        type: (item.querySelector('.activity-badge')?.className.split(' ')[1]) || 'info',
        icon: (item.querySelector('.activity-badge i')?.className) || 'fas fa-info-circle',
        title: item.querySelector('.font-weight-bold')?.textContent || '',
        time: item.querySelector('.text-muted')?.textContent || '',
        details: item.querySelector('.activity-content div:last-child')?.textContent || ''
      };
    });
    localStorage.setItem('wifiActivities', JSON.stringify(activities));
  }

  function loadActivities(){
    const feed = document.getElementById('activity-feed');
    if(!feed) return;
    const activities = JSON.parse(localStorage.getItem('wifiActivities') || '[]');
    feed.innerHTML = '';
    activities.forEach(function(a){
      const html = document.createElement('div');
      html.className = 'activity-item';
      html.innerHTML = '<div class="activity-badge '+(a.type||'info')+'"><i class="'+(a.icon||'fas fa-info-circle')+'"></i></div>'+
        '<div class="activity-content">'+
        '<div class="font-weight-bold">'+a.title+'</div>'+
        '<div class="text-muted small">'+a.time+'</div>'+
        '<div>'+a.details+'</div>'+
        '</div>';
      feed.appendChild(html);
    });
  }

  function calculateConnectionDuration(ssid){
    const start = localStorage.getItem('connection_start_'+ssid);
    if(!start) return '-';
    const duration = Math.floor((Date.now() - parseInt(start,10)) / 1000);
    const hours = Math.floor(duration/3600);
    const minutes = Math.floor((duration%3600)/60);
    const seconds = duration%60;
    return hours+'h '+minutes+'m '+seconds+'s';
  }

  async function loadSavedNetworks(){
    try{
      const r = await fetch('/api/wifi/stored_networks');
      const d = await r.json();
      if(d.success){
        window.savedNetworks = d.networks || [];
        window.lastConnected = d.last_connected || [];
      }
    }catch(_e){
      window.savedNetworks = [];
      window.lastConnected = [];
    }
  }

  async function attemptAutoConnect(){
    try{
      const sR = await fetch('/api/wifi/status');
      const sD = await sR.json();
      if(sD.connected && sD.current_connection){ return; }
      const r = await fetch('/api/wifi/autoconnect');
      const d = await r.json();
      if(d.success){
        HostBerry.showAlert('success', 'Auto-connected to '+d.ssid);
        addActivity('connect','Auto-connected to '+d.ssid);
        await loadStatusAndScan();
      }
    }catch(_e){ }
  }

  function updateStatusDisplay(statusData){
    const isConnected = statusData.connected || statusData.current_connection;
    const isEnabled = statusData.enabled;
    const isBlocked = statusData.hard_blocked || statusData.soft_blocked;
    const wifiStatusTextEl = document.getElementById('wifiStatusText');
    const wifiStatusTextCardEl = document.getElementById('wifiStatusTextCard');
    const alertEl = document.getElementById('wifiStatusAlert');

    function setText(el, txt){ if(el) el.textContent = txt; }
    function swapAlert(kind, text){ if(!alertEl) return; alertEl.classList.add('d-none'); alertEl.classList.remove('alert-success','alert-danger','alert-warning','alert-info'); if(kind){ alertEl.classList.remove('d-none'); alertEl.classList.add('alert-'+kind); const inline = alertEl.querySelector('#wifiStatusTextInline'); if(inline) inline.textContent = text; } }

    let text = 'Enabled', cls = 'text-info';
    if(isBlocked){ text='Blocked'; cls='text-danger'; swapAlert('danger','WiFi is blocked.'); }
    else if(!isEnabled){ text='Disabled'; cls='text-warning'; swapAlert('warning','WiFi is disabled.'); }
    else if(isConnected){ text='Connected'; cls='text-success'; swapAlert(null,''); }
    else { text='Enabled'; cls='text-info'; swapAlert('info','WiFi is enabled but not connected.'); }
    if(statusData.error){ text='Error'; cls='text-danger'; swapAlert('danger','Error fetching WiFi status.'); }

    if(wifiStatusTextEl){ wifiStatusTextEl.className = cls; setText(wifiStatusTextEl, text); }
    if(wifiStatusTextCardEl){ wifiStatusTextCardEl.className = cls; setText(wifiStatusTextCardEl,text); }

    const currentConnectionEl = document.getElementById('currentConnection');
    if(currentConnectionEl){
      if(isConnected && (statusData.current_connection || statusData.ssid)){
        let c = statusData.current_connection || statusData.ssid;
        if(statusData.connection_info && statusData.connection_info.signal){
          const s = parseInt(statusData.connection_info.signal,10);
          let q = '';
          if(s>=80) q='Excelente'; else if(s>=60) q='Buena'; else if(s>=40) q='Regular'; else q='Débil';
          c += ` (${q} - ${s}%)`;
        } else if(statusData.signal){
          c += ` (${statusData.signal})`;
        }
        setText(currentConnectionEl,c);
      } else if(statusData.error){ setText(currentConnectionEl,'Error'); }
      else { setText(currentConnectionEl,'Not connected'); }
    }
  }

  function updateNetworkList(networks){
    const list = document.getElementById('network-list');
    if(!list) return;
    list.innerHTML = '';
    const countEl = document.getElementById('networksCount');
    if(countEl) countEl.textContent = networks.length;
    if(!networks.length){
      list.innerHTML = '<div class="list-group-item text-warning text-center"><i class="fas fa-wifi-slash me-2"></i>No WiFi networks found.</div>';
      return;
    }
    networks.sort(function(a,b){ return parseInt(b.signal,10)-parseInt(a.signal,10); });
    const currentConnectedSSID = (window.currentSSID || '').trim();
    networks.forEach(function(network){
      const signalStrength = parseInt(network.signal,10);
      const signalClass = signalStrength>70 ? 'text-success' : (signalStrength>40 ? 'text-warning' : 'text-danger');
      let securityType = 'Open'; let securityIcon = 'fa-unlock';
      if(network.security && network.security.toLowerCase() !== 'open' && network.security.toLowerCase() !== ''){
        const secLower = network.security.toLowerCase();
        if(secLower.includes('wpa3')) securityType='WPA3';
        else if(secLower.includes('wpa2')) securityType='WPA2';
        else if(secLower.includes('wpa')) securityType='WPA';
        else if(secLower.includes('wep')) securityType='WEP';
        else securityType = network.security.split('/')[0].toUpperCase();
        securityIcon = 'fa-lock';
      }
      const networkSSID = (network.ssid || 'Hidden Network').trim();
      const isConnectedToThisNetwork = currentConnectedSSID && networkSSID && (currentConnectedSSID === networkSSID);
      const isSavedNetwork = Array.isArray(window.savedNetworks) && window.savedNetworks.some(function(sn){ return sn.ssid === networkSSID; });
      const isLastNetwork = Array.isArray(window.lastConnected) && window.lastConnected.length>0 && window.lastConnected[0] === networkSSID;

      const wrapper = document.createElement('div');
      wrapper.className = 'list-group-item list-group-item-action';
      wrapper.setAttribute('data-original-security', securityType);
      wrapper.setAttribute('data-ssid-name', networkSSID);
      wrapper.innerHTML = '<div class="d-flex w-100 justify-content-between align-items-center">'
        +'<div>'
        +'<h6 class="mb-1 d-inline-block">'+networkSSID
        +(isSavedNetwork ? '<i class="fas fa-bookmark text-info ms-1" title="Saved network"></i>' : '')
        +(isLastNetwork ? '<i class="fas fa-history text-success ms-1" title="Last connected network"></i>' : '')
        +'</h6>'
        +'<div class="d-flex align-items-center mt-1">'
        +'<small class="ms-2"><i class="fas '+securityIcon+' me-1"></i>'+securityType+'</small>'
        +'<small class="'+signalClass+' ms-2"><i class="fas fa-signal me-1"></i>'+signalStrength+'%</small>'
        +(isSavedNetwork ? '<small class="text-info ms-2"><i class="fas fa-key me-1"></i>Password saved</small>' : '')
        +'</div>'
        +'</div>'
        +(isConnectedToThisNetwork
          ? '<button class="btn btn-sm btn-danger disconnect-btn" data-ssid="'+networkSSID+'"><i class="fas fa-power-off me-1"></i>Disconnect</button>'
          : '<button class="btn btn-sm btn-outline-primary connect-btn" data-ssid="'+networkSSID+'" data-security="'+securityType+'"><i class="fas fa-plug me-1"></i>Connect</button>'
        )
        +'</div>';
      list.appendChild(wrapper);
    });
  }

  function showToast(message, type){
    HostBerry.showAlert(type==='success'?'success':(type==='danger'?'danger':(type==='warning'?'warning':'info')), message);
  }

  document.addEventListener('DOMContentLoaded', function(){
    loadActivities();
    loadStatusAndScan();
    setInterval(refreshWifiStatusAndButtons, 5000);

    const togglePwd = document.getElementById('togglePwd');
    if(togglePwd){
      togglePwd.addEventListener('click', function(){
        const input = document.getElementById('connectPassword');
        const icon = document.getElementById('togglePwdIcon');
        if(!input || !icon) return;
        const isPass = input.getAttribute('type') === 'password';
        input.setAttribute('type', isPass ? 'text' : 'password');
        icon.classList.toggle('fa-eye');
        icon.classList.toggle('fa-eye-slash');
      });
    }

    const rescanBtn = document.getElementById('rescanBtn');
    if(rescanBtn){
      rescanBtn.addEventListener('click', async function(){
        const btn = rescanBtn;
        const originalHtml = btn.innerHTML;
        btn.disabled = true; btn.innerHTML = '<i class="fas fa-spinner fa-spin me-1"></i> Scanning...';
        const networkList = document.getElementById('network-list');
        if(networkList){
          networkList.innerHTML = '<div class="list-group-item text-center"><div class="spinner-border text-primary mb-2" role="status"><span class="visually-hidden">Loading...</span></div><p class="mb-1">Scanning for WiFi networks...</p><small class="text-muted">This may take 10-15 seconds</small></div>';
        }
        try{
          const controller = new AbortController();
          const timeoutId = setTimeout(function(){ controller.abort(); }, 20000);
          const resp = await fetch('/api/wifi/scan', { signal: controller.signal });
          clearTimeout(timeoutId);
          if(!resp.ok){
            const errData = await resp.json().catch(function(){ return {}; });
            throw new Error(errData.error || ('Error '+resp.status+': '+resp.statusText));
          }
          const data = await resp.json();
          if(!data.success){ throw new Error(data.error || 'Server did not return valid results'); }
          updateNetworkList(data.networks || []);
          if(data.networks && data.networks.length>0){
            const strongest = Math.max.apply(null, data.networks.map(function(n){ return parseInt(n.signal,10); }));
            addActivity('scan', 'Found '+data.networks.length+' networks');
          } else {
            addActivity('scan', 'No networks found during scan.');
          }
        }catch(error){
          let msg = error.message;
          let icon = 'fa-exclamation-triangle';
          if(error.name === 'AbortError'){ msg = 'Scan timed out. Please try again.'; icon = 'fa-clock'; }
          else if((msg||'').includes('Failed to fetch')){ msg = 'Connection error with the server.'; icon = 'fa-plug'; }
          if(networkList){
            networkList.innerHTML = '<div class="list-group-item text-center text-danger"><i class="fas '+icon+' fa-2x mb-2"></i><h5>'+msg+'</h5><button class="btn btn-sm btn-outline-secondary mt-2" id="retryScan">Retry</button></div>';
            const retry = document.getElementById('retryScan');
            if(retry){ retry.addEventListener('click', function(){ rescanBtn.click(); }); }
          }
          addActivity('error', 'Scan failed: '+msg);
        } finally {
          btn.disabled = false; btn.innerHTML = originalHtml;
        }
      });
    }

    document.addEventListener('click', async function(e){
      const connectBtn = e.target.closest('.connect-btn');
      const disconnectBtn = e.target.closest('.disconnect-btn');
      if(connectBtn){
        const ssid = connectBtn.getAttribute('data-ssid');
        const security = connectBtn.getAttribute('data-security');
        const pwdInput = document.getElementById('connectPassword');
        const password = pwdInput ? pwdInput.value : '';
        const saveCredentials = document.getElementById('saveCredentials')?.checked || false;
        const csrfToken = (document.querySelector('input[name="csrf_token"]')?.value) || getCSRFToken() || getCookie('csrf_token');
        if(security !== 'Open' && !password){ HostBerry.showAlert('danger','Please enter the network password.'); return; }
        try{
          const controller = new AbortController();
          const timeoutId = setTimeout(function(){ controller.abort(); }, 30000);
          const resp = await fetch('/api/wifi/connect', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'Accept': 'application/json', 'X-CSRFToken': csrfToken },
            body: JSON.stringify({ ssid: ssid, password: password, security: security, save_credentials: saveCredentials }),
            signal: controller.signal,
            credentials: 'same-origin'
          });
          clearTimeout(timeoutId);
          const json = await resp.json();
          if(json.success){
            localStorage.setItem('connection_start_'+ssid, String(Date.now()));
            HostBerry.showAlert('success','Connected to '+ssid+'!');
            addActivity('connect','Connected to '+ssid);
            setTimeout(function(){ refreshWifiStatusAndButtons(); setTimeout(function(){ const rescan = document.getElementById('rescanBtn'); if(rescan) rescan.click(); }, 3000); }, 2000);
          }else{
            throw new Error(json.error || 'Error connecting to network.');
          }
        }catch(error){
          let msg = error.message;
          if(error.name==='AbortError'){ msg = 'Connection timeout. The server took too long to respond.'; }
          else if((msg||'').includes('Failed to fetch')){ msg = 'Network error. Try again in a few seconds.'; }
          HostBerry.showAlert('danger', msg);
          addActivity('error','Failed to connect to '+ssid+': '+msg);
        }
      } else if(disconnectBtn){
        const ssid = disconnectBtn.getAttribute('data-ssid');
        if(confirm('Are you sure you want to disconnect from '+ssid+'?')){
          disconnectBtn.disabled = true; disconnectBtn.innerHTML = '<i class="fas fa-spinner fa-spin me-1"></i> Disconnecting...';
          try{
            const resp = await fetch('/api/wifi/disconnect', { method:'POST', headers:{ 'Content-Type':'application/json', 'Accept':'application/json', 'X-CSRFToken': getCSRFToken() || getCookie('csrf_token') }, body: JSON.stringify({ ssid: ssid }) });
            const json = await resp.json();
            if(json.success){
              HostBerry.showAlert('success','Disconnected from '+ssid);
              addActivity('disconnect','Disconnected from '+ssid, { duration: calculateConnectionDuration(ssid) });
              await loadStatusAndScan();
            } else {
              throw new Error(json.error || 'Error disconnecting.');
            }
          }catch(error){
            HostBerry.showAlert('danger', error.message || 'Error');
            disconnectBtn.disabled = false; disconnectBtn.innerHTML = '<i class="fas fa-power-off me-1"></i> Disconnect';
          }
        }
      }
    });

    const clearHistoryBtn = document.getElementById('clearHistoryBtn');
    if(clearHistoryBtn){
      clearHistoryBtn.addEventListener('click', function(){
        if(confirm('Are you sure you want to clear the activity history?')){
          const feed = document.getElementById('activity-feed');
          if(feed){ feed.innerHTML = ''; }
          localStorage.removeItem('wifiActivities');
          addActivity('info','Activity log cleared.');
        }
      });
    }

    const enableWifiBtnTop = document.getElementById('enableWifiBtnTop');
    const enableWifiBtnInline = document.getElementById('enableWifiBtnInline');
    function enableWifi(btn){
      const original = btn.innerHTML; btn.disabled = true; btn.innerHTML = '<i class="fas fa-spinner fa-spin me-1"></i> Enabling...';
      fetch('/api/v1/wifi/scan', { method:'POST', headers:{ 'X-CSRFToken': getCSRFToken() || getCookie('csrf_token') } })
        .then(function(r){ return r.json(); })
        .then(async function(j){
          if(j.success){ HostBerry.showAlert('success','WiFi enabled successfully!'); await loadStatusAndScan(); }
          else { HostBerry.showAlert('danger', j.error || 'Error enabling WiFi.'); btn.disabled=false; btn.innerHTML=original; }
        })
        .catch(function(){ HostBerry.showAlert('danger','Server error enabling WiFi interface.'); btn.disabled=false; btn.innerHTML=original; });
    }
    if(enableWifiBtnTop){ enableWifiBtnTop.addEventListener('click', function(){ enableWifi(enableWifiBtnTop); }); }
    if(enableWifiBtnInline){ enableWifiBtnInline.addEventListener('click', function(){ enableWifi(enableWifiBtnInline); }); }

    loadSavedNetworks();
    attemptAutoConnect();
  });
})();

