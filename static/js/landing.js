document.addEventListener('DOMContentLoaded', function () {
  bindPage();
});

function bindPage() {
  bindGuestChrome();
  bindLandingAuth();
  bindMessengerAuth();
  bindRankDialog();
  bindSiteMenu();
  bindAvatarUpload();
  bindProfileTools();
  bindHomeToasts();
  if (typeof window.__kbBindSocial === 'function') {
    window.__kbBindSocial();
  }
  if (typeof window.__kbBindLive === 'function') {
    window.__kbBindLive();
  }
  if (typeof window.__kbBindAlliance === 'function') {
    window.__kbBindAlliance();
  }
  if (typeof window.__kbBindShop === 'function') {
    window.__kbBindShop();
  }
}

window.__kbBindPage = bindPage;

var KB_AUTH_GUARD =
  '[data-like-post], [data-save-post], [data-gif-open], [data-story-viewers], [data-comment-del], [data-comment-reply], #story-like, [data-follow], [data-comment-post], [data-kb-auth], [data-shop-auth], #story-form, #post-form, #story-comment-form, #live-chat-form, #live-donate-form, [data-accept], [data-reject], [data-block], .event-fee-btn, .composer, [data-alliance-action], #alliance-chat-form, form[data-shop-buy]';

function kbIsMember() {
  return document.body.getAttribute('data-kb-member') === '1';
}

function closeAuthPrompt() {
  var dialog = document.getElementById('auth-prompt');
  if (!dialog) {
    return;
  }
  dialog.classList.remove('is-open');
  try {
    if (typeof dialog.close === 'function' && dialog.open) {
      dialog.close();
      return;
    }
  } catch (err) {
    /* ignore */
  }
  dialog.removeAttribute('open');
}

function promptAuth(nextUrl) {
  var dialog = document.getElementById('auth-prompt');
  if (!dialog) {
    return false;
  }
  var cta = dialog.querySelector('.auth-prompt__cta');
  if (cta) {
    var next = nextUrl || window.location.pathname + window.location.search;
    cta.setAttribute('href', '/register/?next=' + encodeURIComponent(next));
  }
  try {
    if (typeof dialog.showModal === 'function' && !dialog.open) {
      dialog.showModal();
      return true;
    }
  } catch (err) {
    /* fall through */
  }
  dialog.setAttribute('open', '');
  dialog.classList.add('is-open');
  return true;
}

function kbRequireAuth() {
  if (kbIsMember()) {
    return true;
  }
  promptAuth();
  return false;
}

window.__kbPromptAuth = promptAuth;
window.__kbRequireAuth = kbRequireAuth;

function bindGuestChrome() {
  if (window.__kbGuestChromeBound) {
    return;
  }
  window.__kbGuestChromeBound = true;
  var banner = document.getElementById('kb-guest-banner');
  try {
    if (banner && window.sessionStorage.getItem('kb_guest_banner_off') === '1') {
      banner.classList.add('is-off');
      document.documentElement.classList.add('is-guest-banner-off');
    }
  } catch (err) {
    /* ignore */
  }
  document.addEventListener(
    'click',
    function (event) {
      var node = event.target;
      if (!node || typeof node.closest !== 'function') {
        return;
      }
      if (node.closest('[data-guest-banner-close]')) {
        if (banner) {
          banner.classList.add('is-off');
        }
        document.documentElement.classList.add('is-guest-banner-off');
        try {
          window.sessionStorage.setItem('kb_guest_banner_off', '1');
        } catch (err) {
          /* ignore */
        }
        return;
      }
      if (node.closest('[data-auth-prompt-close]') || node === document.getElementById('auth-prompt')) {
        closeAuthPrompt();
      }
      if (kbIsMember()) {
        return;
      }
      var gated = node.closest(KB_AUTH_GUARD);
      if (!gated) {
        return;
      }
      event.preventDefault();
      event.stopPropagation();
      var nextNode = node.closest('[data-next]');
      promptAuth((nextNode && nextNode.getAttribute('data-next')) || window.location.pathname + window.location.search);
    },
    true
  );
  document.addEventListener(
    'submit',
    function (event) {
      if (kbIsMember()) {
        return;
      }
      var form = event.target;
      if (!form) {
        return;
      }
      var gated =
        form.id === 'story-form' ||
        form.id === 'post-form' ||
        form.id === 'live-chat-form' ||
        form.id === 'live-donate-form' ||
        form.id === 'story-comment-form' ||
        (form.hasAttribute && form.hasAttribute('data-comment-post')) ||
        (form.hasAttribute && form.hasAttribute('data-shop-buy'));
      if (!gated) {
        return;
      }
      event.preventDefault();
      event.stopPropagation();
      promptAuth();
    },
    true
  );
}

function bindSiteMenu() {
  if (window.__kbMenuBound) {
    return;
  }
  window.__kbMenuBound = true;

  function getDialog() {
    return document.getElementById('site-menu-dialog');
  }

  function openDialog() {
    var dialog = getDialog();
    if (!dialog) {
      return;
    }
    try {
      if (typeof dialog.showModal === 'function' && !dialog.open) {
        dialog.showModal();
        return;
      }
    } catch (err) {
      /* fall through */
    }
    dialog.setAttribute('open', '');
    dialog.classList.add('is-open');
  }

  function closeDialog() {
    var dialog = getDialog();
    if (!dialog) {
      return;
    }
    dialog.classList.remove('is-open');
    try {
      if (typeof dialog.close === 'function' && dialog.open) {
        dialog.close();
        return;
      }
    } catch (err) {
      /* ignore */
    }
    dialog.removeAttribute('open');
  }

  document.addEventListener(
    'click',
    function (event) {
      var node = event.target;
      if (!node || typeof node.closest !== 'function') {
        return;
      }
      if (node.closest('[data-menu-close]')) {
        closeDialog();
        return;
      }
      if (node === getDialog()) {
        closeDialog();
        return;
      }
      if (node.closest('[data-menu-open]')) {
        event.preventDefault();
        event.stopPropagation();
        openDialog();
      }
    },
    true
  );
}

