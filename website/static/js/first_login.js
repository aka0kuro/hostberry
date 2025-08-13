// JS para la página first-login con estética igual al login
(function(){
  // Sistema de traducciones
  function t(key, defaultValue = '') {
    // Primero intentar obtener del elemento i18n-data
    const i18nData = document.getElementById('i18n-data');
    if (i18nData) {
      const dataKey = key.replace(/\./g, '-');
      const value = i18nData.getAttribute(`data-${dataKey}`);
      if (value) {
        return value;
      }
    }
    
    // Fallback al sistema anterior
    const keys = key.split('.');
    let current = window.i18nData || {};
    
    for (const k of keys) {
      if (current && typeof current === 'object' && k in current) {
        current = current[k];
      } else {
        return defaultValue || key;
      }
    }
    
    return current || defaultValue || key;
  }

  // Función para mostrar notificaciones toast
  function showToast(title, message, type = 'info') {
    const toastContainer = document.querySelector('.toast-container');
    if (!toastContainer) {
      const container = document.createElement('div');
      container.className = 'toast-container position-fixed top-0 end-0 p-3';
      container.style.zIndex = '9999';
      document.body.appendChild(container);
    }
    
    const toastId = 'toast-' + Date.now();
    const toastHtml = `
      <div id="${toastId}" class="toast" role="alert" aria-live="assertive" aria-atomic="true">
        <div class="toast-header">
          <strong class="me-auto">${title}</strong>
          <button type="button" class="btn-close" data-bs-dismiss="toast"></button>
        </div>
        <div class="toast-body">${message}</div>
      </div>
    `;
    
    toastContainer.insertAdjacentHTML('beforeend', toastHtml);
    const toastElement = document.getElementById(toastId);
    
    // Usar Bootstrap Toast si está disponible, sino crear uno simple
    if (typeof bootstrap !== 'undefined' && bootstrap.Toast) {
      const toast = new bootstrap.Toast(toastElement);
      toast.show();
    } else {
      // Toast simple sin Bootstrap
      toastElement.style.display = 'block';
      toastElement.style.opacity = '1';
    }
    
    // Auto-remove after 5 seconds
    setTimeout(() => {
      if (toastElement.parentNode) {
        toastElement.remove();
      }
    }, 5000);
  }

  // Función para mostrar notificación de éxito
  function showSuccess(message) {
    showToast(t('common.success', 'Éxito'), message, 'success');
  }

  // Función para mostrar notificación de error
  function showError(message) {
    showToast(t('common.error', 'Error'), message, 'danger');
  }

  // Función para mostrar notificación de información
  function showInfo(message) {
    showToast(t('common.info', 'Información'), message, 'info');
  }

  // Función para procesar errores de validación de Pydantic
  function processValidationError(errorDetail) {
    if (Array.isArray(errorDetail)) {
      // Es un array de errores de validación de Pydantic
      const messages = errorDetail.map(error => {
        const field = error.loc && error.loc.length > 1 ? error.loc[1] : 'campo';
        const message = error.msg || 'Error de validación';
        
        // Traducir nombres de campos
        const fieldNames = {
          'new_username': t('auth.username', 'Usuario'),
          'new_password': t('auth.password', 'Contraseña'),
          'confirm_password': t('auth.confirm_password', 'Confirmar contraseña')
        };
        
        const fieldName = fieldNames[field] || field;
        return `${fieldName}: ${message}`;
      });
      
      return messages.join('\n');
    } else if (typeof errorDetail === 'string') {
      return errorDetail;
    } else if (typeof errorDetail === 'object') {
      return errorDetail.message || errorDetail.error || JSON.stringify(errorDetail);
    }
    
    return t('errors.validation_error', 'Error de validación');
  }

  function attachToggle(btnId, inputId, emojiId){
    const btn = document.getElementById(btnId);
    const input = document.getElementById(inputId);
    const emoji = document.getElementById(emojiId);
    if(!btn || !input || !emoji) return;
    
    btn.addEventListener('click', function(){
      const isPass = input.getAttribute('type') === 'password';
      input.setAttribute('type', isPass ? 'text' : 'password');
      emoji.textContent = isPass ? '🙈' : '👁️';
      emoji.setAttribute('title', isPass ? 'Ocultar contraseña' : 'Mostrar contraseña');
    });
  }

  // Función para cambiar tema
  function toggleTheme() {
    const body = document.body;
    const themeToggle = document.getElementById('theme-toggle');
    const themeEmoji = document.getElementById('theme-emoji');
    
    if (body.classList.contains('dark-theme')) {
      body.classList.remove('dark-theme');
      body.classList.add('light-theme');
      themeToggle.classList.remove('dark');
      themeToggle.classList.add('light');
      themeEmoji.textContent = '🌙';
      localStorage.setItem('theme', 'light');
    } else {
      body.classList.remove('light-theme');
      body.classList.add('dark-theme');
      themeToggle.classList.remove('light');
      themeToggle.classList.add('dark');
      themeEmoji.textContent = '☀️';
      localStorage.setItem('theme', 'dark');
    }
  }

  // Función para aplicar tema guardado
  function applySavedTheme() {
    const savedTheme = localStorage.getItem('theme') || 'dark';
    const body = document.body;
    const themeToggle = document.getElementById('theme-toggle');
    const themeEmoji = document.getElementById('theme-emoji');
    
    if (savedTheme === 'light') {
      body.classList.remove('dark-theme');
      body.classList.add('light-theme');
      themeToggle.classList.remove('dark');
      themeToggle.classList.add('light');
      themeEmoji.textContent = '🌙';
    } else {
      body.classList.remove('light-theme');
      body.classList.add('dark-theme');
      themeToggle.classList.remove('light');
      themeToggle.classList.add('dark');
      themeEmoji.textContent = '☀️';
    }
  }

  document.addEventListener('DOMContentLoaded', function(){
    // Aplicar tema guardado
    applySavedTheme();
    
    // Configurar botones de mostrar/ocultar contraseña
    attachToggle('toggle-new-password', 'new_password', 'eye-emoji-new');
    attachToggle('toggle-confirm-password', 'confirm_password', 'eye-emoji-confirm');
    
    // Configurar cambio de tema
    const themeToggle = document.getElementById('theme-toggle');
    if (themeToggle) {
      themeToggle.addEventListener('click', toggleTheme);
    }
    
    const form = document.getElementById('firstLoginForm');
    
    if(!form) return;
    
    form.addEventListener('submit', async function(e){
      e.preventDefault();
      const fd = new FormData(form);
      const payload = Object.fromEntries(fd.entries());
      
      if(payload.new_password !== payload.confirm_password){
        showError(t('auth.passwords_dont_match', 'Las contraseñas no coinciden'));
        return;
      }
      
      try{
        const resp = await fetch('/api/v1/auth/first-login/change', {
                    method:'POST', 
                    headers:{ 
                        'Content-Type':'application/json'
                    }, 
                    body: JSON.stringify(payload)
                });
        
        const data = await resp.json();
        if(resp.ok){
          showSuccess(data.message || t('auth.credentials_updated', 'Credenciales actualizadas. Vuelve a iniciar sesión.'));
          localStorage.removeItem('access_token');
          setTimeout(function(){ 
            window.location.href = '/login'; 
          }, 2000);
        } else {
          // Procesar errores de validación de Pydantic
          const errorMessage = processValidationError(data.detail);
          showError(errorMessage);
        }
      }catch(_e){
        console.error('Error en first-login:', _e);
        showError(t('errors.connection_error', 'Error de conexión: ') + (_e.message || 'Error desconocido'));
      }
    });
  });
})();

