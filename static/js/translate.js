(function () {
  var allowed = { fa: true, en: true, ar: true, tr: true, ru: true, es: true };

  function readLang() {
    var match = document.cookie.match(/(?:^|; )googtrans=\/fa\/([^;]+)/);
    if (match && allowed[match[1]]) {
      return match[1];
    }
    try {
      var stored = localStorage.getItem('kb-lang') || 'fa';
      return allowed[stored] ? stored : 'fa';
    } catch (err) {
      return 'fa';
    }
  }

  function writeCookie(value) {
    document.cookie = value + '; path=/';
  }

  function setLang(code) {
    if (!allowed[code]) {
      return;
    }
    try {
      localStorage.setItem('kb-lang', code);
    } catch (err) {
      /* ignore */
    }
    if (code === 'fa') {
      writeCookie('googtrans=; Max-Age=0');
    } else {
      writeCookie('googtrans=/fa/' + code);
    }
    window.location.reload();
  }

  window.googleTranslateElementInit = function () {
    if (!window.google || !google.translate) {
      return;
    }
    new google.translate.TranslateElement(
      {
        pageLanguage: 'fa',
        includedLanguages: 'en,ar,tr,ru,es',
        autoDisplay: false,
      },
      'google_translate_element'
    );
  };

  document.addEventListener('click', function (event) {
    var node = event.target;
    if (!node || typeof node.closest !== 'function') {
      return;
    }
    var btn = node.closest('button[data-lang], .lang-btn');
    if (!btn) {
      return;
    }
    event.preventDefault();
    setLang(btn.getAttribute('data-lang'));
  });

  document.addEventListener('DOMContentLoaded', function () {
    var current = readLang();
    document.documentElement.setAttribute('data-lang', current);
    document.querySelectorAll('[data-lang]').forEach(function (btn) {
      btn.classList.toggle('is-active', btn.getAttribute('data-lang') === current);
    });
    if (current === 'fa') {
      return;
    }
    var script = document.createElement('script');
    script.src = 'https://translate.google.com/translate_a/element.js?cb=googleTranslateElementInit';
    document.head.appendChild(script);
  });
})();