function bindLandingAuth() {
  var panel = document.getElementById('auth-panel');
  var sendForm = document.getElementById('auth-send-form');
  var verifyForm = document.getElementById('auth-verify-form');
  var phone = document.getElementById('auth-phone');
  var code = document.getElementById('auth-code');
  var sendBtn = document.getElementById('auth-send-btn');
  var verifyBtn = document.getElementById('auth-verify-btn');
  var status = document.getElementById('auth-status');
  if (!sendForm || !verifyForm || !phone || sendForm.getAttribute('data-kb-bound')) {
    return;
  }
  sendForm.setAttribute('data-kb-bound', '1');

  var sendCsrf = sendForm.querySelector('[name=csrfmiddlewaretoken]');
  var verifyCsrf = verifyForm.querySelector('[name=csrfmiddlewaretoken]');
  var cooldown = Number(panel && panel.getAttribute('data-otp-cooldown')) || 60;
  var timer = 0;
  var lastPhone = '';

  phone.addEventListener('input', function () {
    if (verifyForm.hidden) {
      return;
    }
    if ((phone.value || '').trim() !== lastPhone) {
      verifyForm.hidden = true;
    }
  });

  sendForm.addEventListener('submit', function (event) {
    event.preventDefault();
    var mobile = (phone.value || '').trim();
    if (!mobile) {
      showAuthStatus('شماره موبایل را وارد کنید.', true);
      return;
    }
    sendBtn.disabled = true;
    showAuthStatus('در حال ارسال کد…', false);
    postAuth(sendForm.action, sendCsrf, { phone: mobile })
      .then(function (data) {
        if (!data || !data.success) {
          showAuthStatus((data && data.message) || 'ارسال کد ناموفق بود.', true);
          startCooldown((data && data.retry_after) || 0);
          return;
        }
        lastPhone = mobile;
        verifyForm.hidden = false;
        if (code) {
          code.value = '';
          code.focus();
        }
        showAuthStatus(data.message || 'کد تایید ارسال شد.', false);
        startCooldown(data.retry_after || cooldown);
      })
      .catch(function () {
        showAuthStatus('ارتباط با سرور برقرار نشد.', true);
        sendBtn.disabled = false;
      });
  });

  verifyForm.addEventListener('submit', function (event) {
    event.preventDefault();
    var mobile = (phone.value || '').trim();
    var otp = (code && code.value) || '';
    if (!otp.trim()) {
      showAuthStatus('کد تایید را وارد کنید.', true);
      return;
    }
    verifyBtn.disabled = true;
    showAuthStatus('در حال بررسی کد…', false);
    postAuth(verifyForm.action, verifyCsrf, { phone: mobile, code: otp })
      .then(function (data) {
        verifyBtn.disabled = false;
        if (!data || !data.success) {
          showAuthStatus((data && data.message) || 'کد تایید نادرست است.', true);
          return;
        }
        showAuthStatus(data.message || 'شماره موبایل تایید شد.', false);
        if (window.__kbGo) {
          window.__kbGo(data.redirect || '/');
        } else {
          window.location.assign(data.redirect || '/');
        }
      })
      .catch(function () {
        verifyBtn.disabled = false;
        showAuthStatus('ارتباط با سرور برقرار نشد.', true);
      });
  });

  function postAuth(url, csrfNode, body) {
    return fetch(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': csrfNode ? csrfNode.value : '',
        'X-Requested-With': 'XMLHttpRequest',
      },
      body: JSON.stringify(body),
      credentials: 'same-origin',
    }).then(function (response) {
      return response.json().catch(function () {
        return { success: false, message: 'پاسخ سرور نامعتبر است.' };
      });
    });
  }

  function startCooldown(seconds) {
    window.clearInterval(timer);
    var left = Math.max(0, Number(seconds) || 0);
    var label = sendBtn.querySelector('span');
    if (!left) {
      sendBtn.disabled = false;
      if (label) {
        label.textContent = 'ارسال کد تایید';
      }
      return;
    }
    sendBtn.disabled = true;
    tick();
    timer = window.setInterval(tick, 1000);

    function tick() {
      if (left <= 0) {
        window.clearInterval(timer);
        sendBtn.disabled = false;
        if (label) {
          label.textContent = 'ارسال مجدد کد';
        }
        return;
      }
      if (label) {
        label.textContent = 'ارسال مجدد (' + left + ')';
      }
      left -= 1;
    }
  }

  function showAuthStatus(message, isError) {
    if (!status) {
      return;
    }
    if (!message) {
      status.hidden = true;
      status.textContent = '';
      status.classList.remove('is-error');
      return;
    }
    status.hidden = false;
    status.textContent = message;
    status.classList.toggle('is-error', !!isError);
  }
}

