document.addEventListener('DOMContentLoaded', function () {
  var sceneFx = null;
  var previewFx = null;
  var back = document.getElementById('fog-back');
  var front = document.getElementById('fog-front');
  if (window.KillBoxParticles && window.KillBoxParticles.mountScene) {
    sceneFx = window.KillBoxParticles.mountScene({
      fogBack: back,
      fogFront: front,
      smokeBack: document.getElementById('smoke-back'),
      smokeFront: document.getElementById('smoke-front'),
      ashBack: document.getElementById('ash-back'),
      ashFront: document.getElementById('ash-front') || document.getElementById('ash-field'),
      sceneUrl: (document.querySelector('.landing-bg') &&
        document.querySelector('.landing-bg').getAttribute('data-scene')) || '',
    });
  } else if (back && front && window.KillBoxParticles && window.KillBoxParticles.mountParallax) {
    sceneFx = window.KillBoxParticles.mountParallax(back, front);
  } else if (back && window.KillBoxParticles) {
    sceneFx = window.KillBoxParticles.mount(back, { layer: 'back' });
  }

  var canvas = document.getElementById('lab-dust-field');
  if (canvas && window.KillBoxParticles) {
    previewFx = window.KillBoxParticles.mount(canvas);
  }

  bindThemeSelector();
  bindAtmosphere(sceneFx, previewFx);
  bindStreamHub();
  bindStreamHud();
  bindDonateBox();
  bindLiveChat();
  bindOtpAuth();
  bindEventFrame();
  bindLiveFrame();

  var form = document.getElementById('uid-lookup-form');
  if (form) {
    bindUidLookup(form);
  }
});

function bindAtmosphere(sceneFx, previewFx) {
  var fogInput = document.getElementById('lab-fog-density');
  var lightInput = document.getElementById('lab-light-intensity');
  var fogOut = document.getElementById('lab-fog-density-out');
  var lightOut = document.getElementById('lab-light-intensity-out');
  if (!fogInput || !lightInput) {
    return;
  }

  var stored = null;
  try {
    stored = JSON.parse(window.localStorage.getItem('killbox-lab-atmos') || 'null');
  } catch (error) {
    stored = null;
  }
  if (stored && typeof stored.fog === 'number' && typeof stored.light === 'number') {
    fogInput.value = String(clampAtmos(stored.fog));
    lightInput.value = String(clampAtmos(stored.light));
  }

  apply();
  fogInput.addEventListener('input', apply);
  lightInput.addEventListener('input', apply);

  function apply() {
    var fogPct = clampAtmos(Number(fogInput.value));
    var lightPct = clampAtmos(Number(lightInput.value));
    var fog = fogPct / 100;
    var light = lightPct / 100;
    if (sceneFx && sceneFx.setAtmosphere) {
      sceneFx.setAtmosphere(fog, light);
    }
    if (previewFx && previewFx.setAtmosphere) {
      previewFx.setAtmosphere(fog, light);
    }
    document.body.style.setProperty('--lab-light', String(light));
    if (fogOut) {
      fogOut.value = fogPct + '%';
    }
    if (lightOut) {
      lightOut.value = lightPct + '%';
    }
    try {
      window.localStorage.setItem(
        'killbox-lab-atmos',
        JSON.stringify({ fog: fogPct, light: lightPct })
      );
    } catch (error) {
      /* ignore quota / private mode */
    }
  }

  function clampAtmos(value) {
    if (!isFinite(value)) {
      return 100;
    }
    return Math.max(0, Math.min(160, Math.round(value)));
  }
}

function bindThemeSelector() {
  var buttons = document.querySelectorAll('[data-theme]');
  if (!buttons.length) {
    return;
  }

  var themes = { classic: 1, glass: 1, neon: 1, carbon: 1 };
  var stored = '';
  try {
    stored = window.localStorage.getItem('killbox-lab-theme') || '';
  } catch (error) {
    stored = '';
  }
  applyTheme(themes[stored] ? stored : 'classic');

  Array.prototype.forEach.call(buttons, function (button) {
    button.addEventListener('click', function () {
      applyTheme(button.getAttribute('data-theme'));
    });
  });

  function applyTheme(theme) {
    if (!themes[theme]) {
      theme = 'classic';
    }
    document.body.classList.remove(
      'lab-theme-classic',
      'lab-theme-glass',
      'lab-theme-neon',
      'lab-theme-carbon'
    );
    document.body.classList.add('lab-theme-' + theme);
    Array.prototype.forEach.call(buttons, function (button) {
      var active = button.getAttribute('data-theme') === theme;
      button.classList.toggle('is-active', active);
      button.setAttribute('aria-pressed', active ? 'true' : 'false');
    });
    try {
      window.localStorage.setItem('killbox-lab-theme', theme);
    } catch (error) {
      /* ignore quota / private mode */
    }
  }
}

