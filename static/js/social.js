function bindSocialPage() {
  if (typeof window.__kbDestroyPostViews === 'function') {
    window.__kbDestroyPostViews();
  }
  if (typeof window.__kbDestroyComposerExtras === 'function') {
    window.__kbDestroyComposerExtras();
  }
  if (typeof window.__kbBindMediaForms === 'function') {
    window.__kbBindMediaForms();
  }
  bindStoryViewer();
  bindSocialActions();
  bindChat();
  bindFriends();
  bindHomeSwipe();
  bindPostReader();
  if (typeof window.__kbBindFeedMedia === 'function') {
    window.__kbBindFeedMedia();
  }
  if (typeof window.__kbBindComposerExtras === 'function') {
    window.__kbBindComposerExtras();
  }
  if (typeof window.__kbBindPostViews === 'function') {
    window.__kbBindPostViews();
  }
}

window.__kbBindSocial = bindSocialPage;

function escapeHtml(value) {
  return String(value || '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

function csrfToken() {
  var node = document.querySelector('[name=csrfmiddlewaretoken]');
  return node ? node.value : '';
}

window.__kbPostForm = postForm;
window.__kbFlashSocial = flashSocial;

function postForm(url, data) {
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
    var type = response.headers.get('content-type') || '';
    if (type.indexOf('application/json') === -1) {
      return {
        success: false,
        status: response.status,
        code: 'auth',
        message: 'برای لایک و کامنت باید حسابت را ثبت‌نام کنی.',
      };
    }
    return response.json().then(function (payload) {
      payload.status = response.status;
      if (
        (payload.status === 401 || payload.code === 'auth') &&
        typeof window.__kbPromptAuth === 'function'
      ) {
        window.__kbPromptAuth();
      }
      return payload;
    });
  });
}

function flashSocial(message) {
  if (!message) {
    return;
  }
  var node = document.getElementById('kb-social-flash');
  if (!node) {
    node = document.createElement('p');
    node.id = 'kb-social-flash';
    node.className = 'kb-social-flash';
    document.body.appendChild(node);
  }
  node.hidden = false;
  node.textContent = message;
  window.clearTimeout(node._hide);
  node._hide = window.setTimeout(function () {
    node.hidden = true;
  }, 3200);
}

function bindStoryViewer() {
  if (typeof window.__kbBindStoryViewer === 'function') {
    window.__kbBindStoryViewer();
  }
}

