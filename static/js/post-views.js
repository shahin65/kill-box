(function (win, doc) {
  var RATIO = 0.6;
  var HOLD = 2000;
  var observer = null;
  var timers = {};
  win.__kbPostViewed = win.__kbPostViewed || {};

  function overlayOpen() {
    return doc.body.classList.contains('is-kb-overlay');
  }

  function send(id) {
    if (!id || win.__kbPostViewed[id]) {
      return;
    }
    win.__kbPostViewed[id] = 1;
    if (typeof win.__kbPostForm !== 'function') {
      return;
    }
    win.__kbPostForm('/social/posts/' + id + '/view/').then(function (payload) {
      if (!payload || !payload.success) {
        delete win.__kbPostViewed[id];
        return;
      }
      if (payload.created) {
        doc.querySelectorAll('[data-kb-views="' + id + '"]').forEach(function (node) {
          var label = payload.views_label || String(payload.views || 0);
          var count = node.querySelector('.story-act__count');
          if (count) {
            count.textContent = label;
          } else {
            node.textContent = label;
          }
        });
      }
    });
  }

  function clearTimer(id) {
    if (timers[id]) {
      win.clearTimeout(timers[id]);
      delete timers[id];
    }
  }

  function onEntries(entries) {
    entries.forEach(function (entry) {
      var node = entry.target;
      var id = node.getAttribute('data-kb-view-post');
      if (!id || win.__kbPostViewed[id]) {
        return;
      }
      if (overlayOpen() && !node.closest('#post-reader')) {
        clearTimer(id);
        return;
      }
      if (entry.isIntersecting && entry.intersectionRatio >= RATIO) {
        if (timers[id]) {
          return;
        }
        timers[id] = win.setTimeout(function () {
          delete timers[id];
          send(id);
        }, HOLD);
      } else {
        clearTimer(id);
      }
    });
  }

  function destroy() {
    if (observer) {
      observer.disconnect();
      observer = null;
    }
    Object.keys(timers).forEach(clearTimer);
    timers = {};
  }

  function bind() {
    destroy();
    var nodes = doc.querySelectorAll('[data-kb-view-post]');
    if (!nodes.length || !win.IntersectionObserver) {
      return;
    }
    observer = new IntersectionObserver(onEntries, { threshold: [0, 0.6, 1] });
    nodes.forEach(function (node) {
      observer.observe(node);
    });
  }

  win.__kbBindPostViews = bind;
  win.__kbDestroyPostViews = destroy;
})(window, document);
