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
  }

  DjangoUploadAdapter.prototype.upload = function () {
    var loader = this.loader;
    return loader.file.then(function (file) {
      var data = new FormData();
      data.append('upload', file);
      return fetch('/admin/legal-upload/', {
        method: 'POST',
        headers: { 'X-CSRFToken': csrfToken() },
        credentials: 'same-origin',
        body: data,
      }).then(function (response) {
        return response.json().then(function (payload) {
          payload.ok = response.ok;
          return payload;
        });
      }).then(function (payload) {
        if (!payload.ok || !payload.url) {
          throw new Error((payload.error && payload.error.message) || 'آپلود تصویر ناموفق بود.');
        }
        return { default: payload.url };
      });
    });
  };

  DjangoUploadAdapter.prototype.abort = function () {};

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
