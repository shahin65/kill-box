(function (win, doc) {
  var EMOJIS = ['🔥', '💀', '🎯', '👑', '⚡', '🎮', '😂', '❤️', '👏', '😮'];
  var MAX = 280;
  var bound = false;
  var gifAbort = null;
  var gifTimer = 0;
  var gifPos = '';
  var gifQuery = '';
  var activeForm = null;
  var lastFocus = null;

  function escapeHtml(value) {
    return String(value || '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  function commentMarkup(row) {
    var gif = '';
    if (row.gif_url) {
      gif =
        '<span class="kb-gif"><img src="' +
        escapeHtml(row.gif_preview_url || row.gif_url) +
        '" alt="' +
        escapeHtml(row.alt || 'GIF') +
        '" loading="lazy" decoding="async"></span>';
    }
    var replyBtn = row.parent_id
      ? ''
      : '<button class="kb-comment-reply" type="button" data-comment-reply="' +
        row.id +
        '">پاسخ</button>';
    var delBtn = row.mine
      ? '<button class="kb-comment-del" type="button" data-comment-del="' + row.id + '">حذف</button>'
      : '';
    var avatar = escapeHtml(row.avatar || '/static/images/icons/profile2.webp');
    return (
      '<li class="kb-comment' +
      (row.parent_id ? ' is-reply' : '') +
      '"><img class="kb-comment__avatar" src="' +
      avatar +
      '" alt="" width="32" height="32"><div class="kb-comment__body"><strong>' +
      escapeHtml(row.name) +
      '</strong> ' +
      escapeHtml(row.text) +
      gif +
      replyBtn +
      delBtn +
      '</div></li>'
    );
  }

  win.__kbCommentMarkup = commentMarkup;

  function fieldOf(form) {
    return form.querySelector('textarea, input[type="text"], input:not([type])');
  }

  function wantsGif(form) {
    if (!form) {
      return false;
    }
    if (form.id === 'story-form' || form.id === 'post-form') {
      return false;
    }
    return true;
  }

  function composerOf(node) {
    return node
      ? node.closest(
          '[data-comment-post], [data-kb-composer], #story-form, #post-form, #story-comment-form, #alliance-chat-form'
        )
      : null;
  }

  function gifChipLabel(form) {
    return form && form.getAttribute('data-kb-composer') === 'chat'
      ? 'GIF به پیام اضافه شد'
      : 'GIF به کامنت اضافه شد';
  }

  function ensureGifChip(form) {
    if (!form || form.querySelector('.kb-gif-chip')) {
      return form.querySelector('.kb-gif-chip');
    }
    var chip = doc.createElement('div');
    chip.className = 'kb-gif-chip';
    chip.hidden = true;
    chip.innerHTML =
      '<img alt=""><span>' +
      gifChipLabel(form) +
      '</span><button type="button" data-gif-clear>حذف</button>';
    var row = form.querySelector('.kb-composer-row');
    if (row && row.parentNode) {
      form.insertBefore(chip, row);
    } else {
      form.appendChild(chip);
    }
    return chip;
  }

  function clearGifChip(form) {
    if (!form) {
      return;
    }
    var hidden = form.querySelector('[name="gif_id"]');
    if (hidden) {
      hidden.value = '';
    }
    form.classList.remove('has-gif');
    var chip = form.querySelector('.kb-gif-chip');
    if (chip) {
      chip.hidden = true;
      var img = chip.querySelector('img');
      if (img) {
        img.removeAttribute('src');
      }
    }
  }

  function showGifChip(form, preview) {
    var chip = ensureGifChip(form);
    if (!chip) {
      return;
    }
    var img = chip.querySelector('img');
    if (img && preview) {
      img.src = preview;
    }
    var label = chip.querySelector('span');
    if (label) {
      label.textContent = gifChipLabel(form);
    }
    chip.hidden = false;
    form.classList.add('has-gif');
  }

  function ensureExtras(form) {
    if (!form || form.getAttribute('data-kb-extras') === '1') {
      return;
    }
    form.setAttribute('data-kb-extras', '1');
    form.setAttribute('data-kb-composer', form.getAttribute('data-kb-composer') || '1');
    if (!form.querySelector('.kb-emoji-bar')) {
      var bar = doc.createElement('div');
      bar.className = 'kb-emoji-bar';
      bar.setAttribute('role', 'listbox');
      bar.setAttribute('aria-label', 'ایموجی سریع');
      bar.innerHTML = EMOJIS.map(function (item) {
        return (
          '<button class="kb-emoji" type="button" data-kb-emoji="' +
          item +
          '" aria-label="' +
          item +
          '">' +
          item +
          '</button>'
        );
      }).join('');
      form.insertBefore(bar, form.firstChild);
    }
    if (wantsGif(form) && !form.querySelector('[data-gif-open]')) {
      var gifBtn = doc.createElement('button');
      gifBtn.className = 'kb-gif-btn';
      gifBtn.type = 'button';
      gifBtn.setAttribute('data-gif-open', '');
      gifBtn.setAttribute('aria-label', 'افزودن GIF');
      gifBtn.textContent = 'GIF';
      var submit = form.querySelector('button[type="submit"]');
      if (submit && submit.parentNode) {
        submit.parentNode.insertBefore(gifBtn, submit);
      } else {
        form.appendChild(gifBtn);
      }
    }
    if (wantsGif(form) && !form.querySelector('[name="gif_id"]')) {
      var hidden = doc.createElement('input');
      hidden.type = 'hidden';
      hidden.name = 'gif_id';
      form.appendChild(hidden);
    }
    if (!form.querySelector('[name="parent_id"]')) {
      var parent = doc.createElement('input');
      parent.type = 'hidden';
      parent.name = 'parent_id';
      form.appendChild(parent);
    }
    var field = fieldOf(form);
    if (field && !field.getAttribute('maxlength')) {
      field.setAttribute('maxlength', String(MAX));
    }
    ensureComposerRow(form);
    if (wantsGif(form)) {
      ensureGifChip(form);
    }
  }

  function ensureComposerRow(form) {
    if (!form || form.querySelector('.kb-composer-row')) {
      return;
    }
    if (form.id === 'story-form' || form.id === 'post-form' || form.hasAttribute('data-kb-media-form')) {
      return;
    }
    var row = doc.createElement('div');
    row.className = 'kb-composer-row';
    var kids = Array.prototype.slice.call(form.children);
    kids.forEach(function (node) {
      if (node.classList && node.classList.contains('kb-emoji-bar')) {
        return;
      }
      if (node.tagName === 'INPUT' && (node.type === 'hidden' || node.name === 'gif_id' || node.name === 'parent_id')) {
        return;
      }
      row.appendChild(node);
    });
    var emoji = form.querySelector('.kb-emoji-bar');
    if (emoji && emoji.nextSibling) {
      form.insertBefore(row, emoji.nextSibling);
    } else {
      form.appendChild(row);
    }
  }

  function insertEmoji(form, emoji) {
    var field = fieldOf(form);
    if (!field) {
      return;
    }
    var start = field.selectionStart || field.value.length;
    var end = field.selectionEnd || field.value.length;
    var cap = Number(field.getAttribute('maxlength') || MAX) || MAX;
    var next = field.value.slice(0, start) + emoji + field.value.slice(end);
    if (next.length > cap) {
      next = next.slice(0, cap);
    }
    field.value = next;
    var caret = Math.min(start + emoji.length, cap);
    field.focus();
    if (field.setSelectionRange) {
      field.setSelectionRange(caret, caret);
    }
  }

  function sheet() {
    return doc.getElementById('kb-gif-sheet');
  }

  function setGifOpen(on) {
    var box = sheet();
    if (!box) {
      return;
    }
    box.hidden = !on;
    box.classList.toggle('is-open', on);
    if (on) {
      box.setAttribute('open', '');
      var search = doc.getElementById('kb-gif-q');
      if (search) {
        search.focus();
      }
    } else {
      box.removeAttribute('open');
      if (lastFocus && lastFocus.focus) {
        lastFocus.focus();
      }
    }
    doc.dispatchEvent(new CustomEvent(on ? 'kb-gif-open' : 'kb-gif-close'));
  }

  function gifStatus(text, isError) {
    var node = doc.getElementById('kb-gif-status');
    if (!node) {
      return;
    }
    node.hidden = !text;
    node.textContent = text || '';
    node.classList.toggle('is-error', !!isError);
  }

  function renderGifs(rows, append) {
    var grid = doc.getElementById('kb-gif-grid');
    if (!grid) {
      return;
    }
    if (!append) {
      grid.innerHTML = '';
    }
    grid.insertAdjacentHTML(
      'beforeend',
      rows
        .map(function (row) {
          var w = Number(row.width || 0) || 120;
          var h = Number(row.height || 0) || 90;
          return (
            '<button class="kb-gif-tile" type="button" data-gif-pick="' +
            escapeHtml(row.id) +
            '" style="aspect-ratio:' +
            w +
            '/' +
            h +
            '"><img src="' +
            escapeHtml(row.preview_url || row.url) +
            '" alt="' +
            escapeHtml(row.alt || 'GIF') +
            '" loading="lazy" decoding="async" width="' +
            w +
            '" height="' +
            h +
            '"></button>'
          );
        })
        .join('')
    );
  }

  function loadGifs(reset) {
    var more = doc.getElementById('kb-gif-more');
    if (gifAbort) {
      gifAbort.abort();
    }
    gifAbort = new AbortController();
    if (reset) {
      gifPos = '';
      renderGifs([], false);
    }
    gifStatus('در حال بارگذاری…', false);
    var params = new URLSearchParams();
    if (gifQuery) {
      params.set('q', gifQuery);
    }
    if (gifPos) {
      params.set('pos', gifPos);
    }
    fetch('/social/gifs/?' + params.toString(), {
      headers: { Accept: 'application/json', 'X-Requested-With': 'XMLHttpRequest' },
      credentials: 'same-origin',
      signal: gifAbort.signal,
    })
      .then(function (response) {
        return response.json().then(function (payload) {
          payload.status = response.status;
          return payload;
        });
      })
      .then(function (payload) {
        if (payload.status === 401 && typeof win.__kbPromptAuth === 'function') {
          win.__kbPromptAuth();
        }
        if (!payload.success) {
          gifStatus(payload.message || 'سرویس GIF در دسترس نیست.', true);
          return;
        }
        if (payload.disabled) {
          gifStatus('سرویس GIF پیکربندی نشده است.', true);
          return;
        }
        var rows = payload.results || [];
        renderGifs(rows, !!gifPos);
        gifPos = payload.next || '';
        if (more) {
          more.hidden = !gifPos;
        }
        gifStatus(rows.length || gifPos ? '' : 'نتیجه‌ای پیدا نشد.', false);
      })
      .catch(function (err) {
        if (err && err.name === 'AbortError') {
          return;
        }
        gifStatus('سرویس GIF در دسترس نیست.', true);
      });
  }

  function openGif(form) {
    activeForm = form;
    lastFocus = fieldOf(form);
    gifQuery = '';
    var search = doc.getElementById('kb-gif-q');
    if (search) {
      search.value = '';
    }
    setGifOpen(true);
    loadGifs(true);
  }

  function pickGif(id, tile) {
    if (!activeForm) {
      return;
    }
    ensureExtras(activeForm);
    var hidden = activeForm.querySelector('[name="gif_id"]');
    if (hidden) {
      hidden.value = id;
    }
    var preview = '';
    if (tile) {
      var img = tile.querySelector('img');
      preview = img ? img.getAttribute('src') || '' : '';
    }
    showGifChip(activeForm, preview);
    setGifOpen(false);
  }

  function destroy() {
    if (gifAbort) {
      gifAbort.abort();
      gifAbort = null;
    }
    if (gifTimer) {
      win.clearTimeout(gifTimer);
      gifTimer = 0;
    }
    setGifOpen(false);
  }

  function bindForms() {
    doc
      .querySelectorAll(
        '[data-comment-post], [data-kb-composer], #story-form, #post-form, #story-comment-form, #alliance-chat-form'
      )
      .forEach(ensureExtras);
  }

  function bind() {
    bindForms();
    if (bound) {
      return;
    }
    bound = true;
    doc.addEventListener('click', function (event) {
      var node = event.target;
      if (!node || typeof node.closest !== 'function') {
        return;
      }
      var emoji = node.closest('[data-kb-emoji]');
      if (emoji) {
        event.preventDefault();
        var form = composerOf(emoji);
        insertEmoji(form, emoji.getAttribute('data-kb-emoji') || '');
        return;
      }
      var gifOpen = node.closest('[data-gif-open]');
      if (gifOpen) {
        event.preventDefault();
        openGif(composerOf(gifOpen));
        return;
      }
      var gifClear = node.closest('[data-gif-clear]');
      if (gifClear) {
        event.preventDefault();
        clearGifChip(composerOf(gifClear));
        return;
      }
      if (node.closest('[data-gif-close]') || node.closest('.kb-gif-sheet__backdrop')) {
        event.preventDefault();
        setGifOpen(false);
        return;
      }
      var pick = node.closest('[data-gif-pick]');
      if (pick) {
        event.preventDefault();
        pickGif(pick.getAttribute('data-gif-pick') || '', pick);
        return;
      }
      if (node.closest('#kb-gif-more')) {
        event.preventDefault();
        loadGifs(false);
        return;
      }
      var reply = node.closest('[data-comment-reply]');
      if (reply) {
        event.preventDefault();
        var host = reply.closest('[data-comment-post]') || doc.querySelector('[data-comment-post]');
        if (!host) {
          var slide = reply.closest('.post-reader__slide, .post-card');
          host = slide ? slide.querySelector('[data-comment-post]') : null;
        }
        if (host) {
          ensureExtras(host);
          var parent = host.querySelector('[name="parent_id"]');
          if (parent) {
            parent.value = reply.getAttribute('data-comment-reply') || '';
          }
          host.classList.add('is-replying');
          var field = fieldOf(host);
          if (field) {
            field.focus();
            field.placeholder = 'پاسخ…';
          }
        }
        return;
      }
      var del = node.closest('[data-comment-del]');
      if (del) {
        event.preventDefault();
        if (typeof win.__kbPostForm !== 'function') {
          return;
        }
        win.__kbPostForm('/social/comments/' + del.getAttribute('data-comment-del') + '/delete/').then(
          function (payload) {
            if (!payload.success) {
              if (typeof win.__kbFlashSocial === 'function') {
                win.__kbFlashSocial(payload.message || 'حذف نشد.');
              }
              return;
            }
            var form = del.closest('.post-reader__slide, .post-card, article') || doc;
            var postFormNode = form.querySelector ? form.querySelector('[data-comment-post]') : null;
            var postId = postFormNode ? postFormNode.getAttribute('data-comment-post') : '';
            if (postId && win.__kbUpdatePostComments) {
              win.__kbUpdatePostComments(postId, payload.comments || []);
            }
          }
        );
      }
    });
    var search = doc.getElementById('kb-gif-q');
    if (search) {
      search.addEventListener('input', function () {
        gifQuery = String(search.value || '').trim();
        if (gifTimer) {
          win.clearTimeout(gifTimer);
        }
        gifTimer = win.setTimeout(function () {
          loadGifs(true);
        }, 350);
      });
    }
    doc.addEventListener('keydown', function (event) {
      var box = sheet();
      if (!box || box.hidden || event.key !== 'Escape') {
        return;
      }
      event.preventDefault();
      setGifOpen(false);
    });
  }

  win.__kbBindComposerExtras = bind;
  win.__kbDestroyComposerExtras = destroy;
  win.__kbEnsureCommentExtras = bindForms;
  win.__kbClearGifChip = clearGifChip;
})(window, document);
