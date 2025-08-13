// JS para la página first-login con estética igual al login
(function(){
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
    
    const token = localStorage.getItem('access_token');
    const form = document.getElementById('firstLoginForm');
    const alertBox = document.getElementById('alert');
    
    if(!form || !alertBox) return;
    
    form.addEventListener('submit', async function(e){
      e.preventDefault();
      const fd = new FormData(form);
      const payload = Object.fromEntries(fd.entries());
      
      if(payload.new_password !== payload.confirm_password){
        alertBox.className = 'alert alert-danger';
        alertBox.textContent = 'Las contraseñas no coinciden';
        alertBox.classList.remove('d-none');
        return;
      }
      
      try{
        const resp = await fetch('/api/v1/auth/first-login/change', {
          method:'POST', 
          headers:{ 
            'Content-Type':'application/json', 
            'Authorization': `Bearer ${token}` 
          }, 
          body: JSON.stringify(payload)
        });
        
        const data = await resp.json();
        if(resp.ok){
          alertBox.className = 'alert alert-success';
          alertBox.textContent = data.message || 'Credenciales actualizadas. Vuelve a iniciar sesión.';
          alertBox.classList.remove('d-none');
          localStorage.removeItem('access_token');
          setTimeout(function(){ 
            window.location.href = '/login'; 
          }, 1500);
        } else {
          alertBox.className = 'alert alert-danger';
          // Manejar diferentes tipos de respuesta de error
          let errorMessage = 'Error actualizando credenciales';
          if (data.detail) {
            if (typeof data.detail === 'string') {
              errorMessage = data.detail;
            } else if (typeof data.detail === 'object') {
              errorMessage = data.detail.message || data.detail.error || JSON.stringify(data.detail);
            }
          } else if (data.message) {
            errorMessage = data.message;
          } else if (data.error) {
            errorMessage = data.error;
          }
          alertBox.textContent = errorMessage;
          alertBox.classList.remove('d-none');
        }
      }catch(_e){
        console.error('Error en first-login:', _e);
        alertBox.className = 'alert alert-danger';
        alertBox.textContent = 'Error de conexión: ' + (_e.message || 'Error desconocido');
        alertBox.classList.remove('d-none');
      }
    });
  });
})();

