// Funciones extraídas de templates/security_logs.html
(function(){
  // Auto-refresh cada 30 segundos
  setTimeout(function(){ window.location.reload(); }, 30000);

  // Desbloquear IP con confirmación y fetch
  window.unblockIP = function(ip){
    if(confirm('¿Estás seguro de que deseas desbloquear la IP ' + ip + '?')){
      fetch('/security/unblock/' + ip, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' }
      })
      .then(function(r){ return r.json(); })
      .then(function(data){
        if(data.success){ window.location.reload(); }
        else { alert('Error al desbloquear la IP: ' + data.error); }
      })
      .catch(function(err){ alert('Error al desbloquear la IP: ' + err); });
    }
  };
})();