function bindMessengerAuth() {
  if (window.__kbMessengerAuthBound) {
    return;
  }
  window.__kbMessengerAuthBound = true;
  var timerTick = 0;
  var lastStart = { btn: null, url: '', label: '', ttl: 180 };

  document.addEventListener('click', function (event) {
    var node = event.target;
    if (!node || typeof node.closest !== 'function') {
      return;
    }
    var check = node.closest('[data-messenger-check]');
    if (check) {
      event.preventDefault();
      checkMessengerLink(check);
      return;
    }
    var btn = node.closest('[data-messenger-start]');
    if (!btn || btn.disabled) {
      return;
    }
    event.preventDefault();
    var label = btn.getAttribute('data-messenger-label') || 'پیام‌رسان';
    if (btn.getAttribute('data-messenger-link') === '1' && !kbIsMember()) {
      if (typeof window.__kbPromptAuth === 'function') {
        window.__kbPromptAuth();
      }
      return;
    }
    var popup = null;
    try {
      popup = window.open('about:blank', 'killbox-' + (btn.id || label));
    } catch (err) {
      popup = null;
    }
    btn.disabled = true;
    showMessengerStatus(btn, 'در حال اتصال به ' + label + '…', false);
    var csrf = document.querySelector('[name=csrfmiddlewaretoken]');
    fetch(btn.getAttribute('data-messenger-start'), {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': csrf ? csrf.value : '',
        'X-Requested-With': 'XMLHttpRequest',
      },
      body: '{}',
      credentials: 'same-origin',
    })
      .then(function (response) {
        return response.json().then(function (data) {
          data.status = response.status;
          return data;
        });
      })
      .then(function (data) {
        if (data.status === 401 && typeof window.__kbPromptAuth === 'function') {
          closeMessengerPopup(popup);
          btn.disabled = false;
          window.__kbPromptAuth();
          return;
        }
        if (!data || !data.success || !data.url) {
          closeMessengerPopup(popup);
          btn.disabled = false;
          showMessengerStatus(
            btn,
            (data && data.message) || ('اتصال به ' + label + ' ناموفق بود.'),
            true
          );
          return;
        }
        lastStart = {
          btn: btn,
          url: data.url,
          label: label,
          ttl: Number(data.ttl || 180),
        };
        openMessengerWindow(data.url, popup, btn, label);
        showMessengerStatus(
          btn,
          data.message || ('در ' + label + ' استارت را بزن.'),
          false,
          data.url,
          label
        );
        if (data.mode === 'link') {
          btn.disabled = false;
          showLinkCheck(btn);
          return;
        }
        showMessengerCode(data.url, label, Number(data.ttl || 180));
        btn.disabled = false;
      })
      .catch(function () {
        closeMessengerPopup(popup);
        btn.disabled = false;
        showMessengerStatus(btn, 'ارتباط با سرور برقرار نشد.', true);
      });
  });

  document.addEventListener('submit', function (event) {
    var form = event.target;
    if (!form || form.id !== 'messenger-code-form') {
      return;
    }
    event.preventDefault();
    submitMessengerCode();
  });

  function closeMessengerPopup(popup) {
    if (popup && !popup.closed) {
      popup.close();
    }
  }

  function openMessengerWindow(url, popup, btn, label) {
    if (popup && !popup.closed) {
      popup.location.replace(url);
      try {
        popup.focus();
      } catch (err) {
        /* ignore */
      }
      return;
    }
    var jump = window.open(url, 'killbox-' + (btn.id || label));
    if (!jump) {
      showMessengerStatus(btn, 'بازوی ' + label + ' باز نشد. از لینک زیر وارد شو.', true, url, label);
    }
  }

  function showLinkCheck(btn) {
    var check = document.getElementById('messenger-link-check');
    if (!check) {
      return;
    }
    check.hidden = false;
    check.disabled = false;
    check.setAttribute('data-messenger-status', btn.getAttribute('data-messenger-status') || '');
    check.setAttribute('data-messenger-label', btn.getAttribute('data-messenger-label') || '');
  }

  function checkMessengerLink(check) {
    var statusUrl = check.getAttribute('data-messenger-status');
    var label = check.getAttribute('data-messenger-label') || 'پیام‌رسان';
    if (!statusUrl) {
      return;
    }
    check.disabled = true;
    fetch(statusUrl, {
      credentials: 'same-origin',
      headers: { 'X-Requested-With': 'XMLHttpRequest' },
    })
      .then(function (response) {
        return response.json();
      })
      .then(function (data) {
        check.disabled = false;
        if (!data || !data.success) {
          showMessengerStatus(check, (data && data.message) || 'هنوز متصل نشده. بعد از استارت دوباره بررسی کن.', true);
          return;
        }
        showMessengerStatus(check, data.message || (label + ' متصل شد.'), false);
        check.hidden = true;
        var btn = lastStart.btn;
        if (btn) {
          btn.classList.add('is-on');
          btn.disabled = true;
          var caption = btn.querySelector('span');
          if (caption) {
            caption.textContent = label + ' متصل است';
          }
        }
      })
      .catch(function () {
        check.disabled = false;
        showMessengerStatus(check, 'ارتباط با سرور برقرار نشد.', true);
      });
  }

  function showMessengerCode(url, label, ttl) {
    var form = document.getElementById('messenger-code-form');
    var reopen = document.getElementById('messenger-code-reopen');
    var input = document.getElementById('messenger-code');
    if (!form) {
      return;
    }
    form.hidden = false;
    form.classList.remove('is-expired');
    if (reopen) {
      reopen.href = url || '#';
      reopen.textContent = 'دریافت مجدد کد / باز کردن مجدد بات ' + (label || '');
    }
    if (input) {
      input.value = '';
      input.focus();
    }
    startCodeTimer(ttl);
  }

  function startCodeTimer(ttl) {
    window.clearInterval(timerTick);
    var node = document.getElementById('messenger-code-timer');
    var form = document.getElementById('messenger-code-form');
    var left = Math.max(1, Number(ttl || 180));
    function paint() {
      if (!node) {
        return;
      }
      var mins = Math.floor(left / 60);
      var secs = left % 60;
      node.textContent =
        String(mins).padStart(2, '0') + ':' + String(secs).padStart(2, '0');
    }
    paint();
    timerTick = window.setInterval(function () {
      left -= 1;
      if (left <= 0) {
        window.clearInterval(timerTick);
        left = 0;
        paint();
        if (form) {
          form.classList.add('is-expired');
        }
        showMessengerStatus(
          lastStart.btn,
          'اعتبار کد تمام شد. دوباره بات را باز کن و شماره را بفرست.',
          true,
          lastStart.url,
          lastStart.label
        );
        return;
      }
      paint();
    }, 1000);
  }

  function submitMessengerCode() {
    var form = document.getElementById('messenger-code-form');
    var input = document.getElementById('messenger-code');
    var submit = document.getElementById('messenger-code-btn');
    var panel = document.getElementById('auth-panel');
    var url =
      (panel && panel.getAttribute('data-messenger-verify')) ||
      '/auth/messenger/verify-code/';
    var code = input ? String(input.value || '').trim() : '';
    if (!code) {
      showMessengerStatus(lastStart.btn, 'کد تایید را وارد کن.', true);
      return;
    }
    if (submit) {
      submit.disabled = true;
    }
    var csrf = document.querySelector('[name=csrfmiddlewaretoken]');
    fetch(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': csrf ? csrf.value : '',
        'X-Requested-With': 'XMLHttpRequest',
      },
      body: JSON.stringify({ code: code }),
      credentials: 'same-origin',
    })
      .then(function (response) {
        return response.json().then(function (data) {
          data.status = response.status;
          return data;
        });
      })
      .then(function (data) {
        if (submit) {
          submit.disabled = false;
        }
        if (!data || !data.success) {
          showMessengerStatus(
            lastStart.btn,
            (data && data.message) || 'کد تایید نادرست است.',
            true
          );
          return;
        }
        window.clearInterval(timerTick);
        showMessengerStatus(lastStart.btn, data.message || 'ثبت‌نام شما انجام شد.', false);
        if (form) {
          form.hidden = true;
        }
        if (data.redirect) {
          window.location.assign(data.redirect);
        }
      })
      .catch(function () {
        if (submit) {
          submit.disabled = false;
        }
        showMessengerStatus(lastStart.btn, 'ارتباط با سرور برقرار نشد.', true);
      });
  }

  function showMessengerStatus(btn, message, isError, url, label) {
    var status =
      document.getElementById('auth-status') || document.getElementById('messenger-link-status');
    if (!status) {
      if (typeof window.__kbFlashSocial === 'function') {
        window.__kbFlashSocial(message);
      }
      return;
    }
    status.hidden = !message;
    status.classList.toggle('is-error', !!isError);
    status.textContent = '';
    if (!message) {
      return;
    }
    status.appendChild(document.createTextNode(message));
    if (url) {
      status.appendChild(document.createTextNode(' '));
      var link = document.createElement('a');
      link.href = url;
      link.target = '_blank';
      link.rel = 'noopener';
      link.textContent = 'اگر ' + (label || 'پیام‌رسان') + ' باز نشد، اینجا را بزن.';
      status.appendChild(link);
    }
  }
}

