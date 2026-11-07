document.addEventListener('DOMContentLoaded', function () {
  runLandingIntro();
  bindPage();
});

function bindPage() {
  bindLandingAuth();
  bindMessengerAuth('auth-bale-btn', 'بله');
  bindMessengerAuth('auth-telegram-btn', 'تلگرام');
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
}

window.__kbBindPage = bindPage;

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

function runLandingIntro() {
  var root = document.body;
  if (!root || root.getAttribute('data-intro') !== '1') {
    return;
  }
  var admitted = root.getAttribute('data-admitted') === '1';
  var homeUrl = root.getAttribute('data-home') || '/home/';
  var reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  function finish() {
    if (admitted) {
      if (window.__kbGo) {
        window.__kbGo(homeUrl);
        return;
      }
      window.location.replace(homeUrl);
      return;
    }
    revealAuth();
  }

  function dock() {
    root.classList.add('is-welcome-gone');
    root.classList.add('is-docked');
    window.setTimeout(finish, reduced ? 0 : 980);
  }

  if (reduced) {
    dock();
    return;
  }

  window.setTimeout(function () {
    root.classList.add('is-dissolving');
    window.setTimeout(function () {
      root.classList.remove('is-dissolving');
      dock();
    }, 920);
  }, 2400);
}

function revealAuth() {
  var panel = document.getElementById('auth-panel');
  document.body.classList.add('is-auth');
  if (panel) {
    panel.hidden = false;
  }
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
          window.__kbGo(data.redirect || '/home/');
        } else {
          window.location.assign(data.redirect || '/home/');
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

function bindMessengerAuth(buttonId, label) {
  var btn = document.getElementById(buttonId);
  var status = document.getElementById('auth-status');
  var sendForm = document.getElementById('auth-send-form');
  if (!btn || btn.disabled) {
    return;
  }
  var csrf = document.querySelector('[name=csrfmiddlewaretoken]');
  var poll = 0;

  btn.addEventListener('click', function () {
    var popup = null;
    try {
      popup = window.open('about:blank', 'killbox-' + buttonId);
    } catch (err) {
      popup = null;
    }
    btn.disabled = true;
    showStatus('در حال اتصال به ' + label + '…', false);
    fetch(btn.getAttribute('data-start'), {
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
        return response.json();
      })
      .then(function (data) {
        if (!data || !data.success || !data.url) {
          closePopup(popup);
          btn.disabled = false;
          showStatus((data && data.message) || ('اتصال به ' + label + ' ناموفق بود.'), true);
          return;
        }
        openMessenger(data.url, popup);
        showStatus(
          data.message || ('در ' + label + ' استارت را بزن و شماره را به اشتراک بگذار.'),
          false,
          data.url
        );
        startPoll(btn.getAttribute('data-status'));
      })
      .catch(function () {
        closePopup(popup);
        btn.disabled = false;
        showStatus('ارتباط با سرور برقرار نشد.', true);
      });
  });

  function closePopup(popup) {
    if (popup && !popup.closed) {
      popup.close();
    }
  }

  function openMessenger(url, popup) {
    if (popup && !popup.closed) {
      popup.location.replace(url);
      try {
        popup.focus();
      } catch (err) {
        /* ignore */
      }
      return;
    }
    var jump = window.open(url, 'killbox-' + buttonId);
    if (!jump) {
      showStatus('بازوی ' + label + ' باز نشد. از لینک زیر وارد شو.', true, url);
    }
  }

  function startPoll(url) {
    window.clearInterval(poll);
    var tries = 0;
    poll = window.setInterval(function () {
      tries += 1;
      if (tries > 90) {
        window.clearInterval(poll);
        btn.disabled = false;
        showStatus('زمان تایید ' + label + ' تمام شد. دوباره تلاش کنید.', true);
        return;
      }
      fetch(url, { credentials: 'same-origin', headers: { 'X-Requested-With': 'XMLHttpRequest' } })
        .then(function (response) {
          return response.json();
        })
        .then(function (data) {
          if (data && data.success && data.redirect) {
            window.clearInterval(poll);
            showStatus(data.message || ('ثبت‌نام با ' + label + ' تکمیل شد.'), false);
            if (window.__kbGo) {
              window.__kbGo(data.redirect);
            } else {
              window.location.assign(data.redirect);
            }
          }
        })
        .catch(function () {});
    }, 2000);
  }

  function showStatus(message, isError, url) {
    if (!status) {
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
      link.textContent = 'اگر ' + label + ' باز نشد، اینجا را بزن.';
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
      if (node === getDialog()) {
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
    if (!file) {
      return;
    }
    if (file.size > 8 * 1024 * 1024) {
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

  function uploadAvatar(file, crop) {
    var host = card();
    var csrf = document.querySelector('[name=csrfmiddlewaretoken]');
    if (!file || !host) {
      return;
    }
    showAvatarStatus('در حال بهینه‌سازی و ذخیره آواتار…', false);
    var body = new FormData();
    body.append('avatar', file);
    if (crop && crop.size) {
      body.append('crop_x', String(Math.round(crop.x)));
      body.append('crop_y', String(Math.round(crop.y)));
      body.append('crop_size', String(Math.round(crop.size)));
    }
    fetch(host.getAttribute('data-avatar-upload'), {
      method: 'POST',
      headers: {
        'X-CSRFToken': csrf ? csrf.value : '',
        'X-Requested-With': 'XMLHttpRequest',
      },
      body: body,
      credentials: 'same-origin',
    })
      .then(function (response) {
        return response.json();
      })
      .then(function (data) {
        if (!data || !data.success) {
          showAvatarStatus((data && data.message) || 'آپلود آواتار ناموفق بود.', true);
          return;
        }
        var next = data.url + (data.url.indexOf('?') >= 0 ? '&' : '?') + 'v=' + Date.now();
        document.querySelectorAll('.profile-avatar, .topbar-profile img').forEach(function (img) {
          img.src = next;
          img.classList.add('is-custom');
        });
        showAvatarStatus(data.message || 'آواتار ذخیره شد.', false);
      })
      .catch(function () {
        showAvatarStatus('ارتباط با سرور برقرار نشد.', true);
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
