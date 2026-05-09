(function() {
  "use strict";

  var _preloaderHidden = false;

  function hidePreloader() {
    if (_preloaderHidden) return;
    _preloaderHidden = true;
    var p = document.getElementById('preloader');
    if (p) p.classList.add('hidden');
  }

  window.addEventListener('load', function() {
    setTimeout(hidePreloader, 1800);
  });
  setTimeout(hidePreloader, 3500);

  function generateToken() {
    if (typeof crypto !== 'undefined' && crypto.randomUUID) {
      try {
        return crypto.randomUUID();
      } catch (e) {}
    }
    return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function(c) {
      var r = Math.random() * 16 | 0,
        v = c == 'x' ? r : (r & 0x3 | 0x8);
      return v.toString(16);
    });
  }

  window.generateToken = generateToken;

  var dot = document.getElementById('cursorDot');
  var ring = document.getElementById('cursorRing');
  var mouseX = 0,
    mouseY = 0,
    ringX = 0,
    ringY = 0;
  var isMobile = window.matchMedia('(pointer:coarse)').matches;

  if (dot && ring && !isMobile) {
    document.addEventListener('mousemove', function(e) {
      mouseX = e.clientX;
      mouseY = e.clientY;
      dot.style.left = mouseX + 'px';
      dot.style.top = mouseY + 'px';
    });

    (function animRing() {
      ringX += (mouseX - ringX) * 0.12;
      ringY += (mouseY - ringY) * 0.12;
      ring.style.left = ringX + 'px';
      ring.style.top = ringY + 'px';
      requestAnimationFrame(animRing);
    })();
  }

  var hamburger = document.getElementById('hamburger');
  var mobileMenu = document.getElementById('mobileMenu');
  var mobileClose = document.getElementById('mobileClose');
  var bodyEl = document.body;

  function openMobileMenu() {
    if (!mobileMenu || !hamburger) return;
    mobileMenu.classList.add('active');
    hamburger.classList.add('active');
    hamburger.setAttribute('aria-expanded', 'true');
    bodyEl.style.overflow = 'hidden';
  }

  function closeMobileMenu() {
    if (!mobileMenu || !hamburger) return;
    mobileMenu.classList.remove('active');
    hamburger.classList.remove('active');
    hamburger.setAttribute('aria-expanded', 'false');
    bodyEl.style.overflow = '';
  }

  window.closeMobileMenu = closeMobileMenu;

  if (hamburger) {
    hamburger.addEventListener('click', function(e) {
      e.stopPropagation();
      if (mobileMenu && mobileMenu.classList.contains('active')) closeMobileMenu();
      else openMobileMenu();
    });
  }

  if (mobileClose) mobileClose.addEventListener('click', closeMobileMenu);

  document.addEventListener('keydown', function(e) {
    if (e.key === 'Escape') {
      closeMobileMenu();
      try {
        closeAuthModal();
      } catch (e) {}
    }
  });

  document.addEventListener('click', function(e) {
    if (mobileMenu && mobileMenu.classList.contains('active') && !mobileMenu.contains(e.target) && hamburger && !hamburger.contains(e.target)) {
      closeMobileMenu();
    }
  });

  var mobileLinks = mobileMenu ? mobileMenu.querySelectorAll('a') : [];

  for (var i = 0; i < mobileLinks.length; i++) {
    mobileLinks[i].addEventListener('click', closeMobileMenu);
  }

  var nav = document.getElementById('nav');

  if (nav) {
    window.addEventListener('scroll', function() {
      nav.classList.toggle('scrolled', window.scrollY > 60);
    }, {
      passive: true
    });
  }

  var revEls = document.querySelectorAll('.reveal');

  if ('IntersectionObserver' in window) {
    var ro = new IntersectionObserver(function(entries) {
      entries.forEach(function(e) {
        if (e.isIntersecting) {
          e.target.classList.add('visible');
          ro.unobserve(e.target);
        }
      });
    }, {
      threshold: 0.1,
      rootMargin: '0px 0px -50px 0px'
    });
    revEls.forEach(function(el) {
      ro.observe(el);
    });
  } else {
    for (var i = 0; i < revEls.length; i++) revEls[i].classList.add('visible');
  }

  var heroImg = document.querySelector('.hero-media img');

  if (heroImg && !isMobile) {
    window.addEventListener('scroll', function() {
      heroImg.style.transform = 'scale(1) translateY(' + (window.scrollY * 0.25) + 'px)';
    }, {
      passive: true
    });
  }

  var modalEl = document.getElementById('modal-auth');
  var modalInner = document.getElementById('modal-inner');
  var modalCloseBtn = document.getElementById('modal-close-btn');
  var _activePanel = 'signin';

  function openAuthModal(panel) {
    _activePanel = panel;
    if (panel === 'signin') renderSignIn();
    else if (panel === 'register') renderRegister();
    else if (panel === 'account') renderAccount();
    if (modalEl) modalEl.classList.add('open');
    bodyEl.style.overflow = 'hidden';
    setTimeout(function() {
      var firstInput = modalEl ? modalEl.querySelector('input') : null;
      if (firstInput) firstInput.focus();
    }, 300);
  }

  function closeAuthModal() {
    if (modalEl) modalEl.classList.remove('open');
    bodyEl.style.overflow = '';
  }

  window.openSignIn = function() {
    openAuthModal('signin');
  };
  window.openRegister = function() {
    openAuthModal('register');
  };
  window.openAccountModal = function() {
    openAuthModal('account');
  };
  window.closeAuthModal = closeAuthModal;

  if (modalCloseBtn) modalCloseBtn.addEventListener('click', closeAuthModal);

  if (modalEl) {
    modalEl.addEventListener('click', function(e) {
      if (e.target === modalEl) closeAuthModal();
    });
  }

  function escHtml(s) {
    return String(s || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  }

  function renderSignIn() {
    if (!modalInner) return;
    modalInner.innerHTML =
      '<div class="modal-eyebrow">Welcome Back</div>' +
      '<h2 class="modal-title" id="modal-auth-title">Sign In</h2>' +
      '<div class="modal-error" id="auth-error"></div>' +
      '<div class="modal-field"><label>Email</label><input type="email" id="auth-email" placeholder="your@email.com" autocomplete="email"/></div>' +
      '<div class="modal-field"><label>Password</label><div class="pw-toggle"><input type="password" id="auth-pw" placeholder="••••••••" autocomplete="current-password"/><span class="pw-eye" onclick="togglePw(\'auth-pw\',this)" tabindex="0" aria-label="Show password"><svg viewBox="0 0 24 24"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg></span></div></div>' +
      '<button class="modal-submit" onclick="submitSignIn()"><span id="signin-btn-text">Sign In</span></button>' +
      '<div class="modal-switch">New to Fred Vunjabei? <a onclick="openAuthModal(\'register\')">Create account</a></div>';
    var emailEl = document.getElementById('auth-email');
    var pwEl = document.getElementById('auth-pw');

    if (emailEl && pwEl) {
      emailEl.addEventListener('keydown', function(e) {
        if (e.key === 'Enter') pwEl.focus();
      });
      pwEl.addEventListener('keydown', function(e) {
        if (e.key === 'Enter') submitSignIn();
      });
    }
  }

  function renderRegister() {
    if (!modalInner) return;
    modalInner.innerHTML =
      '<div class="modal-eyebrow">Join La Maison</div>' +
      '<h2 class="modal-title" id="modal-auth-title">Create Account</h2>' +
      '<div class="modal-error" id="auth-error"></div>' +
      '<div class="modal-field-row">' +
      '<div class="modal-field"><label>First Name</label><input type="text" id="reg-first" placeholder="First" autocomplete="given-name"/></div>' +
      '<div class="modal-field"><label>Last Name</label><input type="text" id="reg-last" placeholder="Last" autocomplete="family-name"/></div>' +
      '</div>' +
      '<div class="modal-field"><label>Email</label><input type="email" id="reg-email" placeholder="your@email.com" autocomplete="email"/></div>' +
      '<div class="modal-field"><label>Phone (optional)</label><input type="tel" id="reg-phone" placeholder="+255 7XX XXX XXX" autocomplete="tel"/></div>' +
      '<div class="modal-field"><label>Password</label><div class="pw-toggle"><input type="password" id="reg-pw" placeholder="Min 8 characters" autocomplete="new-password"/><span class="pw-eye" onclick="togglePw(\'reg-pw\',this)" tabindex="0" aria-label="Show password"><svg viewBox="0 0 24 24"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg></span></div></div>' +
      '<button class="modal-submit" onclick="submitRegister()"><span id="reg-btn-text">Create Account</span></button>' +
      '<div class="modal-switch">Already a member? <a onclick="openAuthModal(\'signin\')">Sign in</a></div>';
  }

  function renderAccount() {
    if (!modalInner) return;
    var u = window.FV ? window.FV.user : null;
    var name = u ? ((u.first_name || '') + ' ' + (u.last_name || '')) : '';
    var email = u ? u.email : '';
    modalInner.innerHTML =
      '<div class="modal-eyebrow">My Account</div>' +
      '<div class="modal-user-greeting">' +
      '<span class="user-name">' + escHtml(name.trim() || email) + '</span>' +
      '<p>' + escHtml(email) + '</p>' +
      '</div>' +
      '<div class="modal-user-actions">' +
      '<a href="/account">My Orders</a>' +
      '<a href="/account">Profile Settings</a>' +
      '<a href="/wishlist">Saved Items</a>' +
      '<a class="btn-logout" onclick="logoutUser()" style="cursor:pointer">Sign Out</a>' +
      '</div>';
  }

  function showAuthError(msg) {
    var el = document.getElementById('auth-error');
    if (el) {
      el.textContent = msg;
      el.classList.add('show');
    }
  }

  function hideAuthError() {
    var el = document.getElementById('auth-error');
    if (el) el.classList.remove('show');
  }

  function setLoadingBtn(btnId, textId, loading, defaultText) {
    var btn = document.getElementById(btnId) || document.querySelector('.modal-submit');
    var txt = document.getElementById(textId);
    if (btn) btn.classList.toggle('loading', loading);
    if (txt) txt.textContent = loading ? 'Please wait…' : defaultText;
  }

  window.submitSignIn = function() {
    hideAuthError();
    var email = (document.getElementById('auth-email') || {}).value || '';
    var pw = (document.getElementById('auth-pw') || {}).value || '';

    if (!email || !pw) {
      showAuthError('Please enter your email and password.');
      return;
    }

    setLoadingBtn('', 'signin-btn-text', true, 'Sign In');

    fetch('/api/auth/login', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        email: email,
        password: pw
      })
    }).then(function(r) {
      return r.json();
    }).then(function(d) {
      setLoadingBtn('', 'signin-btn-text', false, 'Sign In');

      if (d.success) {
        localStorage.setItem('user_token', d.data.access_token || '');
        localStorage.setItem('fv_user', JSON.stringify(d.data.user || {}));
        window.FV.token = d.data.access_token || '';
        window.FV.user = d.data.user || {};
        renderNavAuth();
        closeAuthModal();
      } else {
        showAuthError(d.error || 'Invalid email or password.');
      }
    }).catch(function() {
      setLoadingBtn('', 'signin-btn-text', false, 'Sign In');
      showAuthError('Connection error. Please try again.');
    });
  };

  window.submitRegister = function() {
    hideAuthError();
    var first = (document.getElementById('reg-first') || {}).value || '';
    var last = (document.getElementById('reg-last') || {}).value || '';
    var email = (document.getElementById('reg-email') || {}).value || '';
    var phone = (document.getElementById('reg-phone') || {}).value || '';
    var pw = (document.getElementById('reg-pw') || {}).value || '';

    if (!email || !pw) {
      showAuthError('Email and password are required.');
      return;
    }

    if (pw.length < 8) {
      showAuthError('Password must be at least 8 characters.');
      return;
    }

    setLoadingBtn('', 'reg-btn-text', true, 'Create Account');

    fetch('/api/auth/register', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        first_name: first,
        last_name: last,
        email: email,
        phone: phone,
        password: pw
      })
    }).then(function(r) {
      return r.json();
    }).then(function(d) {
      setLoadingBtn('', 'reg-btn-text', false, 'Create Account');

      if (d.success) {
        localStorage.setItem('user_token', d.data.access_token || '');
        localStorage.setItem('fv_user', JSON.stringify(d.data.user || {}));
        window.FV.token = d.data.access_token || '';
        window.FV.user = d.data.user || {};
        renderNavAuth();
        closeAuthModal();
      } else {
        showAuthError(d.error || 'Registration failed. Please try again.');
      }
    }).catch(function() {
      setLoadingBtn('', 'reg-btn-text', false, 'Create Account');
      showAuthError('Connection error. Please try again.');
    });
  };

  window.logoutUser = function() {
    fetch('/api/auth/logout', {
      method: 'POST',
      headers: {
        'Authorization': 'Bearer ' + (window.FV ? window.FV.token : '')
      }
    }).catch(function() {});

    localStorage.removeItem('user_token');
    localStorage.removeItem('fv_user');
    window.FV.token = '';
    window.FV.user = null;
    renderNavAuth();
    closeAuthModal();

    if (window.location.pathname.startsWith('/account')) window.location.href = '/';
  };

  window.togglePw = function(inputId, btn) {
    var inp = document.getElementById(inputId);
    if (!inp) return;
    var shown = inp.type === 'text';
    inp.type = shown ? 'password' : 'text';

    if (btn) btn.querySelector('svg').innerHTML = shown ?
      '<path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/>' :
      '<path d="M17.94 17.94A10.07 10.07 0 0112 20c-7 0-11-8-11-8a18.45 18.45 0 015.06-5.94M9.9 4.24A9.12 9.12 0 0112 4c7 0 11 8 11 8a18.5 18.5 0 01-2.16 3.19m-6.72-1.07a3 3 0 11-4.24-4.24"/><line x1="1" y1="1" x2="23" y2="23"/>';
  };

  function updateCartBadge() {
    var token = localStorage.getItem('cart_token') || '';
    if (!token) return;

    fetch('/api/cart?token=' + token, {
      headers: {
        'X-Cart-Token': token
      }
    }).then(function(r) {
      return r.json();
    }).then(function(d) {
      var items = (d.data && d.data.cart && d.data.cart.items) || [];
      var count = items.reduce(function(sum, i) {
        return sum + (i.quantity || 0);
      }, 0);
      var badge = document.getElementById('cart-badge');

      if (badge) {
        badge.textContent = count > 99 ? '99+' : count;
        badge.classList.toggle('show', count > 0);
      }
    }).catch(function() {});
  }

  document.addEventListener('click', function(e) {
    var btn = e.target.closest('.prod-act');
    if (!btn) return;
    var action = btn.getAttribute('data-action');
    var productId = btn.getAttribute('data-product-id');

    if (action === 'addtocart') {
      var variantId = btn.getAttribute('data-variant-id') || '';
      var token = localStorage.getItem('cart_token') || generateToken();
      localStorage.setItem('cart_token', token);

      fetch('/api/cart/add', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Cart-Token': token
        },
        body: JSON.stringify({
          product_id: productId,
          variant_id: variantId || null,
          quantity: 1,
          token: token
        })
      }).then(function(r) {
        return r.json();
      }).then(function(d) {
        if (d.success) {
          updateCartBadge();
        }
      }).catch(function() {});
    } else if (action === 'wishlist') {
      var wToken = localStorage.getItem('wishlist_token') || generateToken();
      localStorage.setItem('wishlist_token', wToken);

      fetch('/api/wishlist', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Cart-Token': wToken
        },
        body: JSON.stringify({
          product_id: productId,
          token: wToken
        })
      }).then(function(r) {
        return r.json();
      }).then(function(d) {}).catch(function() {});
    }
  });

  window.FV = {
    token: localStorage.getItem('user_token') || '',
    user: null,
  };

  try {
    window.FV.user = JSON.parse(localStorage.getItem('fv_user') || 'null');
  } catch (e) {}

  function renderNavAuth() {
    var area = document.getElementById('nav-auth-area');
    var mobileArea = document.getElementById('mobile-auth-area');
    if (!area) return;

    if (window.FV.user) {
      var name = window.FV.user.first_name || window.FV.user.email.split('@')[0];
      area.innerHTML = '<span class="nav-link-auth" id="nav-auth-trigger" tabindex="0" style="cursor:pointer">' + escHtml(name) + '</span>';

      if (mobileArea) {
        mobileArea.innerHTML = '<button class="btn-signin" onclick="closeMobileMenu();openAccountModal()">Account</button><button class="btn-register" onclick="closeMobileMenu();logoutUser()">Logout</button>';
      }
    } else {
      area.innerHTML = '<span class="nav-link-auth" id="nav-auth-trigger" tabindex="0" style="cursor:pointer">Sign In</span>';

      if (mobileArea) {
        mobileArea.innerHTML = '<button class="btn-signin" onclick="closeMobileMenu();openSignIn()">Sign In</button><button class="btn-register" onclick="closeMobileMenu();openRegister()">Register</button>';
      }
    }

    wireAuthTrigger();
  }

  function wireAuthTrigger() {
    var trigger = document.getElementById('nav-auth-trigger');
    if (!trigger) return;

    trigger.addEventListener('click', function() {
      if (window.FV.user) openAccountModal();
      else openSignIn();
    });

    trigger.addEventListener('keydown', function(e) {
      if (e.key === 'Enter' || e.key === ' ') {
        e.preventDefault();
        trigger.click();
      }
    });
  }

  renderNavAuth();
  updateCartBadge();

  if (window.FV.token) {
    fetch('/api/auth/me', {
      headers: {
        'Authorization': 'Bearer ' + window.FV.token
      }
    }).then(function(r) {
      if (r.status === 401) {
        localStorage.removeItem('user_token');
        localStorage.removeItem('fv_user');
        window.FV.token = '';
        window.FV.user = null;
        renderNavAuth();
      } else return r.json();
    }).then(function(d) {
      if (d && d.success) {
        window.FV.user = d.data;
        localStorage.setItem('fv_user', JSON.stringify(d.data));
        renderNavAuth();
      }
    }).catch(function() {});
  }
  
  
})();