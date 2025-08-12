// JS extraído desde templates/help.html
(function(){
  const form = document.getElementById('contactForm');
  if(!form) return;
  form.addEventListener('submit', async function(e){
    e.preventDefault();
    const fd = new FormData(this);
    const data = { name: fd.get('contact_name'), email: fd.get('contact_email'), subject: fd.get('contact_subject'), message: fd.get('contact_message') };
    try{
      const resp = await fetch('/api/v1/help/contact', { method:'POST', headers:{ 'Content-Type':'application/json', 'Authorization': `Bearer ${localStorage.getItem('access_token')}` }, body: JSON.stringify(data) });
      if(resp.ok){ HostBerry.showAlert('success', HostBerry.t('help.message_sent')); this.reset(); }
      else { HostBerry.showAlert('danger', HostBerry.t('errors.operation_failed')); }
    }catch(_e){ HostBerry.showAlert('danger', HostBerry.t('errors.network_error')); }
  });
})();

