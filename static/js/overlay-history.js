(function (win) {
  var kind = null;
  var closer = null;
  var closing = false;

  function push(nextKind, closeFn) {
    closer = closeFn || closer;
    if (kind) {
      kind = nextKind;
      try {
        win.history.replaceState({ kbNav: 1, kbOverlay: nextKind }, '', win.location.href);
      } catch (err) {}
      return;
    }
    kind = nextKind;
    try {
      if (!win.__kbHist) {
        win.history.replaceState({ kbNav: 1 }, '', win.location.href);
        win.__kbHist = true;
      }
      win.history.pushState({ kbNav: 1, kbOverlay: nextKind }, '', win.location.href);
    } catch (err) {}
  }

  function finishClose() {
    var fn = closer;
    kind = null;
    closer = null;
    if (typeof fn === 'function') {
      fn();
    }
  }

  function closeFromUi() {
    if (!kind && !closing) {
      return false;
    }
    finishClose();
    closing = true;
    try {
      win.history.back();
    } catch (err) {
      closing = false;
    }
    return true;
  }

  win.__kbOverlayPush = push;
  win.__kbOverlayClose = closeFromUi;
  win.__kbOverlayKind = function () {
    return kind;
  };
  win.__kbOverlayPop = function (event) {
    if (closing) {
      closing = false;
      return true;
    }
    var state = event && event.state;
    if (kind && !(state && state.kbOverlay)) {
      finishClose();
      return true;
    }
    return false;
  };
})(window);
