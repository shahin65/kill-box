function bindLivePage() {
  if (!document.querySelector('.event-card, [data-live-room], [data-event-start]')) {
    if (window.__kbEventTick) {
      window.clearInterval(window.__kbEventTick);
      window.__kbEventTick = null;
    }
    return;
  }
  bindEventCards();
  bindLiveRoom();
}

window.__kbBindLive = bindLivePage;

function bindEventCards() {
  document.querySelectorAll('.event-card').forEach(function (card) {
    var img = card.querySelector('.event-card__char');
    var stack = card.querySelector('.event-card__char-stack');
    if (img && stack) {
      stack.style.setProperty('--event-char-mask', 'url("' + img.src + '")');
    }
  });
  tickEventCards();
  if (!window.__kbEventTick) {
    window.__kbEventTick = window.setInterval(tickEventCards, 1000);
  }
}

function tickEventCards() {
  var digits = '۰۱۲۳۴۵۶۷۸۹';
  document.querySelectorAll('[data-event-start]').forEach(function (card) {
    var stamp = Date.parse(card.getAttribute('data-event-start') || '');
    var remain = stamp ? stamp - Date.now() : 0;
    var live = !stamp || remain <= 0;
    card.classList.toggle('is-live', live);
    var status = card.querySelector('[data-event-status]');
    if (status) {
      status.textContent = live
        ? card.getAttribute('data-live-status') || 'زنده'
        : card.getAttribute('data-wait-status') || 'در انتظار';
    }
    var timer = card.querySelector('[data-event-timer]');
    if (!timer) {
      return;
    }
    var total = Math.max(0, Math.floor((live ? 0 : remain) / 1000));
    var clock =
      String(Math.floor(total / 3600) % 24).padStart(2, '0') +
      ':' +
      String(Math.floor(total / 60) % 60).padStart(2, '0') +
      ':' +
      String(total % 60).padStart(2, '0');
    timer.textContent = clock.replace(/\d/g, function (d) {
      return digits[d];
    });
  });
}

function bindLiveRoom() {
  var root = document.querySelector('[data-live-room]');
  if (!root || root.getAttribute('data-kb-bound')) {
    return;
  }
  root.setAttribute('data-kb-bound', '1');
  mountLiveStream();
  var slug = root.getAttribute('data-live-room');
  var log = document.getElementById('live-chat-log');
  var chatForm = document.getElementById('live-chat-form');
  var chatInput = document.getElementById('live-chat-input');
  var donateForm = document.getElementById('live-donate-form');
  var custom = document.getElementById('live-donate-custom');
  var note = document.getElementById('live-donate-note');
  var status = document.getElementById('live-donate-status');
  var chips = root.querySelectorAll('[data-donate-amount]');
  var selected = 50000;
  var csrf = (document.querySelector('[name=csrfmiddlewaretoken]') || {}).value || '';

  function paint(messages) {
    if (!log) {
      return;
    }
    log.innerHTML = (messages || [])
      .map(function (row) {
        return (
          '<article class="kb-live__item' +
          (row.donate ? ' is-donate' : '') +
          '"><strong>' +
          escapeLive(row.name) +
          '</strong><p>' +
          escapeLive(row.text) +
          '</p></article>'
        );
      })
      .join('');
    log.scrollTop = log.scrollHeight;
  }

  function post(url, data) {
    return fetch(url, {
      method: 'POST',
      headers: {
        'X-CSRFToken': csrf,
        'Content-Type': 'application/x-www-form-urlencoded',
      },
      body: new URLSearchParams(data || {}),
    }).then(function (response) {
      return response.json();
    });
  }

  Array.prototype.forEach.call(chips, function (chip) {
    chip.addEventListener('click', function () {
      selected = Number(chip.getAttribute('data-donate-amount')) || 0;
      if (custom) {
        custom.value = '';
      }
      Array.prototype.forEach.call(chips, function (item) {
        var on = item === chip;
        item.classList.toggle('is-active', on);
        item.setAttribute('aria-pressed', on ? 'true' : 'false');
      });
    });
  });
  if (custom) {
    custom.addEventListener('input', function () {
      Array.prototype.forEach.call(chips, function (item) {
        item.classList.remove('is-active');
        item.setAttribute('aria-pressed', 'false');
      });
    });
  }
  if (chatForm && chatInput) {
    chatForm.addEventListener('submit', function (event) {
      event.preventDefault();
      var text = chatInput.value.trim();
      if (!text) {
        return;
      }
      post('/live/' + slug + '/chat/', { text: text }).then(function (payload) {
        if (payload.success) {
          chatInput.value = '';
          paint(payload.messages);
        }
      });
    });
  }
  if (donateForm) {
    donateForm.addEventListener('submit', function (event) {
      event.preventDefault();
      var amount = parseInt(String((custom && custom.value) || '').replace(/[^\d]/g, ''), 10) || selected;
      post('/live/' + slug + '/donate/', {
        amount: String(amount),
        message: (note && note.value) || '',
      }).then(function (payload) {
        if (status) {
          status.hidden = false;
          status.textContent = payload.message || '';
          status.classList.toggle('is-error', !payload.success);
        }
        if (payload.success) {
          paint(payload.messages);
          if (note) {
            note.value = '';
          }
        }
      });
    });
  }
  window.setInterval(function () {
    if (!document.querySelector('[data-live-room="' + slug + '"]')) {
      return;
    }
    fetch('/live/' + slug + '/feed/')
      .then(function (response) {
        return response.json();
      })
      .then(function (payload) {
        if (payload.success) {
          paint(payload.messages);
        }
      })
      .catch(function () {});
  }, 6000);
}

