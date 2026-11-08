(function () {
  function csrfToken() {
    var match = document.cookie.match(/(?:^|; )csrftoken=([^;]+)/);
    if (match) {
      return decodeURIComponent(match[1]);
    }
    var node = document.querySelector('[name=csrfmiddlewaretoken]');
    return node ? node.value : '';
  }

  function DjangoUploadAdapter(loader) {
    this.loader = loader;
    this.xhr = null;
  }

  DjangoUploadAdapter.prototype.upload = function () {
    var loader = this.loader;
    var self = this;
    if (self.busy) {
      return Promise.reject('آپلود در حال انجام است.');
    }
    self.busy = true;
    return loader.file.then(function (file) {
      if (file.size > 6 * 1024 * 1024) {
        self.busy = false;
        return Promise.reject('حجم تصویر زیاد است.');
      }
      var type = String(file.type || '').toLowerCase();
      if (['image/png', 'image/jpeg', 'image/webp', 'image/gif'].indexOf(type) === -1) {
        self.busy = false;
        return Promise.reject('فقط تصویر مجاز است.');
      }
      var data = new FormData();
      data.append('upload', file);
      return new Promise(function (resolve, reject) {
        var xhr = new XMLHttpRequest();
        self.xhr = xhr;
        xhr.open('POST', '/admin/legal-upload/');
        xhr.withCredentials = true;
        xhr.setRequestHeader('X-CSRFToken', csrfToken());
        xhr.setRequestHeader('X-Requested-With', 'XMLHttpRequest');
        xhr.upload.onprogress = function (event) {
          if (!event.lengthComputable) {
            return;
          }
          loader.uploadTotal = event.total;
          loader.uploaded = event.loaded;
        };
        xhr.onerror = function () {
          self.busy = false;
          reject('ارتباط با سرور برقرار نشد.');
        };
        xhr.onabort = function () {
          self.busy = false;
          reject();
        };
        xhr.onload = function () {
          self.busy = false;
          var payload = {};
          try {
            payload = JSON.parse(xhr.responseText || '{}');
          } catch (err) {
            reject('پاسخ سرور نامعتبر بود.');
            return;
          }
          if (xhr.status >= 400 || !payload.url) {
            reject((payload.error && payload.error.message) || 'آپلود تصویر ناموفق بود.');
            return;
          }
          resolve({ default: payload.url });
        };
        xhr.send(data);
      });
    });
  };

  DjangoUploadAdapter.prototype.abort = function () {
    if (this.xhr) {
      this.xhr.abort();
    }
    this.busy = false;
  };

  function DjangoUploadPlugin(editor) {
    editor.plugins.get('FileRepository').createUploadAdapter = function (loader) {
      return new DjangoUploadAdapter(loader);
    };
  }

  function boot() {
    if (!window.ClassicEditor) {
      return;
    }
    document.querySelectorAll('textarea.kb-rich-editor').forEach(function (field) {
      if (field.getAttribute('data-ck-ready')) {
        return;
      }
      field.setAttribute('data-ck-ready', '1');
      window.ClassicEditor.create(field, {
        language: 'fa',
        extraPlugins: [DjangoUploadPlugin],
        toolbar: [
          'heading',
          '|',
          'bold',
          'italic',
          'link',
          'bulletedList',
          'numberedList',
          'blockQuote',
          'uploadImage',
          'undo',
          'redo',
        ],
      }).catch(function () {});
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', boot);
  } else {
    boot();
  }
})();
