(function (win, doc) {
  var PULL = 78;

  function escapeHtml(value) {
    return String(value || '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  function bindReelsViewer() {
    if (win.__kbPostReaderBound) {
      return;
    }
    win.__kbPostReaderBound = true;

    var posts = [];
    var index = 0;
    var observer = null;
    var pulling = false;
    var startY = 0;
    var deltaY = 0;

    function loadPosts() {
      var node = doc.getElementById('post-reader-data');
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
      return doc.getElementById('post-reader');
    }

    function feed() {
      return doc.getElementById('post-reader-stage');
    }

    function slides() {
      var stage = feed();
      return stage ? stage.querySelectorAll('.post-reader__slide') : [];
    }

    function pauseFeedVideos() {
      doc.querySelectorAll('[data-kb-video]').forEach(function (video) {
        if (!box() || !box().contains(video)) {
          if (!video.paused) {
            video.pause();
          }
        }
      });
    }

    function setOpen(on) {
      var dialog = box();
      if (!dialog) {
        return;
      }
      dialog.classList.toggle('is-open', on);
      if (on) {
        dialog.setAttribute('open', '');
        doc.body.classList.add('is-kb-overlay');
      } else {
        dialog.removeAttribute('open');
        if (!win.__kbOverlayKind || !win.__kbOverlayKind()) {
          doc.body.classList.remove('is-kb-overlay');
        }
      }
    }

    function releaseVideo(video) {
      if (!video) {
        return;
      }
      try {
        video.pause();
      } catch (err) {}
      video.muted = true;
      if (video.getAttribute('src')) {
        video.removeAttribute('src');
        try {
          video.load();
        } catch (err2) {}
      }
    }

    function ensureSrc(video, url) {
      if (!video || !url) {
        return;
      }
      if (video.getAttribute('src') !== url) {
        video.setAttribute('src', url);
      }
    }

    function syncSources() {
      var nodes = slides();
      nodes.forEach(function (slide, idx) {
        var video = slide.querySelector('video[data-kb-reel-video]');
        if (!video) {
          return;
        }
        var item = posts[idx];
        var dist = Math.abs(idx - index);
        if (dist > 1) {
          releaseVideo(video);
        } else if (item && item.url) {
          ensureSrc(video, item.url);
        }
      });
    }

    function playCurrent() {
      var nodes = slides();
      nodes.forEach(function (slide, idx) {
        var video = slide.querySelector('video[data-kb-reel-video]');
        if (!video) {
          return;
        }
        if (idx === index) {
          video.playsInline = true;
          if (typeof win.__kbPlayWithSound === 'function') {
            win.__kbPlayWithSound(video);
          } else {
            var play = video.play();
            if (play && play.catch) {
              play.catch(function () {});
            }
          }
        } else if (!video.paused) {
          video.pause();
        }
      });
    }

    function slideMarkup(item, idx) {
      var media = '';
      if (item.url && item.kind === 'video') {
        var poster = item.poster || '';
        var muteHtml = typeof win.__kbMuteMarkup === 'function' ? win.__kbMuteMarkup({ sound: true }) : '';
        media =
          '<div class="kb-media is-video post-reader__media" data-kb-media style="aspect-ratio:9/16;' +
          (poster ? "--kb-poster:url('" + escapeHtml(poster) + "');" : '') +
          '"><video class="kb-media__el" ' +
          (Math.abs(idx - index) <= 1 ? 'src="' + escapeHtml(item.url) + '" ' : '') +
          (poster ? 'poster="' + escapeHtml(poster) + '" ' : '') +
          'playsinline webkit-playsinline preload="auto" data-kb-reel-video data-kb-video></video>' +
          muteHtml +
          '</div>';
      } else if (item.url) {
        media =
          '<div class="kb-media post-reader__media" data-kb-media style="aspect-ratio:9/16">' +
          '<img class="kb-media__el" src="' +
          escapeHtml(item.url) +
          '" alt="" decoding="async" draggable="false"></div>';
      }
      var comments = (item.comment_list || [])
        .map(function (row) {
          return typeof win.__kbCommentMarkup === 'function'
            ? win.__kbCommentMarkup(row)
            : '<li><strong>' + escapeHtml(row.name) + '</strong> ' + escapeHtml(row.text) + '</li>';
        })
        .join('');
      return (
        '<article class="post-reader__slide" data-reel-index="' +
        idx +
        '" data-kb-view-post="' +
        item.id +
        '">' +
        '<div class="post-reader__card">' +
        '<div class="post-reader__user"><img class="post-reader__avatar" src="' +
        escapeHtml(item.avatar || '') +
        '" alt="" width="64" height="64"><span>' +
        escapeHtml(item.name) +
        '</span></div>' +
        media +
        (item.caption ? '<p class="post-reader__caption">' + escapeHtml(item.caption) + '</p>' : '') +
        '<div class="post-reader__bar">' +
        '<button class="story-act story-act--stack' +
        (item.liked ? ' is-on' : '') +
        '" type="button" data-like-post="' +
        item.id +
        '"><svg viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="M12 20.4 10.4 19C5.4 14.4 2 11.3 2 7.6A4.4 4.4 0 0 1 6.4 3.2 4.8 4.8 0 0 1 12 5.6a4.8 4.8 0 0 1 5.6-2.4A4.4 4.4 0 0 1 22 7.6c0 3.7-3.4 6.8-8.4 11.4z"/></svg><span class="story-act__count">' +
        item.likes +
        '</span><span class="story-act__label">پسندیدن</span></button>' +
        '<span class="story-act story-act--stack" data-kb-views="' +
        item.id +
        '"><svg viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="M12 5c5 0 9.3 3.1 11 7-1.7 3.9-6 7-11 7S2.7 15.9 1 12c1.7-3.9 6-7 11-7zm0 3.2A3.8 3.8 0 1 0 15.8 12 3.8 3.8 0 0 0 12 8.2z"/></svg><span class="story-act__count">' +
        escapeHtml(item.views_label || item.views || 0) +
        '</span><span class="story-act__label">بازدید</span></span>' +
        '<button class="story-act story-act--stack' +
        (item.saved ? ' is-on' : '') +
        '" type="button" data-save-post="' +
        item.id +
        '" aria-pressed="' +
        (item.saved ? 'true' : 'false') +
        '"><svg viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="M6 3h12v18l-6-3.4L6 21z"/></svg><span class="story-act__label">ذخیره</span></button></div>' +
        '<ul class="comment-list post-reader__comments">' +
        (comments || '<li>کامنتی نیست.</li>') +
        '</ul>' +
        '<form class="post-reader__comment" data-comment-post="' +
        item.id +
        '"><input type="text" maxlength="280" placeholder="کامنت…"><button class="story-act" type="submit">ارسال</button></form>' +
        '</div></article>'
      );
    }

    function bindSlideVideos() {
      var stage = feed();
      if (!stage) {
        return;
      }
      stage.querySelectorAll('video[data-kb-reel-video]').forEach(function (video) {
        video.loop = false;
        video.muted = false;
        video.defaultMuted = false;
        video.removeAttribute('muted');
        video.playsInline = true;
        video.setAttribute('webkit-playsinline', '');
        video.onended = function () {
          go(index + 1, true);
        };
      });
    }

    function observe() {
      if (observer) {
        observer.disconnect();
      }
      var stage = feed();
      if (!stage || !win.IntersectionObserver) {
        playCurrent();
        return;
      }
      observer = new IntersectionObserver(
        function (entries) {
          var best = index;
          var bestRatio = 0;
          entries.forEach(function (entry) {
            var idx = Number(entry.target.getAttribute('data-reel-index') || 0);
            if (entry.isIntersecting && entry.intersectionRatio >= bestRatio) {
              best = idx;
              bestRatio = entry.intersectionRatio;
            }
          });
          if (bestRatio >= 0.55 && best !== index) {
            index = best;
            syncSources();
            playCurrent();
          } else {
            playCurrent();
          }
        },
        { root: stage, threshold: [0.35, 0.55, 0.75, 1] }
      );
      slides().forEach(function (slide) {
        observer.observe(slide);
      });
    }

    function paint() {
      var stage = feed();
      if (!stage) {
        return;
      }
      stage.innerHTML = posts.map(slideMarkup).join('');
      bindSlideVideos();
      syncSources();
      observe();
      if (typeof win.__kbBindFeedMedia === 'function') {
        win.__kbBindFeedMedia();
      }
      if (typeof win.__kbEnsureCommentExtras === 'function') {
        win.__kbEnsureCommentExtras();
      }
      if (typeof win.__kbBindPostViews === 'function') {
        win.__kbBindPostViews();
      }
    }

    function scrollToIndex(idx, smooth) {
      var nodes = slides();
      var target = nodes[idx];
      if (!target) {
        return;
      }
      target.scrollIntoView({
        behavior: smooth ? 'smooth' : 'auto',
        block: 'start',
      });
    }

    function go(next, smooth) {
      if (!posts.length) {
        return;
      }
      var clamped = Math.max(0, Math.min(posts.length - 1, next));
      if (clamped === index && next > index) {
        return;
      }
      index = clamped;
      syncSources();
      scrollToIndex(index, !!smooth);
      playCurrent();
    }

    function hideViewer(fromHistory) {
      if (observer) {
        observer.disconnect();
        observer = null;
      }
      slides().forEach(function (slide) {
        releaseVideo(slide.querySelector('video'));
      });
      var stage = feed();
      if (stage) {
        stage.innerHTML = '';
      }
      setOpen(false);
      if (typeof win.__kbSyncFeedVideos === 'function') {
        win.__kbSyncFeedVideos();
      }
      if (!fromHistory && win.__kbOverlayKind && win.__kbOverlayKind() === 'reels' && win.__kbOverlayClose) {
        win.__kbOverlayClose();
      }
      if (typeof win.__kbBindPostViews === 'function') {
        win.__kbBindPostViews();
      }
    }

    function closeViewer() {
      if (win.__kbOverlayClose) {
        win.__kbOverlayClose();
        return;
      }
      hideViewer(true);
    }

    function openAt(idx) {
      posts = loadPosts();
      index = Math.max(0, Math.min(posts.length - 1, Number(idx || 0)));
      var dialog = box();
      if (!dialog || !posts[index]) {
        return;
      }
      pauseFeedVideos();
      setOpen(true);
      if (win.__kbOverlayPush) {
        win.__kbOverlayPush('reels', function () {
          hideViewer(true);
        });
      }
      paint();
      win.requestAnimationFrame(function () {
        scrollToIndex(index, false);
        playCurrent();
      });
    }

    function updateSlideMeta(postId, mutator) {
      posts.forEach(function (row, idx) {
        if (String(row.id) !== String(postId)) {
          return;
        }
        mutator(row);
        var slide = feed() && feed().querySelector('[data-reel-index="' + idx + '"]');
        if (!slide) {
          return;
        }
        var btn = slide.querySelector('[data-like-post]');
        var like = btn && (btn.querySelector('.story-act__count') || btn.querySelector('span'));
        if (like) {
          like.textContent = String(row.likes);
        }
        if (btn) {
          btn.classList.toggle('is-on', !!row.liked);
        }
        var saveBtn = slide.querySelector('[data-save-post]');
        if (saveBtn) {
          saveBtn.classList.toggle('is-on', !!row.saved);
          saveBtn.setAttribute('aria-pressed', row.saved ? 'true' : 'false');
        }
        var views = slide.querySelector('[data-kb-views="' + row.id + '"]');
        if (views && row.views_label) {
          var viewCount = views.querySelector('.story-act__count');
          if (viewCount) {
            viewCount.textContent = row.views_label;
          } else {
            views.textContent = row.views_label;
          }
        }
        var list = slide.querySelector('.post-reader__comments');
        if (list && row.comment_list) {
          list.innerHTML = row.comment_list.length
            ? row.comment_list
                .map(function (item) {
                  return typeof win.__kbCommentMarkup === 'function'
                    ? win.__kbCommentMarkup(item)
                    : '<li><strong>' + escapeHtml(item.name) + '</strong> ' + escapeHtml(item.text) + '</li>';
                })
                .join('')
            : '<li>کامنتی نیست.</li>';
        }
      });
    }

    win.__kbPaintPostReader = function () {
      var dialog = box();
      if (dialog && dialog.open) {
        playCurrent();
      }
    };
    win.__kbUpdatePostComments = function (postId, comments) {
      updateSlideMeta(postId, function (row) {
        row.comment_list = comments;
        row.comments = comments.length;
      });
    };
    win.__kbUpdatePostLike = function (postId, payload) {
      updateSlideMeta(postId, function (row) {
        row.liked = payload.liked;
        row.likes = payload.likes;
      });
    };
    win.__kbUpdatePostSave = function (postId, payload) {
      updateSlideMeta(postId, function (row) {
        row.saved = payload.saved;
      });
    };

    doc.addEventListener('click', function (event) {
      var node = event.target;
      if (node && node.nodeType !== 1) {
        node = node.parentElement;
      }
      if (!node || typeof node.closest !== 'function') {
        return;
      }
      if (node.closest('[data-like-post], [data-save-post], [data-comment-post], [data-gif-open], [data-kb-emoji], .home-swipe__nav, .home-swipe__dot, [data-kb-mute]')) {
        return;
      }
      var openBtn = node.closest('[data-post-open]');
      if (openBtn) {
        event.preventDefault();
        event.stopPropagation();
        openAt(openBtn.getAttribute('data-post-open'));
        return;
      }
      if (node.closest('[data-post-close]')) {
        closeViewer();
        return;
      }
      if (node.closest('[data-post-reader-next]')) {
        event.preventDefault();
        go(index + 1, true);
        return;
      }
      if (node.closest('[data-post-reader-prev]')) {
        event.preventDefault();
        go(index - 1, true);
      }
    });

    doc.addEventListener(
      'pointerdown',
      function (event) {
        var dialog = box();
        var stage = feed();
        if (!dialog || !dialog.open || !stage) {
          return;
        }
        if (index !== 0 || stage.scrollTop > 8) {
          return;
        }
        if (!event.target.closest || !event.target.closest('#post-reader-stage')) {
          return;
        }
        if (event.target.closest('[data-like-post], [data-save-post], [data-comment-post], [data-gif-open], [data-kb-emoji], .post-reader__bar, .comment-list, a, [data-kb-mute], input, textarea, .kb-gif-sheet')) {
          return;
        }
        pulling = true;
        startY = event.clientY;
        deltaY = 0;
      },
      true
    );
    doc.addEventListener(
      'pointermove',
      function (event) {
        if (!pulling) {
          return;
        }
        deltaY = event.clientY - startY;
        var dialog = box();
        if (dialog && deltaY > 12) {
          dialog.style.transform = 'translate3d(0,' + Math.min(160, deltaY * 0.55) + 'px,0)';
        }
      },
      true
    );
    function endPull() {
      if (!pulling) {
        return;
      }
      pulling = false;
      var dialog = box();
      if (dialog) {
        dialog.style.transform = '';
      }
      if (deltaY > PULL && index === 0) {
        closeViewer();
      }
    }
    doc.addEventListener('pointerup', endPull, true);
    doc.addEventListener('pointercancel', endPull, true);
    doc.addEventListener('keydown', function (event) {
      var dialog = box();
      if (!dialog || !dialog.open) {
        return;
      }
      if (event.key === 'Escape') {
        event.preventDefault();
        closeViewer();
      }
      if (event.key === 'ArrowDown') {
        event.preventDefault();
        go(index + 1, true);
      }
      if (event.key === 'ArrowUp') {
        event.preventDefault();
        go(index - 1, true);
      }
    });
  }

  win.__kbBindReelsViewer = bindReelsViewer;
})(window, document);