function bindUidLookup(form) {
  var input = document.getElementById('cod-uid');
  var button = document.getElementById('uid-lookup-submit');
  var status = document.getElementById('uid-lookup-status');
  var result = document.getElementById('uid-lookup-result');
  var username = document.getElementById('uid-result-username');
  var level = document.getElementById('uid-result-level');
  var uidOut = document.getElementById('uid-result-uid');
  var fallback = document.getElementById('uid-fallback-form');
  var fallbackMessage = document.getElementById('uid-fallback-message');
  var fallbackName = document.getElementById('cod-nickname');
  var csrfNode = form.querySelector('[name=csrfmiddlewaretoken]');
  var lastUid = '';

  form.addEventListener('submit', function (event) {
    event.preventDefault();
    var uid = (input.value || '').trim();
    if (!/^\d+$/.test(uid)) {
      showStatus('UID باید فقط عدد باشد.', true);
      hidePanels();
      return;
    }

    lastUid = uid;
    button.disabled = true;
    showStatus('در حال استعلام…', false);
    hidePanels();

    fetch(form.action, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': csrfNode ? csrfNode.value : '',
        'X-Requested-With': 'XMLHttpRequest',
      },
      body: JSON.stringify({ uid: uid }),
      credentials: 'same-origin',
    })
      .then(function (response) {
        return response.json().then(function (data) {
          return data;
        });
      })
      .then(function (data) {
        if (data && data.success) {
          renderLive(data);
          showStatus('', false);
          return;
        }
        showFallback((data && data.message) || 'استعلام خودکار در دسترس نیست. لطفاً نام را دستی وارد کنید.');
        showStatus('', false);
      })
      .catch(function () {
        showFallback('استعلام خودکار در دسترس نیست. لطفاً نام را دستی وارد کنید.');
        showStatus('', false);
      })
      .finally(function () {
        button.disabled = false;
      });
  });

  if (fallback) {
    fallback.addEventListener('submit', function (event) {
      event.preventDefault();
      var nickname = (fallbackName.value || '').trim();
      if (!nickname) {
        showStatus('نام کاربری داخل بازی را وارد کنید.', true);
        return;
      }
      username.textContent = nickname;
      level.textContent = '—';
      uidOut.textContent = lastUid || input.value.trim();
      result.classList.remove('is-live');
      result.hidden = false;
      fallback.hidden = true;
      showStatus('', false);
    });
  }

  function renderLive(data) {
    username.textContent = data.nickname;
    level.textContent = String(data.level);
    uidOut.textContent = data.uid;
    result.classList.add('is-live');
    result.hidden = false;
    fallback.hidden = true;
  }

  function showFallback(message) {
    result.hidden = true;
    result.classList.remove('is-live');
    fallback.hidden = false;
    fallbackMessage.textContent = message;
    fallbackName.value = '';
    fallbackName.focus();
  }

  function hidePanels() {
    result.hidden = true;
    result.classList.remove('is-live');
    fallback.hidden = true;
  }

  function showStatus(message, isError) {
    if (!message) {
      status.hidden = true;
      status.textContent = '';
      status.classList.remove('is-error');
      return;
    }
    status.hidden = false;
    status.textContent = message;
    status.classList.toggle('is-error', isError);
  }
}

function bindOtpAuth() {
  var root = document.getElementById('bench-otp');
  var sendForm = document.getElementById('otp-send-form');
  var verifyForm = document.getElementById('otp-verify-form');
  var phone = document.getElementById('otp-phone');
  var code = document.getElementById('otp-code');
  var sendBtn = document.getElementById('otp-send-btn');
  var verifyBtn = document.getElementById('otp-verify-btn');
  var status = document.getElementById('otp-status');
  var verified = document.getElementById('otp-verified');
  var verifiedPhone = document.getElementById('otp-verified-phone');
  if (!sendForm || !verifyForm || !phone) {
    return;
  }

  var sendCsrf = sendForm.querySelector('[name=csrfmiddlewaretoken]');
  var verifyCsrf = verifyForm.querySelector('[name=csrfmiddlewaretoken]');
  var cooldown = Number(root && root.getAttribute('data-otp-cooldown')) || 60;
  var timer = 0;
  var lastPhone = '';

  phone.addEventListener('input', function () {
    if (verifyForm.hidden) {
      return;
    }
    if ((phone.value || '').trim() !== lastPhone) {
      verifyForm.hidden = true;
      if (verified) {
        verified.hidden = true;
        verified.classList.remove('is-live');
      }
    }
  });

  sendForm.addEventListener('submit', function (event) {
    event.preventDefault();
    var mobile = (phone.value || '').trim();
    if (!mobile) {
      showOtpStatus('شماره موبایل را وارد کنید.', true);
      return;
    }
    sendBtn.disabled = true;
    showOtpStatus('در حال ارسال کد…', false);
    postOtp(sendForm.action, sendCsrf, { phone: mobile })
      .then(function (data) {
        if (!data || !data.success) {
          showOtpStatus((data && data.message) || 'ارسال کد ناموفق بود.', true);
          startCooldown((data && data.retry_after) || 0);
          return;
        }
        lastPhone = mobile;
        verifyForm.hidden = false;
        if (code) {
          code.value = '';
          code.focus();
        }
        showOtpStatus(data.message || 'کد تایید ارسال شد.', false);
        startCooldown(data.retry_after || cooldown);
      })
      .catch(function () {
        showOtpStatus('ارتباط با سرور برقرار نشد.', true);
        sendBtn.disabled = false;
      });
  });

  verifyForm.addEventListener('submit', function (event) {
    event.preventDefault();
    var mobile = (phone.value || '').trim();
    var otp = (code && code.value) || '';
    if (!otp.trim()) {
      showOtpStatus('کد تایید را وارد کنید.', true);
      return;
    }
    verifyBtn.disabled = true;
    showOtpStatus('در حال بررسی کد…', false);
    postOtp(verifyForm.action, verifyCsrf, { phone: mobile, code: otp })
      .then(function (data) {
        verifyBtn.disabled = false;
        if (!data || !data.success) {
          showOtpStatus((data && data.message) || 'کد تایید نادرست است.', true);
          return;
        }
        showOtpStatus(data.message || 'شماره موبایل تایید شد.', false);
        if (verified && verifiedPhone) {
          verifiedPhone.textContent = data.phone || mobile;
          verified.hidden = false;
          verified.classList.add('is-live');
        }
      })
      .catch(function () {
        verifyBtn.disabled = false;
        showOtpStatus('ارتباط با سرور برقرار نشد.', true);
      });
  });

  function postOtp(url, csrfNode, body) {
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
    if (!left) {
      sendBtn.disabled = false;
      sendBtn.textContent = 'ارسال کد تایید';
      return;
    }
    sendBtn.disabled = true;
    tick();
    timer = window.setInterval(tick, 1000);

    function tick() {
      if (left <= 0) {
        window.clearInterval(timer);
        sendBtn.disabled = false;
        sendBtn.textContent = 'ارسال مجدد کد';
        return;
      }
      sendBtn.textContent = 'ارسال مجدد (' + left + ')';
      left -= 1;
    }
  }

  function showOtpStatus(message, isError) {
    if (!status) {
      return;
    }
    if (!message) {
      status.hidden = true;
      status.textContent = '';
      status.classList.remove('is-error', 'is-ok');
      return;
    }
    status.hidden = false;
    status.textContent = message;
    status.classList.toggle('is-error', !!isError);
    status.classList.toggle('is-ok', !isError);
  }
}

