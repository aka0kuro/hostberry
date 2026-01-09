// WiFi Page JavaScript
(function() {
  'use strict';

  // Función de traducción
  const t = (key, defaultValue) => {
    if (window.HostBerry && window.HostBerry.t) {
      return window.HostBerry.t(key, defaultValue);
    }
    return defaultValue || key;
  };

  // Función para mostrar alertas
  const showAlert = (type, message) => {
    if (window.HostBerry && window.HostBerry.showAlert) {
      window.HostBerry.showAlert(type, message);
    } else {
      alert(message);
    }
  };

  // Función para hacer peticiones API
  const apiRequest = async (url, options) => {
    if (window.HostBerry && window.HostBerry.apiRequest) {
      return await window.HostBerry.apiRequest(url, options);
    }
    const opts = Object.assign({ method: 'GET', headers: {} }, options || {});
    return await fetch(url, opts);
  };

  // Cargar estado de conexión
  async function loadConnectionStatus() {
    try {
      const resp = await apiRequest('/api/v1/wifi/status');
      if (!resp.ok) {
        console.error('Error obteniendo estado WiFi:', resp.status);
        return;
      }
      const data = await resp.json();
      updateStatusCards(data);
      updateConnectionInfo(data);
    } catch (error) {
      console.error('Error cargando estado WiFi:', error);
    }
  }

  // Actualizar tarjetas de estado
  function updateStatusCards(data) {
    const wifiStatusValue = document.getElementById('wifi-status-value');
    const wifiStatusBar = document.getElementById('wifi-status-bar');
    const wifiStatusIcon = document.getElementById('wifi-status-icon');
    const connectionStatusValue = document.getElementById('connection-status-value');
    const signalValue = document.getElementById('signal-value');
    const signalBar = document.getElementById('signal-bar');
    const networksCountValue = document.getElementById('networks-count-value');
    const networksTable = document.getElementById('networksTable');
    
    // WiFi Status
    if (wifiStatusValue && wifiStatusBar && wifiStatusIcon) {
      const enabled = data.enabled || false;
      wifiStatusValue.textContent = enabled ? t('wifi.enabled', 'Enabled') : t('wifi.disabled', 'Disabled');
      wifiStatusBar.style.width = enabled ? '100%' : '0%';
      wifiStatusIcon.className = enabled ? 'bi bi-wifi' : 'bi bi-wifi-off';
      wifiStatusIcon.style.color = enabled ? 'var(--hb-primary)' : 'var(--hb-text-muted)';
    }

    // Connection Status
    if (connectionStatusValue) {
      const connected = data.connected || false;
      const ssid = data.ssid || '--';
      connectionStatusValue.textContent = connected ? ssid : t('wifi.disconnected', 'Disconnected');
    }

    // Signal
    if (signalValue && signalBar) {
      // Buscar signal en connection_info primero, luego en data directamente
      let signal = 0;
      if (data.connection_info && data.connection_info.signal) {
        signal = parseInt(data.connection_info.signal) || 0;
      } else if (data.signal) {
        signal = parseInt(data.signal) || 0;
      }
      const signalPercent = signal > 0 ? Math.min(100, Math.max(0, (signal + 100) * 2)) : 0;
      signalValue.textContent = signal > 0 ? signal + 'dBm' : '--';
      signalBar.style.width = signalPercent + '%';
    }

    // Networks Count
    if (networksCountValue && networksTable) {
      const count = networksTable.querySelectorAll('.network-card').length;
      networksCountValue.textContent = count;
    }
  }

  // Actualizar información de conexión
  function updateConnectionInfo(data) {
    const statusEl = document.getElementById('connection-status');
    const ssidEl = document.getElementById('connection-ssid');
    const signalEl = document.getElementById('connection-signal');
    const securityEl = document.getElementById('connection-security');
    const channelEl = document.getElementById('connection-channel');
    const ipEl = document.getElementById('connection-ip');
    const macEl = document.getElementById('connection-mac');
    const speedEl = document.getElementById('connection-speed');

    if (statusEl) {
      statusEl.textContent = data.connected 
        ? t('wifi.connected', 'Connected') 
        : t('wifi.disconnected', 'Disconnected');
    }
    if (ssidEl) ssidEl.textContent = data.ssid || '--';
    
    // Buscar signal en connection_info primero
    let signal = 0;
    if (data.connection_info && data.connection_info.signal) {
      signal = parseInt(data.connection_info.signal) || 0;
    } else if (data.signal) {
      signal = parseInt(data.signal) || 0;
    }
    if (signalEl) signalEl.textContent = signal > 0 ? signal + 'dBm' : '--';
    
    // Buscar security en connection_info primero
    const security = (data.connection_info && data.connection_info.security) || data.security || '--';
    if (securityEl) securityEl.textContent = security;
    
    // Buscar channel en connection_info primero
    const channel = (data.connection_info && data.connection_info.channel) || data.channel || '--';
    if (channelEl) channelEl.textContent = channel;
    
    // Buscar ip en connection_info primero
    const ip = (data.connection_info && data.connection_info.ip) || data.ip || '--';
    if (ipEl) ipEl.textContent = ip;
    
    // Buscar mac en connection_info primero
    const mac = (data.connection_info && data.connection_info.mac) || data.mac || '--';
    if (macEl) macEl.textContent = mac;
    
    // Buscar speed en connection_info primero
    const speed = (data.connection_info && data.connection_info.speed) || data.speed || '--';
    if (speedEl) speedEl.textContent = speed;
  }

  // Cargar interfaces WiFi
  async function loadInterfaces() {
    try {
      const resp = await apiRequest('/api/v1/wifi/interfaces');
      if (!resp.ok) return;
      const data = await resp.json();
      const select = document.getElementById('wifi-interface');
      if (!select) return;
      
      select.innerHTML = '<option value="">' + t('wifi.auto_detect', 'Auto-detect') + '</option>';
      if (data.interfaces && Array.isArray(data.interfaces)) {
        data.interfaces.forEach(iface => {
          const option = document.createElement('option');
          option.value = iface;
          option.textContent = iface;
          select.appendChild(option);
        });
      }
    } catch (error) {
      console.error('Error cargando interfaces:', error);
    }
  }

  // Toggle WiFi
  async function toggleWiFi() {
    const btn = document.getElementById('toggle-wifi-btn');
    const icon = document.getElementById('toggle-wifi-icon');
    const text = document.getElementById('toggle-wifi-text');
    
    if (!btn || btn.disabled) return;
    
    btn.disabled = true;
    const originalText = text.textContent;
    text.textContent = t('wifi.enabling', 'Enabling...');
    
    try {
      const resp = await apiRequest('/api/v1/wifi/toggle', { method: 'POST' });
      const data = await resp.json();
      
      if (resp.ok && data.success) {
        showAlert('success', t('wifi.wifi_toggled', 'WiFi state changed successfully'));
        await loadConnectionStatus();
      } else {
        showAlert('danger', data.error || t('wifi.toggle_error', 'Error toggling WiFi'));
      }
    } catch (error) {
      console.error('Error toggling WiFi:', error);
      showAlert('danger', t('wifi.toggle_error', 'Error toggling WiFi'));
    } finally {
      btn.disabled = false;
      text.textContent = originalText;
    }
  }

  // Unblock WiFi
  async function unblockWiFi() {
    const btn = document.getElementById('unblock-wifi-btn');
    if (!btn || btn.disabled) return;
    
    btn.disabled = true;
    const originalText = btn.querySelector('span').textContent;
    btn.querySelector('span').textContent = t('wifi.unblocking', 'Unblocking...');
    
    try {
      const resp = await apiRequest('/api/v1/wifi/unblock', { method: 'POST' });
      const data = await resp.json();
      
      if (resp.ok && data.success) {
        showAlert('success', t('wifi.wifi_unblocked', 'WiFi unblocked successfully'));
        btn.style.display = 'none';
        await loadConnectionStatus();
      } else {
        showAlert('danger', data.error || t('wifi.unblock_error', 'Error unblocking WiFi'));
      }
    } catch (error) {
      console.error('Error unblocking WiFi:', error);
      showAlert('danger', t('wifi.unblock_error', 'Error unblocking WiFi'));
    } finally {
      btn.disabled = false;
      btn.querySelector('span').textContent = originalText;
    }
  }

  // Toggle Software Switch
  async function toggleSoftwareSwitch() {
    const btn = document.getElementById('toggle-software-switch-btn');
    const icon = document.getElementById('software-switch-icon');
    const text = document.getElementById('software-switch-text');
    
    if (!btn || btn.disabled) return;
    
    btn.disabled = true;
    
    try {
      const resp = await apiRequest('/api/v1/wifi/software-switch', { method: 'POST' });
      const data = await resp.json();
      
      if (resp.ok && data.success) {
        showAlert('success', t('wifi.software_switch_toggled', 'Software switch toggled successfully'));
        if (icon) {
          icon.className = data.enabled ? 'bi bi-toggle-on' : 'bi bi-toggle-off';
        }
        if (text) {
          text.textContent = data.enabled 
            ? t('wifi.disable_software_switch', 'Disable Software Switch')
            : t('wifi.enable_software_switch', 'Enable Software Switch');
        }
        await loadConnectionStatus();
      } else {
        showAlert('danger', data.error || t('wifi.toggle_error', 'Error toggling switch'));
      }
    } catch (error) {
      console.error('Error toggling software switch:', error);
      showAlert('danger', t('wifi.toggle_error', 'Error toggling switch'));
    } finally {
      btn.disabled = false;
    }
  }

  // Escanear redes
  async function scanNetworks() {
    const loadingEl = document.getElementById('networks-loading');
    const emptyEl = document.getElementById('networks-empty');
    const tableEl = document.getElementById('networks-table-container');
    const tbody = document.getElementById('networksTable');
    const interfaceSelect = document.getElementById('wifi-interface');
    
    if (loadingEl) loadingEl.style.display = 'block';
    if (emptyEl) emptyEl.style.display = 'none';
    if (tableEl) tableEl.style.display = 'none';
    if (tbody) tbody.innerHTML = '';
    
    try {
      let url = '/api/v1/wifi/scan';
      const selectedInterface = interfaceSelect ? interfaceSelect.value : '';
      if (selectedInterface) {
        url += '?interface=' + encodeURIComponent(selectedInterface);
      }
      
      const resp = await apiRequest(url);
      
      if (!resp.ok) {
        let errorText = '';
        try {
          errorText = await resp.text();
        } catch (e) {
          console.error('No se pudo leer el texto de error:', e);
        }
        
        if (loadingEl) loadingEl.style.display = 'none';
        
        if (emptyEl) {
          emptyEl.style.display = 'block';
          emptyEl.innerHTML = `
            <div class="text-center py-5">
              <i class="bi bi-exclamation-triangle text-warning" style="font-size: 4rem;"></i>
              <p class="mt-3">${t('errors.scan_failed', 'Scan failed')}</p>
              <p class="text-muted small">${errorText || t('errors.unknown_error', 'Unknown error')}</p>
              <button class="btn btn-primary mt-3" onclick="scanNetworks()">
                <i class="bi bi-arrow-clockwise me-2"></i>${t('common.retry', 'Retry')}
              </button>
            </div>
          `;
        }
        throw new Error('Error al escanear redes: HTTP ' + resp.status);
      }
      
      let data;
      try {
        const text = await resp.text();
        if (!text || text.trim() === '') {
          data = { networks: [] };
        } else {
          data = JSON.parse(text);
        }
      } catch (parseError) {
        console.error('Error parsing JSON response:', parseError);
        data = { networks: [] };
      }
      
      if (loadingEl) loadingEl.style.display = 'none';
      
      let networks = [];
      if (data.networks && Array.isArray(data.networks)) {
        networks = data.networks;
      } else if (data && Array.isArray(data)) {
        networks = data;
      }
      
      if (networks.length === 0) {
        if (emptyEl) emptyEl.style.display = 'block';
        if (tableEl) tableEl.style.display = 'none';
      } else {
        if (emptyEl) emptyEl.style.display = 'none';
        if (tableEl) tableEl.style.display = 'block';
        if (tbody) {
          tbody.innerHTML = '';
          networks.forEach((net, index) => {
            const signal = net.signal || net.rssi || 0;
            const signalPercent = Math.min(100, Math.max(0, (parseInt(signal) + 100) * 2));
            const signalColor = signalPercent > 70 ? 'text-success' : (signalPercent > 40 ? 'text-warning' : 'text-danger');
            const security = net.security || net.encryption || 'none';
            const securityIcon = security === 'none' || security === 'Open' ? 'bi-unlock' : 'bi-lock';
            const ssid = net.ssid || `Unnamed-${index}`;
            const escapedSsid = ssid.replace(/'/g, "\\'").replace(/"/g, '&quot;');
            
            const card = document.createElement('div');
            card.className = 'network-card';
            // Guardar información en atributos data para acceso fácil
            card.setAttribute('data-ssid', ssid);
            card.setAttribute('data-security', security);
            card.setAttribute('data-signal', signal);
            card.setAttribute('data-channel', net.channel || '');
            card.innerHTML = `
              <div class="network-card-content">
                <div class="network-card-icon ${signalColor}">
                  <i class="bi bi-wifi"></i>
                </div>
                <div class="network-card-info">
                  <div class="network-card-ssid">${ssid}</div>
                  <div class="network-card-details">
                    <span class="network-card-detail-item">
                      <i class="bi bi-bar-chart me-1"></i> ${signal}dBm (${signalPercent}%)
                    </span>
                    <span class="network-card-detail-item">
                      <i class="bi ${securityIcon} me-1"></i> ${security.toUpperCase()}
                    </span>
                    ${net.channel ? `<span class="network-card-detail-item"><i class="bi bi-hash me-1"></i> ${net.channel}</span>` : ''}
                  </div>
                </div>
              </div>
              <div class="network-card-actions">
                <button class="btn btn-primary btn-sm" onclick="connectToNetwork('${escapedSsid}', '${security}', this)">
                  <i class="bi bi-box-arrow-in-right me-2"></i>${t('wifi.connect', 'Connect')}
                </button>
              </div>
            `;
            tbody.appendChild(card);
          });
        }
      }
      
      updateStatusCards({});
      await loadConnectionStatus();
    } catch (error) {
      console.error('Error escaneando redes:', error);
      
      if (loadingEl) loadingEl.style.display = 'none';
      
      if (emptyEl) {
        emptyEl.style.display = 'block';
        emptyEl.innerHTML = `
          <div class="text-center py-5">
            <i class="bi bi-exclamation-triangle text-danger" style="font-size: 4rem;"></i>
            <p class="mt-3">${t('errors.scan_error', 'Scan error')}</p>
            <p class="text-muted small">${error.message}</p>
            <button class="btn btn-primary mt-3" onclick="scanNetworks()">
              <i class="bi bi-arrow-clockwise me-2"></i>${t('common.retry', 'Retry')}
            </button>
          </div>
        `;
      }
    }
  }

  // Conectar a red
  async function connectToNetwork(ssid, security, buttonElement) {
    const card = buttonElement ? buttonElement.closest('.network-card') : null;
    let formWrapper = card ? card.querySelector('.network-connect-form-wrapper') : null;
    
    // Si ya hay un formulario, removerlo
    if (formWrapper) {
      formWrapper.remove();
      return;
    }
    
    // Obtener información de la red desde la tarjeta
    const cardContent = card ? card.querySelector('.network-card-content') : null;
    let signal = '--';
    let channel = '--';
    let encryption = security || 'Unknown';
    
    if (cardContent) {
      const details = cardContent.querySelectorAll('.network-card-detail-item');
      details.forEach(detail => {
        const text = detail.textContent || '';
        if (text.includes('dBm')) {
          const match = text.match(/(\d+)dBm/);
          if (match) signal = match[1] + 'dBm';
        }
        if (text.includes('#')) {
          const match = text.match(/#\s*(\d+)/);
          if (match) channel = match[1];
        }
      });
    }
    
    // Crear formulario
    formWrapper = document.createElement('div');
    formWrapper.className = 'network-connect-form-wrapper';
    
    const needsPassword = security && security !== 'none' && security !== 'Open' && security !== 'open';
    
    formWrapper.innerHTML = `
      <div class="network-connect-form show">
        <div class="network-connect-info mb-3">
          <div class="row g-2">
            <div class="col-6">
              <div class="network-info-item">
                <label class="network-info-label">${t('wifi.network_signal', 'Signal')}</label>
                <div class="network-info-value">${signal}</div>
              </div>
            </div>
            <div class="col-6">
              <div class="network-info-item">
                <label class="network-info-label">${t('wifi.network_security', 'Security')}</label>
                <div class="network-info-value">${encryption.toUpperCase()}</div>
              </div>
            </div>
            ${channel !== '--' ? `
            <div class="col-6">
              <div class="network-info-item">
                <label class="network-info-label">${t('wifi.network_channel', 'Channel')}</label>
                <div class="network-info-value">${channel}</div>
              </div>
            </div>
            ` : ''}
          </div>
        </div>
        <div class="network-connect-form-group">
          <label class="network-connect-form-label">${t('wifi.network_password', 'Password')}</label>
          <input type="password" class="network-connect-form-input" id="network-password-${ssid.replace(/[^a-zA-Z0-9]/g, '-')}" 
                 placeholder="${needsPassword ? t('wifi.network_password', 'Password') : t('wifi.open_network', 'Open network')}" 
                 ${needsPassword ? 'required' : ''}>
        </div>
        <div class="network-connect-form-actions">
          <button class="btn btn-secondary btn-sm" onclick="this.closest('.network-connect-form-wrapper').remove()">
            ${t('common.cancel', 'Cancel')}
          </button>
          <button class="btn btn-primary btn-sm network-connect-submit" onclick="submitConnect('${ssid.replace(/'/g, "\\'")}', '${security.replace(/'/g, "\\'")}', this)">
            <i class="bi bi-box-arrow-in-right me-2"></i>${t('wifi.connect', 'Connect')}
          </button>
        </div>
      </div>
    `;
    
    if (card) {
      card.appendChild(formWrapper);
    } else {
      // Si no hay card, mostrar modal o alert
      const password = needsPassword ? prompt(t('wifi.network_password', 'Password') + ':', '') : '';
      if (password !== null) {
        await submitConnectDirect(ssid, security, password);
      }
    }
  }

  // Enviar conexión
  async function submitConnect(ssid, security, buttonElement) {
    const formWrapper = buttonElement.closest('.network-connect-form-wrapper');
    const passwordInput = formWrapper.querySelector('input[type="password"]');
    const password = passwordInput ? passwordInput.value : '';
    
    buttonElement.disabled = true;
    buttonElement.innerHTML = `<i class="bi bi-arrow-clockwise spinning me-2"></i>${t('wifi.connecting', 'Connecting...')}`;
    
    try {
      const resp = await apiRequest('/api/v1/wifi/connect', {
        method: 'POST',
        body: {
          ssid: ssid,
          password: password,
          security: security
        }
      });
      
      const data = await resp.json();
      
      if (resp.ok && data.success) {
        showAlert('success', t('wifi.connected_to', 'Connected to {ssid}').replace('{ssid}', ssid));
        formWrapper.remove();
        await loadConnectionStatus();
        // Opcional: escanear nuevamente después de conectar
        setTimeout(() => scanNetworks(), 2000);
      } else {
        showAlert('danger', data.error || t('wifi.connect_error', 'Error connecting to WiFi'));
        buttonElement.disabled = false;
        buttonElement.innerHTML = `<i class="bi bi-box-arrow-in-right me-2"></i>${t('wifi.connect', 'Connect')}`;
      }
    } catch (error) {
      console.error('Error conectando:', error);
      showAlert('danger', t('wifi.connect_error', 'Error connecting to WiFi'));
      buttonElement.disabled = false;
      buttonElement.innerHTML = `<i class="bi bi-box-arrow-in-right me-2"></i>${t('wifi.connect', 'Connect')}`;
    }
  }

  // Enviar conexión directa (sin formulario)
  async function submitConnectDirect(ssid, security, password) {
    try {
      const resp = await apiRequest('/api/v1/wifi/connect', {
        method: 'POST',
        body: {
          ssid: ssid,
          password: password || '',
          security: security
        }
      });
      
      const data = await resp.json();
      
      if (resp.ok && data.success) {
        showAlert('success', t('wifi.connected_to', 'Connected to {ssid}').replace('{ssid}', ssid));
        await loadConnectionStatus();
        setTimeout(() => scanNetworks(), 2000);
      } else {
        showAlert('danger', data.error || t('wifi.connect_error', 'Error connecting to WiFi'));
      }
    } catch (error) {
      console.error('Error conectando:', error);
      showAlert('danger', t('wifi.connect_error', 'Error connecting to WiFi'));
    }
  }

  // Exportar funciones globales
  window.toggleWiFi = toggleWiFi;
  window.unblockWiFi = unblockWiFi;
  window.toggleSoftwareSwitch = toggleSoftwareSwitch;
  window.scanNetworks = scanNetworks;
  window.connectToNetwork = connectToNetwork;
  window.submitConnect = submitConnect;

  // Inicializar cuando el DOM esté listo
  document.addEventListener('DOMContentLoaded', async function() {
    await loadInterfaces();
    await loadConnectionStatus();
    
    // Verificar si WiFi está bloqueado
    try {
      const resp = await apiRequest('/api/v1/wifi/status');
      if (resp.ok) {
        const data = await resp.json();
        const unblockBtn = document.getElementById('unblock-wifi-btn');
        if (unblockBtn && data.hard_blocked) {
          unblockBtn.style.display = 'block';
        }
      }
    } catch (error) {
      console.error('Error verificando estado inicial:', error);
    }
  });
})();
