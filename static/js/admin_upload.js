(function (doc, win) {
  function hasNewFile(form) {
    var inputs = form.querySelectorAll('input[type="file"]');
    for (var i = 0; i < inputs.length; i += 1) {
      if (inputs[i].files && inputs[i].files.length) {
        return true;
      }
    }
    return false;
  }

  function overlay(on, heavy) {
    var box = doc.getElementById('kb-admin-upload');
    if (!box) {
      box = doc.createElement('div');
      box.id = 'kb-admin-upload';
      box.className = 'kb-admin-upload';
      box.innerHTML =
        '<div class="kb-admin-upload__panel" role="status">' +
        '<span class="kb-admin-upload__spin" aria-hidden="true"></span>' +
        '<strong>در حال ذخیره</strong>' +
        '<p data-admin-upload-copy>لطفاً صبر کن؛ از ارسال دوباره خودداری کن.</p>' +
        '<div class="kb-admin-upload__bar" aria-hidden="true"><span></span></div>' +
        '</div>';
      doc.body.appendChild(box);
    }
    var copy = box.querySelector('[data-admin-upload-copy]');
    if (copy) {
      copy.textContent = heavy
        ? 'فایل در حال انتقال به فضای ابری آروان است…'
        : 'در حال ذخیره فرم. از کلیک دوباره خودداری کن.';
    }
    box.classList.toggle('is-on', !!on);
    box.hidden = !on;
  }

  doc.addEventListener(
    'submit',
    function (event) {
      var form = event.target;
      if (!form || form.tagName !== 'FORM') {
        return;
      }
      if (form.getAttribute('data-kb-admin-busy') === '1') {
        event.preventDefault();
        event.stopPropagation();
        return;
      }
      form.setAttribute('data-kb-admin-busy', '1');
      var buttons = form.querySelectorAll('input[type="submit"], button[type="submit"]');
      for (var i = 0; i < buttons.length; i += 1) {
        buttons[i].disabled = true;
        buttons[i].classList.add('kb-admin-busy');
      }
      overlay(true, hasNewFile(form));
    },
    true
  );

  win.addEventListener('pageshow', function (event) {
    if (!event.persisted) {
      return;
    }
    overlay(false, false);
    var forms = doc.querySelectorAll('[data-kb-admin-busy]');
    for (var i = 0; i < forms.length; i += 1) {
      forms[i].removeAttribute('data-kb-admin-busy');
      var buttons = forms[i].querySelectorAll('input[type="submit"], button[type="submit"]');
      for (var j = 0; j < buttons.length; j += 1) {
        buttons[j].disabled = false;
        buttons[j].classList.remove('kb-admin-busy');
      }
    }
  });
})(document, window);
