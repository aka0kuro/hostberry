// JS específico para login: toggles y alerts
(function(){
  // i18n desde dataset HTML (multiidioma)
  const __i18nEl = document.getElementById('i18n-data');
  const i18n = {
    user_not_found: __i18nEl ? __i18nEl.getAttribute('data-user-not-found') : 'User not found',
    incorrect_password: __i18nEl ? __i18nEl.getAttribute('data-incorrect-password') : 'Incorrect password',
    too_many_attempts: __i18nEl ? __i18nEl.getAttribute('data-too-many-attempts') : 'Too many attempts',
    connection_error: __i18nEl ? __i18nEl.getAttribute('data-connection-error') : 'Connection error',
    login_generic_error: __i18nEl ? __i18nEl.getAttribute('data-login-generic-error') : 'Login error',
    login_success: __i18nEl ? __i18nEl.getAttribute('data-login-success') : 'Login successful'
  };

  // Toggle tema
  function toggleTheme(){
    const body = document.body;
    const themeToggle = document.getElementById('theme-toggle');
    const emoji = document.getElementById('theme-emoji');
    if(body.classList.contains('dark-theme')){
      body.classList.remove('dark-theme');
      body.classList.add('light-theme');
      if(themeToggle){ themeToggle.classList.remove('dark'); themeToggle.classList.add('light'); }
      if(emoji){ emoji.textContent = '🌙'; }
      localStorage.setItem('theme','light');
    } else {
      body.classList.remove('light-theme');
      body.classList.add('dark-theme');
      if(themeToggle){ themeToggle.classList.remove('light'); themeToggle.classList.add('dark'); }
      if(emoji){ emoji.textContent = '☀️'; }
      localStorage.setItem('theme','dark');
    }
  }
  window.toggleTheme = toggleTheme;

  // Cargar tema guardado
  document.addEventListener('DOMContentLoaded', function(){
    const saved = localStorage.getItem('theme') || 'dark';
    const body = document.body;
    const themeToggle = document.getElementById('theme-toggle');
    const emoji = document.getElementById('theme-emoji');
    if(saved==='light'){
      body.classList.remove('dark-theme');
      body.classList.add('light-theme');
      if(themeToggle){ themeToggle.classList.remove('dark'); themeToggle.classList.add('light'); }
      if(emoji){ emoji.textContent = '🌙'; }
    }
  });

  // Toggle mostrar/ocultar contraseña (usa emoji de ojo)
  (function(){
    const btn = document.getElementById('toggle-password');
    if(!btn) return;
    btn.addEventListener('click', function(){
      const input = document.getElementById('password');
      const eye = document.getElementById('eye-emoji');
      const isPass = input.getAttribute('type') === 'password';
      input.setAttribute('type', isPass ? 'text' : 'password');
      if(eye) eye.textContent = isPass ? '🙈' : '👁️';
      this.setAttribute('aria-label', isPass ? 'Ocultar contraseña' : 'Mostrar contraseña');
      this.setAttribute('title', isPass ? 'Ocultar contraseña' : 'Mostrar contraseña');
    });
  })();

  // Alert helper
  window.showAlert = function(type, message){
    const alertDiv = document.createElement('div');
    alertDiv.className = `alert alert-${type} alert-dismissible fade show position-fixed`;
    alertDiv.style.cssText = 'top:20px; right:20px; z-index:9999; min-width:300px;';
    alertDiv.innerHTML = `${message}`;
    document.body.appendChild(alertDiv);
    setTimeout(()=> alertDiv.remove(), 5000);
  };

  // Manejador del login
  (function(){
    const form = document.getElementById('loginForm');
    if(!form) return;
    form.addEventListener('submit', async function(e){
      e.preventDefault();
      const fd = new FormData(this);
      const data = {
        username: fd.get('username'),
        password: fd.get('password')
      };
      try{
        const resp = await fetch('/api/v1/auth/login', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(data)
        });
        const result = await resp.json();
        if(resp.ok){
          localStorage.setItem('access_token', result.access_token);
          // Set cookie for backend access
          document.cookie = `access_token=${result.access_token}; path=/; max-age=86400; SameSite=Strict`;
          
          showAlert('success', i18n.login_success);
          setTimeout(()=>{
            if(result.password_change_required){
              window.location.href = '/first-login';
            } else {
              window.location.href = '/dashboard';
            }
          }, 800);
        } else {
          if(resp.status === 422){
            showAlert('danger', i18n.login_generic_error);
            return;
          }
          if(resp.status === 404){
            showAlert('warning', i18n.user_not_found);
          } else if(resp.status === 401){
            showAlert('danger', i18n.incorrect_password);
          } else if(resp.status === 429){
            showAlert('warning', i18n.too_many_attempts);
          } else {
            showAlert('danger', i18n.login_generic_error);
          }
        }
      } catch(err){
        console.error(err);
        showAlert('danger', i18n.connection_error);
      }
    });
  })();
})();

