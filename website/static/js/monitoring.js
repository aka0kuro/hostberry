// JS extraído desde templates/monitoring.html
(function(){
  function formatUptime(seconds){
    const days = Math.floor(seconds / (24*60*60));
    const hours = Math.floor((seconds % (24*60*60)) / (60*60));
    const minutes = Math.floor((seconds % (60*60)) / 60);
    return days+' days, '+hours+' hours, '+minutes+' minutes';
  }
  async function updateStats(){
    try{
      const resp = await fetch('/api/monitoring/stats');
      const data = await resp.json();
      const set = (id, val)=>{ const el = document.getElementById(id); if(el) el.textContent = val; };
      set('uptime', formatUptime(data.uptime));
      set('cpu-usage', data.cpu.usage+'%'); set('cpu-temp', data.cpu.temperature+'°C'); set('cpu-cores', data.cpu.cores); set('cpu-freq', data.cpu.frequency+' MHz');
      const cpuProg = document.getElementById('cpu-progress'); if(cpuProg) cpuProg.style.width = data.cpu.usage+'%';
      set('mem-total', data.memory.total); set('mem-used', data.memory.used); set('mem-free', data.memory.free); set('mem-usage', data.memory.usage+'%');
      const memProg = document.getElementById('mem-progress'); if(memProg) memProg.style.width = data.memory.usage+'%';
      set('disk-total', data.disk.total); set('disk-used', data.disk.used); set('disk-free', data.disk.free); set('disk-usage', data.disk.usage+'%');
      const diskProg = document.getElementById('disk-progress'); if(diskProg) diskProg.style.width = data.disk.usage+'%';
      set('net-ip', data.network.ip); set('net-interface', data.network.interface); set('net-upload', data.network.upload); set('net-download', data.network.download);
    }catch(_e){ /* ignore */ }
  }
  setInterval(updateStats, 5000); updateStats();
})();

