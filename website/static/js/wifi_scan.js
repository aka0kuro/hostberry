// WiFi Scan Page JavaScript
(function(){
  const HostBerry = window.HostBerry || {};
  
  // API Request helper with authentication
  async function apiRequest(url, options) {
    const opts = Object.assign({ method: 'GET', headers: {} }, options || {});
    const headers = new Headers(opts.headers);
    
    // Auth token
    const token = localStorage.getItem('access_token');
    if (token) {
      headers.set('Authorization', 'Bearer ' + token);
    }
    
    // JSON body handling
    if (opts.body && typeof opts.body === 'object' && !(opts.body instanceof FormData)) {
      if (!headers.has('Content-Type')) {
        headers.set('Content-Type', 'application/json');
      }
      opts.body = JSON.stringify(opts.body);
    }
    
    opts.headers = headers;
    
    try {
      const resp = await fetch(url, opts);
      if (resp.status === 401 && !url.includes('/auth/login')) {
        // Auto logout on unauthorized
        localStorage.removeItem('access_token');
        window.location.href = '/login?error=session_expired';
        return resp;
      }
      return resp;
    } catch (e) {
      console.error('API Request failed:', e);
      throw e;
    }
  }
  
  // Alert helper
  function showAlert(type, message) {
    if (HostBerry.showAlert) {
      HostBerry.showAlert(type, message);
    } else {
      alert(message);
    }
  }
  
  // Translation helper
  function t(key, defaultValue) {
    if (HostBerry.t) {
      return HostBerry.t(key, defaultValue);
    }
    // Fallback: try to get from i18n-json
    try {
      const i18nScript = document.getElementById('i18n-json');
      if (i18nScript) {
        const translations = JSON.parse(i18nScript.textContent);
        const keys = key.split('.');
        let value = translations;
        for (const k of keys) {
          value = value && value[k];
        }
        if (typeof value === 'string') return value;
      }
    } catch (e) {}
    return defaultValue || key;
  }
  
  // Utility functions
  function formatDate(date) {
    return new Date(date).toLocaleString(undefined, { dateStyle: 'short', timeStyle: 'medium' });
  }

  window.currentSSID = null;

  async function loadStatusAndScan(){
    try{
      const resp = await apiRequest('/api/wifi/status');
      if (resp.ok) {
        const data = await resp.json();
        const statusData = data.status || data;
        window.currentSSID = statusData.ssid ? statusData.ssid.trim() : (statusData.current_connection ? statusData.current_connection.trim() : null);
        updateStatusDisplay(statusData);
      } else {
        throw new Error('Failed to load status');
      }
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
      const resp = await apiRequest('/api/wifi/status');
      if (resp.ok) {
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
              disconnectButton.innerHTML = '<i class="bi bi-power me-1"></i>' + t('wifi.disconnect', 'Disconnect');
              if(btn) btn.replaceWith(disconnectButton); else item.querySelector('.d-flex').appendChild(disconnectButton);
            }
          }else{
            if(!btn || !btn.classList.contains('connect-btn')){
              const connectButton = document.createElement('button');
              connectButton.className = 'btn btn-sm btn-outline-primary connect-btn';
              connectButton.dataset.ssid = itemSsid;
              connectButton.dataset.security = originalSecurityType || 'Open';
              connectButton.innerHTML = '<i class="bi bi-wifi me-1"></i>' + t('wifi.connect', 'Connect');
              if(btn) btn.replaceWith(connectButton); else item.querySelector('.d-flex').appendChild(connectButton);
            }
          }
        });
      }
    }catch(error){
      console.error('Error in refreshWifiStatusAndButtons:', error);
      updateStatusDisplay({ enabled:false, connected:false, current_connection:null, soft_blocked:false, hard_blocked:false, error:true });
    }
  }

  function addActivity(type, details){
    const feed = document.getElementById('activity-feed');
    if(!feed) return;
    const now = new Date();
    let icon = 'bi-info-circle', color = 'info', title = t('common.information', 'Information');
    if(type==='scan'){ icon='bi-search'; color='info'; title=t('wifi.network_scan', 'Network Scan'); }
    else if(type==='connect'){ icon='bi-wifi'; color='success'; title=t('wifi.connection', 'Connection'); }
    else if(type==='disconnect'){ icon='bi-power'; color='warning'; title=t('wifi.disconnection', 'Disconnection'); }
    else if(type==='error'){ icon='bi-exclamation-triangle'; color='danger'; title=t('common.error', 'Error'); }

    const el = document.createElement('div');
    el.className = 'activity-item';
    el.innerHTML = '<div class="d-flex align-items-center gap-2">' +
      '<i class="bi ' + icon + ' text-' + color + '"></i>' +
      '<div class="flex-grow-1">' +
      '<div class="fw-bold">' + title + '</div>' + 
      '<div class="text-muted small">' + formatDate(now) + '</div>' + 
      '<div>' + details + '</div>' + 
      '</div></div>';
    feed.insertBefore(el, feed.firstChild);
    while(feed.children.length>10){ feed.removeChild(feed.lastElementChild); }
    saveActivities();
  }

  function saveActivities(){
    const feed = document.getElementById('activity-feed');
    if(!feed) return;
    const activities = Array.from(feed.querySelectorAll('.activity-item')).map(function(item){
      const iconEl = item.querySelector('i');
      const titleEl = item.querySelector('.fw-bold');
      const timeEl = item.querySelector('.text-muted');
      const detailsEl = item.querySelector('.fw-bold')?.nextElementSibling?.nextElementSibling;
      return {
        icon: iconEl ? iconEl.className : 'bi bi-info-circle',
        title: titleEl ? titleEl.textContent : '',
        time: timeEl ? timeEl.textContent : '',
        details: detailsEl ? detailsEl.textContent : ''
      };
    });
    localStorage.setItem('wifiActivities', JSON.stringify(activities));
  }

  function loadActivities(){
    const feed = document.getElementById('activity-feed');
    if(!feed) return;
    const activities = JSON.parse(localStorage.getItem('wifiActivities') || '[]');
    feed.innerHTML = '';
    if (activities.length === 0) {
      feed.innerHTML = '<div class="text-center py-4"><i class="bi bi-clock-history" style="font-size: 2rem; opacity: 0.5;"></i><p class="mt-2 text-muted">' + t('wifi.no_activity', 'No recent activity') + '</p></div>';
      return;
    }
    activities.forEach(function(a){
      const html = document.createElement('div');
      html.className = 'activity-item';
      html.innerHTML = '<div class="d-flex align-items-center gap-2">' +
        '<i class="' + (a.icon || 'bi bi-info-circle') + '"></i>' +
        '<div class="flex-grow-1">' +
        '<div class="fw-bold">' + a.title + '</div>' +
        '<div class="text-muted small">' + a.time + '</div>' +
        '<div>' + a.details + '</div>' +
        '</div></div>';
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
      const r = await apiRequest('/api/wifi/stored_networks');
      if (r.ok) {
        const d = await r.json();
        if(d.success){
          window.savedNetworks = d.networks || [];
          window.lastConnected = d.last_connected || [];
        }
      }
    }catch(_e){
      window.savedNetworks = [];
      window.lastConnected = [];
    }
  }

  async function attemptAutoConnect(){
    try{
      const sR = await apiRequest('/api/wifi/status');
      if (sR.ok) {
        const sD = await sR.json();
        if(sD.connected && sD.current_connection){ return; }
        const r = await apiRequest('/api/wifi/autoconnect');
        if (r.ok) {
          const d = await r.json();
          if(d.success){
            showAlert('success', t('wifi.auto_connected', 'Auto-connected to') + ' ' + d.ssid);
            addActivity('connect', t('wifi.auto_connected', 'Auto-connected to') + ' ' + d.ssid);
            await loadStatusAndScan();
          }
        }
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
    const enableWifiBtnTopContainer = document.getElementById('enableWifiBtnTopContainer');
    const enableWifiBtnInline = document.getElementById('enableWifiBtnInline');

    function setText(el, txt){ if(el) el.textContent = txt; }
    function swapAlert(kind, text){ 
      if(!alertEl) return; 
      alertEl.classList.add('d-none'); 
      alertEl.classList.remove('alert-success','alert-danger','alert-warning','alert-info'); 
      if(kind){ 
        alertEl.classList.remove('d-none'); 
        alertEl.classList.add('alert-'+kind); 
        const inline = alertEl.querySelector('#wifiStatusTextInline'); 
        if(inline) inline.textContent = text; 
      } 
    }

    // Mostrar/ocultar botones de habilitar WiFi
    if(!isEnabled || isBlocked){
      if(enableWifiBtnTopContainer) enableWifiBtnTopContainer.style.display = 'block';
      if(enableWifiBtnInline) enableWifiBtnInline.classList.remove('d-none');
    } else {
      if(enableWifiBtnTopContainer) enableWifiBtnTopContainer.style.display = 'none';
      if(enableWifiBtnInline) enableWifiBtnInline.classList.add('d-none');
    }

    let text = t('wifi.enabled', 'Enabled'), cls = 'text-info';
    if(isBlocked){ text=t('wifi.blocked', 'Blocked'); cls='text-danger'; swapAlert('danger', t('wifi.wifi_blocked', 'WiFi is blocked.')); }
    else if(!isEnabled){ text=t('wifi.disabled', 'Disabled'); cls='text-warning'; swapAlert('warning', t('wifi.wifi_disabled', 'WiFi is disabled.')); }
    else if(isConnected){ text=t('wifi.connected', 'Connected'); cls='text-success'; swapAlert(null,''); }
    else { text=t('wifi.enabled', 'Enabled'); cls='text-info'; swapAlert('info', t('wifi.wifi_enabled_not_connected', 'WiFi is enabled but not connected.')); }
    if(statusData.error){ text=t('common.error', 'Error'); cls='text-danger'; swapAlert('danger', t('wifi.status_error', 'Error fetching WiFi status.')); }

    if(wifiStatusTextEl){ wifiStatusTextEl.className = cls; setText(wifiStatusTextEl, text); }
    if(wifiStatusTextCardEl){ wifiStatusTextCardEl.className = cls; setText(wifiStatusTextCardEl,text); }

    const currentConnectionEl = document.getElementById('currentConnection');
    if(currentConnectionEl){
      if(isConnected && (statusData.current_connection || statusData.ssid)){
        let c = statusData.current_connection || statusData.ssid;
        if(statusData.connection_info && statusData.connection_info.signal){
          const s = parseInt(statusData.connection_info.signal,10);
          let q = '';
          if(s>=80) q=t('wifi.excellent', 'Excellent'); else if(s>=60) q=t('wifi.good', 'Good'); else if(s>=40) q=t('wifi.fair', 'Fair'); else q=t('wifi.weak', 'Weak');
          c += ` (${q} - ${s}%)`;
        } else if(statusData.signal){
          c += ` (${statusData.signal})`;
        }
        setText(currentConnectionEl,c);
      } else if(statusData.error){ setText(currentConnectionEl, t('common.error', 'Error')); }
      else { setText(currentConnectionEl, t('wifi.not_connected', 'Not connected')); }
    }
  }

  function updateNetworkList(networks){
    const list = document.getElementById('network-list');
    if(!list) return;
    list.innerHTML = '';
    const countEl = document.getElementById('networksCount');
    if(countEl) countEl.textContent = networks.length;
    if(!networks.length){
      list.innerHTML = '<div class="list-group-item text-warning text-center"><i class="bi bi-wifi-off me-2"></i>' + t('wifi.no_networks', 'No WiFi networks found.') + '</div>';
      return;
    }
    networks.sort(function(a,b){ return parseInt(b.signal,10)-parseInt(a.signal,10); });
    const currentConnectedSSID = (window.currentSSID || '').trim();
    networks.forEach(function(network){
      const signalStrength = parseInt(network.signal,10);
      const signalClass = signalStrength>70 ? 'text-success' : (signalStrength>40 ? 'text-warning' : 'text-danger');
      let securityType = 'Open'; let securityIcon = 'bi-unlock';
      if(network.security && network.security.toLowerCase() !== 'open' && network.security.toLowerCase() !== ''){
        const secLower = network.security.toLowerCase();
        if(secLower.includes('wpa3')) securityType='WPA3';
        else if(secLower.includes('wpa2')) securityType='WPA2';
        else if(secLower.includes('wpa')) securityType='WPA';
        else if(secLower.includes('wep')) securityType='WEP';
        else securityType = network.security.split('/')[0].toUpperCase();
        securityIcon = 'bi-lock';
      }
      const networkSSID = (network.ssid || t('wifi.hidden_network', 'Hidden Network')).trim();
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
        +(isSavedNetwork ? '<i class="bi bi-bookmark text-info ms-1" title="' + t('wifi.saved_network', 'Saved network") + '"></i>' : '')
        +(isLastNetwork ? '<i class="bi bi-clock-history text-success ms-1" title="' + t('wifi.last_connected', 'Last connected network") + '"></i>' : '')
        +'</h6>'
        +'<div class="d-flex align-items-center mt-1">'
        +'<small class="ms-2"><i class="bi '+securityIcon+' me-1"></i>'+securityType+'</small>'
        +'<small class="'+signalClass+' ms-2"><i class="bi bi-signal me-1"></i>'+signalStrength+'%</small>'
        +(isSavedNetwork ? '<small class="text-info ms-2"><i class="bi bi-key me-1"></i>' + t('wifi.password_saved', 'Password saved") + '</small>' : '')
        +'</div>'
        +'</div>'
        +(isConnectedToThisNetwork
          ? '<button class="btn btn-sm btn-danger disconnect-btn" data-ssid="'+networkSSID+'"><i class="bi bi-power me-1"></i>' + t('wifi.disconnect', 'Disconnect') + '</button>'
          : '<button class="btn btn-sm btn-outline-primary connect-btn" data-ssid="'+networkSSID+'" data-security="'+securityType+'"><i class="bi bi-wifi me-1"></i>' + t('wifi.connect', 'Connect') + '</button>'
        )
        +'</div>';
      list.appendChild(wrapper);
    });
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
        icon.classList.toggle('bi-eye');
        icon.classList.toggle('bi-eye-slash');
      });
    }

    const rescanBtn = document.getElementById('rescanBtn');
    if(rescanBtn){
      rescanBtn.addEventListener('click', async function(){
        const btn = rescanBtn;
        const originalHtml = btn.innerHTML;
        btn.disabled = true; 
        btn.innerHTML = '<span class="spinning"><i class="bi bi-arrow-clockwise"></i></span> ' + t('wifi.scanning', 'Scanning...');
        const networkList = document.getElementById('network-list');
        if(networkList){
          networkList.innerHTML = '<div class="list-group-item text-center"><div class="spinning mb-2"><i class="bi bi-arrow-clockwise"></i></div><p class="mb-1">' + t('wifi.scanning_networks', 'Scanning for WiFi networks...") + '</p><small class="text-muted">' + t('wifi.scan_time', 'This may take 10-15 seconds") + '</small></div>';
        }
        try{
          const controller = new AbortController();
          const timeoutId = setTimeout(function(){ controller.abort(); }, 20000);
          const resp = await apiRequest('/api/wifi/scan', { signal: controller.signal });
          clearTimeout(timeoutId);
          if(!resp.ok){
            const errData = await resp.json().catch(function(){ return {}; });
            throw new Error(errData.error || ('Error '+resp.status+': '+resp.statusText));
          }
          const data = await resp.json();
          if(!data.success){ throw new Error(data.error || t('errors.server_error', 'Server did not return valid results')); }
          updateNetworkList(data.networks || []);
          if(data.networks && data.networks.length>0){
            addActivity('scan', t('wifi.found_networks', 'Found {count} networks').replace('{count}', data.networks.length));
          } else {
            addActivity('scan', t('wifi.no_networks_scan', 'No networks found during scan.'));
          }
        }catch(error){
          let msg = error.message;
          let icon = 'bi-exclamation-triangle';
          if(error.name === 'AbortError'){ msg = t('wifi.scan_timeout', 'Scan timed out. Please try again.'); icon = 'bi-clock'; }
          else if((msg||'').includes('Failed to fetch')){ msg = t('errors.connection_error', 'Connection error with the server.'); icon = 'bi-wifi-off'; }
          if(networkList){
            networkList.innerHTML = '<div class="list-group-item text-center text-danger"><i class="bi '+icon+' mb-2" style="font-size: 2rem;"></i><h5>'+msg+'</h5><button class="btn btn-sm btn-outline-secondary mt-2" id="retryScan">' + t('common.retry', 'Retry") + '</button></div>';
            const retry = document.getElementById('retryScan');
            if(retry){ retry.addEventListener('click', function(){ rescanBtn.click(); }); }
          }
          addActivity('error', t('wifi.scan_failed', 'Scan failed:') + ' ' + msg);
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
        const modal = document.getElementById('connectModal');
        const ssidInput = document.getElementById('connectSSID');
        const ssidHidden = document.getElementById('connectSSIDHidden');
        const securityInput = document.getElementById('connectSecurity');
        const securityHidden = document.getElementById('connectSecurityHidden');
        const passwordField = document.getElementById('passwordField');
        
        if(ssidInput) ssidInput.value = ssid;
        if(ssidHidden) ssidHidden.value = ssid;
        if(securityInput) securityInput.value = security;
        if(securityHidden) securityHidden.value = security;
        
        if(security === 'Open' && passwordField) {
          passwordField.style.display = 'none';
          document.getElementById('connectPassword').required = false;
        } else if(passwordField) {
          passwordField.style.display = 'block';
          document.getElementById('connectPassword').required = true;
        }
        
        if(modal) {
          const bsModal = new bootstrap.Modal(modal);
          bsModal.show();
        }
      } else if(disconnectBtn){
        const ssid = disconnectBtn.getAttribute('data-ssid');
        const confirmMsg = t('wifi.disconnect_confirm', 'Are you sure you want to disconnect from {ssid}?').replace('{ssid}', ssid);
        if(confirm(confirmMsg)){
          disconnectBtn.disabled = true; 
          disconnectBtn.innerHTML = '<span class="spinning"><i class="bi bi-arrow-clockwise"></i></span> ' + t('wifi.disconnecting', 'Disconnecting...');
          try{
            const resp = await apiRequest('/api/wifi/disconnect', { 
              method:'POST', 
              body: { ssid: ssid } 
            });
            if (resp.ok) {
              const json = await resp.json();
              if(json.success){
                showAlert('success', t('wifi.disconnected_from', 'Disconnected from") + ' ' + ssid);
                addActivity('disconnect', t('wifi.disconnected_from', 'Disconnected from") + ' ' + ssid);
                await loadStatusAndScan();
              } else {
                throw new Error(json.error || t('errors.disconnect_error', 'Error disconnecting.'));
              }
            } else {
              throw new Error(t('errors.disconnect_error', 'Error disconnecting.'));
            }
          }catch(error){
            showAlert('danger', error.message || t('common.error', 'Error'));
            disconnectBtn.disabled = false; 
            disconnectBtn.innerHTML = '<i class="bi bi-power me-1"></i>' + t('wifi.disconnect', 'Disconnect');
          }
        }
      }
    });

    const wifiConnectForm = document.getElementById('wifiConnectForm');
    if(wifiConnectForm){
      wifiConnectForm.addEventListener('submit', async function(e){
        e.preventDefault();
        const ssid = document.getElementById('connectSSIDHidden')?.value || document.getElementById('connectSSID')?.value;
        const password = document.getElementById('connectPassword')?.value || '';
        const security = document.getElementById('connectSecurityHidden')?.value || document.getElementById('connectSecurity')?.value;
        const saveCredentials = document.getElementById('saveCredentials')?.checked || false;
        const submitBtn = document.getElementById('connectSubmitBtn');
        
        if(security !== 'Open' && !password){ 
          showAlert('danger', t('wifi.password_required', 'Please enter the network password.')); 
          return; 
        }
        
        if(submitBtn) {
          submitBtn.disabled = true;
          submitBtn.innerHTML = '<span class="spinning"><i class="bi bi-arrow-clockwise"></i></span> ' + t('wifi.connecting', 'Connecting...');
        }
        
        try{
          const controller = new AbortController();
          const timeoutId = setTimeout(function(){ controller.abort(); }, 30000);
          const resp = await apiRequest('/api/wifi/connect', {
            method: 'POST',
            body: { ssid: ssid, password: password, security: security, save_credentials: saveCredentials },
            signal: controller.signal
          });
          clearTimeout(timeoutId);
          if (resp.ok) {
            const json = await resp.json();
            if(json.success){
              localStorage.setItem('connection_start_'+ssid, String(Date.now()));
              showAlert('success', t('wifi.connected_to', 'Connected to") + ' ' + ssid + '!');
              addActivity('connect', t('wifi.connected_to', 'Connected to") + ' ' + ssid);
              const modal = bootstrap.Modal.getInstance(document.getElementById('connectModal'));
              if(modal) modal.hide();
              setTimeout(function(){ 
                refreshWifiStatusAndButtons(); 
                setTimeout(function(){ 
                  const rescan = document.getElementById('rescanBtn'); 
                  if(rescan) rescan.click(); 
                }, 3000); 
              }, 2000);
            }else{
              throw new Error(json.error || t('errors.connection_failed', 'Error connecting to network.'));
            }
          } else {
            const errData = await resp.json().catch(() => ({}));
            throw new Error(errData.error || t('errors.connection_failed', 'Error connecting to network.'));
          }
        }catch(error){
          let msg = error.message;
          if(error.name==='AbortError'){ msg = t('wifi.connection_timeout', 'Connection timeout. The server took too long to respond.'); }
          else if((msg||'').includes('Failed to fetch')){ msg = t('errors.network_error', 'Network error. Try again in a few seconds.'); }
          showAlert('danger', msg);
          addActivity('error', t('wifi.connect_failed', 'Failed to connect to") + ' ' + ssid + ': ' + msg);
        } finally {
          if(submitBtn) {
            submitBtn.disabled = false;
            submitBtn.innerHTML = '<i class="bi bi-wifi me-2"></i>' + t('wifi.connect_now', 'Connect Now');
          }
        }
      });
    }

    const clearHistoryBtn = document.getElementById('clearHistoryBtn');
    if(clearHistoryBtn){
      clearHistoryBtn.addEventListener('click', function(){
        const confirmMsg = t('wifi.clear_history_confirm', 'Are you sure you want to clear the activity history?');
        if(confirm(confirmMsg)){
          const feed = document.getElementById('activity-feed');
          if(feed){ feed.innerHTML = '<div class="text-center py-4"><i class="bi bi-clock-history" style="font-size: 2rem; opacity: 0.5;"></i><p class="mt-2 text-muted">' + t('wifi.no_activity', 'No recent activity") + '</p></div>'; }
          localStorage.removeItem('wifiActivities');
          addActivity('info', t('wifi.history_cleared', 'Activity log cleared.'));
        }
      });
    }

    const enableWifiBtnTop = document.getElementById('enableWifiBtnTop');
    const enableWifiBtnInline = document.getElementById('enableWifiBtnInline');
    function enableWifi(btn){
      const original = btn.innerHTML; 
      btn.disabled = true; 
      btn.innerHTML = '<span class="spinning"><i class="bi bi-arrow-clockwise"></i></span> ' + t('wifi.enabling', 'Enabling...');
      apiRequest('/api/v1/wifi/toggle', { method:'POST' })
        .then(async function(r){ 
          if (r.ok) {
            const j = await r.json();
            if(j.success){ 
              showAlert('success', t('wifi.wifi_enabled_success', 'WiFi enabled successfully!")); 
              await loadStatusAndScan(); 
            } else { 
              showAlert('danger', j.error || t('errors.enable_error', 'Error enabling WiFi.')); 
              btn.disabled=false; 
              btn.innerHTML=original; 
            }
          } else {
            showAlert('danger', t('errors.server_error', 'Server error enabling WiFi interface.')); 
            btn.disabled=false; 
            btn.innerHTML=original;
          }
        })
        .catch(function(){ 
          showAlert('danger', t('errors.server_error', 'Server error enabling WiFi interface.')); 
          btn.disabled=false; 
          btn.innerHTML=original; 
        });
    }
    if(enableWifiBtnTop){ enableWifiBtnTop.addEventListener('click', function(){ enableWifi(enableWifiBtnTop); }); }
    if(enableWifiBtnInline){ enableWifiBtnInline.addEventListener('click', function(){ enableWifi(enableWifiBtnInline); }); }

    loadSavedNetworks();
    attemptAutoConnect();
  });
})();
