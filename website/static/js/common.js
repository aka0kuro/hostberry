// Common JS for simple UI behaviours (offline)
(function(){
  // Global Namespace
  const HostBerry = window.HostBerry || {};

  // Simple Dropdown without Bootstrap
  document.addEventListener('click', function(e){
    const toggle = e.target.closest('.dropdown-toggle');
    const inDropdown = e.target.closest('.dropdown');
    document.querySelectorAll('.dropdown').forEach(function(d){
      if(!inDropdown || d !== inDropdown) d.classList.remove('show');
    });
    if(toggle){
      const dd = toggle.closest('.dropdown');
      if(dd) dd.classList.toggle('show');
    }
  });

  // Navbar Toggler (Hamburger)
  document.addEventListener('click', function(e){
    const toggler = e.target.closest('.navbar-toggler');
    if(toggler){
        const targetId = toggler.getAttribute('data-bs-target');
        if(targetId){
            const target = document.querySelector(targetId);
            if(target){
                target.classList.toggle('show');
                const expanded = target.classList.contains('show');
                toggler.setAttribute('aria-expanded', expanded);
            }
        }
    }
  });

  // Load embedded JSON translations if they exist
  function loadTranslations(){
    try{
      const el = document.getElementById('i18n-json');
      if(!el) return {};
      return JSON.parse(el.textContent || el.innerText || '{}');
    }catch(_e){
      return {};
    }
  }

  const translations = loadTranslations();

  // t: nested access to keys 'a.b.c'
  function t(key, defaultValue){
    if(!key) return defaultValue || '';
    const parts = String(key).split('.');
    let cur = translations;
    for(const part of parts){
      if(cur && Object.prototype.hasOwnProperty.call(cur, part)){
        cur = cur[part];
      }else{
        return defaultValue || key;
      }
    }
    return typeof cur === 'string' ? cur : (defaultValue || key);
  }

  // Floating alert top right
  function showAlert(type, message){
    const containerId = 'hb-alert-container';
    let container = document.getElementById(containerId);
    if(!container){
      container = document.createElement('div');
      container.id = containerId;
      container.style.position = 'fixed';
      container.style.top = '20px';
      container.style.right = '20px';
      container.style.zIndex = '9999';
      container.style.maxWidth = '360px';
      document.body.appendChild(container);
    }
    const alert = document.createElement('div');
    alert.className = 'alert alert-' + (type || 'info') + ' shadow';
    alert.style.marginBottom = '10px';
    alert.innerText = message || '';
    container.appendChild(alert);
    setTimeout(function(){
      if(alert && alert.parentNode){ alert.parentNode.removeChild(alert); }
    }, 5000);
  }

  // Fetch wrapper with JSON and token
  async function apiRequest(url, options){
    const opts = Object.assign({ method: 'GET', headers: {} }, options || {});
    const headers = new Headers(opts.headers);
    if(!headers.has('Authorization')){
      const token = localStorage.getItem('access_token');
      if(token) headers.set('Authorization', 'Bearer ' + token);
    }
    if(!headers.has('Content-Type') && opts.body && typeof opts.body === 'object'){
      headers.set('Content-Type', 'application/json');
    }
    opts.headers = headers;
    const resp = await fetch(url, opts);
    return resp;
  }

  // Export
  window.t = t;
  HostBerry.t = t;
  HostBerry.showAlert = showAlert;
  HostBerry.apiRequest = apiRequest;
  // Compat: many views use showAlert() directly
  if(!window.showAlert){ window.showAlert = showAlert; }
  window.HostBerry = HostBerry;
})();