function bindRankDialog() {
  if (window.__kbRankBound) {
    return;
  }
  window.__kbRankBound = true;

  function getDialog() {
    return document.getElementById('rank-dialog');
  }

  function ensureDialog() {
    var dialog = getDialog();
    if (dialog) {
      return dialog;
    }
    var tpl = document.getElementById('rank-dialog-tpl');
    if (!tpl || !tpl.content) {
      return null;
    }
    document.body.appendChild(tpl.content.cloneNode(true));
    return getDialog();
  }

  function openDialog() {
    var dialog = ensureDialog();
    if (!dialog) {
      return;
    }
    try {
      if (typeof dialog.showModal === 'function' && !dialog.open) {
        dialog.showModal();
        return;
      }
    } catch (err) {
      /* fall through to attribute fallback */
    }
    dialog.setAttribute('open', '');
    dialog.classList.add('is-open');
  }

  function closeDialog() {
    var dialog = getDialog();
    if (!dialog) {
      return;
    }
    dialog.classList.remove('is-open');
    try {
      if (typeof dialog.close === 'function' && dialog.open) {
        dialog.close();
        return;
      }
    } catch (err) {
      /* ignore */
    }
    dialog.removeAttribute('open');
  }

  document.addEventListener(
    'click',
    function (event) {
      var node = event.target;
      if (!node || typeof node.closest !== 'function') {
        return;
      }
      if (node.closest('[data-rank-close]')) {
        event.preventDefault();
        closeDialog();
        return;
      }
      var dialog = getDialog();
      if (dialog && node === dialog) {
        closeDialog();
        return;
      }
      if (node.closest('[data-rank-open]')) {
        event.preventDefault();
        event.stopPropagation();
        openDialog();
      }
    },
    true
  );
}

