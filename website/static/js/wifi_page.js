// WiFi Page JavaScript
(function(){
  const HostBerry = window.HostBerry || {};
  
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
  
  // Alert helper
  function showAlert(type, message) {
    if (HostBerry.showAlert) {
      HostBerry.showAlert(type, message);
    } else {
      alert(message);
    }
  }
  
  // API Request helper
  async function apiRequest(url, options) {
    const opts = Object.assign({ method: 'GET', headers: {} }, options || {});
    const headers = new Headers(opts.headers);
    
    const token = localStorage.getItem('access_token');
    if (token) {
      headers.set('Authorization', 'Bearer ' + token);
    }
    
    if (opts.body && typeof opts.body === 'object' && !(opts.body instanceof FormData)) {
      if (!headers.has('Content-Type')) {
        headers.set('Content-Type', 'application/json');
      }
      opts.body = JSON.stringify(opts.body);
    }
    
    opts.headers = headers;
    return await fetch(url, opts);
  }
  
  // Load current connection status
  async function loadConnectionStatus() {
    try {
      const resp = await apiRequest('/api/wifi/status');
      const data = await resp.ok ? await resp.json() : null;
      
      const statusEl = document.getElementById('connection-status');
      const ssidEl = document.getElementById('connection-ssid');
      const signalEl = document.getElementById('connection-signal');
      const securityEl = document.getElementById('connection-security');
      const channelEl = document.getElementById('connection-channel');
      const ipEl = document.getElementById('connection-ip');
      
      if (data && data.connected && data.current_connection) {
        statusEl.innerHTML = '<span class="badge bg-success">' + t('wifi.connected', 'Connected') + '</span>';
        ssidEl.textContent = data.current_connection || data.ssid || '--';
        signalEl.textContent = '--';
        securityEl.textContent = '--';
        channelEl.textContent = '--';
        ipEl.textContent = '--';
        
        // Update health indicators
        updateHealthIndicator('wifi-connected-dot', 'wifi-connected-text', true);
      } else {
        statusEl.innerHTML = '<span class="badge bg-danger">' + t('wifi.not_connected', 'Not Connected') + '</span>';
        ssidEl.textContent = t('wifi.no_connection', 'No connection');
        signalEl.textContent = '--';
        securityEl.textContent = '--';
        channelEl.textContent = '--';
        ipEl.textContent = '--';
        
        // Update health indicators
        updateHealthIndicator('wifi-connected-dot', 'wifi-connected-text', false);
      }
      
      // Update WiFi enabled status
      if (data && data.enabled !== undefined) {
        updateHealthIndicator('wifi-enabled-dot', 'wifi-enabled-text', data.enabled);
        updateToggleButton(data.enabled);
      }
    } catch (e) {
      console.error('Error loading connection status:', e);
      document.getElementById('connection-status').innerHTML = '<span class="badge bg-danger">' + t('errors.load_error', 'Error loading') + '</span>';
    }
  }
  
  // Update health indicator
  function updateHealthIndicator(dotId, textId, isActive) {
    const dot = document.getElementById(dotId);
    const text = document.getElementById(textId);
    
    if (dot && text) {
      dot.className = 'health-dot ' + (isActive ? 'health-dot-success' : 'health-dot-danger');
      text.textContent = isActive ? t('common.active', 'Active') : t('common.inactive', 'Inactive');
    }
  }
  
  // Update toggle button
  function updateToggleButton(isEnabled) {
    const btn = document.getElementById('toggle-wifi-btn');
    const text = document.getElementById('toggle-wifi-text');
    
    if (btn && text) {
      if (isEnabled) {
        btn.className = 'btn btn-danger';
        text.textContent = t('wifi.disable_wifi', 'Disable WiFi');
      } else {
        btn.className = 'btn btn-primary';
        text.textContent = t('wifi.enable_wifi', 'Enable WiFi');
      }
    }
  }
  
  // Load available networks
  async function loadNetworks() {
    const loadingEl = document.getElementById('networks-loading');
    const emptyEl = document.getElementById('networks-empty');
    const tableEl = document.getElementById('networks-table-container');
    const tbody = document.getElementById('networksTable');
    
    if (loadingEl) loadingEl.style.display = 'block';
    if (emptyEl) emptyEl.style.display = 'none';
    if (tableEl) tableEl.style.display = 'none';
    if (tbody) tbody.innerHTML = '';
    
    try {
      const resp = await apiRequest('/api/v1/wifi/networks');
      if (resp.ok) {
        const networks = await resp.json();
        
        if (loadingEl) loadingEl.style.display = 'none';
        
        if (!networks || networks.length === 0) {
          if (emptyEl) emptyEl.style.display = 'block';
        } else {
          if (tableEl) tableEl.style.display = 'block';
          if (tbody) {
            networks.forEach(function(network) {
              const tr = document.createElement('tr');
              const security = network.security || 'Open';
              const securityColor = getSecurityColor(security);
              tr.innerHTML = 
                '<td><strong>' + (network.ssid || 'Unknown') + '</strong></td>' +
                '<td><span class="badge bg-' + securityColor + '">' + security + '</span></td>' +
                '<td>' + (network.signal || '--') + ' dBm</td>' +
                '<td>' + (network.channel || '--') + '</td>' +
                '<td><button class="btn btn-sm btn-outline-primary" onclick="connectToNetwork(\'' + (network.ssid || '').replace(/'/g, "\\'") + '\')"><i class="bi bi-wifi"></i> ' + t('wifi.connect', 'Connect') + '</button></td>';
              tbody.appendChild(tr);
            });
          }
        }
      } else {
        if (loadingEl) loadingEl.style.display = 'none';
        if (emptyEl) emptyEl.style.display = 'block';
      }
    } catch (e) {
      console.error('Error loading networks:', e);
      if (loadingEl) loadingEl.style.display = 'none';
      if (emptyEl) emptyEl.style.display = 'block';
    }
  }
  
  // Get security color
  function getSecurityColor(security) {
    const s = String(security || '').toLowerCase();
    if (s === 'wpa3') return 'success';
    if (s === 'wpa2') return 'primary';
    if (s === 'wep') return 'warning';
    if (s === 'open') return 'danger';
    return 'secondary';
  }
  
  // Toggle WiFi
  async function toggleWiFi() {
    try {
      const resp = await apiRequest('/api/v1/wifi/toggle', { method: 'POST' });
      const data = await resp.json();
      
      if (resp.ok && data.success) {
        showAlert('success', t('messages.operation_successful', 'Operation successful'));
        setTimeout(() => {
          loadConnectionStatus();
          loadNetworks();
        }, 1000);
      } else {
        const errorMsg = data.error || t('errors.operation_failed', 'Operation failed');
        showAlert('danger', errorMsg);
      }
    } catch (e) {
      console.error('Error toggling WiFi:', e);
      showAlert('danger', t('errors.network_error', 'Network error'));
    }
  }
  
  // Check WiFi status before scanning
  async function checkWiFiStatus() {
    try {
      const resp = await apiRequest('/api/wifi/status');
      if (resp.ok) {
        const data = await resp.json();
        const statusData = data.status || data;
        return {
          enabled: statusData.enabled !== false,
          blocked: statusData.hard_blocked || statusData.soft_blocked,
          connected: statusData.connected || statusData.current_connection
        };
      }
    } catch (e) {
      console.error('Error checking WiFi status:', e);
    }
    return { enabled: false, blocked: false, connected: false };
  }
  
  // Scan networks
  async function scanNetworks() {
    const loadingEl = document.getElementById('networks-loading');
    const emptyEl = document.getElementById('networks-empty');
    const tableEl = document.getElementById('networks-table-container');
    const tbody = document.getElementById('networksTable');
    const scanBtn = document.getElementById('scan-networks-btn');
    
    // Verificar estado del WiFi primero
    const wifiStatus = await checkWiFiStatus();
    
    if (!wifiStatus.enabled || wifiStatus.blocked) {
      if (emptyEl) {
        emptyEl.innerHTML = 
          '<div class="text-center py-4">' +
          '<i class="bi bi-wifi-off" style="font-size: 3rem; opacity: 0.5;"></i>' +
          '<p class="mt-2">' + t('wifi.wifi_disabled', 'WiFi is disabled') + '</p>' +
          '<p class="text-muted small">' + t('wifi.enable_to_scan', 'Please enable WiFi to scan for networks') + '</p>' +
          '<button class="btn btn-primary mt-3" onclick="toggleWiFi()">' +
          '<i class="bi bi-power me-2"></i>' + t('wifi.enable_wifi', 'Enable WiFi') +
          '</button>' +
          '</div>';
        emptyEl.style.display = 'block';
      }
      if (loadingEl) loadingEl.style.display = 'none';
      if (tableEl) tableEl.style.display = 'none';
      showAlert('warning', t('wifi.wifi_disabled', 'WiFi is disabled. Please enable it first.'));
      return;
    }
    
    if (loadingEl) loadingEl.style.display = 'block';
    if (emptyEl) emptyEl.style.display = 'none';
    if (tableEl) tableEl.style.display = 'none';
    if (tbody) tbody.innerHTML = '';
    
    if (scanBtn) {
      scanBtn.disabled = true;
      const originalHtml = scanBtn.innerHTML;
      scanBtn.innerHTML = '<span class="spinning"><i class="bi bi-arrow-clockwise"></i></span> ' + t('wifi.scanning', 'Scanning...');
      
      try {
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 20000);
        
        const resp = await apiRequest('/api/v1/wifi/scan', { 
          method: 'POST',
          signal: controller.signal
        });
        
        clearTimeout(timeoutId);
        
        if (resp.ok) {
          const data = await resp.json();
          
          if (loadingEl) loadingEl.style.display = 'none';
          
          if (data.success && data.networks && data.networks.length > 0) {
            if (tableEl) tableEl.style.display = 'block';
            if (tbody) {
              // Ordenar por señal (mayor a menor)
              data.networks.sort((a, b) => {
                const signalA = parseInt(a.signal) || 0;
                const signalB = parseInt(b.signal) || 0;
                return signalB - signalA;
              });
              
              data.networks.forEach(function(network) {
                const tr = document.createElement('tr');
                const security = network.security || 'Open';
                const securityColor = getSecurityColor(security);
                const signalStrength = network.signal || 0;
                const signalPercent = Math.min(100, Math.max(0, (signalStrength + 100) * 2)); // Convertir dBm a porcentaje aproximado
                const signalClass = signalPercent > 70 ? 'text-success' : (signalPercent > 40 ? 'text-warning' : 'text-danger');
                
                tr.innerHTML = 
                  '<td><strong>' + (network.ssid || t('wifi.hidden_network', 'Hidden Network')) + '</strong></td>' +
                  '<td><span class="badge bg-' + securityColor + '">' + security + '</span></td>' +
                  '<td><span class="' + signalClass + '"><i class="bi bi-signal"></i> ' + signalStrength + ' dBm</span></td>' +
                  '<td>' + (network.channel || '--') + '</td>' +
                  '<td><button class="btn btn-sm btn-outline-primary connect-network-btn" data-ssid="' + (network.ssid || '').replace(/"/g, '&quot;') + '" data-security="' + (security || 'Open').replace(/"/g, '&quot;') + '"><i class="bi bi-wifi"></i> ' + t('wifi.connect', 'Connect') + '</button></td>';
                tbody.appendChild(tr);
              });
              
              // Agregar event listeners a los botones de conexión
              tbody.querySelectorAll('.connect-network-btn').forEach(function(btn) {
                btn.addEventListener('click', function() {
                  const ssid = btn.getAttribute('data-ssid');
                  const security = btn.getAttribute('data-security');
                  showConnectModal(ssid, security);
                });
              });
            }
            showAlert('success', t('wifi.found_networks', 'Found {count} networks').replace('{count}', data.networks.length));
          } else {
            if (emptyEl) {
              emptyEl.innerHTML = 
                '<div class="text-center py-4">' +
                '<i class="bi bi-wifi-off" style="font-size: 3rem; opacity: 0.5;"></i>' +
                '<p class="mt-2">' + t('wifi.no_networks', 'No networks found') + '</p>' +
                '<p class="text-muted small">' + t('wifi.no_networks_desc', 'No WiFi networks were found in your area. Make sure WiFi is enabled and try again.') + '</p>' +
                '<button class="btn btn-primary mt-3" onclick="scanNetworks()">' +
                '<i class="bi bi-search me-2"></i>' + t('wifi.scan_networks', 'Scan Networks') +
                '</button>' +
                '</div>';
              emptyEl.style.display = 'block';
            }
            showAlert('info', t('wifi.no_networks_scan', 'No networks found during scan.'));
          }
        } else {
          const errorData = await resp.json().catch(() => ({}));
          if (loadingEl) loadingEl.style.display = 'none';
          if (emptyEl) {
            emptyEl.innerHTML = 
              '<div class="text-center py-4">' +
              '<i class="bi bi-exclamation-triangle text-warning" style="font-size: 3rem;"></i>' +
              '<p class="mt-2">' + t('errors.scan_failed', 'Scan failed') + '</p>' +
              '<p class="text-muted small">' + (errorData.error || t('errors.unknown_error', 'Unknown error')) + '</p>' +
              '<button class="btn btn-primary mt-3" onclick="scanNetworks()">' +
              '<i class="bi bi-arrow-clockwise me-2"></i>' + t('common.retry', 'Retry') +
              '</button>' +
              '</div>';
            emptyEl.style.display = 'block';
          }
          if (tableEl) tableEl.style.display = 'none';
          showAlert('danger', errorData.error || t('errors.scan_failed', 'Scan failed'));
        }
      } catch (error) {
        console.error('Error scanning networks:', error);
        if (loadingEl) loadingEl.style.display = 'none';
        if (emptyEl) {
          emptyEl.innerHTML = 
            '<div class="text-center py-4">' +
            '<i class="bi bi-exclamation-triangle text-danger" style="font-size: 3rem;"></i>' +
            '<p class="mt-2">' + t('errors.scan_error', 'Scan error') + '</p>' +
            '<p class="text-muted small">' + error.message + '</p>' +
            '<button class="btn btn-primary mt-3" onclick="scanNetworks()">' +
            '<i class="bi bi-arrow-clockwise me-2"></i>' + t('common.retry', 'Retry') +
            '</button>' +
            '</div>';
          emptyEl.style.display = 'block';
        }
        if (tableEl) tableEl.style.display = 'none';
        
        let msg = error.message;
        if (error.name === 'AbortError') {
          msg = t('wifi.scan_timeout', 'Scan timed out. Please try again.');
        } else if (msg.includes('Failed to fetch')) {
          msg = t('errors.connection_error', 'Connection error with the server.');
        }
        showAlert('danger', msg);
      } finally {
        if (scanBtn) {
          scanBtn.disabled = false;
          scanBtn.innerHTML = originalHtml;
        }
      }
    }
  }
  
  // Show connect modal
  function showConnectModal(ssid, security) {
    const modal = document.getElementById('connectModal');
    const ssidInput = document.getElementById('connectSSID');
    const ssidHidden = document.getElementById('connectSSIDHidden');
    const securityInput = document.getElementById('connectSecurity');
    const securityHidden = document.getElementById('connectSecurityHidden');
    const passwordField = document.getElementById('passwordField');
    const passwordInput = document.getElementById('connectPassword');
    
    if (ssidInput) ssidInput.value = ssid;
    if (ssidHidden) ssidHidden.value = ssid;
    if (securityInput) securityInput.value = security;
    if (securityHidden) securityHidden.value = security;
    
    if (security === 'Open' && passwordField) {
      passwordField.style.display = 'none';
      if (passwordInput) passwordInput.required = false;
    } else if (passwordField) {
      passwordField.style.display = 'block';
      if (passwordInput) {
        passwordInput.required = true;
        passwordInput.value = '';
      }
    }
    
    if (modal) {
      const bsModal = new bootstrap.Modal(modal);
      bsModal.show();
    }
  }
  
  // Connect to network
  async function connectToNetwork(ssid, security, password) {
    try {
      const resp = await apiRequest('/api/v1/wifi/connect', {
        method: 'POST',
        body: { 
          ssid: ssid, 
          password: password || '',
          security: security || 'Open'
        }
      });
      
      const data = await resp.json();
      
      if (resp.ok && data.success) {
        showAlert('success', t('wifi.connecting', 'Connecting to') + ': ' + ssid);
        const modal = bootstrap.Modal.getInstance(document.getElementById('connectModal'));
        if (modal) modal.hide();
        setTimeout(() => {
          loadConnectionStatus();
          scanNetworks();
        }, 2000);
      } else {
        const errorMsg = data.error || t('errors.connection_failed', 'Connection failed');
        showAlert('danger', errorMsg);
      }
    } catch (e) {
      console.error('Error connecting to network:', e);
      showAlert('danger', t('errors.network_error', 'Network error'));
    }
  }
  
  // Refresh handlers
  document.addEventListener('DOMContentLoaded', function() {
    loadConnectionStatus();
    
    // Mostrar mensaje inicial para escanear redes
    const emptyEl = document.getElementById('networks-empty');
    if (emptyEl) emptyEl.style.display = 'block';
    
    // Refresh connection status every 30 seconds
    setInterval(loadConnectionStatus, 30000);
    
    // Manual refresh buttons
    const refreshConnection = document.getElementById('refresh-connection');
    if (refreshConnection) {
      refreshConnection.addEventListener('click', loadConnectionStatus);
    }
    
    const refreshNetworks = document.getElementById('refresh-networks');
    if (refreshNetworks) {
      refreshNetworks.addEventListener('click', scanNetworks);
    }
    
    // Toggle password visibility
    const togglePwd = document.getElementById('togglePwd');
    if (togglePwd) {
      togglePwd.addEventListener('click', function() {
        const input = document.getElementById('connectPassword');
        const icon = document.getElementById('togglePwdIcon');
        if (!input || !icon) return;
        const isPass = input.getAttribute('type') === 'password';
        input.setAttribute('type', isPass ? 'text' : 'password');
        icon.classList.toggle('bi-eye');
        icon.classList.toggle('bi-eye-slash');
      });
    }
    
    // WiFi connect form
    const wifiConnectForm = document.getElementById('wifiConnectForm');
    if (wifiConnectForm) {
      wifiConnectForm.addEventListener('submit', async function(e) {
        e.preventDefault();
        const ssid = document.getElementById('connectSSIDHidden')?.value || document.getElementById('connectSSID')?.value;
        const password = document.getElementById('connectPassword')?.value || '';
        const security = document.getElementById('connectSecurityHidden')?.value || document.getElementById('connectSecurity')?.value;
        const submitBtn = document.getElementById('connectSubmitBtn');
        
        if (security !== 'Open' && !password) {
          showAlert('danger', t('wifi.password_required', 'Please enter the network password.'));
          return;
        }
        
        if (submitBtn) {
          submitBtn.disabled = true;
          const originalHtml = submitBtn.innerHTML;
          submitBtn.innerHTML = '<span class="spinning"><i class="bi bi-arrow-clockwise"></i></span> ' + t('wifi.connecting', 'Connecting...');
          
          try {
            await connectToNetwork(ssid, security, password);
          } finally {
            if (submitBtn) {
              submitBtn.disabled = false;
              submitBtn.innerHTML = originalHtml;
            }
          }
        }
      });
    }
  });
  
  // Export functions to window
  window.toggleWiFi = toggleWiFi;
  window.scanNetworks = scanNetworks;
  window.connectToNetwork = connectToNetwork;
})();
