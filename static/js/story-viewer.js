(function (win, doc) {
  var HOLD_MS = 180;
  var TAP_X = 0.35;
  var SWIPE_X = 56;
  var SWIPE_Y = 72;
  var MOVE = 22;

  function escapeHtml(value) {
    return String(value || '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  function bindStoryViewer() {
    if (win.__kbStoryViewerBound) {
      return;
    }
    win.__kbStoryViewerBound = true;

    var groups = [];
    var groupIndex = 0;
    var itemIndex = 0;
    var duration = 5000;
    var elapsed = 0;
    var paused = false;
    var mediaReady = false;
    var holding = false;
    var pressAt = 0;
    var pressX = 0;
    var pressY = 0;
    var moveX = 0;
    var moveY = 0;
    var raf = 0;
    var lastTs = 0;
    var tickGen = 0;

    function dialog() {
      var nodes = doc.querySelectorAll('#story-viewer');
      var box = nodes.length ? nodes[nodes.length - 1] : null;
      if (!box) {
        return null;
      }
      nodes.forEach(function (node) {
        if (node !== box) {
          node.remove();
        }
      });
      if (box.parentElement !== doc.body) {
        doc.body.appendChild(box);
      }
      return box;
    }

    function frame() {
      var box = dialog();
      return box ? box.querySelector('.story-viewer__frame') : null;
    }

    function loadGroups() {
      var dataNode = doc.getElementById('story-data');
      if (!dataNode) {
        return [];
      }
      try {
        return JSON.parse(dataNode.textContent || '[]');
      } catch (err) {
        return [];
      }
    }

    function currentGroup() {
      return groups[groupIndex] || null;
    }

    function currentItem() {
      var group = currentGroup();
      return group && group.stories ? group.stories[itemIndex] : null;
    }

    function unseenIndexes(group) {
      var idxs = [];
      ((group && group.stories) || []).forEach(function (row, idx) {
        if (!row.seen) {
          idxs.push(idx);
        }
      });
      return idxs;
    }

    function storyVideo() {
      return doc.querySelector('#story-stage video');
    }

    function stopTick() {
      if (raf) {
        win.cancelAnimationFrame(raf);
        raf = 0;
      }
      lastTs = 0;
    }

    function releaseMedia() {
      stopTick();
      var video = storyVideo();
      if (!video) {
        return;
      }
      try {
        video.pause();
      } catch (err) {}
      video.removeAttribute('src');
      try {
        video.load();
      } catch (err2) {}
    }

    function pauseFeedVideos() {
      doc.querySelectorAll('[data-kb-video]').forEach(function (video) {
        if (!video.paused) {
          video.pause();
        }
      });
    }

    function setOpen(on) {
      var box = dialog();
      if (!box) {
        return;
      }
      box.classList.toggle('is-open', on);
      box.classList.toggle('is-paused', false);
      if (on) {
        box.setAttribute('open', '');
        doc.body.classList.add('is-kb-overlay');
      } else {
        box.removeAttribute('open');
        if (!win.__kbOverlayKind || !win.__kbOverlayKind()) {
          doc.body.classList.remove('is-kb-overlay');
        }
      }
    }

    function paintLike(item) {
      var btn = doc.getElementById('story-like');
      var count = doc.getElementById('story-like-count');
      if (count) {
        count.textContent = String(item.likes || 0);
      }
      if (btn) {
        btn.classList.toggle('is-on', !!item.liked);
      }
    }

    function paintComments(item) {
      var box = doc.getElementById('story-comments');
      if (!box) {
        return;
      }
      var rows = item.comments || [];
      box.hidden = !rows.length;
      box.innerHTML = rows
        .map(function (row) {
          var gif = '';
          if (row.gif_url) {
            gif =
              '<span class="kb-gif"><img src="' +
              escapeHtml(row.gif_preview_url || row.gif_url) +
              '" alt="' +
              escapeHtml(row.alt || 'GIF') +
              '" loading="lazy" decoding="async"></span>';
          }
          return (
            '<p class="kb-comment"><img class="kb-comment__avatar" src="' +
            escapeHtml(row.avatar || '/static/images/icons/profile2.webp') +
            '" alt=""><span class="kb-comment__body"><strong>' +
            escapeHtml(row.name) +
            '</strong> ' +
            escapeHtml(row.text) +
            gif +
            '</span></p>'
          );
        })
        .join('');
    }

    function paintUser() {
      var group = currentGroup();
      var name = doc.getElementById('story-user-name');
      var avatar = doc.getElementById('story-user-avatar');
      if (!group) {
        return;
      }
      if (name) {
        name.textContent = group.name || '';
      }
      if (avatar) {
        avatar.src = group.avatar || group.cover || avatar.getAttribute('data-fallback') || avatar.src;
      }
    }

    var viewersOffset = 0;

    function paintViews(item) {
      var group = currentGroup();
      var btn = doc.getElementById('story-views');
      var count = doc.getElementById('story-view-count');
      var mine = !!(group && group.mine);
      if (count) {
        count.textContent = String((item && (item.views_label || item.views)) || 0);
      }
      if (btn) {
        btn.hidden = !mine;
      }
    }

    function closeViewers() {
      var box = doc.getElementById('story-viewers');
      if (box) {
        box.hidden = true;
      }
    }

    function loadViewers(reset) {
      var item = currentItem();
      var group = currentGroup();
      var list = doc.getElementById('story-viewers-list');
      var more = doc.getElementById('story-viewers-more');
      var panel = doc.getElementById('story-viewers');
      if (!item || !group || !group.mine || !list || !panel) {
        return;
      }
      if (reset) {
        viewersOffset = 0;
        list.innerHTML = '';
      }
      panel.hidden = false;
      fetch('/social/stories/' + item.id + '/viewers/?offset=' + viewersOffset, {
        headers: { Accept: 'application/json', 'X-Requested-With': 'XMLHttpRequest' },
        credentials: 'same-origin',
      })
        .then(function (response) {
          return response.json();
        })
        .then(function (payload) {
          if (!payload.success) {
            return;
          }
          (payload.viewers || []).forEach(function (row) {
            list.insertAdjacentHTML(
              'beforeend',
              '<div class="kb-viewers__row"><img src="' +
                escapeHtml(row.avatar || '') +
                '" alt="" width="40" height="40"><div><strong>' +
                escapeHtml(row.name) +
                '</strong><small>@' +
                escapeHtml(row.username) +
                '</small></div></div>'
            );
          });
          viewersOffset += (payload.viewers || []).length;
          if (more) {
            more.hidden = !payload.has_more;
          }
        });
    }

    function paintRings() {
      doc.querySelectorAll('[data-story-open]').forEach(function (btn) {
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

    function csrfToken() {
      var node = doc.querySelector('[name=csrfmiddlewaretoken]');
      if (node && node.value) {
        return node.value;
      }
      var match = doc.cookie.match(/(?:^|; )csrftoken=([^;]+)/);
      return match ? decodeURIComponent(match[1]) : '';
    }

    function watchMsOf(item) {
      var video = storyVideo();
      var fromVideo = 0;
      if (video && video.currentTime) {
        fromVideo = Math.round(video.currentTime * 1000);
      }
      return Math.max(item._kbWatchMs || 0, elapsed || 0, fromVideo);
    }

    function qualifies(item) {
      if (!item) {
        return false;
      }
      var ms = watchMsOf(item);
      item._kbWatchMs = ms;
      var video = storyVideo();
      if (video && video.duration && isFinite(video.duration) && video.duration > 0) {
        item._kbCompleted = video.currentTime / video.duration >= 0.9;
        if (video.currentTime >= 2) {
          return true;
        }
        if (video.duration >= 8 && video.currentTime / video.duration >= 0.25) {
          return true;
        }
      }
      return ms >= 2000;
    }

    function sendSeen(item, keepalive) {
      if (!item || item._kbViewSent || !qualifies(item)) {
        return;
      }
      if (doc.body.getAttribute('data-kb-member') !== '1') {
        return;
      }
      item._kbViewSent = true;
      item.seen = true;
      paintRings();
      var body =
        'csrfmiddlewaretoken=' +
        encodeURIComponent(csrfToken()) +
        '&watch_ms=' +
        encodeURIComponent(String(Math.round(item._kbWatchMs || 0))) +
        '&completed=' +
        (item._kbCompleted ? '1' : '0');
      var url = '/social/stories/' + item.id + '/seen/';
      if (keepalive && navigator.sendBeacon) {
        try {
          navigator.sendBeacon(url, new Blob([body], { type: 'application/x-www-form-urlencoded' }));
          return;
        } catch (err) {}
      }
      if (typeof win.__kbPostForm === 'function' && !keepalive) {
        win.__kbPostForm(url, {
          watch_ms: String(Math.round(item._kbWatchMs || 0)),
          completed: item._kbCompleted ? '1' : '0',
        });
        return;
      }
      fetch(url, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/x-www-form-urlencoded',
          'X-CSRFToken': csrfToken(),
          'X-Requested-With': 'XMLHttpRequest',
        },
        body: body,
        credentials: 'same-origin',
        keepalive: !!keepalive,
      }).catch(function () {});
    }

    function flushSeen(keepalive) {
      sendSeen(currentItem(), keepalive);
    }

    function setBarFill(ratio) {
      var active = doc.querySelector('#story-bars i.is-active');
      if (active) {
        active.style.transform = 'scaleX(' + Math.max(0, Math.min(1, ratio)) + ')';
      }
    }

    function armProgress(ms) {
      duration = Math.max(800, ms || 5000);
      elapsed = 0;
      var bars = doc.getElementById('story-bars');
      var group = currentGroup();
      if (!bars || !group) {
        return;
      }
      bars.innerHTML = (group.stories || [])
        .map(function (_, idx) {
          var cls = idx < itemIndex ? 'is-done' : idx === itemIndex ? 'is-active' : '';
          return '<span><i class="' + cls + '"></i></span>';
        })
        .join('');
      setBarFill(0);
    }

    function tick(ts) {
      if (paused) {
        lastTs = ts;
        raf = win.requestAnimationFrame(tick);
        return;
      }
      if (!lastTs) {
        lastTs = ts;
      }
      elapsed += ts - lastTs;
      lastTs = ts;
      var item = currentItem();
      if (item) {
        item._kbWatchMs = Math.max(item._kbWatchMs || 0, elapsed);
        if (!item._kbViewSent && qualifies(item)) {
          sendSeen(item, false);
        }
      }
      var fill = duration ? elapsed / duration : 1;
      setBarFill(fill);
      if (fill >= 1) {
        stopTick();
        next();
        return;
      }
      raf = win.requestAnimationFrame(tick);
    }

    function startTick() {
      stopTick();
      var gen = (tickGen += 1);
      raf = win.requestAnimationFrame(function (ts) {
        if (gen !== tickGen) {
          return;
        }
        lastTs = ts;
        tick(ts);
      });
    }

    function pauseStory() {
      if (paused) {
        return;
      }
      paused = true;
      var box = dialog();
      if (box) {
        box.classList.add('is-paused');
      }
      var video = storyVideo();
      if (video && !video.paused) {
        video.pause();
      }
    }

    function gifSheetOpen() {
      var sheet = doc.getElementById('kb-gif-sheet');
      return !!(sheet && sheet.classList.contains('is-open') && !sheet.hidden);
    }

    function commentBusy() {
      var active = doc.activeElement;
      return !!(
        gifSheetOpen() ||
        (active && typeof active.closest === 'function' && active.closest('#story-comment-form'))
      );
    }

    function tryResumeStory() {
      if (!mediaReady || commentBusy()) {
        return;
      }
      resumeStory();
    }

    function resumeStory() {
      if (!paused) {
        return;
      }
      if (!mediaReady || commentBusy()) {
        return;
      }
      paused = false;
      var box = dialog();
      if (box) {
        box.classList.remove('is-paused');
      }
      playStoryVideo();
      if (!raf) {
        startTick();
      }
    }

    function setStageLoading(on) {
      var stage = doc.getElementById('story-stage');
      var box = dialog();
      if (stage) {
        stage.classList.toggle('is-loading', !!on);
      }
      if (box) {
        box.classList.toggle('is-loading', !!on);
      }
    }

    function waitForStoryMedia(stage, done) {
      var img = stage ? stage.querySelector('img.kb-media__el') : null;
      var video = stage ? stage.querySelector('video') : null;
      var settled = false;
      var timer = 0;
      function finish() {
        if (settled) {
          return;
        }
        settled = true;
        if (timer) {
          win.clearTimeout(timer);
        }
        setStageLoading(false);
        done();
      }
      setStageLoading(true);
      if (img) {
        if (img.complete && img.naturalWidth) {
          finish();
          return;
        }
        img.addEventListener('load', finish, { once: true });
        img.addEventListener('error', finish, { once: true });
        timer = win.setTimeout(finish, 12000);
        return;
      }
      if (video) {
        if (video.readyState >= 3) {
          finish();
          return;
        }
        video.addEventListener('canplay', finish, { once: true });
        video.addEventListener('loadeddata', finish, { once: true });
        video.addEventListener('error', finish, { once: true });
        timer = win.setTimeout(finish, 15000);
        return;
      }
      finish();
    }

    function playStoryVideo() {
      var video = storyVideo();
      if (!video) {
        return;
      }
      video.muted = false;
      video.defaultMuted = false;
      video.removeAttribute('muted');
      if (typeof win.__kbPlayWithSound === 'function') {
        win.__kbPlayWithSound(video);
        return;
      }
      var play = video.play();
      if (play && play.catch) {
        play.catch(function () {});
      }
    }

    function showItem() {
      var box = dialog();
      var item = currentItem();
      if (!box || !item) {
        closeViewer();
        return;
      }
      mediaReady = false;
      paused = true;
      holding = false;
      box.classList.add('is-paused');
      releaseMedia();
      pauseFeedVideos();
      stopTick();
      var stage = doc.getElementById('story-stage');
      var poster = item.poster || '';
      var muteHtml = typeof win.__kbMuteMarkup === 'function' ? win.__kbMuteMarkup({ sound: true }) : '';
      if (item.kind === 'video') {
        duration = Math.max(1000, Math.round((Number(item.duration) || 15) * 1000));
        stage.innerHTML =
          '<div class="kb-media is-video is-story" data-kb-media style="aspect-ratio:9/16;' +
          (poster ? "--kb-poster:url('" + escapeHtml(poster) + "');" : '') +
          '"><video class="kb-media__el" src="' +
          escapeHtml(item.url) +
          '"' +
          (poster ? ' poster="' + escapeHtml(poster) + '"' : '') +
          ' playsinline webkit-playsinline preload="auto" data-kb-story-video data-kb-video></video>' +
          muteHtml +
          '</div>';
        var video = stage.querySelector('video');
        if (video) {
          video.playsInline = true;
          video.setAttribute('webkit-playsinline', '');
          video.onloadedmetadata = function () {
            if (!video.duration || !isFinite(video.duration)) {
              return;
            }
            duration = Math.max(1000, Math.round(video.duration * 1000));
            armProgress(duration);
          };
          video.onended = function () {
            next();
          };
        }
      } else {
        duration = 5000;
        stage.innerHTML =
          '<div class="kb-media is-story" data-kb-media style="aspect-ratio:9/16">' +
          '<img class="kb-media__el" src="' +
          escapeHtml(item.url) +
          '" alt="" decoding="async" draggable="false"></div>';
      }
      paintUser();
      var overlay = doc.getElementById('story-overlay-text');
      if (overlay) {
        overlay.textContent = item.overlay || '';
      }
      paintLike(item);
      paintComments(item);
      paintViews(item);
      armProgress(duration);
      if (typeof win.__kbBindFeedMedia === 'function') {
        win.__kbBindFeedMedia();
      }
      if (typeof win.__kbEnsureCommentExtras === 'function') {
        win.__kbEnsureCommentExtras();
      }
      waitForStoryMedia(stage, function () {
        var now = currentItem();
        if (!now || now.id !== item.id) {
          return;
        }
        mediaReady = true;
        holding = false;
        tryResumeStory();
      });
    }

    function hideViewer(fromHistory) {
      flushSeen(true);
      closeViewers();
      tickGen += 1;
      stopTick();
      releaseMedia();
      mediaReady = false;
      paused = false;
      holding = false;
      var sheet = frame();
      if (sheet) {
        sheet.style.transform = '';
      }
      setOpen(false);
      if (typeof win.__kbSyncFeedVideos === 'function') {
        win.__kbSyncFeedVideos();
      }
      if (!fromHistory && win.__kbOverlayKind && win.__kbOverlayKind() === 'story' && win.__kbOverlayClose) {
        win.__kbOverlayClose();
      }
    }

    function closeViewer() {
      if (win.__kbOverlayClose) {
        win.__kbOverlayClose();
        return;
      }
      hideViewer(true);
    }

    function next() {
      flushSeen(true);
      var group = currentGroup();
      if (!group) {
        return;
      }
      if (itemIndex + 1 < group.stories.length) {
        itemIndex += 1;
        showItem();
        return;
      }
      if (groupIndex + 1 < groups.length) {
        groupIndex += 1;
        itemIndex = 0;
        showItem();
        return;
      }
      closeViewer();
    }

    function prev() {
      flushSeen(true);
      if (itemIndex > 0) {
        itemIndex -= 1;
        showItem();
        return true;
      }
      if (groupIndex > 0) {
        groupIndex -= 1;
        itemIndex = Math.max(0, groups[groupIndex].stories.length - 1);
        showItem();
        return true;
      }
      return false;
    }

    function nextGroup() {
      flushSeen(true);
      if (groupIndex + 1 < groups.length) {
        groupIndex += 1;
        itemIndex = unseenIndexes(groups[groupIndex])[0] || 0;
        showItem();
        return;
      }
      closeViewer();
    }

    function prevGroup() {
      flushSeen(true);
      if (groupIndex > 0) {
        groupIndex -= 1;
        itemIndex = 0;
        showItem();
      }
    }

    function openAt(idx) {
      groups = loadGroups();
      groupIndex = Number(idx || 0);
      if (!groups[groupIndex]) {
        return;
      }
      var unseen = unseenIndexes(groups[groupIndex]);
      itemIndex = unseen.length ? unseen[0] : 0;
      setOpen(true);
      if (win.__kbOverlayPush) {
        win.__kbOverlayPush('story', function () {
          hideViewer(true);
        });
      }
      showItem();
    }

    function isChrome(node) {
      return !!(
        node.closest('.story-viewer__dock') ||
        node.closest('.story-viewer__actions') ||
        node.closest('[data-story-close]') ||
        node.closest('.story-viewer__comments') ||
        node.closest('.story-viewer__user') ||
        node.closest('#story-views') ||
        node.closest('.kb-viewers') ||
        node.closest('[data-kb-mute]') ||
        node.closest('[data-kb-emoji]') ||
        node.closest('[data-gif-open]') ||
        node.closest('.kb-emoji-bar') ||
        node.closest('.kb-gif-chip') ||
        node.closest('.kb-gif-sheet')
      );
    }

    doc.addEventListener('click', function (event) {
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
        event.stopPropagation();
        openAt(openBtn.getAttribute('data-story-open'));
        return;
      }
      if (node.closest('[data-story-close]')) {
        closeViewer();
        return;
      }
      if (node.closest('[data-viewers-close]')) {
        closeViewers();
        return;
      }
      if (node.closest('#story-viewers-more')) {
        loadViewers(false);
        return;
      }
      if (node.closest('#story-views') || node.closest('[data-story-viewers]')) {
        loadViewers(true);
        return;
      }
      if (node.closest('#story-like')) {
        var item = currentItem();
        if (!item || typeof win.__kbPostForm !== 'function') {
          return;
        }
        win.__kbPostForm('/social/stories/' + item.id + '/like/').then(function (payload) {
          if (!payload.success) {
            if (typeof win.__kbFlashSocial === 'function') {
              win.__kbFlashSocial(payload.message || 'لایک انجام نشد.');
            }
            return;
          }
          item.liked = payload.liked;
          item.likes = payload.likes;
          paintLike(item);
        });
      }
    });

    doc.addEventListener('pointerdown', function (event) {
      var box = dialog();
      var node = event.target;
      if (!box || !box.open || !node || typeof node.closest !== 'function') {
        return;
      }
      if (isChrome(node)) {
        return;
      }
      if (
        !node.closest('#story-stage') &&
        !node.closest('.story-viewer__canvas') &&
        !node.closest('.story-viewer__overlay') &&
        !node.closest('.story-viewer__bars')
      ) {
        return;
      }
      holding = true;
      pressAt = Date.now();
      pressX = event.clientX;
      pressY = event.clientY;
      moveX = 0;
      moveY = 0;
      try {
        event.preventDefault();
      } catch (err) {}
      pauseStory();
    });

    doc.addEventListener('pointermove', function (event) {
      if (!holding) {
        return;
      }
      moveX = event.clientX - pressX;
      moveY = event.clientY - pressY;
      var sheet = frame();
      if (sheet && moveY > MOVE && Math.abs(moveY) > Math.abs(moveX)) {
        sheet.style.transform = 'translate3d(0,' + Math.min(140, moveY * 0.72) + 'px,0)';
        sheet.style.opacity = String(Math.max(0.45, 1 - moveY / 420));
      }
    });

    function endHold(event) {
      if (!holding) {
        return;
      }
      holding = false;
      var sheet = frame();
      if (sheet) {
        sheet.style.transform = '';
        sheet.style.opacity = '';
      }
      var held = Date.now() - pressAt;
      var dx = event && typeof event.clientX === 'number' ? event.clientX - pressX : moveX;
      var dy = event && typeof event.clientY === 'number' ? event.clientY - pressY : moveY;
      if (dy > SWIPE_Y && Math.abs(dy) > Math.abs(dx)) {
        closeViewer();
        return;
      }
      if (Math.abs(dx) > SWIPE_X && Math.abs(dx) > Math.abs(dy)) {
        if (dx < 0) {
          nextGroup();
        } else {
          prevGroup();
        }
        return;
      }
      if (held < HOLD_MS && Math.abs(dx) < MOVE && Math.abs(dy) < MOVE) {
        var stage = doc.getElementById('story-stage');
        var rect = stage ? stage.getBoundingClientRect() : { left: 0, width: win.innerWidth };
        var x = pressX - rect.left;
        if (x < rect.width * TAP_X) {
          if (!prev()) {
            resumeStory();
          }
        } else {
          next();
        }
        return;
      }
      tryResumeStory();
    }

    doc.addEventListener('pointerup', endHold);
    doc.addEventListener('pointercancel', endHold);
    doc.addEventListener('keydown', function (event) {
      var box = dialog();
      if (!box || !box.open || event.key !== 'Escape') {
        return;
      }
      event.preventDefault();
      closeViewer();
    });
    doc.addEventListener('kb-gif-open', function () {
      var box = dialog();
      if (box && box.open) {
        pauseStory();
      }
    });
    doc.addEventListener('kb-gif-close', function () {
      tryResumeStory();
    });
    doc.addEventListener('focusin', function (event) {
      var box = dialog();
      if (!box || !box.open || !event.target || typeof event.target.closest !== 'function') {
        return;
      }
      if (event.target.closest('#story-comment-form')) {
        pauseStory();
      }
    });
    doc.addEventListener('focusout', function (event) {
      win.setTimeout(function () {
        tryResumeStory();
      }, 0);
    });
    doc.addEventListener('submit', function (event) {
      if (!event.target || event.target.id !== 'story-comment-form') {
        return;
      }
      event.preventDefault();
      var item = currentItem();
      var form = event.target;
      var input = doc.getElementById('story-comment');
      var gifField = form.querySelector('[name="gif_id"]');
      var gifId = gifField ? gifField.value : '';
      if (!item || typeof win.__kbPostForm !== 'function') {
        return;
      }
      if ((!input || !input.value.trim()) && !gifId) {
        return;
      }
      win.__kbPostForm('/social/stories/' + item.id + '/comment/', {
        text: input ? input.value : '',
        gif_id: gifId,
      }).then(function (payload) {
        if (!payload.success) {
          if (typeof win.__kbFlashSocial === 'function') {
            win.__kbFlashSocial(payload.message || 'کامنت ارسال نشد.');
          }
          return;
        }
        item.comments = payload.comments;
        if (input) {
          input.value = '';
        }
        if (typeof win.__kbClearGifChip === 'function') {
          win.__kbClearGifChip(form);
        }
        paintComments(item);
      });
    });
    win.addEventListener('pagehide', function () {
      flushSeen(true);
    });
    doc.addEventListener('visibilitychange', function () {
      if (doc.hidden) {
        flushSeen(true);
      }
    });
  }

  win.__kbBindStoryViewer = bindStoryViewer;
})(window, document);
