// JS extraído desde templates/network.html
(function(){
  async function loadInterfaces(){
    try{
      const resp = await fetch('/api/v1/network/interfaces', { headers:{ 'Authorization': `Bearer ${localStorage.getItem('access_token')}` } });
      if(resp.ok){ displayInterfaces(await resp.json()); } else { HostBerry.showAlert('danger', HostBerry.t('errors.loading_interfaces')); }
    }catch(_e){ HostBerry.showAlert('danger', HostBerry.t('errors.network_error')); }
  }
  function displayInterfaces(interfaces){
    const container = document.getElementById('interfacesContainer'); if(!container) return;
    if(!interfaces || interfaces.length===0){ container.innerHTML = '<p class="text-muted">'+HostBerry.t('network.no_interfaces')+'</p>'; return; }
    let html='';
    interfaces.forEach(function(iface){
      const statusClass = iface.status==='up'?'success':'danger'; const statusIcon = iface.status==='up'?'bi-check-circle':'bi-x-circle';
      html += '<div class="row mb-3">'
        +'<div class="col-md-3"><strong>'+iface.name+'</strong></div>'
        +'<div class="col-md-3"><span class="badge bg-'+statusClass+'"><i class="bi '+statusIcon+'"></i> '+iface.status+'</span></div>'
        +'<div class="col-md-3">'+(iface.ip||'N/A')+'</div>'
        +'<div class="col-md-3">'+(iface.mac||'N/A')+'</div>'
        +'</div>';
    });
    container.innerHTML = html;
  }
  async function loadRoutingTable(){
    try{
      const resp = await fetch('/api/v1/network/routing', { headers:{ 'Authorization': `Bearer ${localStorage.getItem('access_token')}` } });
      if(resp.ok){ displayRoutingTable(await resp.json()); } else { HostBerry.showAlert('danger', HostBerry.t('errors.loading_routing')); }
    }catch(_e){ HostBerry.showAlert('danger', HostBerry.t('errors.network_error')); }
  }
  function displayRoutingTable(routes){
    const tbody = document.getElementById('routingTable'); if(!tbody) return;
    if(!routes || routes.length===0){ tbody.innerHTML = '<tr><td colspan="4" class="text-muted">'+HostBerry.t('network.no_routes')+'</td></tr>'; return; }
    let html='';
    routes.forEach(function(route){ html += '<tr><td>'+route.destination+'</td><td>'+(route.gateway||'*')+'</td><td>'+route.interface+'</td><td>'+(route.metric||'0')+'</td></tr>'; });
    tbody.innerHTML = html;
  }
  async function toggleFirewall(){
    try{
      const resp = await fetch('/api/v1/network/firewall/toggle', { method:'POST', headers:{ 'Authorization': `Bearer ${localStorage.getItem('access_token')}` } });
      if(resp.ok){ HostBerry.showAlert('success', HostBerry.t('messages.operation_successful')); setTimeout(()=>window.location.reload(), 1000); }
      else { HostBerry.showAlert('danger', HostBerry.t('errors.operation_failed')); }
    }catch(_e){ HostBerry.showAlert('danger', HostBerry.t('errors.network_error')); }
  }
  function viewFirewallRules(){ alert(HostBerry.t('network.viewing_firewall_rules','Viendo reglas del firewall')); }
  const configForm = document.getElementById('networkConfigForm');
  if(configForm){
    configForm.addEventListener('submit', async function(e){
      e.preventDefault(); const fd = new FormData(this);
      const data = { hostname: fd.get('hostname'), dns1: fd.get('dns1'), dns2: fd.get('dns2'), gateway: fd.get('gateway') };
      try{
        const resp = await fetch('/api/v1/network/config', { method:'POST', headers:{ 'Content-Type':'application/json', 'Authorization': `Bearer ${localStorage.getItem('access_token')}` }, body: JSON.stringify(data) });
        if(resp.ok){ HostBerry.showAlert('success', HostBerry.t('messages.changes_saved')); }
        else { HostBerry.showAlert('danger', HostBerry.t('errors.configuration_error')); }
      }catch(_e){ HostBerry.showAlert('danger', HostBerry.t('errors.network_error')); }
    });
  }
  document.addEventListener('DOMContentLoaded', function(){ loadInterfaces(); loadRoutingTable(); setInterval(function(){ loadInterfaces(); loadRoutingTable(); }, 30000); });
  window.toggleFirewall = toggleFirewall;
  window.viewFirewallRules = viewFirewallRules;
})();

