// Network Management JavaScript
(function(){
  // Esperar a que HostBerry esté disponible
  function waitForHostBerry(callback, maxAttempts = 50) {
    if (window.HostBerry && window.HostBerry.apiRequest && window.HostBerry.t) {
      callback();
    } else if (maxAttempts > 0) {
      setTimeout(() => waitForHostBerry(callback, maxAttempts - 1), 100);
    } else {
      console.error('HostBerry not available after waiting');
      callback();
    }
  }

  function t(key, fallback) {
    return window.HostBerry?.t ? window.HostBerry.t(key, fallback) : (fallback || key);
  }

  // DNS Presets
  const dnsPresets = {
    google: { primary: '8.8.8.8', secondary: '8.8.4.4' },
    cloudflare: { primary: '1.1.1.1', secondary: '1.0.0.1' },
    opendns: { primary: '208.67.222.222', secondary: '208.67.220.220' },
    quad9: { primary: '9.9.9.9', secondary: '149.112.112.112' },
    adguard: { primary: '94.140.14.14', secondary: '94.140.15.15' }
  };

  // Apply DNS Preset
  window.applyDNSPreset = function() {
    const preset = document.getElementById('dns-preset')?.value;
    if (preset && preset !== 'custom' && dnsPresets[preset]) {
      const dns = dnsPresets[preset];
      const dns1 = document.getElementById('dns1');
      const dns2 = document.getElementById('dns2');
      if (dns1) dns1.value = dns.primary;
      if (dns2) dns2.value = dns.secondary;
    }
  };

  // Toggle DHCP Enabled
  window.toggleDHCPEnabled = function() {
    const enabled = document.getElementById('dhcp-enabled')?.checked || false;
    const form = document.getElementById('dhcpConfigForm');
    const saveBtn = document.getElementById('dhcp-save-btn');
    if (form) {
      const inputs = form.querySelectorAll('input, select');
      inputs.forEach(input => {
        input.disabled = !enabled;
      });
    }
    if (saveBtn) {
      saveBtn.disabled = !enabled;
    }
  };

  // Load Network Interfaces
  async function loadInterfaces() {
    const container = document.getElementById('interfacesContainer');
    if (container) {
      container.innerHTML = '<div class="text-center py-4"><div class="spinning mb-3"><i class="bi bi-arrow-clockwise" style="font-size: 2rem;"></i></div><p class="text-muted">' + t('network.loading_interfaces', 'Loading interfaces...') + '</p></div>';
    }
    
    try {
      const resp = await HostBerry.apiRequest('/api/v1/system/network/interfaces');
      if (!resp) {
        throw new Error('No response from server');
      }
      
      if (resp.ok) {
        let data;
        try {
          data = await resp.json();
        } catch (jsonError) {
          console.error('Error parsing JSON:', jsonError);
          if (container) {
            container.innerHTML = '<p class="text-muted text-center">' + t('network.no_interfaces', 'No interfaces found') + '</p>';
          }
          return;
        }
        
        // Manejar diferentes formatos de respuesta
        let interfaces = [];
        if (Array.isArray(data)) {
          interfaces = data;
        } else if (data.interfaces && Array.isArray(data.interfaces)) {
          interfaces = data.interfaces;
        } else if (data.data && Array.isArray(data.data)) {
          interfaces = data.data;
        } else if (data.success !== false && data.interfaces) {
          interfaces = Array.isArray(data.interfaces) ? data.interfaces : [];
        }
        
        if (interfaces.length > 0) {
          displayInterfaces(interfaces);
          populateInterfaceSelects(interfaces);
        } else {
          if (container) {
            container.innerHTML = '<p class="text-muted text-center">' + t('network.no_interfaces', 'No interfaces found') + '</p>';
          }
        }
      } else {
        // Solo mostrar error si es un error real (500, etc), no si es 200 con datos vacíos
        const status = resp.status;
        if (status >= 500) {
          const errorText = await resp.text().catch(() => '');
          console.error('Server error loading interfaces:', status, errorText);
          HostBerry.showAlert('danger', t('errors.loading_interfaces', 'Error loading interfaces'));
        }
        if (container) {
          container.innerHTML = '<p class="text-muted text-center">' + t('network.no_interfaces', 'No interfaces found') + '</p>';
        }
      }
    } catch (e) {
      console.error('Exception loading interfaces:', e);
      // Solo mostrar notificación si es un error de red real, no un error de parsing
      if (e.message && !e.message.includes('JSON')) {
        HostBerry.showAlert('danger', t('errors.network_error', 'Network connection error'));
      }
      if (container) {
        container.innerHTML = '<p class="text-muted text-center">' + t('network.no_interfaces', 'No interfaces found') + '</p>';
      }
    }
  }

  function displayInterfaces(interfaces) {
    const container = document.getElementById('interfacesContainer');
    if (!container) return;
    
    if (!interfaces || !Array.isArray(interfaces) || interfaces.length === 0) {
      container.innerHTML = '<p class="text-muted text-center">' + t('network.no_interfaces', 'No interfaces found') + '</p>';
      return;
    }
    
    let html = '<div class="table-responsive"><table class="table table-hover"><thead><tr><th>' + t('network.interface', 'Interface') + '</th><th>' + t('network.status', 'Status') + '</th><th>' + t('network.ip_address', 'IP Address') + '</th><th>' + t('network.mac_address', 'MAC Address') + '</th></tr></thead><tbody>';
    
    let activeCount = 0;
    interfaces.forEach(function(iface) {
      if (!iface) return;
      const isUp = (iface.status === 'up' || iface.status === 'connected' || iface.connected === true || (iface.status && iface.status.toLowerCase() === 'up'));
      if (isUp) activeCount++;
      const statusClass = isUp ? 'success' : 'danger';
      const statusIcon = isUp ? 'bi-check-circle' : 'bi-x-circle';
      const statusText = isUp ? t('network.connected', 'Connected') : t('network.disconnected', 'Disconnected');
      const ifaceName = iface.name || iface.interface || 'Unknown';
      const ifaceIp = iface.ip || iface.ip_address || 'N/A';
      const ifaceMac = iface.mac || iface.mac_address || 'N/A';
      
      html += '<tr><td><strong>' + ifaceName + '</strong></td><td><span class="badge bg-' + statusClass + '"><i class="bi ' + statusIcon + '"></i> ' + statusText + '</span></td><td>' + ifaceIp + '</td><td>' + ifaceMac + '</td></tr>';
    });
    
    html += '</tbody></table></div>';
    container.innerHTML = html;
    
    // Update active interfaces count
    const activeCountEl = document.getElementById('active-interfaces-count');
    if (activeCountEl) {
      activeCountEl.textContent = activeCount;
    }
  }

  function populateInterfaceSelects(interfaces) {
    const selects = [
      document.getElementById('dhcp-interface'),
      document.getElementById('net-traffic-interface-select')
    ];
    
    selects.forEach(select => {
      if (!select) return;
      
      // Clear existing options except first
      while (select.options.length > 1) {
        select.remove(1);
      }
      
      if (Array.isArray(interfaces) && interfaces.length > 0) {
        interfaces.forEach(iface => {
          const ifaceName = (typeof iface === 'string') ? iface : (iface.name || iface.interface || iface);
          if (ifaceName && ifaceName !== 'lo') {
            const option = document.createElement('option');
            option.value = ifaceName;
            option.textContent = ifaceName;
            select.appendChild(option);
          }
        });
      }
    });
  }

  // Load Routing Table
  async function loadRoutingTable() {
    const tbody = document.getElementById('routingTable');
    if (tbody) {
      tbody.innerHTML = '<tr><td colspan="4" class="text-center text-muted"><div class="spinning mb-2"><i class="bi bi-arrow-clockwise"></i></div><p class="mb-0">' + t('network.loading_routes', 'Loading routes...') + '</p></td></tr>';
    }
    
    try {
      const resp = await HostBerry.apiRequest('/api/v1/system/network/routing');
      if (!resp) {
        throw new Error('No response from server');
      }
      
      if (resp.ok) {
        let data;
        try {
          data = await resp.json();
        } catch (jsonError) {
          console.error('Error parsing JSON:', jsonError);
          if (tbody) {
            tbody.innerHTML = '<tr><td colspan="4" class="text-center text-muted">' + t('network.no_routes', 'No routes found') + '</td></tr>';
          }
          return;
        }
        
        // Manejar diferentes formatos de respuesta
        let routes = [];
        if (Array.isArray(data)) {
          routes = data;
        } else if (data.routes && Array.isArray(data.routes)) {
          routes = data.routes;
        } else if (data.data && Array.isArray(data.data)) {
          routes = data.data;
        }
        
        if (routes.length > 0) {
          displayRoutingTable(routes);
        } else {
          if (tbody) {
            tbody.innerHTML = '<tr><td colspan="4" class="text-center text-muted">' + t('network.no_routes', 'No routes found') + '</td></tr>';
          }
        }
      } else {
        // Solo mostrar error si es un error real del servidor (500, etc)
        const status = resp.status;
        if (status >= 500) {
          const errorText = await resp.text().catch(() => '');
          console.error('Server error loading routing table:', status, errorText);
          HostBerry.showAlert('danger', t('errors.loading_routing', 'Error loading routing table'));
        }
        if (tbody) {
          tbody.innerHTML = '<tr><td colspan="4" class="text-center text-muted">' + t('network.no_routes', 'No routes found') + '</td></tr>';
        }
      }
    } catch (e) {
      console.error('Exception loading routing table:', e);
      // Solo mostrar notificación si es un error de red real, no un error de parsing
      if (e.message && !e.message.includes('JSON')) {
        HostBerry.showAlert('danger', t('errors.network_error', 'Network connection error'));
      }
      if (tbody) {
        tbody.innerHTML = '<tr><td colspan="4" class="text-center text-muted">' + t('network.no_routes', 'No routes found') + '</td></tr>';
      }
    }
  }

  function displayRoutingTable(routes) {
    const tbody = document.getElementById('routingTable');
    if (!tbody) return;
    
    if (!routes || !Array.isArray(routes) || routes.length === 0) {
      tbody.innerHTML = '<tr><td colspan="4" class="text-center text-muted">' + t('network.no_routes', 'No routes found') + '</td></tr>';
      return;
    }
    
    let html = '';
    routes.forEach(function(route) {
      if (!route) return;
      html += '<tr><td>' + (route.destination || '0.0.0.0') + '</td><td>' + (route.gateway || '*') + '</td><td>' + (route.interface || route.dev || '-') + '</td><td>' + (route.metric || '0') + '</td></tr>';
    });
    tbody.innerHTML = html;
  }

  // Network Traffic Monitoring
  let selectedTrafficInterface = '';
  let lastTrafficSnapshot = null;
  let netTrafficChart = null;
  const netTrafficHistory = { labels: [], download: [], upload: [] };

  function formatBytes(bytes) {
    if (!bytes || bytes === 0 || !Number.isFinite(bytes) || bytes < 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    const sizeIndex = Math.max(0, Math.min(i, sizes.length - 1));
    const value = bytes / Math.pow(k, sizeIndex);
    return `${value.toFixed(1)} ${sizes[sizeIndex]}`;
  }

  function computeNetworkRates(current) {
    if (!current || typeof current !== 'object') {
      return {
        download_speed: 0.0,
        upload_speed: 0.0,
        bytes_recv: 0,
        bytes_sent: 0,
        interface: selectedTrafficInterface || '',
        ip_address: '--'
      };
    }
    
    const bytesRecv = typeof current.bytes_recv === 'number' && !isNaN(current.bytes_recv) ? current.bytes_recv : 0;
    const bytesSent = typeof current.bytes_sent === 'number' && !isNaN(current.bytes_sent) ? current.bytes_sent : 0;
    
    if (lastTrafficSnapshot && current.interface && lastTrafficSnapshot.interface && current.interface !== lastTrafficSnapshot.interface) {
      lastTrafficSnapshot = null;
      netTrafficHistory.labels.length = 0;
      netTrafficHistory.download.length = 0;
      netTrafficHistory.upload.length = 0;
      if (netTrafficChart) netTrafficChart.update();
    }
    
    const now = Date.now();
    if (!lastTrafficSnapshot) {
      lastTrafficSnapshot = { 
        time: now, 
        bytes_recv: bytesRecv,
        bytes_sent: bytesSent,
        interface: current.interface || selectedTrafficInterface || ''
      };
      return {
        ...current,
        download_speed: 0.0,
        upload_speed: 0.0,
        bytes_recv: bytesRecv,
        bytes_sent: bytesSent
      };
    }
    
    const timeDelta = (now - lastTrafficSnapshot.time) / 1000;
    if (timeDelta <= 0.1 || timeDelta > 60) {
      lastTrafficSnapshot = { 
        time: now, 
        bytes_recv: bytesRecv,
        bytes_sent: bytesSent,
        interface: current.interface || selectedTrafficInterface || ''
      };
      return {
        ...current,
        download_speed: 0.0,
        upload_speed: 0.0,
        bytes_recv: bytesRecv,
        bytes_sent: bytesSent
      };
    }
    
    const prevBytesRecv = lastTrafficSnapshot.bytes_recv || 0;
    const prevBytesSent = lastTrafficSnapshot.bytes_sent || 0;
    
    let bytesRecvDelta = bytesRecv - prevBytesRecv;
    let bytesSentDelta = bytesSent - prevBytesSent;
    
    if (bytesRecvDelta < 0 && Math.abs(bytesRecvDelta) > prevBytesRecv * 0.5) {
      bytesRecvDelta = bytesRecv;
    }
    if (bytesSentDelta < 0 && Math.abs(bytesSentDelta) > prevBytesSent * 0.5) {
      bytesSentDelta = bytesSent;
    }
    
    const downloadSpeed = Math.max(0, bytesRecvDelta / timeDelta);
    const uploadSpeed = Math.max(0, bytesSentDelta / timeDelta);
    
    lastTrafficSnapshot = {
      time: now,
      bytes_recv: bytesRecv,
      bytes_sent: bytesSent,
      interface: current.interface || selectedTrafficInterface || ''
    };
    
    return {
      ...current,
      download_speed: downloadSpeed,
      upload_speed: uploadSpeed,
      bytes_recv: bytesRecv,
      bytes_sent: bytesSent
    };
  }

  function pushTrafficHistory(download, upload) {
    const downloadValue = (typeof download === 'number' && !isNaN(download) && isFinite(download)) ? download : 0;
    const uploadValue = (typeof upload === 'number' && !isNaN(upload) && isFinite(upload)) ? upload : 0;
    
    const now = new Date();
    const timeLabel = now.getHours().toString().padStart(2, '0') + ':' + 
                      now.getMinutes().toString().padStart(2, '0') + ':' + 
                      now.getSeconds().toString().padStart(2, '0');
    
    netTrafficHistory.labels.push(timeLabel);
    netTrafficHistory.download.push(Math.max(0, downloadValue));
    netTrafficHistory.upload.push(Math.max(0, uploadValue));
    
    if (netTrafficHistory.labels.length > 30) {
      netTrafficHistory.labels.shift();
      netTrafficHistory.download.shift();
      netTrafficHistory.upload.shift();
    }
  }

  function ensureTrafficChart() {
    const canvas = document.getElementById('net-traffic-chart');
    if (!canvas) {
      // Intentar de nuevo después de un tiempo si el canvas no está disponible
      setTimeout(ensureTrafficChart, 500);
      return;
    }
    
    if (netTrafficChart) return;
    
    // Verificar si Chart.js está disponible
    if (typeof Chart === 'undefined' && typeof window.Chart === 'undefined') {
      console.warn('Chart.js not loaded, retrying...');
      setTimeout(ensureTrafficChart, 500);
      return;
    }
    
    const ChartLib = typeof Chart !== 'undefined' ? Chart : window.Chart;
    
    if (netTrafficHistory.labels.length === 0) {
      const now = new Date();
      for (let i = 9; i >= 0; i--) {
        const time = new Date(now.getTime() - i * 1000);
        const timeLabel = time.getHours().toString().padStart(2, '0') + ':' + 
                          time.getMinutes().toString().padStart(2, '0') + ':' + 
                          time.getSeconds().toString().padStart(2, '0');
        netTrafficHistory.labels.push(timeLabel);
        netTrafficHistory.download.push(0);
        netTrafficHistory.upload.push(0);
      }
    }
    
    try {
      const ctx = canvas.getContext('2d');
      const ChartLib = typeof Chart !== 'undefined' ? Chart : window.Chart;
      // Ocultar mensaje de carga
      const chartLoading = document.getElementById('chart-loading');
      if (chartLoading) chartLoading.style.display = 'none';
      
      netTrafficChart = new ChartLib(ctx, {
        type: 'line',
        data: {
          labels: netTrafficHistory.labels,
          datasets: [
            {
              label: t('monitoring.download', 'Download'),
              data: netTrafficHistory.download,
              borderColor: '#0dcaf0',
              backgroundColor: 'rgba(13, 202, 240, 0.1)',
              tension: 0.4,
              fill: true,
              pointRadius: 0,
              pointHoverRadius: 4
            },
            {
              label: t('monitoring.upload', 'Upload'),
              data: netTrafficHistory.upload,
              borderColor: '#198754',
              backgroundColor: 'rgba(25, 135, 84, 0.1)',
              tension: 0.4,
              fill: true,
              pointRadius: 0,
              pointHoverRadius: 4
            }
          ]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          animation: { duration: 0 },
          plugins: {
            legend: {
              labels: { color: window.getComputedStyle(document.body).color },
              display: true
            },
            tooltip: {
              mode: 'index',
              intersect: false
            }
          },
          scales: {
            x: { 
              ticks: { 
                color: window.getComputedStyle(document.body).color,
                maxRotation: 45,
                minRotation: 0
              },
              grid: { color: 'rgba(255,255,255,0.1)' }
            },
            y: { 
              ticks: { 
                color: window.getComputedStyle(document.body).color,
                callback: function(value) {
                  return formatBytes(value) + '/s';
                }
              },
              grid: { color: 'rgba(255,255,255,0.1)' },
              beginAtZero: true
            }
          },
          interaction: {
            mode: 'nearest',
            axis: 'x',
            intersect: false
          }
        }
      });
    } catch (error) {
      console.error('Error creating traffic chart:', error);
    }
  }

  window.updateTrafficStats = async function() {
    try {
      let url = '/api/v1/system/network';
      if (selectedTrafficInterface) {
        url += `?interface=${encodeURIComponent(selectedTrafficInterface)}&_t=${Date.now()}`;
      } else {
        url += `?_t=${Date.now()}`;
      }
      const resp = await HostBerry.apiRequest(url);
      
      if (!resp || !resp.ok) {
        throw new Error('Network request failed');
      }
      
      const networkStatsRaw = await resp.json();
      if (!networkStatsRaw || typeof networkStatsRaw !== 'object') {
        throw new Error('Invalid network stats response');
      }
      
      const networkStats = computeNetworkRates(networkStatsRaw);
      
      if (networkStats.interfaces && Array.isArray(networkStats.interfaces)) {
        populateInterfaceSelects(networkStats.interfaces);
      } else if (networkStatsRaw.interfaces && Array.isArray(networkStatsRaw.interfaces)) {
        populateInterfaceSelects(networkStatsRaw.interfaces);
      }

      const setText = (id, value) => {
        const el = document.getElementById(id);
        if (el) el.textContent = value;
      };

      setText('net-traffic-interface', networkStats.interface || networkStatsRaw.interface || '--');
      setText('net-traffic-ip', networkStats.ip_address || networkStatsRaw.ip_address || '--');
      
      const downloadSpeed = networkStats.download_speed || 0;
      const uploadSpeed = networkStats.upload_speed || 0;
      
      const downloadText = downloadSpeed > 0 ? formatBytes(downloadSpeed) + '/s' : '0 B/s';
      const uploadText = uploadSpeed > 0 ? formatBytes(uploadSpeed) + '/s' : '0 B/s';
      
      setText('net-traffic-download', downloadText);
      setText('net-traffic-upload', uploadText);
      setText('traffic-download-value', downloadText);
      setText('traffic-upload-value', uploadText);
      
      const bytesRecv = networkStats.bytes_recv || networkStatsRaw.bytes_recv || 0;
      const bytesSent = networkStats.bytes_sent || networkStatsRaw.bytes_sent || 0;
      setText('net-traffic-bytes-recv', formatBytes(bytesRecv));
      setText('net-traffic-bytes-sent', formatBytes(bytesSent));
      
      const packetsSent = networkStats.packets_sent || networkStatsRaw.packets_sent || 0;
      const packetsRecv = networkStats.packets_recv || networkStatsRaw.packets_recv || 0;
      setText('net-traffic-packets', `${packetsSent} / ${packetsRecv}`);
      
      const errors = (networkStats.errors || networkStatsRaw.errors || 0) + 
                     (networkStats.drop || networkStatsRaw.drop || 0);
      setText('net-traffic-errors', errors || '0');

      const validDownloadSpeed = (typeof downloadSpeed === 'number' && !isNaN(downloadSpeed) && isFinite(downloadSpeed)) ? downloadSpeed : 0;
      const validUploadSpeed = (typeof uploadSpeed === 'number' && !isNaN(uploadSpeed) && isFinite(uploadSpeed)) ? uploadSpeed : 0;
      
      pushTrafficHistory(validDownloadSpeed, validUploadSpeed);

      ensureTrafficChart();
      
      if (netTrafficChart) {
        netTrafficChart.data.labels = [...netTrafficHistory.labels];
        netTrafficChart.data.datasets[0].data = [...netTrafficHistory.download];
        netTrafficChart.data.datasets[1].data = [...netTrafficHistory.upload];
        netTrafficChart.data.datasets[0].label = t('monitoring.download', 'Download');
        netTrafficChart.data.datasets[1].label = t('monitoring.upload', 'Upload');
        netTrafficChart.update('none');
      }
    } catch (error) {
      console.error('Error updating traffic stats:', error);
    }
  };

  // Initialize Network Page
  function initNetworkPage() {
    loadInterfaces();
    loadRoutingTable();
    
    // Network Basic Config Form
    const basicConfigForm = document.getElementById('networkBasicConfigForm');
    if (basicConfigForm) {
      basicConfigForm.addEventListener('submit', async function(e) {
        e.preventDefault();
        const fd = new FormData(this);
        const data = {
          hostname: fd.get('hostname'),
          dns1: fd.get('dns1'),
          dns2: fd.get('dns2'),
          gateway: fd.get('gateway')
        };
        try {
          const resp = await HostBerry.apiRequest('/api/v1/system/network/config', {
            method: 'POST',
            body: data
          });
          if (resp && resp.ok) {
            HostBerry.showAlert('success', t('messages.config_saved', 'Configuration saved'));
          } else {
            HostBerry.showAlert('danger', t('errors.config_update_error', 'Error updating configuration'));
          }
        } catch (e) {
          HostBerry.showAlert('danger', t('errors.network_error', 'Network error'));
        }
      });
    }

    // DHCP Config Form
    const dhcpConfigForm = document.getElementById('dhcpConfigForm');
    if (dhcpConfigForm) {
      dhcpConfigForm.addEventListener('submit', async function(e) {
        e.preventDefault();
        const fd = new FormData(this);
        const data = {
          dhcp_enabled: document.getElementById('dhcp-enabled')?.checked || false,
          dhcp_interface: fd.get('dhcp_interface'),
          dhcp_range_start: fd.get('dhcp_range_start'),
          dhcp_range_end: fd.get('dhcp_range_end'),
          dhcp_gateway: fd.get('dhcp_gateway'),
          dhcp_lease_time: fd.get('dhcp_lease_time')
        };
        try {
          const resp = await HostBerry.apiRequest('/api/v1/system/network/dhcp/config', {
            method: 'POST',
            body: data
          });
          if (resp && resp.ok) {
            HostBerry.showAlert('success', t('messages.config_saved', 'Configuration saved'));
          } else {
            HostBerry.showAlert('danger', t('errors.config_update_error', 'Error updating configuration'));
          }
        } catch (e) {
          HostBerry.showAlert('danger', t('errors.network_error', 'Network error'));
        }
      });
    }

    // Traffic Interface Select
    const trafficSelect = document.getElementById('net-traffic-interface-select');
    if (trafficSelect) {
      trafficSelect.addEventListener('change', function(e) {
        selectedTrafficInterface = e.target.value || '';
        lastTrafficSnapshot = null;
        netTrafficHistory.labels.length = 0;
        netTrafficHistory.download.length = 0;
        netTrafficHistory.upload.length = 0;
        if (netTrafficChart) netTrafficChart.update();
        updateTrafficStats();
      });
    }
    
    // Start traffic updates
    updateTrafficStats();
    setInterval(updateTrafficStats, 5000);
    
    // Refresh interfaces and routing table periodically
    setInterval(() => {
      loadInterfaces();
      loadRoutingTable();
    }, 30000);
  }

  // Export functions
  window.loadInterfaces = loadInterfaces;
  window.loadRoutingTable = loadRoutingTable;

  // Initialize
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => waitForHostBerry(initNetworkPage));
  } else {
    waitForHostBerry(initNetworkPage);
  }
})();
