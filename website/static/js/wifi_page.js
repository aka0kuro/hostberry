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
    
    try {
      const resp = await fetch(url, opts);
      if (resp.status === 401 && !url.includes('/auth/login')) {
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
  
  // Update status cards
  function updateStatusCards(data) {
    const wifiStatusValue = document.getElementById('wifi-status-value');
    const wifiStatusBar = document.getElementById('wifi-status-bar');
    const wifiStatusIcon = document.getElementById('wifi-status-icon');
    const connectionSsidValue = document.getElementById('connection-ssid-value');
    const connectionSignalBar = document.getElementById('connection-signal-bar');
    const networksCountValue = document.getElementById('networks-count-value');
    const networksCountBar = document.getElementById('networks-count-bar');
    
    // WiFi Status Card
    if (wifiStatusValue && wifiStatusBar && wifiStatusIcon) {
      const isEnabled = data.enabled !== false;
      const isBlocked = data.hard_blocked || data.soft_blocked;
      
      if (isBlocked) {
        wifiStatusValue.textContent = t('wifi.blocked', 'Blocked');
        wifiStatusBar.style.width = '0%';
        wifiStatusBar.style.background = '#dc3545';
        wifiStatusIcon.className = 'bi bi-wifi-off';
      } else if (!isEnabled) {
        wifiStatusValue.textContent = t('wifi.disabled', 'Disabled');
        wifiStatusBar.style.width = '0%';
        wifiStatusBar.style.background = '#ffc107';
        wifiStatusIcon.className = 'bi bi-wifi-off';
      } else {
        wifiStatusValue.textContent = t('wifi.enabled', 'Enabled');
        wifiStatusBar.style.width = '100%';
        wifiStatusBar.style.background = 'linear-gradient(90deg, var(--hb-primary), var(--hb-primary-dark))';
        wifiStatusIcon.className = 'bi bi-wifi';
      }
    }
    
    // Connection Status Card
    if (connectionSsidValue && connectionSignalBar) {
      const isConnected = data.connected || data.current_connection;
      if (isConnected) {
        const ssid = data.current_connection || data.ssid || t('wifi.connected', 'Connected');
        connectionSsidValue.textContent = ssid.length > 20 ? ssid.substring(0, 20) + '...' : ssid;
        const signal = data.connection_info?.signal || data.signal || 0;
        const signalPercent = Math.min(100, Math.max(0, (parseInt(signal) + 100) * 2));
        connectionSignalBar.style.width = signalPercent + '%';
        connectionSignalBar.style.background = signalPercent > 70 ? '#28a745' : (signalPercent > 40 ? '#ffc107' : '#dc3545');
      } else {
        connectionSsidValue.textContent = t('wifi.not_connected', 'Not Connected');
        connectionSignalBar.style.width = '0%';
        connectionSignalBar.style.background = '#dc3545';
      }
    }
    
    // Networks Count Card
    const networksTable = document.getElementById('networksTable');
    if (networksCountValue && networksCountBar && networksTable) {
      const count = networksTable.querySelectorAll('tr').length;
      networksCountValue.textContent = count;
      const countPercent = Math.min(100, (count / 20) * 100); // Asumiendo máximo 20 redes
      networksCountBar.style.width = countPercent + '%';
      networksCountBar.style.background = count > 0 ? 'linear-gradient(90deg, var(--hb-primary), var(--hb-primary-dark))' : '#6c757d';
    }
  }
  
  // Load current connection status
  async function loadConnectionStatus() {
    try {
      const resp = await apiRequest('/api/wifi/status');
      const data = await resp.ok ? await resp.json() : null;
      const statusData = data?.status || data || {};
      
      const statusEl = document.getElementById('connection-status');
      const ssidEl = document.getElementById('connection-ssid');
      const signalEl = document.getElementById('connection-signal');
      const securityEl = document.getElementById('connection-security');
      const channelEl = document.getElementById('connection-channel');
      const ipEl = document.getElementById('connection-ip');
      const macEl = document.getElementById('connection-mac');
      const speedEl = document.getElementById('connection-speed');
      
      // Update status cards
      updateStatusCards(statusData);
      
      if (statusData.connected && statusData.current_connection) {
        if (statusEl) statusEl.innerHTML = '<span class="badge bg-success">' + t('wifi.connected', 'Connected') + '</span>';
        if (ssidEl) ssidEl.textContent = statusData.current_connection || statusData.ssid || '--';
        if (signalEl) signalEl.textContent = (statusData.connection_info?.signal || statusData.signal || '--') + ' dBm';
        if (securityEl) securityEl.textContent = statusData.connection_info?.security || statusData.security || '--';
        if (channelEl) channelEl.textContent = statusData.connection_info?.channel || statusData.channel || '--';
        if (ipEl) ipEl.textContent = statusData.connection_info?.ip || statusData.ip || '--';
        if (macEl) macEl.textContent = statusData.connection_info?.mac || statusData.mac || '--';
        if (speedEl) speedEl.textContent = statusData.connection_info?.speed || statusData.speed || '--';
      } else {
        if (statusEl) statusEl.innerHTML = '<span class="badge bg-danger">' + t('wifi.not_connected', 'Not Connected') + '</span>';
        if (ssidEl) ssidEl.textContent = t('wifi.no_connection', 'No connection');
        if (signalEl) signalEl.textContent = '--';
        if (securityEl) securityEl.textContent = '--';
        if (channelEl) channelEl.textContent = '--';
        if (ipEl) ipEl.textContent = '--';
        if (macEl) macEl.textContent = '--';
        if (speedEl) speedEl.textContent = '--';
      }
      
      // Update toggle button
      if (statusData.enabled !== undefined) {
        updateToggleButton(statusData);
      }
    } catch (e) {
      console.error('Error loading connection status:', e);
      const statusEl = document.getElementById('connection-status');
      if (statusEl) statusEl.innerHTML = '<span class="badge bg-danger">' + t('errors.load_error', 'Error loading') + '</span>';
    }
  }
  
  // Update toggle button
  function updateToggleButton(statusData) {
    const btn = document.getElementById('toggle-wifi-btn');
    const text = document.getElementById('toggle-wifi-text');
    const icon = document.getElementById('toggle-wifi-icon');
    const unblockBtn = document.getElementById('unblock-wifi-btn');
    
    const isEnabled = statusData.enabled !== false;
    const isBlocked = statusData.hard_blocked || statusData.soft_blocked;
    
    if (isBlocked) {
      // Mostrar botón de desbloqueo y ocultar toggle
      if (unblockBtn) {
        unblockBtn.style.display = 'block';
        if (statusData.hard_blocked) {
          unblockBtn.className = 'btn btn-secondary btn-lg w-100';
          unblockBtn.disabled = true;
          unblockBtn.title = t('wifi.hard_blocked', 'Hard blocked: Check physical WiFi switch');
        } else {
          unblockBtn.className = 'btn btn-warning btn-lg w-100';
          unblockBtn.disabled = false;
          unblockBtn.title = '';
        }
      }
      if (btn) btn.style.display = 'none';
    } else {
      // Mostrar botón de toggle y ocultar desbloqueo
      if (unblockBtn) unblockBtn.style.display = 'none';
      if (btn) {
        btn.style.display = 'block';
        if (isEnabled) {
          btn.className = 'btn btn-danger btn-lg w-100';
          text.textContent = t('wifi.disable_wifi', 'Disable WiFi');
          icon.className = 'bi bi-wifi-off';
        } else {
          btn.className = 'btn btn-primary btn-lg w-100';
          text.textContent = t('wifi.enable_wifi', 'Enable WiFi');
          icon.className = 'bi bi-wifi';
        }
      }
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
  
  // Toggle WiFi
  async function toggleWiFi() {
    const btn = document.getElementById('toggle-wifi-btn');
    
    if (btn) {
      btn.disabled = true;
      const originalHtml = btn.innerHTML;
      btn.innerHTML = '<span class="spinning"><i class="bi bi-arrow-clockwise"></i></span> ' + t('wifi.processing', 'Processing...');
      
      try {
        const resp = await apiRequest('/api/v1/wifi/toggle', { method: 'POST' });
        
        // Verificar si la respuesta es exitosa antes de parsear JSON
        if (!resp.ok) {
          // Si es 401, el apiRequest ya maneja la redirección
          if (resp.status === 401) {
            return; // Ya se redirigió a login
          }
          
          // Intentar obtener mensaje de error
          let errorMsg = t('errors.operation_failed', 'Operation failed');
          try {
            const errorData = await resp.json();
            errorMsg = errorData.error || errorMsg;
          } catch (e) {
            // Si no se puede parsear JSON, usar mensaje genérico
            errorMsg = t('errors.operation_failed', 'Operation failed') + ' (HTTP ' + resp.status + ')';
          }
          showAlert('danger', errorMsg);
          return;
        }
        
        // Parsear respuesta solo si es exitosa
        let data;
        try {
          data = await resp.json();
        } catch (e) {
          console.error('Error parsing response:', e);
          showAlert('danger', t('errors.invalid_response', 'Invalid response from server'));
          return;
        }
        
        if (data.success) {
          showAlert('success', t('wifi.wifi_toggled', 'WiFi status changed successfully'));
          setTimeout(async () => {
            await loadConnectionStatus();
            const status = await checkWiFiStatus();
            if (status.enabled && !status.blocked) {
              setTimeout(() => {
                scanNetworks();
              }, 2000);
            }
          }, 2000);
        } else {
          const errorMsg = data.error || t('errors.operation_failed', 'Operation failed');
          showAlert('danger', errorMsg);
        }
      } catch (e) {
        console.error('Error toggling WiFi:', e);
        // No cerrar sesión por errores de red, solo mostrar mensaje
        if (e.message && e.message.includes('401')) {
          // Si es 401, ya se manejó en apiRequest
          return;
        }
        showAlert('danger', t('errors.network_error', 'Network error: ') + e.message);
      } finally {
        if (btn) {
          btn.disabled = false;
          btn.innerHTML = originalHtml;
        }
      }
    }
  }
  
  // Unblock WiFi
  async function unblockWiFi() {
    const btn = document.getElementById('unblock-wifi-btn');
    
    if (btn) {
      btn.disabled = true;
      const originalHtml = btn.innerHTML;
      btn.innerHTML = '<span class="spinning"><i class="bi bi-arrow-clockwise"></i></span> ' + t('wifi.unblocking', 'Unblocking...');
      
      try {
        // Usar el endpoint específico para desbloquear
        const resp = await apiRequest('/api/v1/wifi/unblock', { method: 'POST' });
        
        // Verificar si la respuesta es exitosa antes de parsear JSON
        if (!resp.ok) {
          // Si es 401, el apiRequest ya maneja la redirección
          if (resp.status === 401) {
            return; // Ya se redirigió a login
          }
          
          // Intentar obtener mensaje de error
          let errorMsg = t('errors.operation_failed', 'Operation failed');
          try {
            const errorData = await resp.json();
            errorMsg = errorData.error || errorMsg;
          } catch (e) {
            errorMsg = t('errors.operation_failed', 'Operation failed') + ' (HTTP ' + resp.status + ')';
          }
          showAlert('danger', errorMsg);
          return;
        }
        
        // Parsear respuesta solo si es exitosa
        let data;
        try {
          data = await resp.json();
        } catch (e) {
          console.error('Error parsing response:', e);
          showAlert('danger', t('errors.invalid_response', 'Invalid response from server'));
          return;
        }
        
        if (data.success) {
          showAlert('success', t('wifi.wifi_unblocked', 'WiFi unblocked successfully'));
          // Esperar un poco más para que el sistema aplique los cambios
          setTimeout(async () => {
            await loadConnectionStatus();
            // Verificar el estado después de un momento adicional
            setTimeout(async () => {
              await loadConnectionStatus();
              const status = await checkWiFiStatus();
              if (status.enabled && !status.blocked) {
                setTimeout(() => {
                  scanNetworks();
                }, 1000);
              }
            }, 1000);
          }, 1500);
        } else {
          const errorMsg = data.error || t('errors.operation_failed', 'Operation failed');
          showAlert('danger', errorMsg);
        }
      } catch (e) {
        console.error('Error unblocking WiFi:', e);
        // No cerrar sesión por errores de red, solo mostrar mensaje
        if (e.message && e.message.includes('401')) {
          // Si es 401, ya se manejó en apiRequest
          return;
        }
        showAlert('danger', t('errors.network_error', 'Network error: ') + e.message);
      } finally {
        if (btn) {
          btn.disabled = false;
          btn.innerHTML = originalHtml;
        }
      }
    }
  }
  
  // Load WiFi interfaces
  async function loadWiFiInterfaces() {
    try {
      const resp = await apiRequest('/api/v1/wifi/interfaces');
      if (resp.ok) {
        const data = await resp.json();
        const interfaceSelect = document.getElementById('wifi-interface');
        if (interfaceSelect && data.interfaces) {
          // Limpiar opciones existentes (excepto auto-detect)
          while (interfaceSelect.options.length > 1) {
            interfaceSelect.remove(1);
          }
          
          // Agregar interfaces
          data.interfaces.forEach(function(iface) {
            const option = document.createElement('option');
            option.value = iface.name;
            option.textContent = iface.name + (iface.state ? ' (' + iface.state + ')' : '');
            interfaceSelect.appendChild(option);
          });
          
          // Cargar interfaz guardada DESPUÉS de agregar las opciones
          const savedInterface = localStorage.getItem('wifi_interface');
          if (savedInterface) {
            // Verificar que la interfaz guardada existe en las opciones
            let found = false;
            for (let i = 0; i < interfaceSelect.options.length; i++) {
              if (interfaceSelect.options[i].value === savedInterface) {
                found = true;
                break;
              }
            }
            if (found) {
              interfaceSelect.value = savedInterface;
              console.log('Interfaz WiFi cargada:', savedInterface);
            } else {
              // Si la interfaz guardada no existe, limpiar localStorage
              localStorage.removeItem('wifi_interface');
              console.log('Interfaz WiFi guardada no encontrada, usando auto-detect');
            }
          }
        }
      }
    } catch (e) {
      console.error('Error loading WiFi interfaces:', e);
    }
  }
  
  // Scan networks
  async function scanNetworks() {
    const loadingEl = document.getElementById('networks-loading');
    const emptyEl = document.getElementById('networks-empty');
    const tableEl = document.getElementById('networks-table-container');
    const tbody = document.getElementById('networksTable');
    const scanBtn = document.getElementById('scan-networks-btn');
    const interfaceSelect = document.getElementById('wifi-interface');
    
    // Obtener interfaz seleccionada
    const selectedInterface = interfaceSelect ? interfaceSelect.value : '';
    if (selectedInterface) {
      localStorage.setItem('wifi_interface', selectedInterface);
      console.log('Interfaz WiFi guardada:', selectedInterface);
    } else {
      // Si es auto-detect (vacío), limpiar localStorage
      localStorage.removeItem('wifi_interface');
      console.log('Usando auto-detección de interfaz WiFi');
    }
    
    // Verificar estado del WiFi primero
    const wifiStatus = await checkWiFiStatus();
    
    if (!wifiStatus.enabled || wifiStatus.blocked) {
      if (emptyEl) {
        emptyEl.innerHTML = 
          '<div class="text-center py-5">' +
          '<i class="bi bi-wifi-off" style="font-size: 4rem; opacity: 0.5;"></i>' +
          '<p class="mt-3">' + t('wifi.wifi_disabled', 'WiFi is disabled') + '</p>' +
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
        
        const requestBody = selectedInterface ? { interface: selectedInterface } : {};
        const resp = await apiRequest('/api/v1/wifi/scan', { 
          method: 'POST',
          body: requestBody,
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
                const signalPercent = Math.min(100, Math.max(0, (signalStrength + 100) * 2));
                const signalClass = signalPercent > 70 ? 'text-success' : (signalPercent > 40 ? 'text-warning' : 'text-danger');
                const frequency = network.frequency || network.channel ? getFrequencyFromChannel(network.channel) : '--';
                
                tr.innerHTML = 
                  '<td><strong>' + (network.ssid || t('wifi.hidden_network', 'Hidden Network')) + '</strong></td>' +
                  '<td><span class="badge bg-' + securityColor + '">' + security + '</span></td>' +
                  '<td><span class="' + signalClass + '"><i class="bi bi-signal"></i> ' + signalStrength + ' dBm</span></td>' +
                  '<td>' + (network.channel || '--') + '</td>' +
                  '<td>' + frequency + '</td>' +
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
              
              // Actualizar contador de redes
              updateStatusCards({});
            }
            showAlert('success', t('wifi.found_networks', 'Found {count} networks').replace('{count}', data.networks.length));
          } else {
            if (emptyEl) {
              emptyEl.innerHTML = 
                '<div class="text-center py-5">' +
                '<i class="bi bi-wifi-off" style="font-size: 4rem; opacity: 0.5;"></i>' +
                '<p class="mt-3">' + t('wifi.no_networks', 'No networks found') + '</p>' +
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
              '<div class="text-center py-5">' +
              '<i class="bi bi-exclamation-triangle text-warning" style="font-size: 4rem;"></i>' +
              '<p class="mt-3">' + t('errors.scan_failed', 'Scan failed') + '</p>' +
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
            '<div class="text-center py-5">' +
            '<i class="bi bi-exclamation-triangle text-danger" style="font-size: 4rem;"></i>' +
            '<p class="mt-3">' + t('errors.scan_error', 'Scan error') + '</p>' +
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
  
  // Get frequency from channel
  function getFrequencyFromChannel(channel) {
    if (!channel) return '--';
    const ch = parseInt(channel);
    if (ch >= 1 && ch <= 13) {
      return (2407 + (ch * 5)) + ' MHz';
    } else if (ch >= 36 && ch <= 165) {
      return (5000 + (ch * 5)) + ' MHz';
    }
    return '--';
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
          password: password || ''
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
  
  // Save WiFi region
  async function saveRegion(region) {
    try {
      const resp = await apiRequest('/api/v1/wifi/config', {
        method: 'POST',
        body: { region: region }
      });
      
      const data = await resp.json();
      
      if (resp.ok && data.success) {
        showAlert('success', t('wifi.region_saved', 'Region saved successfully'));
        return true;
      } else {
        const errorMsg = data.error || t('errors.operation_failed', 'Operation failed');
        showAlert('danger', errorMsg);
        return false;
      }
    } catch (e) {
      console.error('Error saving region:', e);
      showAlert('danger', t('errors.network_error', 'Network error'));
      return false;
    }
  }
  
  // Load WiFi region
  async function loadRegion() {
    try {
      // Intentar obtener la región desde localStorage o configuración
      const savedRegion = localStorage.getItem('wifi_region') || 'US';
      const regionSelect = document.getElementById('wifi-region');
      if (regionSelect) {
        regionSelect.value = savedRegion;
      }
    } catch (e) {
      console.error('Error loading region:', e);
    }
  }
  
  // Toggle auto-connect
  function toggleAutoConnect() {
    const btn = document.getElementById('auto-connect-btn');
    const icon = document.getElementById('auto-connect-icon');
    const text = document.getElementById('auto-connect-text');
    
    if (btn && icon && text) {
      const isEnabled = btn.classList.contains('active');
      if (isEnabled) {
        btn.classList.remove('active');
        btn.classList.remove('btn-primary');
        btn.classList.add('btn-outline-light');
        icon.className = 'bi bi-link-45deg';
        text.textContent = t('wifi.auto_connect', 'Auto Connect');
        localStorage.setItem('wifi_auto_connect', 'false');
      } else {
        btn.classList.add('active');
        btn.classList.remove('btn-outline-light');
        btn.classList.add('btn-primary');
        icon.className = 'bi bi-link-45deg';
        text.textContent = t('wifi.auto_connect_enabled', 'Auto Connect Enabled');
        localStorage.setItem('wifi_auto_connect', 'true');
      }
    }
  }
  
  // Refresh handlers
  document.addEventListener('DOMContentLoaded', function() {
    loadConnectionStatus();
    loadRegion();
    
    // Cargar interfaces WiFi y restaurar selección guardada
    loadWiFiInterfaces().then(function() {
      // Asegurar que la interfaz guardada se seleccione después de cargar
      const interfaceSelect = document.getElementById('wifi-interface');
      const savedInterface = localStorage.getItem('wifi_interface');
      if (interfaceSelect && savedInterface) {
        // Esperar un momento para que las opciones se agreguen completamente
        setTimeout(function() {
          const option = interfaceSelect.querySelector('option[value="' + savedInterface + '"]');
          if (option) {
            interfaceSelect.value = savedInterface;
            console.log('Interfaz WiFi restaurada:', savedInterface);
          } else {
            console.log('Interfaz WiFi guardada no encontrada en opciones, usando auto-detect');
            localStorage.removeItem('wifi_interface');
          }
        }, 200);
      }
    });
    
    // Cargar estado de auto-connect
    const autoConnectEnabled = localStorage.getItem('wifi_auto_connect') === 'true';
    if (autoConnectEnabled) {
      toggleAutoConnect();
    }
    
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
    
    // Region form
    const regionForm = document.getElementById('regionForm');
    if (regionForm) {
      regionForm.addEventListener('submit', async function(e) {
        e.preventDefault();
        const regionSelect = document.getElementById('wifi-region');
        if (regionSelect) {
          const region = regionSelect.value;
          const submitBtn = regionForm.querySelector('button[type="submit"]');
          if (submitBtn) {
            submitBtn.disabled = true;
            const originalHtml = submitBtn.innerHTML;
            submitBtn.innerHTML = '<span class="spinning"><i class="bi bi-arrow-clockwise"></i></span> ' + t('common.saving', 'Saving...');
            
            try {
              const success = await saveRegion(region);
              if (success) {
                localStorage.setItem('wifi_region', region);
              }
            } finally {
              if (submitBtn) {
                submitBtn.disabled = false;
                submitBtn.innerHTML = originalHtml;
              }
            }
          }
        }
      });
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
  window.unblockWiFi = unblockWiFi;
  window.scanNetworks = scanNetworks;
  window.connectToNetwork = connectToNetwork;
  window.toggleAutoConnect = toggleAutoConnect;
})();