function bindHomeToasts() {
  var host = document.getElementById('home-toast');
  if (!host) {
    return;
  }
  var xp = (host.getAttribute('data-xp') || '').trim();
  var xpIcon = host.getAttribute('data-xp-icon') || '';
  var rankIcon = (host.getAttribute('data-rank-icon') || '').trim();
  var rankTitle = (host.getAttribute('data-rank-title') || '').trim();
  var queue = [];
  if (xp) {
    queue.push({
      icon: xpIcon,
      label: '+' + xp + ' XP',
      ltr: true,
    });
  }
  if (rankIcon) {
    queue.push({
      icon: rankIcon,
      label: rankTitle || 'لول آپ',
    });
  }
  if (!queue.length) {
    return;
  }

  function showNext() {
    var item = queue.shift();
    if (!item) {
      host.hidden = true;
      host.innerHTML = '';
      return;
    }
    host.hidden = false;
    host.innerHTML =
      '<div class="home-toast__card">' +
      '<img src="' + item.icon + '" alt="" width="512" height="512">' +
      '<p class="home-toast__label"' + (item.ltr ? ' dir="ltr"' : '') + '>' + item.label + '</p>' +
      '</div>';
    window.setTimeout(showNext, 3000);
  }

  showNext();
}

function bindAvatarUpload() {
  if (window.__kbAvatarBound) {
    return;
  }
  window.__kbAvatarBound = true;

  var sourceFile = null;
  var lastCrop = null;
  var avatarBusy = false;
  var avatarHolder = { xhr: null };
  var natural = { w: 0, h: 0 };
  var pan = { x: 0, y: 0 };
  var drag = null;
  var objectUrl = '';

  function card() {
    return document.querySelector('[data-avatar-upload]');
  }

  function dialog() {
    return document.getElementById('avatar-crop-dialog');
  }

  function stage() {
    return document.getElementById('avatar-crop-stage');
  }

  function preview() {
    return document.getElementById('avatar-crop-image');
  }

  function zoom() {
    return document.getElementById('avatar-crop-zoom');
  }

  function onFileChange(event) {
    var fileInput = event.target;
    var file = fileInput.files && fileInput.files[0];
    fileInput.value = '';
    if (!file || avatarBusy) {
      return;
    }
    if (window.__kbUpload) {
      if (!window.__kbUpload.isImage(file)) {
        showAvatarStatus('فقط تصویر JPG، PNG، WEBP یا GIF مجاز است.', true);
        return;
      }
      var check = window.__kbUpload.validateFile(file, { maxImage: 8 * 1024 * 1024 });
      if (!check.ok) {
        showAvatarStatus(check.message, true);
        return;
      }
    } else if (file.size > 8 * 1024 * 1024) {
      showAvatarStatus('حجم تصویر نباید بیشتر از ۸ مگابایت باشد.', true);
      return;
    }
    sourceFile = file;
    var img = new Image();
    img.onload = function () {
      natural.w = img.naturalWidth;
      natural.h = img.naturalHeight;
      URL.revokeObjectURL(img.src);
      if (Math.abs(natural.w - natural.h) < 8) {
        uploadAvatar(file, { x: 0, y: 0, size: Math.min(natural.w, natural.h) });
        return;
      }
      openCrop();
    };
    img.onerror = function () {
      showAvatarStatus('تصویر قابل خواندن نبود.', true);
    };
    img.src = URL.createObjectURL(file);
  }

  function openCrop() {
    var box = dialog();
    var image = preview();
    var zoomInput = zoom();
    if (!box || !image || !zoomInput) {
      uploadAvatar(sourceFile, null);
      return;
    }
    if (objectUrl) {
      URL.revokeObjectURL(objectUrl);
    }
    objectUrl = URL.createObjectURL(sourceFile);
    image.src = objectUrl;
    pan.x = 0;
    pan.y = 0;
    zoomInput.value = '100';
    if (typeof box.showModal === 'function') {
      box.showModal();
    } else {
      box.setAttribute('open', '');
    }
    window.setTimeout(function () {
      image.onload = layoutCrop;
      layoutCrop();
    }, 40);
  }

  function closeCrop() {
    var box = dialog();
    if (!box) {
      return;
    }
    if (typeof box.close === 'function' && box.open) {
      box.close();
    } else {
      box.removeAttribute('open');
    }
    if (objectUrl) {
      URL.revokeObjectURL(objectUrl);
      objectUrl = '';
    }
  }

  function layoutCrop() {
    var cropStage = stage();
    var image = preview();
    var zoomInput = zoom();
    if (!cropStage || !image || !zoomInput || !natural.w) {
      return;
    }
    var box = cropStage.getBoundingClientRect();
    var cover = Math.max(box.width / natural.w, box.height / natural.h);
    var scale = cover * (Number(zoomInput.value) / 100);
    var width = natural.w * scale;
    var height = natural.h * scale;
    var minX = box.width - width;
    var minY = box.height - height;
    pan.x = clamp(pan.x, Math.min(0, minX), 0);
    pan.y = clamp(pan.y, Math.min(0, minY), 0);
    image.style.width = width + 'px';
    image.style.height = height + 'px';
    image.style.left = pan.x + 'px';
    image.style.top = pan.y + 'px';
  }

  function currentCrop() {
    var cropStage = stage();
    var zoomInput = zoom();
    if (!cropStage || !zoomInput || !natural.w) {
      return null;
    }
    var box = cropStage.getBoundingClientRect();
    var cover = Math.max(box.width / natural.w, box.height / natural.h);
    var scale = cover * (Number(zoomInput.value) / 100);
    return {
      x: Math.max(0, -pan.x / scale),
      y: Math.max(0, -pan.y / scale),
      size: box.width / scale,
    };
  }

  function paintAvatarProgress(percent, label) {
    var bar = document.getElementById('avatar-upload-bar');
    var fill = bar && bar.querySelector('.kb-upload-bar__fill');
    var text = bar && bar.querySelector('.kb-upload-bar__label');
    if (!bar) {
      return;
    }
    bar.hidden = percent == null && !label;
    if (fill) {
      fill.style.transform = 'scaleX(' + Math.max(0, Math.min(1, (percent || 0) / 100)) + ')';
    }
    if (text) {
      text.textContent = label || '';
    }
  }

  function setAvatarBusy(on) {
    avatarBusy = !!on;
    var apply = document.getElementById('avatar-crop-apply');
    if (apply) {
      apply.disabled = !!on;
      apply.classList.toggle('is-busy', !!on);
    }
    var uploadLabel = document.querySelector('.profile-avatar-upload');
    if (uploadLabel) {
      uploadLabel.classList.toggle('is-busy', !!on);
    }
  }

  function failAvatar(message) {
    setAvatarBusy(false);
    paintAvatarProgress(0, '');
    showAvatarStatus(message || 'آپلود آواتار ناموفق بود.', true);
    var retry = document.getElementById('avatar-retry');
    if (retry) {
      retry.hidden = false;
    }
  }

  function uploadAvatar(file, crop) {
    var host = card();
    if (!file || !host || avatarBusy) {
      return;
    }
    lastCrop = crop || null;
    sourceFile = file;
    var retry = document.getElementById('avatar-retry');
    if (retry) {
      retry.hidden = true;
    }
    setAvatarBusy(true);
    paintAvatarProgress(0, 'در حال بارگذاری: ۰٪');
    showAvatarStatus('', false);
    var body = new FormData();
    body.append('avatar', file);
    if (crop && crop.size) {
      body.append('crop_x', String(Math.round(crop.x)));
      body.append('crop_y', String(Math.round(crop.y)));
      body.append('crop_size', String(Math.round(crop.size)));
    }
    var send = window.__kbUpload && window.__kbUpload.send
      ? window.__kbUpload.send(host.getAttribute('data-avatar-upload'), body, {
          holder: avatarHolder,
          onProgress: function (percent) {
            if (percent >= 100) {
              paintAvatarProgress(100, 'در حال ذخیره‌سازی و پردازش…');
              return;
            }
            paintAvatarProgress(percent, 'در حال بارگذاری: ' + percent + '٪');
          },
        })
      : Promise.reject(new Error('ماژول آپلود در دسترس نیست.'));
    send
      .then(function (data) {
        if (!data || !data.success) {
          failAvatar((data && data.message) || 'آپلود آواتار ناموفق بود.');
          return;
        }
        setAvatarBusy(false);
        paintAvatarProgress(100, 'ذخیره شد.');
        var next = data.url + (data.url.indexOf('?') >= 0 ? '&' : '?') + 'v=' + Date.now();
        document.querySelectorAll('.profile-avatar, .topbar-profile img').forEach(function (img) {
          img.src = next;
          img.classList.add('is-custom');
        });
        showAvatarStatus(data.message || 'آواتار ذخیره شد.', false);
      })
      .catch(function (err) {
        if (err && err.code === 'abort') {
          return;
        }
        failAvatar((err && err.message) || 'ارتباط با سرور برقرار نشد.');
      });
  }

  function showAvatarStatus(message, isError) {
    var status = document.getElementById('avatar-status');
    if (!status) {
      return;
    }
    status.hidden = !message;
    status.textContent = message || '';
    status.classList.toggle('is-error', !!isError);
  }

  document.addEventListener(
    'click',
    function (event) {
      var node = event.target;
      if (!node || typeof node.closest !== 'function') {
        return;
      }
      if (node.closest('#avatar-crop-cancel')) {
        event.preventDefault();
        closeCrop();
        return;
      }
      if (node.closest('#avatar-crop-apply')) {
        event.preventDefault();
        uploadAvatar(sourceFile, currentCrop());
        closeCrop();
        return;
      }
      if (node.closest('#avatar-retry')) {
        event.preventDefault();
        if (sourceFile) {
          uploadAvatar(sourceFile, lastCrop);
        }
      }
    },
    true
  );

  document.addEventListener('change', function (event) {
    if (event.target && event.target.id === 'avatar-file') {
      onFileChange(event);
    }
  });

  document.addEventListener('input', function (event) {
    if (event.target && event.target.id === 'avatar-crop-zoom') {
      layoutCrop();
    }
  });

  document.addEventListener('pointerdown', function (event) {
    var cropStage = stage();
    if (!cropStage || !cropStage.contains(event.target)) {
      return;
    }
    drag = { x: event.clientX - pan.x, y: event.clientY - pan.y };
    cropStage.classList.add('is-dragging');
    cropStage.setPointerCapture(event.pointerId);
  });

  document.addEventListener('pointermove', function (event) {
    if (!drag) {
      return;
    }
    pan.x = event.clientX - drag.x;
    pan.y = event.clientY - drag.y;
    layoutCrop();
  });

  document.addEventListener('pointerup', function () {
    var cropStage = stage();
    drag = null;
    if (cropStage) {
      cropStage.classList.remove('is-dragging');
    }
  });

  document.addEventListener('pointercancel', function () {
    var cropStage = stage();
    drag = null;
    if (cropStage) {
      cropStage.classList.remove('is-dragging');
    }
  });
}