function bindStreamHub() {
  var form = document.getElementById('stream-embed-form');
  var input = document.getElementById('stream-embed-input');
  var status = document.getElementById('stream-embed-status');
  var screen = document.getElementById('stream-screen');
  var idle = document.getElementById('stream-idle');
  var chips = document.querySelectorAll('[data-stream-provider]');
  if (!form || !input || !screen) {
    return;
  }

  var provider = 'aparat';

  Array.prototype.forEach.call(chips, function (chip) {
    chip.addEventListener('click', function () {
      provider = chip.getAttribute('data-stream-provider') || 'aparat';
      Array.prototype.forEach.call(chips, function (item) {
        var active = item === chip;
        item.classList.toggle('is-active', active);
        item.setAttribute('aria-pressed', active ? 'true' : 'false');
      });
      input.placeholder =
        provider === 'youtube' ? 'لینک یا embed یوتیوب' : 'لینک یا embed آپارات';
    });
  });

  form.addEventListener('submit', function (event) {
    event.preventDefault();
    var embedUrl = resolveStreamUrl(provider, input.value);
    if (!embedUrl) {
      showHubStatus(status, 'لینک یا کد embed معتبر نیست.', true);
      mountStream(screen, idle, '');
      return;
    }
    if (/youtube\.com\/embed/i.test(embedUrl)) {
      setProvider('youtube');
    } else if (/aparat\.com/i.test(embedUrl)) {
      setProvider('aparat');
    }
    showHubStatus(status, '', false);
    mountStream(screen, idle, embedUrl);
  });

  function setProvider(next) {
    provider = next;
    Array.prototype.forEach.call(chips, function (item) {
      var active = (item.getAttribute('data-stream-provider') || '') === next;
      item.classList.toggle('is-active', active);
      item.setAttribute('aria-pressed', active ? 'true' : 'false');
    });
    input.placeholder =
      next === 'youtube' ? 'لینک یا embed یوتیوب' : 'لینک یا embed آپارات';
  }
}

function mountStream(screen, idle, url) {
  var current = screen.querySelector('iframe');
  if (current) {
    current.remove();
  }
  if (!url) {
    if (idle) {
      idle.hidden = false;
    }
    return;
  }
  if (idle) {
    idle.hidden = true;
  }
  var iframe = document.createElement('iframe');
  iframe.title = 'KILLBOX live stream';
  iframe.setAttribute('allowfullscreen', 'true');
  iframe.setAttribute(
    'allow',
    'accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; fullscreen'
  );
  iframe.referrerPolicy = 'origin';
  iframe.src = url;
  screen.appendChild(iframe);
}

