(function (win, doc) {
  var IMAGE_TYPES = {
    'image/jpeg': 1,
    'image/jpg': 1,
    'image/pjpeg': 1,
    'image/png': 1,
    'image/webp': 1,
    'image/gif': 1,
  };
  var VIDEO_TYPES = {
    'video/mp4': 1,
    'video/webm': 1,
    'video/quicktime': 1,
    'video/x-m4v': 1,
  };

  function csrfToken() {
    var node = doc.querySelector('[name=csrfmiddlewaretoken]');
    if (node && node.value) {
      return node.value;
    }
    var match = doc.cookie.match(/(?:^|; )csrftoken=([^;]+)/);
    return match ? decodeURIComponent(match[1]) : '';
  }

  function isImage(file) {
    var type = String((file && file.type) || '').toLowerCase();
    if (IMAGE_TYPES[type]) {
      return true;
    }
    return /\.(jpe?g|png|webp|gif)$/i.test((file && file.name) || '');
  }

  function isVideo(file) {
    var type = String((file && file.type) || '').toLowerCase();
    if (VIDEO_TYPES[type]) {
      return true;
    }
    return /\.(mp4|webm|mov|m4v)$/i.test((file && file.name) || '');
  }

  function validateFile(file, rules) {
    rules = rules || {};
    if (!file) {
      return { ok: false, message: 'فایل انتخاب نشده است.' };
    }
    var maxImage = Number(rules.maxImage || 8 * 1024 * 1024);
    var maxVideo = Number(rules.maxVideo || 40 * 1024 * 1024);
    if (isImage(file)) {
      if (file.size > maxImage) {
        return { ok: false, message: 'حجم تصویر بیش از حد مجاز است.' };
      }
      return { ok: true, kind: 'image' };
    }
    if (isVideo(file)) {
      if (file.size > maxVideo) {
        return { ok: false, message: 'حجم ویدیو بیش از حد مجاز است.' };
      }
      return { ok: true, kind: 'video' };
    }
    return { ok: false, message: 'فقط تصویر JPG، PNG، WEBP، GIF یا ویدیو MP4/WEBM پذیرفته می‌شود.' };
  }

  function send(url, formData, options) {
    options = options || {};
    return new Promise(function (resolve, reject) {
      var xhr = new XMLHttpRequest();
      if (options.holder) {
        if (options.holder.xhr && options.holder.xhr.abort) {
          options.holder.xhr.abort();
        }
        options.holder.xhr = xhr;
      }
      xhr.open('POST', url);
      xhr.withCredentials = true;
      xhr.setRequestHeader('X-CSRFToken', csrfToken());
      xhr.setRequestHeader('X-Requested-With', 'XMLHttpRequest');
      xhr.setRequestHeader('Accept', 'application/json');
      xhr.upload.onprogress = function (event) {
        if (!event.lengthComputable || !options.onProgress) {
          return;
        }
        var percent = Math.max(0, Math.min(100, Math.round((event.loaded / event.total) * 100)));
        options.onProgress(percent, event.loaded, event.total);
      };
      xhr.onerror = function () {
        reject(new Error('ارتباط با سرور برقرار نشد.'));
      };
      xhr.onabort = function () {
        var err = new Error('canceled');
        err.code = 'abort';
        reject(err);
      };
      xhr.onload = function () {
        var type = xhr.getResponseHeader('content-type') || '';
        var payload;
        if (type.indexOf('application/json') === -1) {
          payload = {
            success: false,
            status: xhr.status,
            code: 'auth',
            message: 'برای این کار باید وارد حسابت شوی.',
          };
        } else {
          try {
            payload = JSON.parse(xhr.responseText || '{}');
          } catch (err) {
            reject(new Error('پاسخ سرور نامعتبر بود.'));
            return;
          }
        }
        payload.status = xhr.status;
        if ((payload.status === 401 || payload.code === 'auth') && typeof win.__kbPromptAuth === 'function') {
          win.__kbPromptAuth();
        }
        resolve(payload);
      };
      xhr.send(formData);
    });
  }

  function setBusy(form, on) {
    form.classList.toggle('is-uploading', !!on);
    form.setAttribute('data-kb-busy', on ? '1' : '0');
    form.querySelectorAll('button[type="submit"], .auth-btn').forEach(function (btn) {
      btn.disabled = !!on;
      btn.classList.toggle('is-busy', !!on);
    });
  }

  function progressUi(form, percent, label) {
    var bar = form.querySelector('.kb-upload-bar');
    var fill = form.querySelector('.kb-upload-bar__fill');
    var text = form.querySelector('.kb-upload-bar__label');
    if (!bar) {
      return;
    }
    bar.hidden = percent == null && !label;
    if (fill) {
      fill.style.transform = 'scaleX(' + Math.max(0, Math.min(1, (percent || 0) / 100)) + ')';
    }
    if (text) {
      text.textContent = label || '';
    }
  }

  function showPreview(form, file) {
    var box = form.querySelector('.kb-upload-preview');
    var img = form.querySelector('.kb-upload-preview__img');
    var vid = form.querySelector('.kb-upload-preview__vid');
    if (!box) {
      return;
    }
    clearPreview(form);
    box.hidden = !file;
    if (!file) {
      return;
    }
    var url = URL.createObjectURL(file);
    form._kbPreviewUrl = url;
    if (isVideo(file) && vid) {
      vid.hidden = false;
      if (img) {
        img.hidden = true;
      }
      vid.src = url;
      vid.muted = true;
      vid.playsInline = true;
      return;
    }
    if (img) {
      img.hidden = false;
      img.src = url;
    }
    if (vid) {
      vid.hidden = true;
    }
  }

  function clearPreview(form) {
    var box = form.querySelector('.kb-upload-preview');
    var img = form.querySelector('.kb-upload-preview__img');
    var vid = form.querySelector('.kb-upload-preview__vid');
    if (form._kbPreviewUrl) {
      URL.revokeObjectURL(form._kbPreviewUrl);
      form._kbPreviewUrl = '';
    }
    if (img) {
      img.removeAttribute('src');
      img.hidden = true;
    }
    if (vid) {
      vid.removeAttribute('src');
      try {
        vid.load();
      } catch (err) {}
      vid.hidden = true;
    }
    if (box) {
      box.hidden = true;
    }
  }

  function setStatus(form, message, isError) {
    var id = form.getAttribute('data-status') || '';
    var node = (id && doc.getElementById(id)) || form.querySelector('.auth-status');
    if (!node) {
      return;
    }
    node.hidden = !message;
    node.textContent = message || '';
    node.classList.toggle('is-error', !!isError);
  }

  function rulesOf(form) {
    return {
      maxImage: Number(form.getAttribute('data-max-image') || 8 * 1024 * 1024),
      maxVideo: Number(form.getAttribute('data-max-video') || 40 * 1024 * 1024),
      maxSeconds: Number(form.getAttribute('data-max-seconds') || 0),
    };
  }

  function fileInput(form) {
    return form.querySelector('input[type="file"]');
  }

  function bindMediaForms() {
    doc.querySelectorAll('[data-kb-media-form]').forEach(function (form) {
      if (form.getAttribute('data-kb-upload-bound') === '1') {
        return;
      }
      form.setAttribute('data-kb-upload-bound', '1');
      var holder = { xhr: null };
      form._kbUpload = holder;

      form.addEventListener('change', function (event) {
        if (!event.target || event.target.type !== 'file') {
          return;
        }
        var file = event.target.files && event.target.files[0];
        var retry = form.querySelector('[data-upload-retry]');
        if (retry) {
          retry.hidden = true;
        }
        if (!file) {
          clearPreview(form);
          return;
        }
        var check = validateFile(file, rulesOf(form));
        if (!check.ok) {
          event.target.value = '';
          clearPreview(form);
          setStatus(form, check.message, true);
          return;
        }
        setStatus(form, '', false);
        showPreview(form, file);
      });

      form.addEventListener('click', function (event) {
        var node = event.target;
        if (!node || typeof node.closest !== 'function') {
          return;
        }
        if (node.closest('[data-upload-clear]')) {
          event.preventDefault();
          var input = fileInput(form);
          if (input) {
            input.value = '';
          }
          clearPreview(form);
          setStatus(form, '', false);
          progressUi(form, null, '');
          var retry = form.querySelector('[data-upload-retry]');
          if (retry) {
            retry.hidden = true;
          }
          return;
        }
        if (node.closest('[data-upload-retry]')) {
          event.preventDefault();
          submitForm(form, holder);
        }
      });

      form.addEventListener('submit', function (event) {
        event.preventDefault();
        submitForm(form, holder);
      });
    });
  }

  function videoDuration(file) {
    if (!file || !isVideo(file)) {
      return Promise.resolve(0);
    }
    return new Promise(function (resolve, reject) {
      var video = doc.createElement('video');
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

  function submitForm(form, holder) {
    if (form.getAttribute('data-kb-busy') === '1') {
      return;
    }
    var input = fileInput(form);
    var file = input && input.files && input.files[0];
    var check = validateFile(file, rulesOf(form));
    var retry = form.querySelector('[data-upload-retry]');
    if (retry) {
      retry.hidden = true;
    }
    if (!check.ok) {
      setStatus(form, check.message, true);
      return;
    }
    var rules = rulesOf(form);
    var url = form.getAttribute('data-create-url') || '';
    setBusy(form, true);
    progressUi(form, 0, 'در حال بارگذاری: ۰٪');
    setStatus(form, '', false);
    videoDuration(file)
      .then(function (duration) {
        if (rules.maxSeconds && duration > rules.maxSeconds + 0.4) {
          throw new Error('مدت فیلم بیش از حد مجاز است.');
        }
        var data = new FormData();
        data.append('media', file);
        form.querySelectorAll('input:not([type="file"]), textarea').forEach(function (field) {
          if (!field.name && !field.id) {
            return;
          }
          if (field.id === 'story-overlay') {
            data.append('overlay', field.value || '');
          } else if (field.id === 'post-caption') {
            data.append('caption', field.value || '');
          } else if (field.name) {
            data.append(field.name, field.value || '');
          }
        });
        var posterFn = win.__kbExtractVideoPoster;
        return (posterFn ? posterFn(file) : Promise.resolve(null)).then(function (blob) {
          if (blob) {
            data.append('thumbnail', blob, 'poster.webp');
          }
          return send(url, data, {
            holder: holder,
            onProgress: function (percent) {
              if (percent >= 100) {
                progressUi(form, 100, 'در حال ذخیره‌سازی و پردازش…');
                return;
              }
              progressUi(form, percent, 'در حال بارگذاری: ' + percent + '٪');
            },
          });
        });
      })
      .then(function (payload) {
        setBusy(form, false);
        if (!payload || !payload.success) {
          progressUi(form, 0, '');
          setStatus(form, (payload && payload.message) || 'ارسال ناموفق بود.', true);
          if (retry) {
            retry.hidden = false;
          }
          return;
        }
        progressUi(form, 100, 'ذخیره شد.');
        setStatus(form, payload.message || 'ارسال شد.', false);
        if (win.__kbSoftReload) {
          win.__kbSoftReload();
        } else {
          win.location.reload();
        }
      })
      .catch(function (err) {
        setBusy(form, false);
        if (err && err.code === 'abort') {
          return;
        }
        progressUi(form, 0, '');
        setStatus(form, (err && err.message) || 'ارسال ناموفق بود.', true);
        if (retry) {
          retry.hidden = false;
        }
      });
  }

  win.__kbUpload = {
    send: send,
    validateFile: validateFile,
    isImage: isImage,
    isVideo: isVideo,
  };
  win.__kbBindMediaForms = bindMediaForms;
})(window, document);