function clamp(value, min, max) {
  return Math.min(max, Math.max(min, value));
}

function bindProfileTools() {
  syncBioUi();
  bindCodmConnect();
  if (window.__kbProfileBound) {
    return;
  }
  window.__kbProfileBound = true;

  function csrf() {
    var node = document.querySelector('[name=csrfmiddlewaretoken]');
    return node ? node.value : '';
  }

  function postProfile(url, data) {
    return fetch(url, {
      method: 'POST',
      headers: {
        'X-CSRFToken': csrf(),
        'Content-Type': 'application/x-www-form-urlencoded',
      },
      credentials: 'same-origin',
      body: new URLSearchParams(data),
    }).then(function (response) {
      return response.json();
    });
  }

  function nameDialog() {
    return document.getElementById('name-dialog');
  }

  function selectInviteField() {
    var invite = document.getElementById('invite-url');
    if (!invite) {
      return null;
    }
    try {
      invite.removeAttribute('readonly');
      invite.focus();
      invite.select();
      if (typeof invite.setSelectionRange === 'function') {
        invite.setSelectionRange(0, invite.value.length);
      }
    } catch (err) {}
    return invite;
  }

  function copyFromNode(node, text) {
    if (!node) {
      return false;
    }
    try {
      node.focus();
      if (typeof node.select === 'function') {
        node.select();
      }
      if (typeof node.setSelectionRange === 'function') {
        node.setSelectionRange(0, String(text || node.value || '').length);
      }
      return document.execCommand('copy');
    } catch (err) {
      return false;
    }
  }

  function copyText(value) {
    var text = String(value || '');
    var invite = selectInviteField();
    if (invite && invite.value === text && copyFromNode(invite, text)) {
      invite.setAttribute('readonly', '');
      return Promise.resolve();
    }
    var field = document.createElement('textarea');
    field.value = text;
    field.style.cssText = 'position:fixed;top:8px;left:8px;width:8px;height:8px;opacity:0.01;z-index:9';
    document.body.appendChild(field);
    var copied = copyFromNode(field, text);
    document.body.removeChild(field);
    if (invite) {
      invite.setAttribute('readonly', '');
      selectInviteField();
      invite.setAttribute('readonly', '');
    }
    if (copied) {
      return Promise.resolve();
    }
    if (navigator.clipboard && navigator.clipboard.writeText) {
      return navigator.clipboard.writeText(text).catch(function () {
        return Promise.resolve();
      });
    }
    return Promise.resolve();
  }

  function showInviteStatus(message, isError) {
    var status = document.getElementById('invite-status');
    if (!status) {
      return;
    }
    status.hidden = !message;
    status.removeAttribute('hidden');
    if (!message) {
      status.setAttribute('hidden', '');
    }
    status.textContent = message || '';
    status.classList.toggle('is-error', !!isError);
  }

  function inviteUrl() {
    var invite = document.getElementById('invite-url');
    if (invite && invite.value) {
      return invite.value;
    }
    var host = document.querySelector('[data-invite-url]');
    return host ? String(host.getAttribute('data-invite-url') || '') : '';
  }

  document.addEventListener('input', function (event) {
    if (event.target && event.target.id === 'profile-bio') {
      syncBioUi();
    }
  });

  document.addEventListener(
    'click',
    function (event) {
      var node = event.target;
      if (node && node.nodeType !== 1) {
        node = node.parentElement;
      }
      if (!node || typeof node.closest !== 'function') {
        return;
      }
      if (node.closest('[data-copy-uid]')) {
        var uid = document.getElementById('profile-uid');
        if (uid) {
          copyText(uid.textContent.trim());
        }
        return;
      }
      if (node.closest('[data-name-open]')) {
        var dialog = nameDialog();
        if (dialog && dialog.showModal) {
          dialog.showModal();
        }
        return;
      }
      if (node.closest('[data-name-close]')) {
        var box = nameDialog();
        if (box && box.close) {
          box.close();
        }
        return;
      }
      if (node.closest('#name-save')) {
        var card = document.querySelector('[data-name-url]');
        var input = document.getElementById('name-input');
        if (!card || !input) {
          return;
        }
        postProfile(card.getAttribute('data-name-url'), { display_name: input.value }).then(function (payload) {
          if (!payload.success) {
            return;
          }
          var title = document.getElementById('profile-display-name');
          if (title) {
            title.textContent = payload.display_name;
          }
          var closed = nameDialog();
          if (closed && closed.close) {
            closed.close();
          }
        });
        return;
      }
      if (node.closest('#bio-edit')) {
        var wrap = document.querySelector('.profile-bio');
        if (!wrap) {
          return;
        }
        wrap.classList.remove('is-saved');
        wrap.classList.add('is-editing');
        var field = document.getElementById('profile-bio');
        if (field) {
          field.focus();
        }
        syncBioUi();
        return;
      }
      if (node.closest('#bio-save')) {
        event.preventDefault();
        var host = document.querySelector('[data-bio-url]');
        var bioField = document.getElementById('profile-bio');
        if (!host || !bioField) {
          return;
        }
        postProfile(host.getAttribute('data-bio-url'), { bio: bioField.value }).then(function (payload) {
          if (!payload.success) {
            return;
          }
          var box = document.querySelector('.profile-bio');
          var text = document.getElementById('bio-text');
          if (box) {
            box.setAttribute('data-saved-bio', payload.bio || '');
          }
          if (text) {
            text.textContent = payload.bio || '';
          }
          if (payload.bio) {
            box.classList.add('is-saved');
            box.classList.remove('is-editing');
          }
          syncBioUi();
        });
        return;
      }
      if (node.closest('[data-copy-invite]')) {
        event.preventDefault();
        event.stopPropagation();
        var url = inviteUrl();
        if (!url) {
          showInviteStatus('لینک دعوت آماده نیست.', true);
          return;
        }
        copyText(url)
          .then(function () {
            showInviteStatus('کپی شد', false);
          })
          .catch(function () {
            showInviteStatus('کپی لینک انجام نشد.', true);
          });
        return;
      }
      if (node.closest('[data-share-invite]')) {
        event.preventDefault();
        event.stopPropagation();
        var shareUrl = inviteUrl();
        if (!shareUrl) {
          showInviteStatus('لینک دعوت آماده نیست.', true);
          return;
        }
        var shareData = {
          title: 'KILLBOX',
          text: 'با این لینک در کیل‌باکس عضو شو',
          url: shareUrl,
        };
        function copyAsShare() {
          copyText(shareUrl)
            .then(function () {
              showInviteStatus('کپی شد', false);
            })
            .catch(function () {
              showInviteStatus('اشتراک‌گذاری در این مرورگر نیست؛ لینک را دستی کپی کن.', true);
            });
        }
        if (typeof navigator.share === 'function') {
          try {
            var sharing = navigator.share(shareData);
            if (sharing && typeof sharing.then === 'function') {
              sharing.then(function () {
                showInviteStatus('ارسال شد', false);
              }).catch(function (err) {
                if (err && err.name === 'AbortError') {
                  return;
                }
                copyAsShare();
              });
              return;
            }
          } catch (err) {
            copyAsShare();
            return;
          }
        }
        copyAsShare();
      }
    },
    true
  );
}