function bindHomeSwipe() {
  var dragging = false;
  var swiped = false;
  var startX = 0;
  var deltaX = 0;
  var active = null;

  function hosts() {
    return document.querySelectorAll('[data-kb-swipe], [data-post-swipe]');
  }

  function swipeBox(node) {
    return node && node.closest ? node.closest('[data-kb-swipe], [data-post-swipe]') : null;
  }

  function pairLocked(box) {
    return !!(box && box.querySelector('.home-swipe.is-pair') && window.matchMedia('(min-width: 720px)').matches);
  }

  function isPeek(box) {
    return !!(box && box.querySelector('.home-swipe.is-peek'));
  }

  function peekStep(box) {
    var rail = box.querySelector('.home-swipe__track');
    var slide = slidesOf(box)[0];
    if (!rail || !slide) {
      return 0;
    }
    var gap = parseFloat(window.getComputedStyle(rail).columnGap || window.getComputedStyle(rail).gap) || 0;
    return slide.getBoundingClientRect().width + gap;
  }

  function slidesOf(box) {
    return box ? box.querySelectorAll('.home-swipe__slide') : [];
  }

  function indexOf(box) {
    return Number(box.getAttribute('data-index') || 0);
  }

  function wrapIndex(box, idx) {
    var total = slidesOf(box).length;
    if (!total) {
      return 0;
    }
    return ((idx % total) + total) % total;
  }

  function paint(box, idx, offset, draggingNow) {
    var rail = box.querySelector('.home-swipe__track');
    var slides = slidesOf(box);
    var dots = box.querySelector('.home-swipe__dots');
    var pos = box.querySelector('[data-post-pos]');
    if (!rail || !slides.length) {
      return;
    }
    idx = wrapIndex(box, idx);
    box.setAttribute('data-index', String(idx));
    if (pairLocked(box)) {
      rail.style.transform = 'none';
    } else if (isPeek(box)) {
      rail.style.transform = 'translateX(' + (-idx * peekStep(box) + (offset || 0)) + 'px)';
    } else {
      rail.style.transform =
        'translateX(calc(' + idx * -100 + '% + ' + (offset || 0) + 'px))';
    }
    if (pos) {
      pos.textContent = String(idx + 1);
    }
    if (!dots || draggingNow) {
      return;
    }
    dots.innerHTML = Array.prototype.map
      .call(slides, function (_, slideIdx) {
        return (
          '<button type="button" class="home-swipe__dot' +
          (slideIdx === idx ? ' is-on' : '') +
          '" data-post-dot="' +
          slideIdx +
          '" aria-label="آیتم ' +
          (slideIdx + 1) +
          '"></button>'
        );
      })
      .join('');
  }

  function go(box, next) {
    var rail = box.querySelector('.home-swipe__track');
    if (rail) {
      rail.style.transition = '';
    }
    paint(box, next, 0, false);
  }

  hosts().forEach(function (box) {
    paint(box, indexOf(box), 0, false);
  });
  if (window.__kbHomeSwipeBound) {
    return;
  }
  window.__kbHomeSwipeBound = true;
  window.addEventListener('resize', function () {
    hosts().forEach(function (box) {
      paint(box, indexOf(box), 0, false);
    });
  });

  document.addEventListener('click', function (event) {
    var node = event.target;
    if (node && node.nodeType !== 1) {
      node = node.parentElement;
    }
    if (!node || typeof node.closest !== 'function') {
      return;
    }
    if (swiped) {
      event.preventDefault();
      event.stopPropagation();
      swiped = false;
      return;
    }
    var box = swipeBox(node);
    if (!box) {
      return;
    }
    var idx = indexOf(box);
    if (node.closest('[data-post-next]')) {
      event.preventDefault();
      go(box, idx + 1);
      return;
    }
    if (node.closest('[data-post-prev]')) {
      event.preventDefault();
      go(box, idx - 1);
      return;
    }
    var dot = node.closest('[data-post-dot]');
    if (dot) {
      event.preventDefault();
      go(box, Number(dot.getAttribute('data-post-dot') || 0));
    }
  }, true);
  document.addEventListener(
    'pointerdown',
    function (event) {
      var view = event.target.closest && event.target.closest('.home-swipe');
      var box = view && swipeBox(view);
      if (!view || !box || pairLocked(box)) {
        return;
      }
      if (typeof window.__kbOverlayKind === 'function' && window.__kbOverlayKind()) {
        return;
      }
      if (event.target.closest('.home-swipe__nav, .home-swipe__acts, [data-like-post], [data-kb-mute]')) {
        return;
      }
      dragging = true;
      swiped = false;
      active = box;
      startX = event.clientX;
      deltaX = 0;
      var rail = box.querySelector('.home-swipe__track');
      if (rail) {
        rail.style.transition = 'none';
      }
    },
    true
  );
  document.addEventListener(
    'pointermove',
    function (event) {
      if (!dragging || !active) {
        return;
      }
      deltaX = event.clientX - startX;
      if (Math.abs(deltaX) > 28) {
        swiped = true;
        paint(active, indexOf(active), deltaX, true);
      }
    },
    true
  );
  function endDrag() {
    if (!dragging) {
      return;
    }
    dragging = false;
    var box = active;
    active = null;
    if (!box) {
      return;
    }
    var idx = indexOf(box);
    if (Math.abs(deltaX) < 28) {
      go(box, idx);
      return;
    }
    if (deltaX < -36) {
      go(box, idx + 1);
    } else if (deltaX > 36) {
      go(box, idx - 1);
    } else {
      go(box, idx);
    }
  }
  document.addEventListener('pointerup', endDrag, true);
  document.addEventListener('pointercancel', endDrag, true);
  window.addEventListener('resize', function () {
    hosts().forEach(function (box) {
      paint(box, indexOf(box), 0, false);
    });
  });
}

function bindPostReader() {
  if (typeof window.__kbBindReelsViewer === 'function') {
    window.__kbBindReelsViewer();
  }
}


