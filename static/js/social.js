function bindSocialPage() {
  bindStoryComposer();
  bindStoryViewer();
  bindPostComposer();
  bindSocialActions();
  bindChat();
  bindFriends();
  bindHomeSwipe();
  bindPostReader();
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

function postForm(url, data) {
  var body = data instanceof FormData ? data : new URLSearchParams(data || {});
  return fetch(url, {
    method: 'POST',
    headers: data instanceof FormData ? { 'X-CSRFToken': csrfToken() } : {
      'X-CSRFToken': csrfToken(),
      'Content-Type': 'application/x-www-form-urlencoded',
    },
    body: body,
  }).then(function (response) {
    return response.json().then(function (payload) {
      payload.status = response.status;
      return payload;
    });
  });
}

function videoDuration(file) {
  if (!file || !String(file.type || '').startsWith('video/')) {
    return Promise.resolve(0);
  }
  return new Promise(function (resolve, reject) {
    var video = document.createElement('video');
    video.preload = 'metadata';
    video.onloadedmetadata = function () {
      var duration = video.duration || 0;
      URL.revokeObjectURL(video.src);
      resolve(duration);
    };
    video.onerror = function () {
      URL.revokeObjectURL(video.src);
      reject(new Error('ویدیو قابل خواندن نبود.'));
    };
    video.src = URL.createObjectURL(file);
  });
}

function showStatus(id, message, isError) {
  var node = document.getElementById(id);
  if (!node) {
    return;
  }
  node.hidden = !message;
  node.textContent = message || '';
  node.classList.toggle('is-error', !!isError);
}

function bindStoryComposer() {
  var form = document.getElementById('story-form');
  var card = document.querySelector('[data-story-create]');
  if (!form || !card || form.getAttribute('data-kb-bound')) {
    return;
  }
  form.setAttribute('data-kb-bound', '1');
  form.addEventListener('submit', function (event) {
    event.preventDefault();
    var file = document.getElementById('story-file').files[0];
    if (!file) {
      return;
    }
    videoDuration(file)
      .then(function (duration) {
        if (duration > 30.4) {
          throw new Error('مدت استوری نباید بیشتر از ۳۰ ثانیه باشد.');
        }
        var data = new FormData();
        data.append('media', file);
        data.append('overlay', document.getElementById('story-overlay').value || '');
        return postForm(card.getAttribute('data-story-create'), data);
      })
      .then(function (payload) {
        if (!payload) {
          return;
        }
        if (!payload.success) {
          showStatus('story-status', payload.message, true);
          return;
        }
        if (window.__kbSoftReload) {
          window.__kbSoftReload();
        } else {
          window.location.reload();
        }
      })
      .catch(function (err) {
        showStatus('story-status', err.message || 'ارسال استوری ناموفق بود.', true);
      });
  });
}

function bindStoryViewer() {
  if (window.__kbStoryViewerBound) {
    return;
  }
  window.__kbStoryViewerBound = true;
  var groups = [];
  var groupIndex = 0;
  var itemIndex = 0;
  var timer = 0;
  var started = 0;
  var elapsed = 0;
  var duration = 5000;
  var paused = false;
  var holding = false;
  var pressAt = 0;
  var pressX = 0;

  function dialog() {
    return document.getElementById('story-viewer');
  }

  function loadGroups() {
    var dataNode = document.getElementById('story-data');
    if (!dataNode) {
      return [];
    }
    try {
      return JSON.parse(dataNode.textContent || '[]');
    } catch (err) {
      return [];
    }
  }

  function currentItem() {
    return groups[groupIndex] && groups[groupIndex].stories[itemIndex];
  }

  function unseenIndexes(group) {
    var idxs = [];
    (group.stories || []).forEach(function (row, idx) {
      if (!row.seen) {
        idxs.push(idx);
      }
    });
    return idxs;
  }

  function paintLike(item) {
    var btn = document.getElementById('story-like');
    var count = document.getElementById('story-like-count');
    if (count) {
      count.textContent = String(item.likes || 0);
    }
    if (btn) {
      btn.classList.toggle('is-on', !!item.liked);
    }
  }

  function paintComments(item) {
    var box = document.getElementById('story-comments');
    if (!box) {
      return;
    }
    box.innerHTML = (item.comments || [])
      .map(function (row) {
        return '<p><strong>' + escapeHtml(row.name) + '</strong> ' + escapeHtml(row.text) + '</p>';
      })
      .join('');
  }

  function paintRings() {
    document.querySelectorAll('[data-story-open]').forEach(function (btn) {
      var idx = Number(btn.getAttribute('data-story-open') || 0);
      var group = groups[idx];
      if (!group) {
        return;
      }
      var unseen = unseenIndexes(group).length > 0;
      btn.classList.toggle('is-unseen', unseen);
      btn.classList.toggle('is-seen', !unseen);
    });
  }

  function markSeen(item) {
    if (!item) {
      return;
    }
    var wasSeen = !!item.seen;
    item.seen = true;
    paintRings();
    if (!wasSeen) {
      postForm('/social/stories/' + item.id + '/seen/');
    }
  }

  function consumed() {
    if (paused) {
      return elapsed;
    }
    return elapsed + (Date.now() - started);
  }

  function pauseStory() {
    if (paused) {
      return;
    }
    elapsed = consumed();
    paused = true;
    window.clearTimeout(timer);
    var box = dialog();
    if (box) {
      box.classList.add('is-paused');
    }
    var video = document.querySelector('#story-stage video');
    if (video && !video.paused) {
      video.pause();
    }
  }

  function resumeStory() {
    if (!paused) {
      return;
    }
    paused = false;
    started = Date.now();
    var box = dialog();
    if (box) {
      box.classList.remove('is-paused');
    }
    var video = document.querySelector('#story-stage video');
    if (video) {
      video.play();
    }
    tick();
  }

  function showItem() {
    var box = dialog();
    var item = currentItem();
    if (!box || !item) {
      if (box && box.close) {
        box.close();
      }
      return;
    }
    window.clearTimeout(timer);
    paused = false;
    elapsed = 0;
    holding = false;
    box.classList.remove('is-paused');
    var bars = document.getElementById('story-bars');
    bars.innerHTML = groups[groupIndex].stories
      .map(function (_, idx) {
        return '<span><i data-bar="' + idx + '"></i></span>';
      })
      .join('');
    var stage = document.getElementById('story-stage');
    if (item.kind === 'video') {
      stage.innerHTML = '<video src="' + item.url + '" autoplay playsinline></video>';
      var video = stage.querySelector('video');
      duration = Math.min(15000, ((video && video.duration) || 15) * 1000);
      if (video) {
        video.onloadedmetadata = function () {
          duration = Math.min(15000, video.duration * 1000);
        };
      }
    } else {
      stage.innerHTML = '<img src="' + item.url + '" alt="" draggable="false">';
      duration = 5000;
    }
    document.getElementById('story-overlay-text').textContent = item.overlay || '';
    paintLike(item);
    paintComments(item);
    markSeen(item);
    started = Date.now();
    tick();
  }

  function tick() {
    if (paused) {
      return;
    }
    var fill = Math.min(1, consumed() / duration);
    groups[groupIndex].stories.forEach(function (_, idx) {
      var bar = document.querySelector('[data-bar="' + idx + '"]');
      if (!bar) {
        return;
      }
      bar.style.width = idx < itemIndex ? '100%' : idx === itemIndex ? fill * 100 + '%' : '0%';
    });
    if (fill >= 1) {
      next();
      return;
    }
    timer = window.setTimeout(tick, 80);
  }

  function closeViewer() {
    window.clearTimeout(timer);
    paused = false;
    holding = false;
    var box = dialog();
    if (box) {
      box.classList.remove('is-paused');
      if (box.close) {
        box.close();
      }
    }
  }

  function next() {
    if (!groups[groupIndex]) {
      return;
    }
    if (itemIndex + 1 < groups[groupIndex].stories.length) {
      itemIndex += 1;
      showItem();
      return;
    }
    var total = groups.length;
    var step;
    for (step = 1; step <= total; step += 1) {
      var idx = (groupIndex + step) % total;
      var unseen = unseenIndexes(groups[idx]);
      if (unseen.length) {
        groupIndex = idx;
        itemIndex = unseen[0];
        showItem();
        return;
      }
    }
    closeViewer();
  }

  function prev() {
    if (itemIndex > 0) {
      itemIndex -= 1;
      showItem();
      return true;
    }
    if (groupIndex > 0) {
      groupIndex -= 1;
      itemIndex = groups[groupIndex].stories.length - 1;
      showItem();
      return true;
    }
    return false;
  }

  document.addEventListener('click', function (event) {
    var node = event.target;
    if (node && node.nodeType !== 1) {
      node = node.parentElement;
    }
    if (!node || typeof node.closest !== 'function') {
      return;
    }
    var openBtn = node.closest('[data-story-open]');
    if (openBtn) {
      event.preventDefault();
      groups = loadGroups();
      groupIndex = Number(openBtn.getAttribute('data-story-open') || 0);
      var openedFrom = groupIndex;
      var unseen = groups[groupIndex] ? unseenIndexes(groups[groupIndex]) : [];
      if (unseen.length) {
        itemIndex = unseen[0];
      } else {
        itemIndex = 0;
        var hop = 1;
        while (hop <= groups.length) {
          var wrapIdx = (openedFrom + hop) % groups.length;
          var wrapUnseen = unseenIndexes(groups[wrapIdx] || { stories: [] });
          if (wrapUnseen.length) {
            groupIndex = wrapIdx;
            itemIndex = wrapUnseen[0];
            break;
          }
          hop += 1;
        }
      }
      var box = dialog();
      if (!box || !groups[groupIndex]) {
        return;
      }
      if (box.showModal) {
        box.showModal();
      }
      showItem();
      return;
    }
    if (node.closest('[data-story-close]')) {
      closeViewer();
      return;
    }
    if (node.closest('#story-like')) {
      var item = currentItem();
      if (!item) {
        return;
      }
      postForm('/social/stories/' + item.id + '/like/').then(function (payload) {
        if (!payload.success) {
          return;
        }
        item.liked = payload.liked;
        item.likes = payload.likes;
        paintLike(item);
      });
    }
  });
  document.addEventListener('pointerdown', function (event) {
    var box = dialog();
    var node = event.target;
    if (!box || !box.open || !node || typeof node.closest !== 'function') {
      return;
    }
    if (node.closest('.story-viewer__actions') || node.closest('[data-story-close]') || node.closest('.story-viewer__comments')) {
      return;
    }
    if (!node.closest('#story-stage') && !node.closest('.story-viewer__overlay') && !node.closest('.story-viewer__bars')) {
      return;
    }
    holding = true;
    pressAt = Date.now();
    pressX = event.clientX;
    try {
      event.preventDefault();
    } catch (err) {}
    pauseStory();
  });
  document.addEventListener('pointerup', function (event) {
    if (!holding) {
      return;
    }
    holding = false;
    var held = Date.now() - pressAt;
    if (held < 220) {
      if (pressX < window.innerWidth / 2) {
        if (!prev()) {
          resumeStory();
        }
      } else {
        next();
      }
      return;
    }
    resumeStory();
  });
  document.addEventListener('pointercancel', function () {
    if (!holding) {
      return;
    }
    holding = false;
    resumeStory();
  });
  document.addEventListener('submit', function (event) {
    if (!event.target || event.target.id !== 'story-comment-form') {
      return;
    }
    event.preventDefault();
    var item = currentItem();
    var input = document.getElementById('story-comment');
    if (!item || !input || !input.value.trim()) {
      return;
    }
    postForm('/social/stories/' + item.id + '/comment/', { text: input.value }).then(function (payload) {
      if (!payload.success) {
        return;
      }
      item.comments = payload.comments;
      input.value = '';
      paintComments(item);
    });
  });
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
      if (!view || !box || event.target.closest('.home-swipe__nav') || pairLocked(box)) {
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
      if (Math.abs(deltaX) > 12) {
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
      if (!box.querySelector('.event-card')) {
        go(box, idx + 1);
      } else {
        go(box, idx);
      }
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
  if (window.__kbPostReaderBound) {
    return;
  }
  window.__kbPostReaderBound = true;
  var posts = [];
  var index = 0;
  var startY = 0;
  var deltaY = 0;
  var dragging = false;

  function loadPosts() {
    var node = document.getElementById('post-reader-data');
    if (!node) {
      return [];
    }
    try {
      return JSON.parse(node.textContent || '[]');
    } catch (err) {
      return [];
    }
  }

  function box() {
    return document.getElementById('post-reader');
  }

  function paint() {
    var stage = document.getElementById('post-reader-stage');
    var item = posts[index];
    if (!stage || !item) {
      return;
    }
    var media = item.url
      ? item.kind === 'video'
        ? '<video src="' + escapeHtml(item.url) + '" controls playsinline></video>'
        : '<img src="' + escapeHtml(item.url) + '" alt="" draggable="false">'
      : '';
    var caption = item.caption ? '<p>' + escapeHtml(item.caption) + '</p>' : '';
    stage.innerHTML =
      '<article class="post-reader__card">' +
      '<div class="post-reader__user"><img src="' +
      escapeHtml(item.avatar) +
      '" alt=""><span>' +
      escapeHtml(item.name) +
      '</span></div>' +
      media +
      caption +
      '<button class="story-act" type="button" data-like-post="' +
      item.id +
      '"><svg viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="M12 20.4 10.4 19C5.4 14.4 2 11.3 2 7.6A4.4 4.4 0 0 1 6.4 3.2 4.8 4.8 0 0 1 12 5.6a4.8 4.8 0 0 1 5.6-2.4A4.4 4.4 0 0 1 22 7.6c0 3.7-3.4 6.8-8.4 11.4z"/></svg><span>' +
      item.likes +
      '</span></button></article>';
  }

  function go(next) {
    if (!posts.length) {
      return;
    }
    index = Math.max(0, Math.min(posts.length - 1, next));
    paint();
  }

  document.addEventListener('click', function (event) {
    var node = event.target;
    if (node && node.nodeType !== 1) {
      node = node.parentElement;
    }
    if (!node || typeof node.closest !== 'function') {
      return;
    }
    var openBtn = node.closest('[data-post-open]');
    if (openBtn) {
      event.preventDefault();
      posts = loadPosts();
      index = Number(openBtn.getAttribute('data-post-open') || 0);
      var dialog = box();
      if (!dialog || !posts[index]) {
        return;
      }
      if (dialog.showModal) {
        dialog.showModal();
      }
      paint();
      return;
    }
    if (node.closest('[data-post-close]')) {
      var closed = box();
      if (closed && closed.close) {
        closed.close();
      }
      return;
    }
    if (node.closest('[data-post-reader-next]')) {
      event.preventDefault();
      go(index + 1);
      return;
    }
    if (node.closest('[data-post-reader-prev]')) {
      event.preventDefault();
      go(index - 1);
      return;
    }
    var dialogOpen = box();
    if (
      dialogOpen &&
      dialogOpen.open &&
      node.closest('#post-reader-stage') &&
      !node.closest('[data-like-post]')
    ) {
      go(index + 1);
    }
  });
  document.addEventListener(
    'pointerdown',
    function (event) {
      var dialog = box();
      if (!dialog || !dialog.open) {
        return;
      }
      if (!event.target.closest || !event.target.closest('#post-reader-stage')) {
        return;
      }
      dragging = true;
      startY = event.clientY;
      deltaY = 0;
    },
    true
  );
  document.addEventListener(
    'pointermove',
    function (event) {
      if (!dragging) {
        return;
      }
      deltaY = event.clientY - startY;
    },
    true
  );
  document.addEventListener(
    'pointerup',
    function () {
      if (!dragging) {
        return;
      }
      dragging = false;
      if (deltaY < -40) {
        go(index + 1);
      } else if (deltaY > 40) {
        go(index - 1);
      }
    },
    true
  );
}

function bindPostComposer() {
  var form = document.getElementById('post-form');
  var card = document.querySelector('[data-post-create]');
  if (!form || !card || form.getAttribute('data-kb-bound')) {
    return;
  }
  form.setAttribute('data-kb-bound', '1');
  form.addEventListener('submit', function (event) {
    event.preventDefault();
    sendPost(false);
  });

  function sendPost(replace) {
    var file = document.getElementById('post-file').files[0];
    if (!file) {
      return;
    }
    videoDuration(file)
      .then(function (duration) {
        if (duration > 60.4) {
          throw new Error('مدت فیلم پست نباید بیشتر از یک دقیقه باشد.');
        }
        var data = new FormData();
        data.append('media', file);
        data.append('caption', document.getElementById('post-caption').value || '');
        if (replace) {
          data.append('replace', '1');
        }
        return postForm(card.getAttribute('data-post-create'), data);
      })
      .then(function (payload) {
        if (!payload) {
          return;
        }
        if (payload.code === 'cap' && payload.replace_ok) {
          if (window.confirm(payload.message)) {
            sendPost(true);
          }
          return;
        }
        if (!payload.success) {
          showStatus('post-status', payload.message, true);
          return;
        }
        if (window.__kbSoftReload) {
          window.__kbSoftReload();
        } else {
          window.location.reload();
        }
      })
      .catch(function (err) {
        showStatus('post-status', err.message || 'انتشار پست ناموفق بود.', true);
      });
  }
}

function bindSocialActions() {
  document.querySelectorAll('[data-comment-post]').forEach(function (form) {
    if (form.getAttribute('data-kb-bound')) {
      return;
    }
    form.setAttribute('data-kb-bound', '1');
    form.addEventListener('submit', function (event) {
      event.preventDefault();
      var input = form.querySelector('input');
      postForm('/social/posts/' + form.getAttribute('data-comment-post') + '/comment/', {
        text: input.value,
      }).then(function (payload) {
        if (!payload.success) {
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
  if (window.__kbSocialActionsBound) {
    return;
  }
  window.__kbSocialActionsBound = true;
  document.addEventListener('click', function (event) {
    var node = event.target;
    if (!node || typeof node.closest !== 'function') {
      return;
    }
    var like = node.closest('[data-like-post]');
    if (like) {
      postForm('/social/posts/' + like.getAttribute('data-like-post') + '/like/').then(function (payload) {
        if (!payload.success) {
          return;
        }
        var count = like.querySelector('span');
        if (count) {
          count.textContent = String(payload.likes);
        } else {
          like.textContent = 'لایک ' + payload.likes;
        }
        like.classList.toggle('is-on', !!payload.liked);
      });
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