function bindCodmConnect() {
  var box = document.querySelector('[data-codm-url]');
  var form = document.getElementById('codm-form');
  if (!box || !form || form.getAttribute('data-kb-bound')) {
    return;
  }
  form.setAttribute('data-kb-bound', '1');
  var url = box.getAttribute('data-codm-url');
  var uidField = document.getElementById('codm-uid');
  var submit = document.getElementById('codm-submit');
  var status = document.getElementById('codm-status');
  var result = document.getElementById('codm-result');
  var nameOut = document.getElementById('codm-result-name');
  var levelOut = document.getElementById('codm-result-level');
  var uidOut = document.getElementById('codm-result-uid');
  var fallback = document.getElementById('codm-fallback');
  var nickField = document.getElementById('codm-nickname');
  var csrfNode = document.querySelector('[name=csrfmiddlewaretoken]');

  function showStatus(message, isError) {
    if (!status) {
      return;
    }
    status.hidden = !message;
    status.textContent = message || '';
    status.classList.toggle('is-error', !!isError);
  }

  function paintResult(payload) {
    if (nameOut) {
      nameOut.textContent = payload.nickname || '—';
    }
    if (levelOut) {
      levelOut.textContent = payload.level || '—';
    }
    if (uidOut) {
      uidOut.textContent = payload.uid || '—';
    }
    if (result) {
      result.hidden = false;
    }
    if (fallback) {
      fallback.hidden = true;
    }
  }

  function send(extra) {
    var uid = (uidField && uidField.value ? uidField.value : '').trim();
    if (!/^\d+$/.test(uid)) {
      showStatus('UID باید فقط عدد باشد.', true);
      return;
    }
    if (submit) {
      submit.disabled = true;
    }
    showStatus('در حال اتصال…', false);
    var body = { uid: uid };
    if (extra && extra.nickname) {
      body.nickname = extra.nickname;
    }
    fetch(url, {
      method: 'POST',
      headers: {
        'X-CSRFToken': csrfNode ? csrfNode.value : '',
        'Content-Type': 'application/x-www-form-urlencoded',
        'X-Requested-With': 'XMLHttpRequest',
      },
      credentials: 'same-origin',
      body: new URLSearchParams(body),
    })
      .then(function (response) {
        return response.json();
      })
      .then(function (payload) {
        if (payload && payload.success) {
          paintResult(payload);
          showStatus(payload.message || 'اکانت بازی متصل شد.', false);
          return;
        }
        if (payload && payload.source === 'fallback' && fallback) {
          fallback.hidden = false;
          if (result) {
            result.hidden = true;
          }
        }
        showStatus((payload && payload.message) || 'اتصال ناموفق بود.', true);
      })
      .catch(function () {
        showStatus('ارتباط با سرور برقرار نشد.', true);
      })
      .finally(function () {
        if (submit) {
          submit.disabled = false;
        }
      });
  }

  form.addEventListener('submit', function (event) {
    event.preventDefault();
    send();
  });
  if (fallback) {
    fallback.addEventListener('submit', function (event) {
      event.preventDefault();
      send({ nickname: nickField ? nickField.value.trim() : '' });
    });
  }
}

function syncBioUi() {
  var wrap = document.querySelector('.profile-bio');
  var field = document.getElementById('profile-bio');
  var count = document.getElementById('bio-count');
  var save = document.getElementById('bio-save');
  if (field && count) {
    count.textContent = String(field.value.length);
  }
  if (!wrap || !field || !save) {
    return;
  }
  var saved = String(wrap.getAttribute('data-saved-bio') || '');
  var dirty = field.value !== saved;
  save.hidden = !dirty || !wrap.classList.contains('is-editing');
}
