(function () {
  var chatTimer = null;
  var presenceTimer = null;

  function csrfToken() {
    var node = document.querySelector('[name=csrfmiddlewaretoken]');
    return node ? node.value : '';
  }

  function post(url, data) {
    var body = data instanceof FormData ? data : new URLSearchParams(data || {});
    var headers = {
      'X-CSRFToken': csrfToken(),
      'X-Requested-With': 'XMLHttpRequest',
      Accept: 'application/json',
    };
    if (!(data instanceof FormData)) {
      headers['Content-Type'] = 'application/x-www-form-urlencoded';
    }
    return fetch(url, {
      method: 'POST',
      headers: headers,
      body: body,
      credentials: 'same-origin',
    }).then(function (response) {
      return response.json().catch(function () {
        return { success: false, message: 'پاسخ نامعتبر بود.', status: response.status };
      });
    });
  }

  function getJson(url) {
    return fetch(url, {
      headers: { Accept: 'application/json', 'X-Requested-With': 'XMLHttpRequest' },
      credentials: 'same-origin',
    }).then(function (response) {
      return response.json();
    });
  }

  function flash(message) {
    if (typeof window.__kbFlashSocial === 'function') {
      window.__kbFlashSocial(message);
      return;
    }
    window.alert(message);
  }

  function escapeHtml(value) {
    return String(value || '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  function renderCard(card) {
    return (
      '<a class="kb-alliance-card feed-card" href="/alliance/' +
      encodeURIComponent(card.slug) +
      '/" data-kb-nav>' +
      '<div class="kb-alliance-card__art"' +
      (card.banner_url ? ' style="background-image:url(\'' + escapeHtml(card.banner_url) + '\')"' : '') +
      '>' +
      (card.logo_url
        ? '<img class="kb-alliance-card__logo" src="' + escapeHtml(card.logo_url) + '" alt="" width="72" height="72">'
        : '') +
      '</div><div class="kb-alliance-card__body"><strong>' +
      escapeHtml(card.name) +
      '</strong><p>' +
      escapeHtml(card.description || 'بدون توضیحات') +
      '</p><small>' +
      escapeHtml(String(card.member_count || 0)) +
      ' / ' +
      escapeHtml(String(card.max_members || 50)) +
      ' عضو · ' +
      escapeHtml(card.join_policy_label || '') +
      '</small></div></a>'
    );
  }

  function bindSearch() {
    var box = document.querySelector('[data-alliance-search]');
    if (!box) {
      return;
    }
    var input = box.querySelector('input[type="search"]');
    var results = box.querySelector('[data-alliance-results]');
    var url = box.getAttribute('data-alliance-search');
    if (!input || !results || !url) {
      return;
    }
    var timer = null;
    input.addEventListener('input', function () {
      clearTimeout(timer);
      timer = setTimeout(function () {
        getJson(url + '?q=' + encodeURIComponent(input.value.trim())).then(function (payload) {
          if (!payload.success) {
            return;
          }
          var rows = payload.results || [];
          results.innerHTML = rows.length
            ? rows.map(renderCard).join('')
            : '<p class="profile-copy">اتحادی پیدا نشد.</p>';
        });
      }, 220);
    });
  }

  function bindActions() {
    document.querySelectorAll('[data-alliance-action]').forEach(function (form) {
      if (form.getAttribute('data-alliance-bound') === '1') {
        return;
      }
      form.setAttribute('data-alliance-bound', '1');
      form.addEventListener('submit', function (event) {
        event.preventDefault();
        post(form.getAttribute('action'), new FormData(form)).then(function (payload) {
          if (payload.status === 401 && typeof window.__kbPromptAuth === 'function') {
            window.__kbPromptAuth();
            return;
          }
          if (!payload.success) {
            flash(payload.message || 'انجام نشد.');
            return;
          }
          if (payload.href && window.__kbGo) {
            window.__kbGo(payload.href);
            return;
          }
          if (window.__kbSoftReload) {
            window.__kbSoftReload();
          } else {
            window.location.reload();
          }
        });
      });
    });
  }

  function paintMessage(log, row) {
    if (!row || log.querySelector('[data-msg-id="' + row.id + '"]')) {
      return;
    }
    var empty = log.querySelector('[data-alliance-empty]');
    if (empty) {
      empty.remove();
    }
    var item = document.createElement('article');
    item.className = 'kb-alliance-chat__item';
    item.setAttribute('data-msg-id', String(row.id));
    item.innerHTML =
      '<strong>' +
      escapeHtml(row.name) +
      '</strong>' +
      (row.text ? '<p>' + escapeHtml(row.text) + '</p>' : '') +
      (row.image_url ? '<img src="' + escapeHtml(row.image_url) + '" alt="">' : '');
    log.appendChild(item);
    log.scrollTop = log.scrollHeight;
  }

  function lastId(log) {
    var nodes = log.querySelectorAll('[data-msg-id]');
    if (!nodes.length) {
      return 0;
    }
    return Number(nodes[nodes.length - 1].getAttribute('data-msg-id') || 0);
  }

  function bindChat() {
    var box = document.querySelector('[data-alliance-chat]');
    if (!box) {
      return;
    }
    var log = document.getElementById('alliance-chat-log');
    var form = document.getElementById('alliance-chat-form');
    var online = box.querySelector('[data-alliance-online]');
    var messagesUrl = box.getAttribute('data-messages-url');
    var presenceUrl = box.getAttribute('data-presence-url');
    function tick() {
      if (!messagesUrl) {
        return;
      }
      getJson(messagesUrl + '?after=' + lastId(log)).then(function (payload) {
        if (!payload.success) {
          return;
        }
        (payload.results || []).forEach(function (row) {
          paintMessage(log, row);
        });
        if (online && payload.online) {
          online.textContent = payload.online.length + ' آنلاین';
        }
      });
    }
    if (form) {
      form.addEventListener('submit', function (event) {
        event.preventDefault();
        post(messagesUrl, new FormData(form)).then(function (payload) {
          if (!payload.success) {
            flash(payload.message || 'ارسال نشد.');
            return;
          }
          paintMessage(log, payload.item);
          form.reset();
        });
      });
    }
    tick();
    chatTimer = window.setInterval(tick, 4000);
    if (presenceUrl) {
      presenceTimer = window.setInterval(function () {
        post(presenceUrl, {});
      }, 20000);
    }
  }

  function bindAlliancePage() {
    if (chatTimer) {
      window.clearInterval(chatTimer);
      chatTimer = null;
    }
    if (presenceTimer) {
      window.clearInterval(presenceTimer);
      presenceTimer = null;
    }
    bindSearch();
    bindActions();
    bindChat();
  }

  window.__kbBindAlliance = bindAlliancePage;
})();
