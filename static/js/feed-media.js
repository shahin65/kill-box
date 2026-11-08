(function (win, doc) {
  var observer = null;

  function mediaWrap(node) {
    return node && node.closest ? node.closest('[data-kb-media]') : null;
  }

  function markReady(wrap) {
    if (wrap) {
      wrap.classList.add('is-ready');
    }
  }

  function bindShimmer() {
    doc.querySelectorAll('[data-kb-media]').forEach(function (wrap) {
      if (wrap.getAttribute('data-kb-img-bound')) {
        return;
      }
      wrap.setAttribute('data-kb-img-bound', '1');
      var img = wrap.querySelector('img.kb-media__el');
      var video = wrap.querySelector('video.kb-media__el');
      if (img) {
        if (img.complete && img.naturalWidth) {
          markReady(wrap);
        } else {
          img.addEventListener('load', function () {
            markReady(wrap);
          });
          img.addEventListener('error', function () {
            markReady(wrap);
          });
        }
      }
      if (video) {
        if (video.readyState >= 2 || wrap.style.getPropertyValue('--kb-poster')) {
          markReady(wrap);
        }
        video.addEventListener('loadeddata', function () {
          markReady(wrap);
        });
        video.addEventListener('error', function () {
          markReady(wrap);
        });
      }
    });
  }

  function tryPlay(video) {
    if (!video || !video.paused) {
      return;
    }
    var play = video.play();
    if (play && play.catch) {
      play.catch(function () {});
    }
  }

  function overlayOpen() {
    var reader = doc.getElementById('post-reader');
    var story = doc.getElementById('story-viewer');
    return {
      reader: !!(reader && (reader.open || reader.classList.contains('is-open'))),
      story: !!(story && (story.open || story.classList.contains('is-open'))),
      readerNode: reader,
      storyNode: story,
    };
  }

  function inOpenOverlay(video, state) {
    if (state.reader && state.readerNode && state.readerNode.contains(video)) {
      return true;
    }
    if (state.story && state.storyNode && state.storyNode.contains(video)) {
      return true;
    }
    return false;
  }

  function syncFeedVideos() {
    var state = overlayOpen();
    var videos = doc.querySelectorAll('[data-kb-video]');
    var best = null;
    var bestRatio = 0;
    videos.forEach(function (video) {
      if (state.reader || state.story) {
        if (!inOpenOverlay(video, state)) {
          return;
        }
      }
      var ratio = video._kbRatio || 0;
      if (ratio >= 0.6 && ratio > bestRatio) {
        best = video;
        bestRatio = ratio;
      }
    });
    videos.forEach(function (video) {
      if (video === best) {
        tryPlay(video);
      } else if (!video.paused) {
        video.pause();
      }
    });
  }

  function bindVideos() {
    if (observer) {
      observer.disconnect();
    }
    observer = new IntersectionObserver(
      function (entries) {
        entries.forEach(function (entry) {
          entry.target._kbRatio = entry.intersectionRatio;
        });
        syncFeedVideos();
      },
      { threshold: [0, 0.25, 0.6, 0.75, 1], rootMargin: '0px' }
    );
    var state = overlayOpen();
    doc.querySelectorAll('[data-kb-video]').forEach(function (video) {
      video.muted = true;
      video.defaultMuted = true;
      video.playsInline = true;
      video.setAttribute('webkit-playsinline', '');
      video.preload = 'metadata';
      video.loop = !video.hasAttribute('data-kb-reel-video');
      if (inOpenOverlay(video, state)) {
        video._kbRatio = 1;
      }
      observer.observe(video);
    });
    syncFeedVideos();
  }

  function setMuteState(video, button, muted) {
    video.muted = muted;
    button.classList.toggle('is-muted', muted);
    button.setAttribute('aria-pressed', muted ? 'true' : 'false');
    button.title = muted ? 'صدا' : 'بی‌صدا';
  }

  function bindMute() {
    if (win.__kbMuteBound) {
      return;
    }
    win.__kbMuteBound = true;
    doc.addEventListener(
      'click',
      function (event) {
        var btn = event.target && event.target.closest ? event.target.closest('[data-kb-mute]') : null;
        if (!btn) {
          return;
        }
        event.preventDefault();
        event.stopPropagation();
        var wrap = mediaWrap(btn);
        var video = wrap ? wrap.querySelector('video') : null;
        if (!video) {
          return;
        }
        setMuteState(video, btn, !video.muted);
        if (!video.muted) {
          tryPlay(video);
        }
      },
      true
    );
  }

  function extractVideoPoster(file) {
    if (!file || !String(file.type || '').startsWith('video/')) {
      return Promise.resolve(null);
    }
    return new Promise(function (resolve) {
      var video = doc.createElement('video');
      var url = URL.createObjectURL(file);
      var done = function (blob) {
        URL.revokeObjectURL(url);
        resolve(blob || null);
      };
      video.muted = true;
      video.playsInline = true;
      video.preload = 'auto';
      video.onloadeddata = function () {
        try {
          video.currentTime = Math.min(0.18, (video.duration || 1) * 0.04);
        } catch (err) {
          done(null);
        }
      };
      video.onseeked = function () {
        try {
          var canvas = doc.createElement('canvas');
          var width = video.videoWidth || 720;
          var height = video.videoHeight || 900;
          var maxSide = 720;
          var scale = Math.min(1, maxSide / Math.max(width, height));
          canvas.width = Math.max(32, Math.round(width * scale));
          canvas.height = Math.max(32, Math.round(height * scale));
          canvas.getContext('2d').drawImage(video, 0, 0, canvas.width, canvas.height);
          if (canvas.toBlob) {
            canvas.toBlob(done, 'image/webp', 0.8);
          } else {
            done(null);
          }
        } catch (err) {
          done(null);
        }
      };
      video.onerror = function () {
        done(null);
      };
      win.setTimeout(function () {
        if (!video.videoWidth) {
          done(null);
        }
      }, 4000);
      video.src = url;
    });
  }

  function mediaMarkup(item, opts) {
    opts = opts || {};
    var ratio = opts.ratio || '4/5';
    var extra = opts.className || '';
    var loop = opts.loop !== false;
    var lazy = opts.lazy !== false;
    var poster = item.poster || '';
    var videoAttrs =
      ' muted playsinline webkit-playsinline preload="metadata"' + (loop ? ' loop' : '');
    if (item.kind === 'video') {
      return (
        '<div class="kb-media is-video ' +
        extra +
        '" data-kb-media style="aspect-ratio:' +
        ratio +
        ';' +
        (poster ? "--kb-poster:url('" + escapeAttr(poster) + "');" : '') +
        '">' +
        '<video class="kb-media__el" src="' +
        escapeAttr(item.url) +
        '"' +
        (poster ? ' poster="' + escapeAttr(poster) + '"' : '') +
        videoAttrs +
        ' data-kb-video></video>' +
        muteMarkup() +
        '</div>'
      );
    }
    return (
      '<div class="kb-media ' +
      extra +
      '" data-kb-media style="aspect-ratio:' +
      ratio +
      '">' +
      '<img class="kb-media__el" src="' +
      escapeAttr(item.url) +
      '" alt=""' +
      (lazy ? ' loading="lazy"' : '') +
      ' decoding="async" draggable="false">' +
      '</div>'
    );
  }

  function muteMarkup() {
    return (
      '<button class="kb-mute is-muted" type="button" data-kb-mute aria-pressed="true" title="صدا">' +
      '<svg class="kb-mute__off" viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="M4.3 3.3 3 4.6 7.4 9H3v6h4l5 5V8.6l5.4 5.4A6 6 0 0 1 17 18.9l1.4 1.4A8 8 0 0 0 21 12c0-1.4-.4-2.8-1-4l1.7-1.7-1.4-1.4zM14 3.2v2.1a6 6 0 0 1 4 4.7l2 .5A8 8 0 0 0 14 3.2zM12 7.2 9.8 9.4 12 11.6z"/></svg>' +
      '<svg class="kb-mute__on" viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="M3 9v6h4l5 5V4L7 9zm11 3a2.8 2.8 0 0 0-1.6-2.5v5A2.8 2.8 0 0 0 14 12zm0-7.8v2.1a6 6 0 0 1 0 11.4v2.1a8 8 0 0 0 0-15.6z"/></svg>' +
      '</button>'
    );
  }

  function escapeAttr(value) {
    return String(value || '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/"/g, '&quot;');
  }

  function bindFeedMedia() {
    bindShimmer();
    bindVideos();
    bindMute();
  }

  win.__kbBindFeedMedia = bindFeedMedia;
  win.__kbMediaMarkup = mediaMarkup;
  win.__kbExtractVideoPoster = extractVideoPoster;
  win.__kbSyncFeedVideos = syncFeedVideos;
  win.__kbMuteMarkup = muteMarkup;
})(window, document);
