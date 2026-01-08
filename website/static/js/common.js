// Common JS for simple UI behaviours (offline)
(function(){
  // Global Namespace
  const HostBerry = window.HostBerry || {};

  async function performLogout(event){
    if(event){ event.preventDefault(); }
    try{
      await HostBerry.apiRequest('/api/v1/auth/logout', { method: 'POST' });
    }catch(_e){
      // ignore errors to ensure client-side logout proceeds
    }finally{
      localStorage.removeItem('access_token');
      localStorage.removeItem('user_info');
      if(HostBerry.showAlert){
        HostBerry.showAlert('info', HostBerry.t ? HostBerry.t('auth.logout_success', 'Logout successful') : 'Logout successful');
      }
      window.location.href = '/login';
    }
  }

  async function performRestart(event){
    if(event){ event.preventDefault(); }
    const confirmMsg = HostBerry.t ? HostBerry.t('system.restart_confirm', 'Are you sure you want to restart the system? This will disconnect all users.') : 'Are you sure you want to restart the system? This will disconnect all users.';
    if(!confirm(confirmMsg)) return;
    
    try{
      if(HostBerry.showAlert){
        HostBerry.showAlert('warning', HostBerry.t ? HostBerry.t('system.restarting', 'Restarting system...') : 'Restarting system...');
      }
      await HostBerry.apiRequest('/api/v1/system/restart', { method: 'POST' });
      if(HostBerry.showAlert){
        HostBerry.showAlert('info', HostBerry.t ? HostBerry.t('system.restart_pending', 'Restart command sent') : 'Restart command sent');
      }
      setTimeout(function(){ window.location.reload(); }, 5000);
    }catch(error){
      console.error('Restart failed', error);
      if(HostBerry.showAlert){
        HostBerry.showAlert('danger', HostBerry.t ? HostBerry.t('system.restart_error', 'Unable to restart system') : 'Unable to restart system');
      }
    }
  }

  async function performShutdown(event){
    if(event){ event.preventDefault(); }
    const confirmMsg = HostBerry.t ? HostBerry.t('system.shutdown_confirm', 'Are you sure you want to shutdown the system? This will disconnect all users.') : 'Are you sure you want to shutdown the system? This will disconnect all users.';
    if(!confirm(confirmMsg)) return;
    
    const doubleConfirm = HostBerry.t ? HostBerry.t('system.shutdown_double_confirm', 'Type SHUTDOWN to confirm') : 'Type SHUTDOWN to confirm';
    const userInput = prompt(doubleConfirm);
    if(userInput !== 'SHUTDOWN') return;
    
    try{
      if(HostBerry.showAlert){
        HostBerry.showAlert('warning', HostBerry.t ? HostBerry.t('system.shutting_down', 'Shutting down system...') : 'Shutting down system...');
      }
      await HostBerry.apiRequest('/api/v1/system/shutdown', { method: 'POST' });
      if(HostBerry.showAlert){
        HostBerry.showAlert('info', HostBerry.t ? HostBerry.t('system.shutdown_pending', 'Shutdown command sent') : 'Shutdown command sent');
      }
    }catch(error){
      console.error('Shutdown failed', error);
      if(HostBerry.showAlert){
        HostBerry.showAlert('danger', HostBerry.t ? HostBerry.t('system.shutdown_error', 'Unable to shutdown system') : 'Unable to shutdown system');
      }
    }
  }

  // Simple Dropdown without Bootstrap
  document.addEventListener('click', function(e){
    const toggle = e.target.closest('.dropdown-toggle');
    const inDropdown = e.target.closest('.dropdown');
    const isDropdownItem = e.target.closest('.dropdown-item');
    
    // Si se hace clic en un item del dropdown, no cerrar el dropdown
    if(isDropdownItem && !isDropdownItem.hasAttribute('data-action')){
      return;
    }
    
    document.querySelectorAll('.dropdown').forEach(function(d){
      if(!inDropdown || d !== inDropdown) d.classList.remove('show');
    });
    if(toggle){
      e.preventDefault();
      e.stopPropagation();
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
    
    // Auth token
    if(!headers.has('Authorization')){
      let token = localStorage.getItem('access_token');
      // Fallback: si no hay token en localStorage, intentar leerlo de la URL (?token=)
      // Esto permite que funcione incluso si el navegador no guarda cookies.
      if(!token){
        try{
          const u = new URL(window.location.href);
          token = u.searchParams.get('token') || '';
        }catch(_e){
          token = '';
        }
      }
      if(token) headers.set('Authorization', 'Bearer ' + token);
    }
    
    // JSON body handling
    if(opts.body && typeof opts.body === 'object' && !(opts.body instanceof FormData)){
      if(!headers.has('Content-Type')){
      headers.set('Content-Type', 'application/json');
      }
      opts.body = JSON.stringify(opts.body);
    }
    
    opts.headers = headers;
    try {
    const resp = await fetch(url, opts);
      if(resp.status === 401 && !url.includes('/auth/login')){
        // Auto logout on unauthorized
        localStorage.removeItem('access_token');
        window.location.href = '/login?error=session_expired';
      }
    return resp;
    } catch (e) {
      console.error('API Request failed:', e);
      throw e;
    }
  }

  // Timezone/locale helpers (timezone guardado en Settings y servido por backend)
  function getServerTimezone(){
    return (window.HostBerryServerSettings && window.HostBerryServerSettings.timezone) ? window.HostBerryServerSettings.timezone : 'UTC';
  }

  function getServerLanguage(){
    const lang = (document.documentElement && document.documentElement.lang) ? document.documentElement.lang : 'en';
    return (lang === 'es') ? 'es' : 'en';
  }

  function formatTime(date, options){
    const tz = getServerTimezone();
    const lang = getServerLanguage();
    const locale = (lang === 'es') ? 'es-ES' : 'en-US';
    const d = (date instanceof Date) ? date : new Date(date);
    const fmtOpts = Object.assign({ hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit', timeZone: tz }, options || {});
    try{
      return new Intl.DateTimeFormat(locale, fmtOpts).format(d);
    }catch(_e){
      // Fallback si Intl/timeZone no está disponible
      return d.toLocaleTimeString(locale, { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' });
    }
  }

  // Export
  window.t = t;
  HostBerry.t = t;
  HostBerry.showAlert = showAlert;
  HostBerry.apiRequest = apiRequest;
  HostBerry.getServerTimezone = getServerTimezone;
  HostBerry.formatTime = formatTime;

  // Populate navbar username from API if logged in
  document.addEventListener('DOMContentLoaded', async function(){
    try{
      const el = document.getElementById('hb-current-username');
      const token = localStorage.getItem('access_token');
      if(!el || !token) return;

      const resp = await apiRequest('/api/v1/auth/me');
      if(!resp || !resp.ok) return;
      const data = await resp.json();
      if(data && data.username){
        el.textContent = data.username;
      }
    }catch(_e){
      // silent
    }

    document.querySelectorAll('[data-action="logout"]').forEach(function(btn){
      btn.addEventListener('click', performLogout);
    });
    
    document.querySelectorAll('[data-action="restart"]').forEach(function(btn){
      btn.addEventListener('click', performRestart);
    });
    
    document.querySelectorAll('[data-action="shutdown"]').forEach(function(btn){
      btn.addEventListener('click', performShutdown);
    });
  });

  // Compat: many views use showAlert() directly
  if(!window.showAlert){ window.showAlert = showAlert; }
  HostBerry.performLogout = performLogout;
  HostBerry.performRestart = performRestart;
  HostBerry.performShutdown = performShutdown;
  window.HostBerry = HostBerry;
})();