function normalizeStreamInput(raw) {
  raw = stripBidi(raw);
  if (!raw) {
    return '';
  }
  var srcMatch = raw.match(/\bsrc\s*=\s*["']([^"']+)["']/i);
  if (srcMatch) {
    raw = stripBidi(srcMatch[1]);
  }
  var embeddedUrl = raw.match(/https?:\/\/[^\s"'<>]+/i);
  if (embeddedUrl && /youtube|youtu\.be|aparat/i.test(embeddedUrl[0])) {
    raw = embeddedUrl[0];
  }
  raw = raw.replace(/^\/\//, 'https://');
  if (!/^https?:\/\//i.test(raw) && /youtube|youtu\.be|aparat/i.test(raw)) {
    raw = 'https://' + raw.replace(/^\/+/, '');
  }
  return raw.replace(/[?&]amp;/g, '&').replace(/&amp;/g, '&');
}

function resolveStreamUrl(provider, raw) {
  raw = normalizeStreamInput(raw);
  if (!raw) {
    return '';
  }
  var youtubeish = looksLikeYouTube(raw);
  var aparatish = looksLikeAparat(raw);
  if (youtubeish && !aparatish) {
    return toYouTubeEmbed(raw);
  }
  if (aparatish && !youtubeish) {
    return extractAparatEmbed(raw);
  }
  if (provider === 'youtube') {
    return toYouTubeEmbed(raw) || extractAparatEmbed(raw);
  }
  return extractAparatEmbed(raw) || toYouTubeEmbed(raw);
}

function toYouTubeEmbed(raw) {
  var videoId = extractYouTubeId(raw);
  if (videoId) {
    return 'https://www.youtube.com/embed/' + videoId;
  }
  var channelLive = raw.match(
    /youtube(?:-nocookie)?\.com\/embed\/live_stream\?([^"'<\s]+)/i
  );
  if (channelLive) {
    return 'https://www.youtube.com/embed/live_stream?' + channelLive[1];
  }
  return '';
}

function extractYouTubeId(raw) {
  raw = stripBidi(raw);
  if (isYouTubeId(raw)) {
    return raw;
  }

  var patterns = [
    /(?:youtube(?:-nocookie)?\.com|m\.youtube\.com|music\.youtube\.com)\/live\/([a-zA-Z0-9_-]{11})/i,
    /(?:youtube(?:-nocookie)?\.com|m\.youtube\.com)\/embed\/([a-zA-Z0-9_-]{11})/i,
    /(?:youtube(?:-nocookie)?\.com|m\.youtube\.com)\/shorts\/([a-zA-Z0-9_-]{11})/i,
    /(?:youtube(?:-nocookie)?\.com|m\.youtube\.com)\/(?:v|e)\/([a-zA-Z0-9_-]{11})/i,
    /youtu\.be\/(?:live\/)?([a-zA-Z0-9_-]{11})/i,
    /[?&]v=([a-zA-Z0-9_-]{11})/i
  ];
  var i;
  for (i = 0; i < patterns.length; i += 1) {
    var fromPattern = raw.match(patterns[i]);
    if (fromPattern && isYouTubeId(fromPattern[1])) {
      return fromPattern[1];
    }
  }

  var url = parseLooseUrl(raw);
  if (!url || !isYouTubeHost(url.hostname)) {
    return '';
  }
  var fromQuery = url.searchParams.get('v');
  if (isYouTubeId(fromQuery)) {
    return fromQuery;
  }
  var parts = url.pathname.split('/').filter(Boolean);
  var host = normalizeHost(url.hostname);
  if (host === 'youtu.be') {
    if (parts[0] && parts[0].toLowerCase() === 'live' && isYouTubeId(parts[1])) {
      return parts[1];
    }
    if (isYouTubeId(parts[0])) {
      return parts[0];
    }
  }
  var markers = { live: 1, embed: 1, shorts: 1, v: 1, e: 1, watch: 1 };
  for (i = 0; i < parts.length; i += 1) {
    var key = String(parts[i] || '').toLowerCase();
    if (markers[key] && isYouTubeId(parts[i + 1])) {
      return parts[i + 1];
    }
  }
  var last = String(parts[parts.length - 1] || '').replace(/\.(html?)$/i, '');
  if (isYouTubeId(last) && last.toLowerCase() !== 'live_stream') {
    return last;
  }
  return '';
}

function extractAparatEmbed(raw) {
  raw = stripBidi(raw);
  if (/^[A-Za-z0-9]{4,64}$/.test(raw)) {
    return aparatVideoEmbed(raw);
  }

  var liveMatch = raw.match(/aparat\.com\/(?:embed\/)?live\/([A-Za-z0-9._-]+)/i);
  if (liveMatch) {
    return 'https://www.aparat.com/embed/live/' + liveMatch[1];
  }
  var hashMatch = raw.match(
    /aparat\.com\/(?:video\/video\/embed\/videohash\/|videos?\/videohash\/|videohash\/|embed\/(?!live\/)|v\/|video\/(?!video\/))([A-Za-z0-9]+)/i
  );
  if (hashMatch && !isAparatReserved(hashMatch[1])) {
    return aparatVideoEmbed(hashMatch[1]);
  }

  var url = parseLooseUrl(raw);
  if (!url || normalizeHost(url.hostname) !== 'aparat.com') {
    return '';
  }
  var parts = url.pathname.split('/').filter(Boolean);
  var index;
  for (index = 0; index < parts.length; index += 1) {
    var piece = String(parts[index] || '').toLowerCase();
    var next = parts[index + 1];
    if (piece === 'live' && next) {
      return 'https://www.aparat.com/embed/live/' + next;
    }
    if ((piece === 'v' || piece === 'videohash' || piece === 'embed') && isAparatHash(next)) {
      return aparatVideoEmbed(next);
    }
    if (piece === 'video' && isAparatHash(next)) {
      return aparatVideoEmbed(next);
    }
  }
  return '';
}

function aparatVideoEmbed(hash) {
  return 'https://www.aparat.com/video/video/embed/videohash/' + hash + '/vt/frame';
}

function isAparatHash(value) {
  return /^[A-Za-z0-9]{4,64}$/.test(value || '') && !isAparatReserved(value);
}

function isAparatReserved(value) {
  return /^(video|videos|embed|live|videohash|vt|frame|showvideo|playlist)$/i.test(
    value || ''
  );
}

function isYouTubeId(value) {
  return /^[a-zA-Z0-9_-]{11}$/.test(value || '');
}

function looksLikeYouTube(raw) {
  return /youtu\.be|youtube(?:-nocookie)?\.com/i.test(raw);
}

function looksLikeAparat(raw) {
  return /aparat\.com/i.test(raw);
}

function isYouTubeHost(host) {
  host = normalizeHost(host);
  return (
    host === 'youtube.com' ||
    host === 'm.youtube.com' ||
    host === 'music.youtube.com' ||
    host === 'youtu.be' ||
    host === 'youtube-nocookie.com'
  );
}

function isAllowedStreamHost(host) {
  host = normalizeHost(host);
  return isYouTubeHost(host) || host === 'aparat.com';
}

function normalizeHost(host) {
  return String(host || '')
    .toLowerCase()
    .replace(/^www\./, '');
}

function parseLooseUrl(raw) {
  try {
    return new URL(raw);
  } catch (error) {
    try {
      return new URL('https://' + String(raw || '').replace(/^\/\//, ''));
    } catch (retry) {
      return null;
    }
  }
}

function stripBidi(value) {
  return String(value || '')
    .replace(/[\u200B-\u200F\u202A-\u202E\u2066-\u2069]/g, '')
    .trim();
}

function bindDonateBox() {
  var form = document.getElementById('donate-form');
  var custom = document.getElementById('donate-custom');
  var message = document.getElementById('donate-message');
  var status = document.getElementById('donate-status');
  var chips = document.querySelectorAll('[data-donate-amount]');
  if (!form || !custom) {
    return;
  }

  var selected = 50000;

  Array.prototype.forEach.call(chips, function (chip) {
    chip.addEventListener('click', function () {
      selected = Number(chip.getAttribute('data-donate-amount')) || 0;
      custom.value = '';
      Array.prototype.forEach.call(chips, function (item) {
        var active = item === chip;
        item.classList.toggle('is-active', active);
        item.setAttribute('aria-pressed', active ? 'true' : 'false');
      });
    });
  });

  custom.addEventListener('input', function () {
    Array.prototype.forEach.call(chips, function (item) {
      item.classList.remove('is-active');
      item.setAttribute('aria-pressed', 'false');
    });
  });

  form.addEventListener('submit', function (event) {
    event.preventDefault();
    var amount = parseToman(custom.value) || selected;
    if (!amount || amount < 1000) {
      showHubStatus(status, 'مبلغ معتبر وارد کنید.', true);
      return;
    }
    var slogan = (message.value || '').trim();
    var copy = 'پرداخت آزمایشی ثبت شد: ' + formatToman(amount) + ' تومان';
    if (slogan) {
      copy += ' · ' + slogan;
    }
    showHubStatus(status, copy, false);
    var donor = document.getElementById('chat-input');
    pushDonation({
      name: (donor && donor.getAttribute('data-chat-user')) || 'Operator',
      amount: amount,
      note: slogan,
    });
  });
}

function bindLiveChat() {
  var log = document.getElementById('chat-log');
  var form = document.getElementById('chat-form');
  var input = document.getElementById('chat-input');
  if (!log || !form || !input) {
    return;
  }

  var seed = [
    { level: 38, name: 'ShaunL33T92', text: 'گلادیاتورها آماده‌ان. لابی ۵ را پر کنید.' },
    { level: 21, name: 'Ghost_IR', text: 'استعلام UID اوکی بود، وارد شدم.' },
    { level: 54, name: 'Navid.Sniper', text: 'دونیت برای تیم آلفا، هل بدهید.' },
    { level: 12, name: 'RookieTehran', text: 'کی استریم آپارات وصل می‌شه؟' },
  ];
  seed.forEach(function (item) {
    pushChat(item.level, item.name, item.text);
  });

  form.addEventListener('submit', function (event) {
    event.preventDefault();
    var text = (input.value || '').trim();
    if (!text) {
      return;
    }
    var name = input.getAttribute('data-chat-user') || 'Operator';
    pushChat(99, name, text);
    input.value = '';
    log.scrollTop = log.scrollHeight;
  });
}

var KillBoxHub = {
  unread: 0,
  chatOpen: false,
  donateOpen: false,
  donations: [],
};

function appendChat(log, level, name, text) {
  if (!log) {
    return;
  }
  var item = document.createElement('article');
  item.className = 'lab-chat__item';
  var meta = document.createElement('div');
  meta.className = 'lab-chat__meta';
  meta.textContent = '[Level ' + level + '] ' + name;
  var body = document.createElement('p');
  body.className = 'lab-chat__text';
  body.textContent = text;
  item.appendChild(meta);
  item.appendChild(body);
  log.appendChild(item);
  log.scrollTop = log.scrollHeight;
}

function pushChat(level, name, text) {
  appendChat(document.getElementById('chat-log'), level, name, text);
  appendChat(document.getElementById('hud-chat-log'), level, name, text);
  if (!KillBoxHub.chatOpen) {
    KillBoxHub.unread += 1;
  }
  updateHudBadges();
}

function pushDonation(entry) {
  KillBoxHub.donations.unshift(entry);
  renderDonateFeed();
  updateHudBadges();
}

function updateHudBadges() {
  var chatBadge = document.getElementById('hud-chat-badge');
  if (chatBadge) {
    if (KillBoxHub.unread > 0) {
      chatBadge.hidden = false;
      chatBadge.textContent = KillBoxHub.unread > 99 ? '99+' : String(KillBoxHub.unread);
    } else {
      chatBadge.hidden = true;
      chatBadge.textContent = '';
    }
  }
  var donateBadge = document.getElementById('hud-donate-badge');
  var latest = KillBoxHub.donations[0];
  if (donateBadge) {
    if (latest) {
      donateBadge.hidden = false;
      donateBadge.textContent = compactToman(latest.amount);
    } else {
      donateBadge.hidden = true;
      donateBadge.textContent = '';
    }
  }
}

function compactToman(amount) {
  if (amount >= 1000) {
    return formatToman(Math.round(amount / 1000)) + 'هزار';
  }
  return formatToman(amount);
}

function renderDonateFeed() {
  var list = document.getElementById('hud-donate-list');
  if (!list) {
    return;
  }
  list.textContent = '';
  if (!KillBoxHub.donations.length) {
    var empty = document.createElement('p');
    empty.className = 'lab-hud__empty';
    empty.textContent = 'هنوز دونیتی ثبت نشده.';
    list.appendChild(empty);
    return;
  }
  KillBoxHub.donations.forEach(function (gift) {
    var row = document.createElement('article');
    row.className = 'lab-hud__gift';
    var amount = document.createElement('div');
    amount.className = 'lab-hud__gift-amount';
    amount.textContent = formatToman(gift.amount) + ' تومان';
    var who = document.createElement('div');
    who.className = 'lab-hud__gift-name';
    who.textContent = gift.name;
    row.appendChild(amount);
    row.appendChild(who);
    if (gift.note) {
      var note = document.createElement('div');
      note.className = 'lab-hud__gift-note';
      note.textContent = gift.note;
      row.appendChild(note);
    }
    list.appendChild(row);
  });
}

function bindStreamHud() {
  var stage = document.getElementById('stream-stage');
  var fsBtn = document.getElementById('stream-fs-btn');
  var chatBtn = document.getElementById('hud-chat-btn');
  var donateBtn = document.getElementById('hud-donate-btn');
  var chatPanel = document.getElementById('hud-chat-panel');
  var donatePanel = document.getElementById('hud-donate-panel');
  if (!stage || !fsBtn) {
    return;
  }

  fsBtn.addEventListener('click', function () {
    if (stage.classList.contains('is-fs')) {
      exitStreamFs(stage, fsBtn);
      return;
    }
    enterStreamFs(stage, fsBtn);
  });

  document.addEventListener('keydown', function (event) {
    if (event.key === 'Escape' && stage.classList.contains('is-fs')) {
      exitStreamFs(stage, fsBtn);
    }
  });

  document.addEventListener('fullscreenchange', function () {
    if (!document.fullscreenElement && stage.classList.contains('is-fs')) {
      exitStreamFs(stage, fsBtn, true);
    }
  });

  if (chatBtn && chatPanel) {
    chatBtn.addEventListener('click', function () {
      setHudPanel('chat', chatPanel.hidden);
    });
  }
  if (donateBtn && donatePanel) {
    donateBtn.addEventListener('click', function () {
      setHudPanel('donate', donatePanel.hidden);
    });
  }

  Array.prototype.forEach.call(document.querySelectorAll('[data-hud-collapse]'), function (btn) {
    btn.addEventListener('click', function () {
      setHudPanel(btn.getAttribute('data-hud-collapse'), false);
    });
  });

  pushDonation({
    name: 'Navid.Sniper',
    amount: 50000,
    note: 'برای تیم آلفا',
  });
}

function setHudPanel(which, open) {
  var chatPanel = document.getElementById('hud-chat-panel');
  var donatePanel = document.getElementById('hud-donate-panel');
  var chatBtn = document.getElementById('hud-chat-btn');
  var donateBtn = document.getElementById('hud-donate-btn');
  if (which === 'chat' && chatPanel) {
    chatPanel.hidden = !open;
    KillBoxHub.chatOpen = !!open;
    if (chatBtn) {
      chatBtn.setAttribute('aria-expanded', open ? 'true' : 'false');
    }
    if (open) {
      KillBoxHub.unread = 0;
      updateHudBadges();
      var log = document.getElementById('hud-chat-log');
      if (log) {
        log.scrollTop = log.scrollHeight;
      }
    }
  }
  if (which === 'donate' && donatePanel) {
    donatePanel.hidden = !open;
    KillBoxHub.donateOpen = !!open;
    if (donateBtn) {
      donateBtn.setAttribute('aria-expanded', open ? 'true' : 'false');
    }
  }
}

var streamFsHome = null;

function enterStreamFs(stage, fsBtn) {
  if (!streamFsHome) {
    streamFsHome = { parent: stage.parentNode, next: stage.nextSibling };
    document.body.appendChild(stage);
  }
  stage.classList.add('is-fs');
  document.body.classList.add('is-stream-fs');
  fsBtn.setAttribute('aria-pressed', 'true');
  fsBtn.title = 'خروج از تمام‌صفحه';
  if (stage.requestFullscreen) {
    var request = stage.requestFullscreen();
    if (request && request.catch) {
      request.catch(function () {
        /* theater fallback remains */
      });
    }
  }
}

function exitStreamFs(stage, fsBtn, fromEvent) {
  stage.classList.remove('is-fs');
  document.body.classList.remove('is-stream-fs');
  fsBtn.setAttribute('aria-pressed', 'false');
  fsBtn.title = 'تمام‌صفحه';
  setHudPanel('chat', false);
  setHudPanel('donate', false);
  if (streamFsHome && streamFsHome.parent) {
    if (streamFsHome.next && streamFsHome.next.parentNode === streamFsHome.parent) {
      streamFsHome.parent.insertBefore(stage, streamFsHome.next);
    } else {
      streamFsHome.parent.appendChild(stage);
    }
  }
  streamFsHome = null;
  if (!fromEvent && document.fullscreenElement && document.exitFullscreen) {
    document.exitFullscreen().catch(function () {
      /* ignore */
    });
  }
}

function showHubStatus(node, message, isError) {
  if (!node) {
    return;
  }
  if (!message) {
    node.hidden = true;
    node.textContent = '';
    node.classList.remove('is-error');
    return;
  }
  node.hidden = false;
  node.textContent = message;
  node.classList.toggle('is-error', !!isError);
}

function bindEventFrame() {
  bindFrameCard('event', {
    storageKey: 'killbox-lab-event-frame',
    waitingLabel: 'در حال عضو گیری',
    liveLabel: 'در حال برگزاری',
    extras: true,
    dateIncludesTime: true,
  });
}

function bindLiveFrame() {
  bindFrameCard('live', {
    storageKey: 'killbox-lab-live-frame',
    waitingLabel: 'در انتظار پخش',
    liveLabel: 'در حال پخش زنده',
    extras: false,
    dateIncludesTime: false,
  });
}

function bindFrameCard(prefix, options) {
  options = options || {};
  var form = document.getElementById(prefix + '-frame-form');
  var card = document.getElementById(prefix + '-card');
  var frameImg = document.getElementById(prefix + '-card-frame');
  var charImg = document.getElementById(prefix + '-card-char');
  var charStack = document.getElementById(prefix + '-char-stack');
  var nameInput = document.getElementById(prefix + '-name');
  var dateInput = document.getElementById(prefix + '-date');
  var yearSelect = document.getElementById(prefix + '-j-year');
  var monthSelect = document.getElementById(prefix + '-j-month');
  var daySelect = document.getElementById(prefix + '-j-day');
  var timeInput = document.getElementById(prefix + '-time');
  var capInput = document.getElementById(prefix + '-capacity');
  var prizeInput = document.getElementById(prefix + '-prize');
  var feeInput = document.getElementById(prefix + '-fee');
  var nameView = document.getElementById(prefix + '-view-name');
  var dateView = document.getElementById(prefix + '-view-date');
  var timeView = document.getElementById(prefix + '-view-time');
  var capView = document.getElementById(prefix + '-view-capacity');
  var prizeView = document.getElementById(prefix + '-view-prize');
  var feeView = document.getElementById(prefix + '-view-fee-text');
  var statusLabel = document.getElementById(prefix + '-view-status-label');
  var timerView = document.getElementById(prefix + '-view-timer-text');
  var framePicks = form ? form.querySelectorAll('.event-lab__pick[data-frame]') : [];
  var charPicks = form ? form.querySelectorAll('.event-lab__pick[data-char]') : [];
  if (!form || !card || !frameImg) {
    return;
  }

  var stored = null;
  try {
    stored = JSON.parse(window.localStorage.getItem(options.storageKey) || 'null');
  } catch (error) {
    stored = null;
  }
  if (stored && typeof stored === 'object') {
    if (stored.name && nameInput) {
      nameInput.value = stored.name;
    }
    if (stored.time && timeInput) {
      timeInput.value = stored.time;
    }
    if (stored.capacity != null && capInput) {
      capInput.value = String(stored.capacity);
    }
    if (stored.prize != null && prizeInput) {
      prizeInput.value = String(stored.prize);
    }
    if (stored.fee != null && feeInput) {
      feeInput.value = String(stored.fee);
    }
    if (stored.frame) {
      applyChoice(framePicks, 'data-frame', String(stored.frame), frameImg, 'data-frame');
    }
    if (stored.char) {
      applyChoice(charPicks, 'data-char', String(stored.char), charImg, 'data-char');
    }
  }
  if (timeInput && !timeInput.value) {
    timeInput.value = '18:00';
  }
  initJalaliDate((stored && stored.date) || defaultEventDate());
  if (charImg) {
    charImg.addEventListener('load', syncCharMask);
  }

  Array.prototype.forEach.call(framePicks, function (pick) {
    pick.addEventListener('click', function () {
      applyChoice(framePicks, 'data-frame', pick.getAttribute('data-frame'), frameImg, 'data-frame');
      render();
    });
  });
  Array.prototype.forEach.call(charPicks, function (pick) {
    pick.addEventListener('click', function () {
      applyChoice(charPicks, 'data-char', pick.getAttribute('data-char'), charImg, 'data-char');
      render();
    });
  });
  if (yearSelect) {
    yearSelect.addEventListener('change', onJalaliMonthYearChange);
  }
  if (monthSelect) {
    monthSelect.addEventListener('change', onJalaliMonthYearChange);
  }
  if (daySelect) {
    daySelect.addEventListener('change', onJalaliDayChange);
  }
  form.addEventListener('input', render);
  form.addEventListener('change', render);
  if (feeView) {
    var feeBtn = document.getElementById('event-view-fee');
    if (feeBtn) {
      feeBtn.addEventListener('click', function () {
        /* payment gateway will hook here */
      });
    }
  }
  render();
  window.setInterval(tickTimer, 1000);

  function initJalaliDate(iso) {
    var gregorian = parseIsoDate(iso) || parseIsoDate(defaultEventDate());
    var jalali = gregorianToJalali(gregorian[0], gregorian[1], gregorian[2]);
    fillJalaliSelects(jalali[0], jalali[1], jalali[2]);
    writeGregorianDate();
  }

  function onJalaliMonthYearChange() {
    var year = Number(yearSelect && yearSelect.value);
    var month = Number(monthSelect && monthSelect.value);
    var day = Number(daySelect && daySelect.value);
    fillJalaliDays(year, month, day);
    writeGregorianDate();
    render();
  }

  function onJalaliDayChange() {
    writeGregorianDate();
    render();
  }

  function fillJalaliSelects(year, month, day) {
    if (!yearSelect || !monthSelect || !daySelect) {
      return;
    }
    var today = new Date();
    var nowJalali = gregorianToJalali(today.getFullYear(), today.getMonth() + 1, today.getDate());
    yearSelect.innerHTML = '';
    for (var y = nowJalali[0] - 1; y <= nowJalali[0] + 3; y++) {
      yearSelect.appendChild(jalaliOption(y, toFaDigits(y), y === year));
    }
    monthSelect.innerHTML = '';
    for (var m = 1; m <= 12; m++) {
      monthSelect.appendChild(jalaliOption(m, JALALI_MONTHS[m - 1], m === month));
    }
    fillJalaliDays(year, month, day);
  }

  function fillJalaliDays(year, month, selectedDay) {
    if (!daySelect) {
      return;
    }
    var days = jalaliMonthLength(year, month);
    var keep = Math.min(Math.max(1, selectedDay || 1), days);
    daySelect.innerHTML = '';
    for (var d = 1; d <= days; d++) {
      daySelect.appendChild(jalaliOption(d, toFaDigits(d), d === keep));
    }
  }

  function jalaliOption(value, label, selected) {
    var option = document.createElement('option');
    option.value = String(value);
    option.textContent = label;
    option.selected = !!selected;
    return option;
  }

  function writeGregorianDate() {
    if (!dateInput || !yearSelect || !monthSelect || !daySelect) {
      return;
    }
    var g = jalaliToGregorian(
      Number(yearSelect.value),
      Number(monthSelect.value),
      Number(daySelect.value)
    );
    dateInput.value = g[0] + '-' + padIso(g[1]) + '-' + padIso(g[2]);
  }

  function applyChoice(buttons, attr, id, image, cardAttr) {
    var pick = null;
    Array.prototype.forEach.call(buttons, function (button) {
      var on = button.getAttribute(attr) === String(id);
      button.classList.toggle('is-active', on);
      button.setAttribute('aria-pressed', on ? 'true' : 'false');
      if (on) {
        pick = button;
      }
    });
    if (!pick) {
      return;
    }
    card.setAttribute(cardAttr, pick.getAttribute(attr) || '1');
    if (image) {
      image.src = pick.getAttribute('data-src') || image.src;
    }
    if (attr === 'data-char') {
      syncCharMask();
    }
  }

  function syncCharMask() {
    if (!charStack || !charImg) {
      return;
    }
    charStack.style.setProperty('--event-char-mask', 'url("' + charImg.src + '")');
  }

  function render() {
    var name = ((nameInput && nameInput.value) || '').trim() || 'بدون نام';
    var capacity = Math.max(0, parseInt(String((capInput && capInput.value) || '0'), 10) || 0);
    var registered = Math.max(0, parseInt(card.getAttribute('data-registered') || '0', 10) || 0);
    var remaining = Math.max(0, capacity - registered);
    if (nameView) {
      nameView.textContent = name;
    }
    if (dateView) {
      dateView.textContent = formatEventDate(
        dateInput && dateInput.value,
        timeInput && timeInput.value,
        !options.dateIncludesTime
      );
    }
    if (timeView) {
      timeView.textContent = formatEventTime(timeInput && timeInput.value);
    }
    if (capView) {
      capView.textContent = formatToman(remaining) + '/' + formatToman(registered);
    }
    if (prizeView) {
      prizeView.textContent = 'جایزه ' + formatMoneyLabel((prizeInput && prizeInput.value) || '');
    }
    if (feeView) {
      feeView.textContent = formatMoneyLabel((feeInput && feeInput.value) || '');
    }
    syncCharMask();
    tickTimer();
    try {
      window.localStorage.setItem(
        options.storageKey,
        JSON.stringify({
          frame: card.getAttribute('data-frame') || '1',
          char: card.getAttribute('data-char') || '1',
          name: (nameInput && nameInput.value) || '',
          date: (dateInput && dateInput.value) || '',
          time: (timeInput && timeInput.value) || '',
          capacity: capacity,
          prize: (prizeInput && prizeInput.value) || '',
          fee: (feeInput && feeInput.value) || '',
        })
      );
    } catch (error) {
      /* ignore quota / private mode */
    }
  }

  function eventStartMs() {
    var dateValue = dateInput && dateInput.value;
    if (!dateValue) {
      return 0;
    }
    var parts = String(dateValue).split('-');
    if (parts.length !== 3) {
      return 0;
    }
    var clock = String((timeInput && timeInput.value) || '00:00').split(':');
    var hours = Number(clock[0] || 0);
    var minutes = Number(clock[1] || 0);
    var stamp = new Date(
      Number(parts[0]),
      Number(parts[1]) - 1,
      Number(parts[2]),
      hours,
      minutes,
      0
    );
    return stamp.getTime();
  }

  function tickTimer() {
    var start = eventStartMs();
    var remain = start ? start - Date.now() : 0;
    var live = !start || remain <= 0;
    card.classList.toggle('is-live', live);
    if (statusLabel) {
      statusLabel.textContent = live ? options.liveLabel : options.waitingLabel;
    }
    if (timerView) {
      timerView.textContent = formatCountdown(live ? 0 : remain);
    }
  }

  function formatCountdown(ms) {
    var total = Math.max(0, Math.floor(ms / 1000));
    var seconds = total % 60;
    var minutes = Math.floor(total / 60) % 60;
    var hours = Math.floor(total / 3600) % 24;
    var days = Math.floor(total / 86400);
    var clock = padFa(hours) + ':' + padFa(minutes) + ':' + padFa(seconds);
    if (days > 0) {
      return padFa(days) + ':' + clock;
    }
    return clock;
  }

  function padFa(value) {
    return toFaDigits(String(value).padStart(2, '0'));
  }

  function toFaDigits(value) {
    return String(value).replace(/\d/g, function (digit) {
      return '۰۱۲۳۴۵۶۷۸۹'[digit];
    });
  }

  function defaultEventDate() {
    var next = new Date();
    next.setDate(next.getDate() + 7);
    var month = String(next.getMonth() + 1).padStart(2, '0');
    var day = String(next.getDate()).padStart(2, '0');
    return next.getFullYear() + '-' + month + '-' + day;
  }

  function formatEventDate(value, timeValue, dateOnly) {
    if (!value) {
      return 'تاریخ تعیین نشده';
    }
    var parts = String(value).split('-');
    if (parts.length !== 3) {
      return String(value);
    }
    var clock = String(timeValue || '00:00').split(':');
    var stamp = new Date(
      Number(parts[0]),
      Number(parts[1]) - 1,
      Number(parts[2]),
      Number(clock[0] || 0),
      Number(clock[1] || 0)
    );
    if (isNaN(stamp.getTime())) {
      return String(value);
    }
    var opts = {
      year: 'numeric',
      month: 'long',
      day: 'numeric',
    };
    if (!dateOnly) {
      opts.hour = '2-digit';
      opts.minute = '2-digit';
    }
    try {
      return stamp.toLocaleString('fa-IR', opts);
    } catch (error) {
      return String(value);
    }
  }

  function formatEventTime(timeValue) {
    if (!timeValue) {
      return 'ساعت تعیین نشده';
    }
    var clock = String(timeValue).split(':');
    return padFa(Number(clock[0] || 0)) + ':' + padFa(Number(clock[1] || 0));
  }

  function formatMoneyLabel(raw) {
    var text = String(raw || '').trim() || '—';
    var digits = text.replace(/[۰-۹]/g, function (digit) {
      return String('۰۱۲۳۴۵۶۷۸۹'.indexOf(digit));
    });
    if (/^\d+$/.test(digits.replace(/[^\d]/g, '')) && !/[^\d۰-۹,\s]/.test(text)) {
      var amount = parseToman(text);
      if (amount) {
        return formatToman(amount) + ' تومان';
      }
    }
    return text;
  }
}

var JALALI_MONTHS = [
  'فروردین',
  'اردیبهشت',
  'خرداد',
  'تیر',
  'مرداد',
  'شهریور',
  'مهر',
  'آبان',
  'آذر',
  'دی',
  'بهمن',
  'اسفند',
];

function padIso(value) {
  return String(value).padStart(2, '0');
}

function parseIsoDate(value) {
  var parts = String(value || '').split('-');
  if (parts.length !== 3) {
    return null;
  }
  var year = Number(parts[0]);
  var month = Number(parts[1]);
  var day = Number(parts[2]);
  if (!year || !month || !day) {
    return null;
  }
  return [year, month, day];
}

function jalaliMonthLength(year, month) {
  if (month <= 6) {
    return 31;
  }
  if (month <= 11) {
    return 30;
  }
  var probe = jalaliToGregorian(year, 12, 30);
  var back = gregorianToJalali(probe[0], probe[1], probe[2]);
  return back[0] === year && back[1] === 12 && back[2] === 30 ? 30 : 29;
}

function gregorianToJalali(gy, gm, gd) {
  var g_d_m = [0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334];
  var gy2 = gm > 2 ? gy + 1 : gy;
  var days =
    355666 +
    365 * gy +
    Math.floor((gy2 + 3) / 4) -
    Math.floor((gy2 + 99) / 100) +
    Math.floor((gy2 + 399) / 400) +
    gd +
    g_d_m[gm - 1];
  var jy = -1595 + 33 * Math.floor(days / 12053);
  days %= 12053;
  jy += 4 * Math.floor(days / 1461);
  days %= 1461;
  if (days > 365) {
    jy += Math.floor((days - 1) / 365);
    days = (days - 1) % 365;
  }
  var jm;
  var jd;
  if (days < 186) {
    jm = 1 + Math.floor(days / 31);
    jd = 1 + (days % 31);
  } else {
    jm = 7 + Math.floor((days - 186) / 30);
    jd = 1 + ((days - 186) % 30);
  }
  return [jy, jm, jd];
}

function jalaliToGregorian(jy, jm, jd) {
  jy += 1595;
  var days =
    -355668 +
    365 * jy +
    Math.floor(jy / 33) * 8 +
    Math.floor(((jy % 33) + 3) / 4) +
    jd +
    (jm < 7 ? (jm - 1) * 31 : (jm - 7) * 30 + 186);
  var gy = 400 * Math.floor(days / 146097);
  days %= 146097;
  if (days > 36524) {
    gy += 100 * Math.floor(--days / 36524);
    days %= 36524;
    if (days >= 365) {
      days += 1;
    }
  }
  gy += 4 * Math.floor(days / 1461);
  days %= 1461;
  if (days > 365) {
    gy += Math.floor((days - 1) / 365);
    days = (days - 1) % 365;
  }
  var gd = days + 1;
  var leap = (gy % 4 === 0 && gy % 100 !== 0) || gy % 400 === 0;
  var sal = [0, 31, leap ? 29 : 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31];
  var gm = 1;
  while (gm < 13 && gd > sal[gm]) {
    gd -= sal[gm];
    gm += 1;
  }
  return [gy, gm, gd];
}

function parseToman(value) {
  var normalized = String(value || '')
    .replace(/[۰-۹]/g, function (digit) {
      return String('۰۱۲۳۴۵۶۷۸۹'.indexOf(digit));
    })
    .replace(/[^\d]/g, '');
  if (!normalized) {
    return 0;
  }
  return Number(normalized);
}

function formatToman(amount) {
  try {
    return Number(amount).toLocaleString('fa-IR');
  } catch (error) {
    return String(amount);
  }
}
