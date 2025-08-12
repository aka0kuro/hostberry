// JS extraído desde templates/first_login.html
(function(){
  function attachToggle(btnId, inputId){
    const btn = document.getElementById(btnId);
    const input = document.getElementById(inputId);
    if(!btn || !input) return;
    btn.addEventListener('click', function(){
      const icon = this.querySelector('i');
      const isPass = input.getAttribute('type') === 'password';
      input.setAttribute('type', isPass ? 'text' : 'password');
      icon.className = isPass ? 'bi bi-eye-slash' : 'bi bi-eye';
    });
  }

  document.addEventListener('DOMContentLoaded', function(){
    attachToggle('toggle-new-password','new_password');
    attachToggle('toggle-confirm-password','confirm_password');
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
          method:'POST', headers:{ 'Content-Type':'application/json', 'Authorization': `Bearer ${token}` }, body: JSON.stringify(payload)
        });
        const data = await resp.json();
        if(resp.ok){
          alertBox.className = 'alert alert-success';
          alertBox.textContent = data.message || 'Credenciales actualizadas. Vuelve a iniciar sesión.';
          alertBox.classList.remove('d-none');
          localStorage.removeItem('access_token');
          setTimeout(function(){ window.location.href = '/login'; }, 1500);
        } else {
          alertBox.className = 'alert alert-danger';
          alertBox.textContent = data.detail || 'Error actualizando credenciales';
          alertBox.classList.remove('d-none');
        }
      }catch(_e){
        alertBox.className = 'alert alert-danger';
        alertBox.textContent = 'Error de conexión';
        alertBox.classList.remove('d-none');
      }
    });
  });
})();

