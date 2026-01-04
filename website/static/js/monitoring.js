// Monitoring dashboard interactions
(function(){
  const setText = (id, value) => {
    const el = document.getElementById(id);
    if(el) el.textContent = value;
  };

  function safeToFixed(value, digits = 1){
    if(typeof value !== 'number' || Number.isNaN(value)) return '0.0';
    return value.toFixed(digits);
  }

  function formatUptime(seconds){
    if(!Number.isFinite(seconds) || seconds < 0) return '--';
    const days = Math.floor(seconds / 86400);
    const hours = Math.floor((seconds % 86400) / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    return `${days}d ${hours}h ${minutes}m`;
  }

  function formatBytes(bytes){
    if(!Number.isFinite(bytes)) return '0 MB';
    const mb = bytes / (1024 * 1024);
    return `${safeToFixed(mb, 1)} MB`;
  }

  async function fetchJson(url){
    const resp = await HostBerry.apiRequest(url);
    if(resp.status === 401){
      // token inválido, redirige a login
      window.location.href = '/login';
      throw new Error('Unauthorized');
    }
    if(!resp.ok){
      const errText = await resp.text();
      throw new Error(`Request failed ${resp.status}: ${errText}`);
    }
    return resp.json();
  }

  function updateProgress(id, percent){
    const bar = document.getElementById(id);
    if(bar && Number.isFinite(percent)){
      const clamped = Math.min(100, Math.max(0, percent));
      bar.style.width = `${clamped}%`;
    }
  }

  let netChart;
  let selectedInterface = '';
  const netHistory = {
    labels: [],
    download: [],
    upload: []
  };
  let lastNetSnapshot = null;

  function ensureNetChart(){
    if(netChart) return netChart;
    const ctx = document.getElementById('net-chart');
    if(!ctx || typeof Chart === 'undefined') return null;
    netChart = new Chart(ctx, {
      type: 'line',
      data: {
        labels: netHistory.labels,
        datasets: [
          {
            label: 'Download KB/s',
            data: netHistory.download,
            borderColor: '#6366f1',
            backgroundColor: 'rgba(99, 102, 241, 0.25)',
            tension: 0.25,
            fill: true
          },
          {
            label: 'Upload KB/s',
            data: netHistory.upload,
            borderColor: '#ec4899',
            backgroundColor: 'rgba(236, 72, 153, 0.2)',
            tension: 0.25,
            fill: true
          }
        ]
      },
      options: {
        responsive: true,
        scales: {
          y: { beginAtZero: true, ticks: { color: '#cbd5e1' }, grid: { color: 'rgba(255,255,255,0.08)' } },
          x: { ticks: { color: '#cbd5e1' }, grid: { display: false } }
        },
        plugins: { legend: { labels: { color: '#e2e8f0' } } }
      }
    });
    return netChart;
  }

  function pushNetHistory(download, upload){
    const now = new Date().toLocaleTimeString();
    netHistory.labels.push(now);
    netHistory.download.push(download);
    netHistory.upload.push(upload);
    const maxPoints = 20;
    if(netHistory.labels.length > maxPoints){
      netHistory.labels.shift();
      netHistory.download.shift();
      netHistory.upload.shift();
    }
    if(netChart){
      netChart.update();
    }
  }

  async function updateStats(){
    try{
      const [systemStats, networkStatsRaw] = await Promise.all([
        fetchJson('/api/v1/system/stats'),
        fetchJson(`/api/v1/system/network${selectedInterface ? `?interface=${encodeURIComponent(selectedInterface)}` : ''}`)
      ]);
      const networkStats = computeNetworkRates(networkStatsRaw);
      populateInterfaceSelect(networkStats.interfaces || []);

      setText('uptime-value', formatUptime(systemStats.uptime));
      setText('cpu-usage', `${safeToFixed(systemStats.cpu_usage)}%`);
      updateProgress('cpu-progress', systemStats.cpu_usage);
      if(typeof systemStats.cpu_temperature === 'number'){
        setText('cpu-temp', `${safeToFixed(systemStats.cpu_temperature)}°C`);
      }
      setText('cpu-cores', systemStats.cpu_cores ? String(systemStats.cpu_cores) : '-');

      setText('mem-usage', `${safeToFixed(systemStats.memory_usage)}%`);
      updateProgress('mem-progress', systemStats.memory_usage);
      if(systemStats.memory_total){
        setText('mem-total', `${safeToFixed(systemStats.memory_total / (1024 ** 3),1)} GB`);
      }
      if(systemStats.memory_free){
        setText('mem-free', `${safeToFixed(systemStats.memory_free / (1024 ** 3),1)} GB`);
      }

      setText('disk-usage', `${safeToFixed(systemStats.disk_usage)}%`);
      updateProgress('disk-progress', systemStats.disk_usage);
      if(systemStats.disk_total){
        setText('disk-total', `${safeToFixed(systemStats.disk_total / (1024 ** 3),1)} GB`);
      }
      if(systemStats.disk_used){
        setText('disk-used', `${safeToFixed(systemStats.disk_used / (1024 ** 3),1)} GB`);
      }

      setText('net-interface', networkStats.interface || '-');
      setText('net-ip', networkStats.ip_address || '--');
      setText('net-download', `${safeToFixed(networkStats.download_speed || 0, 2)} KB/s`);
      setText('net-upload', `${safeToFixed(networkStats.upload_speed || 0, 2)} KB/s`);
      setText('net-bytes-recv', formatBytes(networkStats.bytes_recv || 0));
      setText('net-bytes-sent', formatBytes(networkStats.bytes_sent || 0));
      setText('net-packets', `${networkStats.packets_sent || 0} / ${networkStats.packets_recv || 0}`);
      pushNetHistory(networkStats.download_speed || 0, networkStats.upload_speed || 0);

      setText('monitoring-last-update', new Date().toLocaleTimeString());
      ensureNetChart();
    }catch(error){
      console.error('Error updating monitoring stats:', error);
      HostBerry.showAlert?.('danger', HostBerry.t?.('errors.monitoring_stats', 'Unable to refresh monitoring stats') || 'Unable to refresh monitoring stats');
    }
  }

  function computeNetworkRates(current){
    if(!current || typeof current.bytes_recv !== 'number' || typeof current.bytes_sent !== 'number'){
      return current || {};
    }
    // reset snapshot if cambia interfaz
    if(lastNetSnapshot && current.interface !== lastNetSnapshot.interface){
      lastNetSnapshot = null;
      netHistory.labels.length = 0;
      netHistory.download.length = 0;
      netHistory.upload.length = 0;
      if(netChart){ netChart.update(); }
    }
    const now = Date.now();
    if(!lastNetSnapshot){
      lastNetSnapshot = { time: now, ...current };
      return current;
    }
    const elapsedSec = (now - lastNetSnapshot.time) / 1000;
    if(elapsedSec <= 0){
      return current;
    }
    const dlRate = (current.bytes_recv - (lastNetSnapshot.bytes_recv || 0)) / 1024 / elapsedSec;
    const ulRate = (current.bytes_sent - (lastNetSnapshot.bytes_sent || 0)) / 1024 / elapsedSec;
    lastNetSnapshot = { time: now, ...current };
    return {
      ...current,
      download_speed: Math.max(0, dlRate),
      upload_speed: Math.max(0, ulRate)
    };
  }

  function initMonitoring(){
    updateStats();
    setInterval(updateStats, 60000);
    const ifaceSelect = document.getElementById('net-interface-select');
    if(ifaceSelect){
      ifaceSelect.addEventListener('change', ()=>{
        selectedInterface = ifaceSelect.value;
        lastNetSnapshot = null;
        netHistory.labels.length = 0;
        netHistory.download.length = 0;
        netHistory.upload.length = 0;
        if(netChart){ netChart.update(); }
        updateStats();
      });
    }
  }

  document.addEventListener('DOMContentLoaded', initMonitoring);
})();


  function populateInterfaceSelect(list){
    const select = document.getElementById('net-interface-select');
    if(!select || !Array.isArray(list)) return;
    const current = select.value;
    const existing = Array.from(select.options).map(o => o.value);
    let changed = false;
    list.forEach(iface=>{
      if(iface && !existing.includes(iface)){
        const opt = document.createElement('option');
        opt.value = iface;
        opt.textContent = iface;
        select.appendChild(opt);
        changed = true;
      }
    });
    if(current && !list.includes(current)){
      select.value = '';
      selectedInterface = '';
      changed = true;
    }
    if(!current && selectedInterface){
      select.value = selectedInterface;
    }
    if(changed && select.value !== current){
      select.dispatchEvent(new Event('change'));
    }
  }
