const token = localStorage.getItem('admin_token');
if (!token) { window.location.href = '/admin'; }

function toggleSidebar() {
  const s = document.getElementById('adminSidebar');
  const o = document.getElementById('overlay');
  const open = s.classList.toggle('open');
  o.classList.toggle('on', open);
  document.body.style.overflow = open ? 'hidden' : '';
}

function logoutAdmin() {
  localStorage.removeItem('admin_token');
  window.location.href = '/admin';
}

function showToast(message, type) {
  type = type || 'success';
  var container = document.querySelector('.toast-container');
  if (!container) {
    container = document.createElement('div');
    container.className = 'toast-container';
    document.body.appendChild(container);
  }
  var toast = document.createElement('div');
  toast.className = 'toast ' + type;
  var iconSvg = type === 'success'
    ? '<svg viewBox="0 0 24 24"><path d="M22 11.08V12a10 10 0 11-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></svg>'
    : '<svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>';
  toast.innerHTML = '<span class="toast-icon">' + iconSvg + '</span><span>' + (message || '') + '</span>';
  container.appendChild(toast);
  setTimeout(function() { toast.classList.add('show'); }, 10);
  setTimeout(function() {
    toast.classList.remove('show');
    toast.addEventListener('transitionend', function() {
      if (toast.parentNode) toast.parentNode.removeChild(toast);
    });
  }, 4000);
}

window.showSuccessToast = function(msg) { showToast(msg, 'success'); };
window.showErrorToast = function(msg) { showToast(msg, 'error'); };