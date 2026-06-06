/**
 * app.js — PruebaTecnica web helpers
 *
 * Responsibilities:
 *  1. Store JWT token in localStorage after a successful login response.
 *  2. Inject the Authorization header into every HTMX request.
 *  3. Provide a global logout() helper.
 */

// ---------------------------------------------------------------------------
// 1. Store token + redirect after successful login
// ---------------------------------------------------------------------------
document.body.addEventListener('htmx:afterRequest', function (evt) {
  const path = evt.detail.requestConfig && evt.detail.requestConfig.path;
  if (path && path.includes('/auth/login') && evt.detail.successful) {
    try {
      const data = JSON.parse(evt.detail.xhr.responseText);
      if (data.access_token) {
        localStorage.setItem('token', data.access_token);
        window.location.href = '/documents';
      }
    } catch (e) {
      // Malformed JSON — show error inline
      const alertEl = document.getElementById('login-alert');
      if (alertEl) {
        alertEl.innerHTML =
          '<div class="alert alert-danger py-2 small">Error inesperado. Intentá nuevamente.</div>';
      }
    }
  }

  // Show inline error for failed login
  if (path && path.includes('/auth/login') && !evt.detail.successful) {
    const alertEl = document.getElementById('login-alert');
    if (alertEl) {
      let msg = 'Credenciales inválidas.';
      try {
        const data = JSON.parse(evt.detail.xhr.responseText);
        if (data.detail) msg = data.detail;
      } catch (_) {}
      alertEl.innerHTML =
        '<div class="alert alert-danger py-2 small">' + msg + '</div>';
    }
  }
});

// ---------------------------------------------------------------------------
// 2. Add Authorization header to all HTMX requests
// ---------------------------------------------------------------------------
document.body.addEventListener('htmx:configRequest', function (evt) {
  const token = localStorage.getItem('token');
  if (token) {
    evt.detail.headers['Authorization'] = 'Bearer ' + token;
  }
});

// ---------------------------------------------------------------------------
// 3. Logout
// ---------------------------------------------------------------------------
function logout() {
  localStorage.removeItem('token');
  window.location.href = '/login';
}