function bindSocialActions() {
  if (window.__kbSocialActionsBound) {
    return;
  }
  window.__kbSocialActionsBound = true;
  document.addEventListener('submit', function (event) {
    var form = event.target && event.target.closest ? event.target.closest('[data-comment-post]') : null;
    if (!form) {
      return;
    }
    event.preventDefault();
    var input = form.querySelector('textarea, input[type="text"]') || form.querySelector('input:not([type="hidden"])');
    var gifField = form.querySelector('[name="gif_id"]');
    var parentField = form.querySelector('[name="parent_id"]');
    var postId = form.getAttribute('data-comment-post');
    postForm('/social/posts/' + postId + '/comment/', {
      text: input ? input.value : '',
      gif_id: gifField ? gifField.value : '',
      parent_id: parentField ? parentField.value : '',
    }).then(function (payload) {
      if (!payload.success) {
        flashSocial(payload.message || 'کامنت ارسال نشد.');
        return;
      }
      if (input) {
        input.value = '';
        input.placeholder = 'کامنت…';
      }
      if (gifField) {
        gifField.value = '';
      }
      if (parentField) {
        parentField.value = '';
      }
      form.classList.remove('has-gif', 'is-replying');
      var reader = document.getElementById('post-reader');
      if (reader && reader.open && window.__kbPaintPostReader) {
        window.__kbUpdatePostComments(postId, payload.comments || []);
        return;
      }
      if (window.__kbSoftReload) {
        window.__kbSoftReload();
      } else {
        window.location.reload();
      }
    });
  });
  document.addEventListener('click', function (event) {
    var node = event.target;
    if (!node || typeof node.closest !== 'function') {
      return;
    }
    var save = node.closest('[data-save-post]');
    if (save) {
      event.preventDefault();
      event.stopPropagation();
      if (save.getAttribute('data-kb-busy') === '1') {
        return;
      }
      var wasOn = save.classList.contains('is-on');
      save.setAttribute('data-kb-busy', '1');
      save.classList.toggle('is-on', !wasOn);
      save.setAttribute('aria-pressed', wasOn ? 'false' : 'true');
      postForm('/social/posts/' + save.getAttribute('data-save-post') + '/save/').then(function (payload) {
        save.removeAttribute('data-kb-busy');
        if (!payload.success) {
          save.classList.toggle('is-on', wasOn);
          save.setAttribute('aria-pressed', wasOn ? 'true' : 'false');
          flashSocial(payload.message || 'ذخیره انجام نشد.');
          return;
        }
        save.classList.toggle('is-on', !!payload.saved);
        save.setAttribute('aria-pressed', payload.saved ? 'true' : 'false');
        if (window.__kbUpdatePostSave) {
          window.__kbUpdatePostSave(save.getAttribute('data-save-post'), payload);
        }
      });
      return;
    }
    var more = node.closest('[data-saved-more]');
    if (more) {
      event.preventDefault();
      if (more.getAttribute('data-kb-busy') === '1') {
        return;
      }
      more.setAttribute('data-kb-busy', '1');
      var page = more.getAttribute('data-saved-more');
      fetch('/social/saved/?page=' + encodeURIComponent(page), {
        headers: { Accept: 'application/json', 'X-Requested-With': 'XMLHttpRequest' },
        credentials: 'same-origin',
      })
        .then(function (response) {
          return response.json();
        })
        .then(function (payload) {
          more.removeAttribute('data-kb-busy');
          if (!payload.success) {
            return;
          }
          var feed = document.getElementById('saved-feed');
          var dataNode = document.getElementById('post-reader-data');
          var rows = [];
          if (dataNode) {
            try {
              rows = JSON.parse(dataNode.textContent || '[]');
            } catch (err) {
              rows = [];
            }
          }
          (payload.posts || []).forEach(function (post) {
            rows.push(post);
            if (!feed) {
              return;
            }
            var article = document.createElement('article');
            article.className = 'post-card';
            article.setAttribute('data-post-id', String(post.id));
            article.setAttribute('data-post-open', String(rows.length - 1));
            article.setAttribute('data-kb-view-post', String(post.id));
            article.innerHTML =
              '<header class="post-card__head"><strong>' +
              escapeHtml(post.name) +
              '</strong></header>' +
              (post.url
                ? '<div class="kb-media post-card__media" style="aspect-ratio:4/5"><img class="kb-media__el" src="' +
                  escapeHtml(post.poster || post.url) +
                  '" alt="" loading="lazy" decoding="async"></div>'
                : '') +
              (post.caption ? '<p class="post-card__caption">' + escapeHtml(post.caption) + '</p>' : '') +
              '<div class="post-card__bar"><button type="button" data-like-post="' +
              post.id +
              '">لایک ' +
              escapeHtml(post.likes) +
              '</button><span class="story-act" data-kb-views="' +
              post.id +
              '">' +
              escapeHtml(post.views_label || post.views || 0) +
              '</span><button class="story-act is-on" type="button" data-save-post="' +
              post.id +
              '" aria-pressed="true">ذخیره</button></div>';
            feed.appendChild(article);
          });
          if (dataNode) {
            dataNode.textContent = JSON.stringify(rows);
          }
          if (payload.has_more && payload.next_page) {
            more.setAttribute('data-saved-more', String(payload.next_page));
          } else {
            more.remove();
          }
          if (typeof window.__kbBindPostViews === 'function') {
            window.__kbBindPostViews();
          }
        })
        .catch(function () {
          more.removeAttribute('data-kb-busy');
        });
      return;
    }
    var like = node.closest('[data-like-post]');
    if (like) {
      event.preventDefault();
      event.stopPropagation();
      postForm('/social/posts/' + like.getAttribute('data-like-post') + '/like/').then(function (payload) {
        if (!payload.success) {
          flashSocial(payload.message || 'لایک انجام نشد.');
          return;
        }
        var count = like.querySelector('span');
        if (count) {
          count.textContent = String(payload.likes);
        } else {
          like.textContent = 'لایک ' + payload.likes;
        }
        like.classList.toggle('is-on', !!payload.liked);
        if (window.__kbUpdatePostLike) {
          window.__kbUpdatePostLike(like.getAttribute('data-like-post'), payload);
        }
      });
      return;
    }
    var follow = event.target.closest('[data-follow]');
    if (follow) {
      postForm('/social/follow/' + follow.getAttribute('data-follow') + '/').then(function (payload) {
        if (payload.success) {
          follow.textContent = payload.following ? 'لغو دنبال' : 'دنبال کردن';
        }
      });
    }
    var share = event.target.closest('[data-share]');
    if (share) {
      var url = share.getAttribute('data-share');
      if (navigator.share) {
        navigator.share({ url: url, title: 'KILLBOX' });
      } else {
        window.open('https://t.me/share/url?url=' + encodeURIComponent(url), '_blank');
        if (navigator.clipboard) {
          navigator.clipboard.writeText(url);
        }
      }
    }
    var accept = event.target.closest('[data-accept]');
    if (accept) {
      postForm('/social/messages/' + accept.getAttribute('data-accept') + '/accept/').then(function () {
        if (window.__kbSoftReload) {
          window.__kbSoftReload();
        } else {
          window.location.reload();
        }
      });
    }
    var reject = event.target.closest('[data-reject]');
    if (reject) {
      postForm('/social/messages/' + reject.getAttribute('data-reject') + '/reject/').then(function () {
        if (window.__kbSoftReload) {
          window.__kbSoftReload();
        } else {
          window.location.reload();
        }
      });
    }
    var block = event.target.closest('[data-block]');
    if (block) {
      postForm('/social/messages/' + block.getAttribute('data-block') + '/block/').then(function () {
        if (window.__kbSoftReload) {
          window.__kbSoftReload();
        } else {
          window.location.reload();
        }
      });
    }
  });
}

