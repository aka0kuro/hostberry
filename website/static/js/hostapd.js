// HostAPD Page JavaScript
(function() {
  'use strict';

  // Función de traducción
  const t = (key, defaultValue) => {
    if (window.HostBerry && window.HostBerry.t) {
      return window.HostBerry.t(key, defaultValue);
    }
    return defaultValue || key;
  };

  // Función para traducir mensajes de error del backend
  const translateError = (errorMessage) => {
    if (!errorMessage) return '';
    
    const errorLower = errorMessage.toLowerCase();
    
    // Mapeo de mensajes de error comunes del backend
    const errorMap = {
      'hostapd toggle no implementado': t('hostapd.toggle_not_implemented', 'HostAPD toggle not implemented'),
      'hostapd restart no implementado': t('hostapd.restart_not_implemented', 'HostAPD restart not implemented'),
      'hostapd config no implementado': t('hostapd.config_not_implemented', 'HostAPD config not implemented'),
      'error loading access points': t('hostapd.error_loading_aps', 'Error loading access points'),
      'error loading clients': t('hostapd.error_loading_clients', 'Error loading clients'),
      'operation failed': t('errors.operation_failed', 'Operation failed'),
      'network error': t('errors.network_error', 'Network error'),
    };
    
    for (const [key, value] of Object.entries(errorMap)) {
      if (errorLower.includes(key)) {
        return value;
      }
    }
    
    return errorMessage;
  };

  // Cargar estado de HostAPD
  async function loadHostAPDStatus() {
    const container = document.getElementById('hostapdStatusContainer');
    if (!container) return;
    
    try {
      // Intentar obtener el estado del servicio
      const resp = await HostBerry.apiRequest('/api/v1/system/services');
      if (resp && resp.ok) {
        const data = await resp.json();
        const hostapd = data.services?.hostapd || {};
        const enabled = hostapd.active || false;
        const running = hostapd.status === 'active';
        
        // Actualizar UI
        updateStatusUI(enabled, running);
      } else {
        // Si no hay servicio, mostrar estado desconocido
        updateStatusUI(false, false);
      }
    } catch (e) {
      console.error('Error loading HostAPD status:', e);
      updateStatusUI(false, false);
    }
  }

  function updateStatusUI(enabled, running) {
    // Actualizar tarjeta de estado
    const statusValue = document.getElementById('hostapd-status-value');
    const statusBar = document.getElementById('hostapd-status-bar');
    const statusIcon = document.getElementById('hostapd-status-icon');
    const toggleBtn = document.getElementById('toggle-hostapd-btn');
    const toggleText = document.getElementById('toggle-hostapd-text');
    const container = document.getElementById('hostapdStatusContainer');
    
    if (statusValue) {
      statusValue.textContent = enabled ? t('hostapd.enabled', 'Enabled') : t('hostapd.disabled', 'Disabled');
      statusValue.className = 'stat-value' + (enabled ? ' text-success' : ' text-danger');
    }
    
    if (statusBar) {
      statusBar.style.width = enabled ? '100%' : '0%';
      statusBar.className = 'stat-progress-bar' + (enabled ? ' bg-success' : ' bg-danger');
    }
    
    if (statusIcon) {
      statusIcon.className = 'bi ' + (enabled ? 'bi-heart-pulse-fill text-success' : 'bi-heart-pulse text-danger');
    }
    
    if (toggleBtn) {
      toggleBtn.className = 'btn ' + (enabled ? 'btn-outline-danger' : 'btn-outline-success');
      toggleBtn.disabled = false; // Asegurar que el botón esté habilitado
    }
    
    if (toggleText) {
      toggleText.innerHTML = enabled ? t('hostapd.disable_hostapd', 'Disable HostAPD') : t('hostapd.enable_hostapd', 'Enable HostAPD');
    } else if (toggleBtn) {
      // Si no hay toggleText, actualizar el contenido del botón directamente
      const icon = enabled ? 'bi-x-circle' : 'bi-router';
      toggleBtn.innerHTML = '<i class="bi ' + icon + ' me-2"></i><span>' + (enabled ? t('hostapd.disable_hostapd', 'Disable HostAPD') : t('hostapd.enable_hostapd', 'Enable HostAPD')) + '</span>';
    }
    
    if (container) {
      container.innerHTML = `
        <div class="info-grid">
          <div class="info-item">
            <span class="info-label">${t('hostapd.hostapd_status', 'HostAPD Status')}</span>
            <span class="info-value ${enabled ? 'text-success' : 'text-danger'}">
              <i class="bi ${enabled ? 'bi-check-circle' : 'bi-x-circle'} me-1"></i>
              ${enabled ? t('hostapd.enabled', 'Enabled') : t('hostapd.disabled', 'Disabled')}
            </span>
          </div>
          <div class="info-item">
            <span class="info-label">${t('hostapd.service_status', 'Service Status')}</span>
            <span class="info-value ${running ? 'text-success' : 'text-danger'}">
              <i class="bi ${running ? 'bi-check-circle' : 'bi-x-circle'} me-1"></i>
              ${running ? t('hostapd.running', 'Running') : t('hostapd.stopped', 'Stopped')}
            </span>
          </div>
        </div>
      `;
    }
  }

  // Cargar puntos de acceso
  async function loadAccessPoints() {
    const container = document.getElementById('accessPointsContainer');
    if (!container) return;
    
    container.innerHTML = '<div class="text-center py-4"><div class="spinning mb-3"><i class="bi bi-arrow-clockwise" style="font-size: 2rem;"></i></div><p class="text-muted">' + t('common.loading', 'Loading...') + '</p></div>';
    
    try {
      const resp = await HostBerry.apiRequest('/api/v1/hostapd/access-points');
      if (resp && resp.ok) {
        const aps = await resp.json();
        const countEl = document.getElementById('access-points-count');
        if (countEl) countEl.textContent = Array.isArray(aps) ? aps.length : 0;
        
        if (!Array.isArray(aps) || aps.length === 0) {
          container.innerHTML = `
            <div class="text-center py-4">
              <i class="bi bi-wifi text-muted" style="font-size: 3rem;"></i>
              <p class="text-muted mt-3">${t('hostapd.no_access_points', 'No access points configured')}</p>
            </div>
          `;
          return;
        }
        
        let html = '<div class="table-responsive"><table class="table table-hover"><thead><tr>';
        html += `<th>${t('hostapd.access_point_name', 'Name')}</th>`;
        html += `<th>${t('hostapd.access_point_ssid', 'SSID')}</th>`;
        html += `<th>${t('hostapd.access_point_status', 'Status')}</th>`;
        html += `<th>${t('hostapd.access_point_clients', 'Clients')}</th>`;
        html += `<th>${t('common.actions', 'Actions')}</th>`;
        html += '</tr></thead><tbody>';
        
        aps.forEach(ap => {
          const enabled = ap.enabled !== false;
          html += '<tr>';
          html += `<td>${ap.name || ap.ssid || '-'}</td>`;
          html += `<td>${ap.ssid || '-'}</td>`;
          html += `<td><span class="badge bg-${enabled ? 'success' : 'danger'}">${enabled ? t('hostapd.active', 'Active') : t('hostapd.inactive', 'Inactive')}</span></td>`;
          html += `<td>${ap.clients_count || 0}</td>`;
          html += `<td><button class="btn btn-sm btn-outline-primary" onclick="configureAccessPoint('${ap.name || ap.ssid || ''}')"><i class="bi bi-gear"></i></button></td>`;
          html += '</tr>';
        });
        
        html += '</tbody></table></div>';
        container.innerHTML = html;
      } else {
        const errorText = await resp.text().catch(() => '');
        container.innerHTML = `
          <div class="text-center py-4">
            <i class="bi bi-exclamation-triangle text-warning" style="font-size: 3rem;"></i>
            <p class="text-muted mt-3">${translateError(errorText) || t('hostapd.error_loading_aps', 'Error loading access points')}</p>
          </div>
        `;
        if (resp.status >= 500) {
          HostBerry.showAlert('danger', translateError(errorText) || t('hostapd.error_loading_aps', 'Error loading access points'));
        }
      }
    } catch (e) {
      console.error('Error loading access points:', e);
      container.innerHTML = `
        <div class="text-center py-4">
          <i class="bi bi-exclamation-triangle text-danger" style="font-size: 3rem;"></i>
          <p class="text-muted mt-3">${t('errors.network_error', 'Network error')}</p>
        </div>
      `;
      HostBerry.showAlert('danger', t('errors.network_error', 'Network error'));
    }
  }

  // Cargar clientes
  async function loadClients() {
    const container = document.getElementById('clientsContainer');
    if (!container) return;
    
    container.innerHTML = '<div class="text-center py-4"><div class="spinning mb-3"><i class="bi bi-arrow-clockwise" style="font-size: 2rem;"></i></div><p class="text-muted">' + t('common.loading', 'Loading...') + '</p></div>';
    
    try {
      const resp = await HostBerry.apiRequest('/api/v1/hostapd/clients');
      if (resp && resp.ok) {
        const clients = await resp.json();
        const countEl = document.getElementById('clients-count');
        if (countEl) countEl.textContent = Array.isArray(clients) ? clients.length : 0;
        
        if (!Array.isArray(clients) || clients.length === 0) {
          container.innerHTML = `
            <div class="text-center py-4">
              <i class="bi bi-people text-muted" style="font-size: 3rem;"></i>
              <p class="text-muted mt-3">${t('hostapd.no_clients', 'No clients connected')}</p>
            </div>
          `;
          return;
        }
        
        let html = '<div class="table-responsive"><table class="table table-hover"><thead><tr>';
        html += `<th>${t('hostapd.client_mac', 'MAC Address')}</th>`;
        html += `<th>${t('hostapd.client_ip', 'IP Address')}</th>`;
        html += `<th>${t('hostapd.client_signal', 'Signal')}</th>`;
        html += `<th>${t('hostapd.client_uptime', 'Uptime')}</th>`;
        html += '</tr></thead><tbody>';
        
        clients.forEach(client => {
          html += '<tr>';
          html += `<td>${client.mac_address || client.mac || '-'}</td>`;
          html += `<td>${client.ip_address || client.ip || '-'}</td>`;
          html += `<td>${client.signal ? client.signal + ' dBm' : '-'}</td>`;
          html += `<td>${client.uptime || '-'}</td>`;
          html += '</tr>';
        });
        
        html += '</tbody></table></div>';
        container.innerHTML = html;
      } else {
        const errorText = await resp.text().catch(() => '');
        container.innerHTML = `
          <div class="text-center py-4">
            <i class="bi bi-exclamation-triangle text-warning" style="font-size: 3rem;"></i>
            <p class="text-muted mt-3">${translateError(errorText) || t('hostapd.error_loading_clients', 'Error loading clients')}</p>
          </div>
        `;
        if (resp.status >= 500) {
          HostBerry.showAlert('danger', translateError(errorText) || t('hostapd.error_loading_clients', 'Error loading clients'));
        }
      }
    } catch (e) {
      console.error('Error loading clients:', e);
      container.innerHTML = `
        <div class="text-center py-4">
          <i class="bi bi-exclamation-triangle text-danger" style="font-size: 3rem;"></i>
          <p class="text-muted mt-3">${t('errors.network_error', 'Network error')}</p>
        </div>
      `;
      HostBerry.showAlert('danger', t('errors.network_error', 'Network error'));
    }
  }

  // Toggle HostAPD
  window.toggleHostAPD = async function() {
    const btn = document.getElementById('toggle-hostapd-btn');
    const toggleText = document.getElementById('toggle-hostapd-text');
    let originalBtnClass = '';
    let originalText = '';
    
    if (btn) {
      btn.disabled = true;
      originalBtnClass = btn.className;
      originalText = toggleText ? toggleText.textContent : btn.textContent;
      if (toggleText) {
        toggleText.innerHTML = '<i class="bi bi-arrow-clockwise spinning me-2"></i>' + t('common.loading', 'Loading...');
      } else {
        btn.innerHTML = '<i class="bi bi-arrow-clockwise spinning me-2"></i>' + t('common.loading', 'Loading...');
      }
    }
    
    const restoreButton = () => {
      if (btn) {
        btn.disabled = false;
        // Recargar el estado para actualizar el botón correctamente
        // Usar un pequeño delay para asegurar que el estado del servidor se haya actualizado
        setTimeout(() => {
          loadHostAPDStatus();
        }, 300);
      }
    };
    
    try {
      console.log('Toggling HostAPD...');
      const resp = await HostBerry.apiRequest('/api/v1/hostapd/toggle', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        }
      });
      
      console.log('HostAPD toggle response:', resp);
      
      if (resp && resp.ok) {
        let result;
        try {
          result = await resp.json();
        } catch (jsonErr) {
          console.error('Error parsing JSON response:', jsonErr);
          const text = await resp.text().catch(() => '');
          console.log('Response text:', text);
          HostBerry.showAlert('warning', t('errors.unexpected_response', 'Unexpected response from server'));
          restoreButton();
          return;
        }
        
        console.log('HostAPD toggle result:', result);
        
        if (result.error) {
          HostBerry.showAlert('warning', translateError(result.error));
          restoreButton();
        } else {
          // Usar el estado real del servicio desde la respuesta
          const actuallyEnabled = result.enabled === true;
          const action = actuallyEnabled ? t('hostapd.enabled', 'Enabled') : t('hostapd.disabled', 'Disabled');
          const statusMsg = result.status ? ` (${result.status})` : '';
          
          if (actuallyEnabled) {
            HostBerry.showAlert('success', t('hostapd.hostapd_status_changed', 'HostAPD {status}').replace('{status}', action) + statusMsg);
          } else {
            // Si se intentó activar pero no se activó, mostrar advertencia
            if (result.action === 'enable') {
              HostBerry.showAlert('warning', t('hostapd.enable_failed', 'Failed to enable HostAPD. Check configuration and logs.') + statusMsg);
            } else {
              HostBerry.showAlert('success', t('hostapd.hostapd_status_changed', 'HostAPD {status}').replace('{status}', action) + statusMsg);
            }
          }
          
          // Restaurar el botón y recargar el estado
          restoreButton();
          setTimeout(() => {
            loadAccessPoints();
            loadClients();
          }, 500);
        }
      } else {
        const status = resp ? resp.status : 'unknown';
        console.error('HostAPD toggle failed with status:', status);
        let errorText = '';
        try {
          errorText = await resp.text();
        } catch (e) {
          errorText = `HTTP ${status}`;
        }
        console.error('Error response:', errorText);
        HostBerry.showAlert('danger', translateError(errorText) || t('errors.operation_failed', 'Operation failed'));
        restoreButton();
      }
    } catch (e) {
      console.error('Error toggling HostAPD:', e);
      HostBerry.showAlert('danger', t('errors.network_error', 'Network error') + ': ' + (e.message || String(e)));
      restoreButton();
    }
  };

  // Restart HostAPD
  window.restartHostAPD = async function() {
    if (!confirm(t('hostapd.confirm_restart', 'Are you sure you want to restart HostAPD?'))) {
      return;
    }
    
    try {
      const resp = await HostBerry.apiRequest('/api/v1/hostapd/restart', {
        method: 'POST'
      });
      
      if (resp && resp.ok) {
        const result = await resp.json();
        if (result.error) {
          HostBerry.showAlert('warning', translateError(result.error));
        } else {
          HostBerry.showAlert('success', t('messages.operation_successful', 'Operation successful'));
          setTimeout(() => {
            loadHostAPDStatus();
            loadAccessPoints();
            loadClients();
          }, 2000);
        }
      } else {
        const errorText = await resp.text().catch(() => '');
        HostBerry.showAlert('danger', translateError(errorText) || t('errors.operation_failed', 'Operation failed'));
      }
    } catch (e) {
      console.error('Error restarting HostAPD:', e);
      HostBerry.showAlert('danger', t('errors.network_error', 'Network error'));
    }
  };

  // Configure Access Point
  window.configureAccessPoint = function(apName) {
    HostBerry.showAlert('info', t('hostapd.configuring_access_point', 'Configuring access point') + ': ' + apName);
    // TODO: Implementar modal de configuración
  };

  // Toggle password visibility
  window.toggleHostAPDPassword = function() {
    const passwordInput = document.getElementById('hostapd-password');
    const toggleIcon = document.getElementById('hostapd-password-toggle-icon');
    if (passwordInput && toggleIcon) {
      if (passwordInput.type === 'password') {
        passwordInput.type = 'text';
        toggleIcon.className = 'bi bi-eye-slash';
      } else {
        passwordInput.type = 'password';
        toggleIcon.className = 'bi bi-eye';
      }
    }
  };

  // Cargar interfaces WiFi para el selector
  async function loadInterfaces() {
    const select = document.getElementById('hostapd-interface');
    if (!select) return;
    
    try {
      const resp = await HostBerry.apiRequest('/api/v1/wifi/interfaces');
      if (resp && resp.ok) {
        const data = await resp.json();
        const interfaces = Array.isArray(data) ? data : (data.interfaces || []);
        
        select.innerHTML = '<option value="">' + t('hostapd.select_interface', 'Select Interface') + '</option>';
        interfaces.forEach(iface => {
          const name = iface.name || iface;
          const option = document.createElement('option');
          option.value = name;
          option.textContent = name;
          select.appendChild(option);
        });
      }
    } catch (e) {
      console.error('Error loading interfaces:', e);
    }
  }

  // Inicializar página
  function initHostAPDPage() {
    // Esperar a que HostBerry esté disponible
    function waitForHostBerry(callback) {
      if (window.HostBerry && window.HostBerry.apiRequest) {
        callback();
      } else {
        setTimeout(() => waitForHostBerry(callback), 100);
      }
    }
    
    waitForHostBerry(() => {
      loadHostAPDStatus();
      loadAccessPoints();
      loadClients();
      loadInterfaces();
      
      // Configurar formulario
      const form = document.getElementById('hostapdConfigForm');
      if (form) {
        form.addEventListener('submit', async function(e) {
          e.preventDefault();
          const fd = new FormData(this);
          const data = {
            interface: fd.get('interface'),
            ssid: fd.get('ssid'),
            password: fd.get('password') || '',
            channel: parseInt(fd.get('channel')),
            security: fd.get('security'),
            gateway: fd.get('gateway') || '192.168.4.1',
            dhcp_range_start: fd.get('dhcp_range_start') || '192.168.4.2',
            dhcp_range_end: fd.get('dhcp_range_end') || '192.168.4.254',
            lease_time: fd.get('lease_time') || '12h'
          };
          
          try {
            const resp = await HostBerry.apiRequest('/api/v1/hostapd/config', {
              method: 'POST',
              body: data
            });
            
            if (resp && resp.ok) {
              const result = await resp.json();
              if (result.error) {
                HostBerry.showAlert('warning', translateError(result.error));
              } else {
                HostBerry.showAlert('success', t('messages.changes_saved', 'Changes saved successfully'));
                setTimeout(() => {
                  loadAccessPoints();
                }, 1000);
              }
            } else {
              const errorText = await resp.text().catch(() => '');
              HostBerry.showAlert('danger', translateError(errorText) || t('errors.configuration_error', 'Configuration error'));
            }
          } catch (e) {
            console.error('Error saving HostAPD config:', e);
            HostBerry.showAlert('danger', t('errors.network_error', 'Network error'));
          }
        });
      }
      
      // Actualizar periódicamente
      setInterval(() => {
        loadHostAPDStatus();
        loadAccessPoints();
        loadClients();
      }, 30000);
    });
  }

  // Inicializar cuando el DOM esté listo
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initHostAPDPage);
  } else {
    initHostAPDPage();
  }
})();