function mountLiveStream() {
  var screen = document.getElementById('live-screen');
  var idle = document.getElementById('live-idle');
  if (!screen) {
    return;
  }
  var url = resolvePublicStream(screen.getAttribute('data-stream-url') || '');
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
  iframe.setAttribute('referrerpolicy', 'strict-origin-when-cross-origin');
  iframe.src = url;
  screen.appendChild(iframe);
}

function resolvePublicStream(raw) {
  raw = String(raw || '').trim();
  if (!raw) {
    return '';
  }
  var src = raw.match(/src\s*=\s*["']([^"']+)/i);
  if (src) {
    raw = src[1];
  }
  raw = raw.replace(/^\/\//, 'https://');
  if (!/^https?:\/\//i.test(raw) && /youtube|youtu\.be|aparat/i.test(raw)) {
    raw = 'https://' + raw.replace(/^\/+/, '');
  }
  var yt = extractYouTubeId(raw);
  if (yt) {
    return 'https://www.youtube.com/embed/' + yt;
  }
  var live = raw.match(/aparat\.com\/(?:embed\/)?live\/([A-Za-z0-9._-]+)/i);
  if (live) {
    return 'https://www.aparat.com/embed/live/' + live[1];
  }
  var ap = raw.match(/aparat\.com\/(?:embed\/|v\/|video\/)?([A-Za-z0-9]+)/i);
  if (ap && !/aparat\.com\/?$/i.test(raw)) {
    return 'https://www.aparat.com/video/video/embed/videohash/' + ap[1] + '/vt/frame';
  }
  if (/^https?:\/\/www\.youtube\.com\/embed\//i.test(raw) || /^https?:\/\/www\.aparat\.com\//i.test(raw)) {
    return raw;
  }
  return '';
}

function extractYouTubeId(raw) {
  var patterns = [
    /(?:youtube(?:-nocookie)?\.com|m\.youtube\.com)\/live\/([a-zA-Z0-9_-]{11})/i,
    /(?:youtube(?:-nocookie)?\.com|m\.youtube\.com)\/embed\/([a-zA-Z0-9_-]{11})/i,
    /(?:youtube(?:-nocookie)?\.com|m\.youtube\.com)\/shorts\/([a-zA-Z0-9_-]{11})/i,
    /(?:youtube(?:-nocookie)?\.com|m\.youtube\.com)\/(?:v|e)\/([a-zA-Z0-9_-]{11})/i,
    /youtu\.be\/(?:live\/)?([a-zA-Z0-9_-]{11})/i,
    /[?&]v=([a-zA-Z0-9_-]{11})/i,
  ];
  var i;
  for (i = 0; i < patterns.length; i += 1) {
    var match = raw.match(patterns[i]);
    if (match && /^[a-zA-Z0-9_-]{11}$/.test(match[1])) {
      return match[1];
    }
  }
  return '';
}

function escapeLive(value) {
  return String(value || '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

document.addEventListener('DOMContentLoaded', bindLivePage);