function bindChat() {
  var form = document.getElementById('chat-form');
  var card = document.querySelector('[data-thread]');
  if (!form || !card || form.getAttribute('data-kb-bound')) {
    return;
  }
  form.setAttribute('data-kb-bound', '1');
  form.addEventListener('submit', function (event) {
    event.preventDefault();
    var input = document.getElementById('chat-text');
    postForm('/social/messages/' + card.getAttribute('data-thread') + '/send/', {
      text: input.value,
    }).then(function (payload) {
      if (!payload.success) {
        window.alert(payload.message || 'ارسال نشد.');
        return;
      }
      window.location.reload();
    });
  });
}

function bindFriends() {
  if (window.__kbFriendsBound) {
    return;
  }
  window.__kbFriendsBound = true;
  document.addEventListener('click', function (event) {
    var node = event.target;
    if (!node || typeof node.closest !== 'function') {
      return;
    }
    var requestBtn = node.closest('[data-friend-request]');
    var acceptBtn = node.closest('[data-friend-accept]');
    var rejectBtn = node.closest('[data-friend-reject]');
    var userId = '';
    var url = '';
    if (requestBtn) {
      userId = requestBtn.getAttribute('data-friend-request');
      url = '/social/friends/' + userId + '/request/';
    } else if (acceptBtn) {
      userId = acceptBtn.getAttribute('data-friend-accept');
      url = '/social/friends/' + userId + '/accept/';
    } else if (rejectBtn) {
      userId = rejectBtn.getAttribute('data-friend-reject');
      url = '/social/friends/' + userId + '/reject/';
    }
    if (!url) {
      return;
    }
    postForm(url).then(function (payload) {
      var status = document.getElementById('friend-status');
      if (status) {
        status.hidden = false;
        status.textContent = payload.message || '';
        status.classList.toggle('is-error', !payload.success);
      }
      if (payload.success && window.__kbSoftReload) {
        window.__kbSoftReload();
      }
    });
  });
}
