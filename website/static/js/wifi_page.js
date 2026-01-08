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
      if (i18nScript && i18nScript.textContent) {
        const content = i18nScript.textContent.trim();
        if (content && content !== '') {
          const translations = JSON.parse(content);
          if (translations && typeof translations === 'object') {
            const keys = key.split('.');
            let value = translations;
            for (const k of keys) {
              value = value && value[k];
            }
            if (typeof value === 'string') return value;
          }
        }
      }
    } catch (e) {
      console.warn('Error parsing translations:', e);
    }
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
  
  // Expose apiRequest to HostBerry namespace for compatibility
  if (!window.HostBerry) {
    window.HostBerry = {};
  }
  window.HostBerry.apiRequest = apiRequest;
  
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
      // Verificar explícitamente si enabled es true
      const isEnabled = data.enabled === true || (data.enabled !== false && !data.hard_blocked && !data.soft_blocked);
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
      console.log('Cargando estado de conexión WiFi...');
      const resp = await apiRequest('/api/wifi/status');
      
      if (!resp.ok) {
        console.error('Error en respuesta API:', resp.status, resp.statusText);
        let errorText = '';
        try {
          errorText = await resp.text();
          console.error('Error response:', errorText);
        } catch (e) {
          console.error('No se pudo leer el texto de error:', e);
        }
        throw new Error('Error al cargar estado: HTTP ' + resp.status);
      }
      
      let data;
      try {
        const text = await resp.text();
        if (!text || text.trim() === '') {
          console.warn('Respuesta vacía del servidor');
          data = {};
        } else {
          data = JSON.parse(text);
        }
      } catch (parseError) {
        console.error('Error parsing JSON response:', parseError);
        console.error('Response was not valid JSON');
        // Continuar con objeto vacío en lugar de lanzar error
        data = {};
      }
      
      console.log('Datos recibidos del API:', data);
      const statusData = data?.status || data || {};
      console.log('Estado procesado:', statusData);
      
      // Debug: mostrar todos los datos disponibles
      if (Object.keys(statusData).length === 0 && Object.keys(data).length > 0) {
        console.warn('⚠️ statusData está vacío, datos completos:', data);
      }
      
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
      
        // Mostrar datos incluso si no está conectado (pero WiFi está habilitado)
      if (statusData.connected && statusData.current_connection) {
        if (statusEl) statusEl.innerHTML = '<span class="badge bg-success">' + t('wifi.connected', 'Connected') + '</span>';
        if (ssidEl) ssidEl.textContent = statusData.current_connection || statusData.ssid || '--';
        
        // Obtener información de conexión
        const connInfo = statusData.connection_info || {};
        const signal = connInfo.signal || statusData.signal;
        const security = connInfo.security || statusData.security;
        const channel = connInfo.channel || statusData.channel;
        const ip = connInfo.ip || statusData.ip;
        const mac = connInfo.mac || statusData.mac;
        const speed = connInfo.speed || statusData.speed;
        
        if (signalEl) signalEl.textContent = signal ? (signal + ' dBm') : '--';
        if (securityEl) securityEl.textContent = security || '--';
        if (channelEl) channelEl.textContent = channel || '--';
        if (ipEl) ipEl.textContent = ip || '--';
        if (macEl) macEl.textContent = mac || '--';
        if (speedEl) speedEl.textContent = speed || '--';
        
        // Actualizar botones de conexión en las tarjetas
        updateConnectButtons(statusData.current_connection);
      } else {
        // No conectado
        if (statusEl) statusEl.innerHTML = '<span class="badge bg-danger">' + t('wifi.not_connected', 'Not Connected') + '</span>';
        if (ssidEl) ssidEl.textContent = t('wifi.no_connection', 'No connection');
        
        // Obtener información básica de connection_info aunque no esté conectado
        const connInfo = statusData.connection_info || {};
        const mac = connInfo.mac || statusData.mac;
        
        if (signalEl) signalEl.textContent = '--';
        if (securityEl) securityEl.textContent = '--';
        if (channelEl) channelEl.textContent = '--';
        if (ipEl) ipEl.textContent = '--';
        if (macEl) macEl.textContent = mac || '--';
        if (speedEl) speedEl.textContent = '--';
      }
      
      // Update toggle button
      if (statusData.enabled !== undefined) {
        updateToggleButton(statusData);
      }
      
      // Update connect buttons if connected
      if (statusData.connected && statusData.current_connection) {
        updateConnectButtons(statusData.current_connection);
      } else {
        // Si no está conectado, restaurar todos los botones
        updateConnectButtons(null);
      }
      
      console.log('✅ Estado de conexión cargado correctamente');
    } catch (e) {
      console.error('❌ Error loading connection status:', e);
      console.error('Stack trace:', e.stack);
      const statusEl = document.getElementById('connection-status');
      if (statusEl) statusEl.innerHTML = '<span class="badge bg-danger">' + t('errors.load_error', 'Error loading') + '</span>';
      
      // Mostrar error en los campos
      const ssidEl = document.getElementById('connection-ssid');
      const signalEl = document.getElementById('connection-signal');
      const securityEl = document.getElementById('connection-security');
      const channelEl = document.getElementById('connection-channel');
      const ipEl = document.getElementById('connection-ip');
      const macEl = document.getElementById('connection-mac');
      const speedEl = document.getElementById('connection-speed');
      
      if (ssidEl) ssidEl.textContent = 'Error';
      if (signalEl) signalEl.textContent = '--';
      if (securityEl) securityEl.textContent = '--';
      if (channelEl) channelEl.textContent = '--';
      if (ipEl) ipEl.textContent = '--';
      if (macEl) macEl.textContent = '--';
      if (speedEl) speedEl.textContent = '--';
    }
  }
  
  // Update connect buttons in network cards
  function updateConnectButtons(currentSSID) {
    const tbody = document.getElementById('networksTable');
    if (!tbody) return;
    
    const buttons = tbody.querySelectorAll('.connect-network-btn');
    buttons.forEach(function(btn) {
      const btnSSID = btn.getAttribute('data-ssid');
      
      if (currentSSID && btnSSID === currentSSID) {
        // Esta es la red conectada
        if (!btn.disabled || btn.className.indexOf('btn-success') === -1) {
          btn.className = 'btn btn-success connect-network-btn';
          btn.disabled = true;
          btn.innerHTML = '<i class="bi bi-check-circle me-2"></i>' + t('wifi.connected', 'Connected');
        }
      } else {
        // Ya no está conectada o no es la red conectada, restaurar botón
        if (btn.disabled || btn.className.indexOf('btn-success') !== -1) {
          btn.className = 'btn btn-primary connect-network-btn';
          btn.disabled = false;
          btn.innerHTML = '<i class="bi bi-wifi me-2"></i>' + t('wifi.connect', 'Connect');
          
          // Re-agregar event listener
          const card = btn.closest('.network-card');
          if (card) {
            btn.onclick = function(e) {
              e.stopPropagation();
              const ssid = btn.getAttribute('data-ssid');
              const security = btn.getAttribute('data-security');
              showConnectInline(ssid, security, card);
            };
          }
        }
      }
    });
  }
  
  // Update toggle button
  function updateToggleButton(statusData) {
    const btn = document.getElementById('toggle-wifi-btn');
    const text = document.getElementById('toggle-wifi-text');
    const icon = document.getElementById('toggle-wifi-icon');
    const unblockBtn = document.getElementById('unblock-wifi-btn');
    const softwareSwitchBtn = document.getElementById('toggle-software-switch-btn');
    const softwareSwitchText = document.getElementById('software-switch-text');
    const softwareSwitchIcon = document.getElementById('software-switch-icon');
    
    const isEnabled = statusData.enabled !== false;
    const isBlocked = statusData.hard_blocked || statusData.soft_blocked;
    const isSoftBlocked = statusData.soft_blocked;
    
    // Actualizar botón de software switch
    if (softwareSwitchBtn && softwareSwitchText && softwareSwitchIcon) {
      if (isSoftBlocked) {
        softwareSwitchBtn.className = 'btn btn-success btn-lg';
        softwareSwitchText.textContent = t('wifi.enable_software_switch', 'Enable Software Switch');
        softwareSwitchIcon.className = 'bi bi-toggle-on me-2';
      } else {
        softwareSwitchBtn.className = 'btn btn-secondary btn-lg';
        softwareSwitchText.textContent = t('wifi.disable_software_switch', 'Disable Software Switch');
        softwareSwitchIcon.className = 'bi bi-toggle-off me-2';
      }
    }
    
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
        // Verificar explícitamente si enabled es true (no solo "no es false")
        const enabled = statusData.enabled === true || (statusData.enabled !== false && !statusData.hard_blocked && !statusData.soft_blocked);
        return {
          enabled: enabled,
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
        
        // Verificar si la operación fue exitosa
        if (data.success === true) {
          showAlert('success', t('wifi.wifi_toggled', 'WiFi status changed successfully'));
          
          // Esperar un momento inicial para que el comando se ejecute
          await new Promise(resolve => setTimeout(resolve, 1500));
          
          // Actualizar estado inmediatamente
          await loadConnectionStatus();
          
          // Verificar estado con múltiples intentos (hasta 10 segundos)
          let status = await checkWiFiStatus();
          let attempts = 0;
          const maxAttempts = 10;
          
          // Si WiFi estaba deshabilitado, esperar a que se habilite
          const wasDisabled = !status.enabled || status.blocked;
          
          if (wasDisabled) {
            // Esperar y verificar hasta que esté habilitado
            while ((!status.enabled || status.blocked) && attempts < maxAttempts) {
              await new Promise(resolve => setTimeout(resolve, 1000));
              await loadConnectionStatus(); // Actualizar UI
              status = await checkWiFiStatus();
              attempts++;
              
              // Mostrar progreso cada 2 intentos
              if (attempts % 2 === 0) {
                console.log(`Esperando activación de WiFi... (intento ${attempts}/${maxAttempts})`);
              }
            }
          }
          
          // Actualizar estado final
          await loadConnectionStatus();
          status = await checkWiFiStatus();
          
          // Intentar escanear siempre después de activar WiFi
          if (status.enabled && !status.blocked) {
            // WiFi está habilitado, escanear automáticamente
            showAlert('info', t('wifi.scanning_networks', 'Scanning for networks...'));
            setTimeout(() => {
              scanNetworks();
            }, 2000);
          } else {
            // Aún no se detecta como habilitado, pero intentar escanear de todos modos
            // (puede que el sistema aún esté aplicando los cambios)
            showAlert('info', t('wifi.scanning_networks', 'Scanning for networks...'));
            setTimeout(async () => {
              // Actualizar estado una vez más
              await loadConnectionStatus();
              // Intentar escanear (la función scanNetworks verificará el estado)
              scanNetworks();
            }, 3000);
          }
        } else {
          // Si success es false o no está definido, mostrar error
          const errorMsg = data.error || data.message || t('errors.operation_failed', 'Operation failed');
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
        
        // Verificar si la operación fue exitosa
        if (data.success === true) {
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
          // Si success es false o no está definido, mostrar error
          const errorMsg = data.error || data.message || t('errors.operation_failed', 'Operation failed');
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
    
    // Verificar estado del WiFi primero (con múltiples intentos)
    let wifiStatus = await checkWiFiStatus();
    let statusAttempts = 0;
    const maxStatusAttempts = 5; // Aumentar intentos
    
    // Si WiFi no está habilitado, intentar verificar varias veces (puede estar activándose)
    while ((!wifiStatus.enabled || wifiStatus.blocked) && statusAttempts < maxStatusAttempts) {
      await new Promise(resolve => setTimeout(resolve, 1500)); // Esperar más entre intentos
      await loadConnectionStatus(); // Actualizar estado en UI
      wifiStatus = await checkWiFiStatus();
      statusAttempts++;
    }
    
    // Si después de todos los intentos aún no está habilitado, mostrar mensaje pero intentar escanear de todos modos
    if (!wifiStatus.enabled || wifiStatus.blocked) {
      // Intentar escanear de todos modos (puede que el estado no se haya actualizado pero WiFi esté activo)
      console.log("WiFi puede estar activándose, intentando escanear de todos modos...");
      // Mostrar advertencia pero continuar con el escaneo
      showAlert('warning', t('wifi.wifi_may_be_enabling', 'WiFi may still be enabling, attempting to scan anyway...'));
    }
    
    if (loadingEl) loadingEl.style.display = 'block';
    if (emptyEl) emptyEl.style.display = 'none';
    if (tableEl) tableEl.style.display = 'none';
    if (tbody) tbody.innerHTML = '';
    
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
            // Mostrar tarjetas con las redes
            if (tableEl) tableEl.style.display = 'block';
            if (tbody) {
              // Obtener red conectada actual para comparar
              let currentSSID = null;
              try {
                const statusResp = await apiRequest('/api/wifi/status');
                if (statusResp.ok) {
                  const statusData = await statusResp.json();
                  const status = statusData.status || statusData;
                  if (status.connected && status.current_connection) {
                    currentSSID = status.current_connection;
                  }
                }
              } catch (e) {
                console.error('Error getting current connection:', e);
              }
              
              // Ordenar por señal (mayor a menor)
              data.networks.sort((a, b) => {
                const signalA = parseInt(a.signal) || 0;
                const signalB = parseInt(b.signal) || 0;
                return signalB - signalA;
              });
              
              data.networks.forEach(function(network) {
                const card = document.createElement('div');
                card.className = 'network-card';
                const security = network.security || 'Open';
                const securityColor = getSecurityColor(security);
                const signalStrength = network.signal || 0;
                const signalPercent = Math.min(100, Math.max(0, (signalStrength + 100) * 2));
                const signalClass = signalPercent > 70 ? 'text-success' : (signalPercent > 40 ? 'text-warning' : 'text-danger');
                const signalIcon = signalPercent > 70 ? 'bi-wifi' : (signalPercent > 40 ? 'bi-wifi-2' : 'bi-wifi-1');
                const frequency = network.frequency || (network.channel ? getFrequencyFromChannel(network.channel) : '--');
                const ssid = network.ssid || t('wifi.hidden_network', 'Hidden Network');
                const isConnected = currentSSID && currentSSID === ssid;
                
                // Botón de conexión - mostrar "Connected" si está conectado
                let connectButtonHtml = '';
                if (isConnected) {
                  connectButtonHtml = '<button class="btn btn-success connect-network-btn" data-ssid="' + ssid.replace(/"/g, '&quot;') + '" data-security="' + (security || 'Open').replace(/"/g, '&quot;') + '" disabled>' +
                    '<i class="bi bi-check-circle me-2"></i>' + t('wifi.connected', 'Connected') +
                  '</button>';
                } else {
                  connectButtonHtml = '<button class="btn btn-primary connect-network-btn" data-ssid="' + ssid.replace(/"/g, '&quot;') + '" data-security="' + (security || 'Open').replace(/"/g, '&quot;') + '">' +
                    '<i class="bi bi-wifi me-2"></i>' + t('wifi.connect', 'Connect') +
                  '</button>';
                }
                
                card.innerHTML = 
                  '<div class="network-card-content">' +
                    '<div class="network-card-icon ' + signalClass + '">' +
                      '<i class="bi ' + signalIcon + '"></i>' +
                    '</div>' +
                    '<div class="network-card-info">' +
                      '<h6 class="network-card-ssid">' + ssid + '</h6>' +
                      '<div class="network-card-details">' +
                        '<div class="network-card-detail-item">' +
                          '<span class="badge bg-' + securityColor + ' network-card-security-badge">' + security + '</span>' +
                        '</div>' +
                        '<div class="network-card-detail-item network-card-signal ' + signalClass + '">' +
                          '<i class="bi bi-signal"></i> ' +
                          '<span>' + signalStrength + ' dBm</span>' +
                        '</div>' +
                        '<div class="network-card-detail-item">' +
                          '<i class="bi bi-broadcast"></i> ' +
                          '<span>' + t('wifi.network_channel', 'Channel') + ': ' + (network.channel || '--') + '</span>' +
                        '</div>' +
                        '<div class="network-card-detail-item">' +
                          '<i class="bi bi-speedometer2"></i> ' +
                          '<span>' + frequency + '</span>' +
                        '</div>' +
                      '</div>' +
                    '</div>' +
                  '</div>' +
                  '<div class="network-card-actions">' +
                    connectButtonHtml +
                  '</div>';
                
                tbody.appendChild(card);
              });
              
              // Agregar event listeners a los botones de conexión (solo los que no están conectados)
              tbody.querySelectorAll('.connect-network-btn:not([disabled])').forEach(function(btn) {
                btn.addEventListener('click', function(e) {
                  e.stopPropagation();
                  const ssid = btn.getAttribute('data-ssid');
                  const security = btn.getAttribute('data-security');
                  const card = btn.closest('.network-card');
                  if (card) {
                    showConnectInline(ssid, security, card);
                  }
                });
              });
            }
            
            // Actualizar contador de redes
            updateStatusCards({});
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
      }
    } catch (e) {
      console.error('Error scanning networks:', e);
      if (loadingEl) loadingEl.style.display = 'none';
      if (emptyEl) {
        emptyEl.innerHTML = 
          '<div class="text-center py-5">' +
          '<i class="bi bi-exclamation-triangle text-danger" style="font-size: 4rem;"></i>' +
          '<p class="mt-3">' + t('errors.scan_error', 'Scan error') + '</p>' +
          '<p class="text-muted small">' + (e.message || 'Unknown error') + '</p>' +
          '</div>';
        emptyEl.style.display = 'block';
      }
      if (tableEl) tableEl.style.display = 'none';
      
      let msg = e.message || t('errors.operation_failed', 'Operation failed');
      if (e.name === 'AbortError') {
        msg = t('wifi.scan_timeout', 'Scan timed out. Please try again.');
      } else if (msg.includes('Failed to fetch')) {
        msg = t('errors.connection_error', 'Connection error with the server.');
      }
      showAlert('danger', msg);
    }
  }
  
  // Show connect inline form in network card
  function showConnectInline(ssid, security, cardElement) {
    // Verificar si ya hay un formulario en esta tarjeta
    let formDiv = cardElement.querySelector('.network-connect-form-wrapper');
    if (formDiv) {
      formDiv.remove();
      return;
    }
    
    // Crear nuevo div con formulario
    const formWrapper = document.createElement('div');
    formWrapper.className = 'network-connect-form-wrapper';
    formWrapper.style.cssText = 'width: 100%; margin-top: 1rem; padding-top: 1rem; border-top: 1px solid rgba(255, 255, 255, 0.1);';
    formWrapper.innerHTML = 
      '<div style="padding: 1.5rem; background: rgba(255, 255, 255, 0.02); border-radius: 8px;">' +
        '<div class="network-connect-form show">' +
          '<div class="network-connect-form-group">' +
            '<label class="network-connect-form-label">' + t('wifi.network_ssid', 'Network Name (SSID)') + '</label>' +
            '<input type="text" class="network-connect-form-input" value="' + ssid.replace(/"/g, '&quot;') + '" readonly>' +
          '</div>' +
          '<div class="network-connect-form-group">' +
            '<label class="network-connect-form-label">' + t('wifi.security_type', 'Security Type') + '</label>' +
            '<input type="text" class="network-connect-form-input" value="' + security.replace(/"/g, '&quot;') + '" readonly>' +
          '</div>' +
          (security !== 'Open' ? 
            '<div class="network-connect-form-group">' +
              '<label class="network-connect-form-label">' + t('auth.password', 'Password') + '</label>' +
              '<div style="position: relative;">' +
                '<input type="password" class="network-connect-form-input network-connect-password" placeholder="' + t('auth.password_placeholder', 'Password') + '" autocomplete="current-password">' +
                '<button type="button" class="btn btn-sm btn-outline-secondary" style="position: absolute; right: 0.5rem; top: 50%; transform: translateY(-50%);" onclick="togglePasswordVisibility(this)">' +
                  '<i class="bi bi-eye"></i>' +
                '</button>' +
              '</div>' +
            '</div>' : '') +
          '<div class="network-connect-form-actions">' +
            '<button type="button" class="btn btn-secondary network-connect-cancel">' + t('common.cancel', 'Cancel') + '</button>' +
            '<button type="button" class="btn btn-primary network-connect-submit">' +
              '<i class="bi bi-wifi me-2"></i>' + t('wifi.connect_now', 'Connect Now') +
            '</button>' +
          '</div>' +
        '</div>' +
      '</div>';
    
    // Insertar después del contenido de la tarjeta
    const cardContent = cardElement.querySelector('.network-card-content');
    if (cardContent) {
      cardElement.insertBefore(formWrapper, cardContent.nextSibling);
    } else {
      cardElement.appendChild(formWrapper);
    }
    
    // Hacer scroll hacia el formulario
    setTimeout(() => {
      formWrapper.scrollIntoView({ behavior: 'smooth', block: 'center' });
      const passwordInput = formWrapper.querySelector('.network-connect-password');
      if (passwordInput) {
        passwordInput.focus();
      }
    }, 100);
    
    // Botón cancelar
    const cancelBtn = formWrapper.querySelector('.network-connect-cancel');
    if (cancelBtn) {
      cancelBtn.addEventListener('click', function() {
        formWrapper.remove();
      });
    }
    
    // Botón conectar
    const submitBtn = formWrapper.querySelector('.network-connect-submit');
    if (submitBtn) {
      submitBtn.addEventListener('click', function() {
        const passwordInput = formWrapper.querySelector('.network-connect-password');
        const password = passwordInput ? passwordInput.value : '';
        
        if (security !== 'Open' && !password) {
          showAlert('danger', t('wifi.password_required', 'Please enter the network password.'));
          if (passwordInput) passwordInput.focus();
          return;
        }
        
        connectToNetwork(ssid, security, password, cardElement);
      });
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
  
  // Toggle password visibility
  window.togglePasswordVisibility = function(btn) {
    const icon = btn.querySelector('i');
    const input = btn.parentElement.querySelector('input[type="password"], input[type="text"]');
    if (input) {
      if (input.type === 'password') {
        input.type = 'text';
        icon.className = 'bi bi-eye-slash';
      } else {
        input.type = 'password';
        icon.className = 'bi bi-eye';
      }
    }
  };
  
  // Connect to network
  async function connectToNetwork(ssid, security, password, cardElement) {
    const submitBtn = cardElement ? cardElement.querySelector('.network-connect-submit') : null;
    const form = cardElement ? cardElement.querySelector('.network-connect-form') : null;
    
    if (submitBtn) {
      submitBtn.disabled = true;
      const originalHtml = submitBtn.innerHTML;
      submitBtn.innerHTML = '<span class="spinning"><i class="bi bi-arrow-clockwise"></i></span> ' + t('wifi.connecting', 'Connecting...');
      
      try {
        const resp = await apiRequest('/api/v1/wifi/connect', {
          method: 'POST',
          body: { 
            ssid: ssid, 
            password: password || ''
          }
        });
        
        if (!resp.ok) {
          if (resp.status === 401) return;
          let errorMsg = t('errors.connection_failed', 'Connection failed');
          try {
            const errorData = await resp.json();
            errorMsg = errorData.error || errorMsg;
          } catch (e) {
            errorMsg = t('errors.connection_failed', 'Connection failed') + ' (HTTP ' + resp.status + ')';
          }
          showAlert('danger', errorMsg);
          return;
        }
        
        const data = await resp.json();
        
        if (data.success) {
          showAlert('success', t('wifi.connected_to', 'Connected to') + ': ' + ssid);
          
          // Guardar última red conectada para auto-reconexión
          localStorage.setItem('wifi_last_connected_ssid', ssid);
          if (password) {
            localStorage.setItem('wifi_last_connected_password', password);
          } else {
            localStorage.removeItem('wifi_last_connected_password');
          }
          
          // Ocultar el formulario
          if (form) {
            form.classList.remove('show');
          }
          
          // Ocultar formulario inline si existe
          const formWrapper = cardElement ? cardElement.querySelector('.network-connect-form-wrapper') : null;
          if (formWrapper) {
            formWrapper.remove();
          }
          
          // Actualizar botones inmediatamente
          updateConnectButtons(ssid);
          
          setTimeout(() => {
            loadConnectionStatus();
            // Actualizar botones nuevamente después de cargar estado
            setTimeout(() => {
              updateConnectButtons(ssid);
            }, 500);
          }, 2000);
        } else {
          const errorMsg = data.error || t('errors.connection_failed', 'Connection failed');
          showAlert('danger', errorMsg);
        }
      } catch (e) {
        console.error('Error connecting to network:', e);
        if (e.message && e.message.includes('401')) return;
        showAlert('danger', t('errors.network_error', 'Network error: ') + e.message);
      } finally {
        if (submitBtn) {
          submitBtn.disabled = false;
          submitBtn.innerHTML = originalHtml;
        }
      }
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
  
    // Auto-connect to last network
    async function autoConnectToLastNetwork() {
      try {
        // Obtener última red conectada desde localStorage
        const lastSSID = localStorage.getItem('wifi_last_connected_ssid');
        const lastPassword = localStorage.getItem('wifi_last_connected_password');
        
        if (!lastSSID) {
          return; // No hay última red guardada
        }
        
        // Verificar estado actual de WiFi
        const statusResp = await apiRequest('/api/wifi/status');
        if (!statusResp.ok) return;
        
        const statusData = await statusResp.json();
        const status = statusData.status || statusData;
        
        // Si ya está conectado a esta red, no hacer nada
        if (status.connected && status.current_connection === lastSSID) {
          return;
        }
        
        // Si WiFi está deshabilitado o bloqueado, no intentar conectar
        if (!status.enabled || status.hard_blocked || status.soft_blocked) {
          return;
        }
        
        // Esperar un momento para que WiFi esté listo
        await new Promise(resolve => setTimeout(resolve, 2000));
        
        // Intentar conectar automáticamente
        const resp = await apiRequest('/api/v1/wifi/connect', {
          method: 'POST',
          body: { 
            ssid: lastSSID, 
            password: lastPassword || ''
          }
        });
        
        if (resp.ok) {
          const data = await resp.json();
          if (data.success) {
            console.log('Auto-conectado a:', lastSSID);
            // Actualizar estado después de un momento
            setTimeout(() => {
              loadConnectionStatus();
            }, 3000);
          }
        }
      } catch (e) {
        console.error('Error en auto-conexión:', e);
      }
    }
    
    // Refresh handlers
    function initWiFiPage() {
      console.log('Inicializando página WiFi...');
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
    const autoConnectEnabled = localStorage.getItem('wifi_auto_connect') !== 'false'; // Por defecto true
    if (autoConnectEnabled) {
      // Intentar auto-conectar después de un momento
      setTimeout(() => {
        autoConnectToLastNetwork();
      }, 3000);
    }
    
    // Mostrar mensaje inicial para escanear redes
    const emptyEl = document.getElementById('networks-empty');
    if (emptyEl) emptyEl.style.display = 'block';
    
    // Refresh connection status every 30 seconds
    setInterval(loadConnectionStatus, 30000);
    
    // Auto-scan networks on page load
    setTimeout(() => {
      scanNetworks();
    }, 2000);
    
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
  }
  
  // Toggle Software Switch
  async function toggleSoftwareSwitch() {
    const btn = document.getElementById('toggle-software-switch-btn');
    
    if (btn) {
      btn.disabled = true;
      const originalHtml = btn.innerHTML;
      btn.innerHTML = '<span class="spinning"><i class="bi bi-arrow-clockwise"></i></span> ' + t('wifi.processing', 'Processing...');
      
      try {
        const resp = await apiRequest('/api/v1/wifi/software-switch', { method: 'POST' });
        
        if (!resp.ok) {
          if (resp.status === 401) return;
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
        
        let data;
        try {
          data = await resp.json();
        } catch (e) {
          console.error('Error parsing response:', e);
          showAlert('danger', t('errors.invalid_response', 'Invalid response from server'));
          return;
        }
        
        if (data.success === true) {
          showAlert('success', data.message || t('wifi.software_switch_toggled', 'Software switch toggled successfully'));
          
          // Actualizar estado después de un momento
          setTimeout(async () => {
            await loadConnectionStatus();
          }, 1500);
        } else {
          const errorMsg = data.error || data.message || t('errors.operation_failed', 'Operation failed');
          showAlert('danger', errorMsg);
        }
      } catch (e) {
        console.error('Error toggling software switch:', e);
        if (e.message && e.message.includes('401')) return;
        showAlert('danger', t('errors.network_error', 'Network error: ') + e.message);
      } finally {
        if (btn) {
          btn.disabled = false;
          btn.innerHTML = originalHtml;
        }
      }
    }
  }

  // Export functions to window immediately (before DOM ready)
  window.toggleWiFi = toggleWiFi;
  window.unblockWiFi = unblockWiFi;
  window.toggleSoftwareSwitch = toggleSoftwareSwitch;
  window.scanNetworks = scanNetworks;
  window.connectToNetwork = connectToNetwork;
  window.toggleAutoConnect = toggleAutoConnect;
  window.loadConnectionStatus = loadConnectionStatus;
  
  // Initialize when DOM is ready
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initWiFiPage);
  } else {
    // DOM already loaded, initialize immediately
    setTimeout(initWiFiPage, 100);
  }
})();
