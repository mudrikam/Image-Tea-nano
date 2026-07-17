// Vees Downloader - Content Script
// Injected into vectorizer.studio pages
// Handles: dropzone upload, Ctrl+V paste fallback, blob detection, blob download relay

(function () {
  if (window.__VEES_CONTENT_LOADED__) return;
  window.__VEES_CONTENT_LOADED__ = true;

  let currentProcessing = null;
  let blobObserver = null;
  let processTimeout = null;
  let blobCache = new Set();

  function log(msg) {
    console.log('[Vees]', msg);
    try {
      chrome.runtime.sendMessage({ type: 'LOG', message: '[Vees] ' + msg }).catch(function () {});
    } catch (e) {}
  }

  function base64ToBlob(base64, mime) {
    var byteString = atob(base64.split(',')[1]);
    var ab = new ArrayBuffer(byteString.length);
    var ia = new Uint8Array(ab);
    for (var i = 0; i < byteString.length; i++) {
      ia[i] = byteString.charCodeAt(i);
    }
    return new Blob([ab], { type: mime });
  }

  function getFileExtension(fileName) {
    var parts = fileName.split('.');
    return parts.length > 1 ? parts.pop().toLowerCase() : 'png';
  }

  function mimeFromExtension(ext) {
    var map = { png: 'image/png', jpg: 'image/jpeg', jpeg: 'image/jpeg', webp: 'image/webp', gif: 'image/gif', bmp: 'image/bmp' };
    return map[ext] || 'image/png';
  }

  function findDropzone() {
    var dz = document.querySelector('.hero-dropzone');
    if (dz) return dz;
    dz = document.querySelector('[data-testid="landing-dropzone"]');
    if (dz) return dz;
    return null;
  }

  function findDropzoneInput() {
    var dz = findDropzone();
    if (dz) {
      var input = dz.querySelector('input[type="file"]');
      if (input) return input;
    }
    var inputs = document.querySelectorAll('input[type="file"]');
    for (var i = 0; i < inputs.length; i++) {
      if (inputs[i].closest('.hero-dropzone') || inputs[i].closest('[data-testid="landing-dropzone"]')) {
        return inputs[i];
      }
    }
    if (inputs.length > 0) return inputs[0];
    return null;
  }

  function uploadViaDropzone(fileName, base64Data, fileType) {
    return new Promise(function (resolve) {
      var input = findDropzoneInput();
      if (!input) {
        log('Dropzone input not found');
        resolve({ success: false, reason: 'dropzone not found' });
        return;
      }
      var blob = base64ToBlob(base64Data, fileType);
      var file = new File([blob], fileName, { type: fileType });
      var dt = new DataTransfer();
      dt.items.add(file);
      input.files = dt.files;
      input.dispatchEvent(new Event('change', { bubbles: true }));
      log('File dispatched to dropzone: ' + fileName);
      resolve({ success: true });
    });
  }

  function uploadViaPaste(fileName, base64Data, fileType) {
    return new Promise(function (resolve) {
      try {
        var ext = getFileExtension(fileName);
        var mime = fileType || mimeFromExtension(ext);
        var blob = base64ToBlob(base64Data, mime);
        var clipboardItem = new ClipboardItem({ [mime]: blob });
        navigator.clipboard.write([clipboardItem]).then(function () {
          log('Image copied to clipboard, dispatching Ctrl+V');
          var body = document.body || document.documentElement;
          ['keydown', 'keypress'].forEach(function (eventType) {
            body.dispatchEvent(new KeyboardEvent(eventType, {
              key: 'v', code: 'KeyV', keyCode: 86, which: 86,
              ctrlKey: true, metaKey: true, bubbles: true, cancelable: true
            }));
          });
          setTimeout(function () {
            resolve({ success: true });
          }, 500);
        }).catch(function (err) {
          log('Clipboard write failed: ' + err.message);
          resolve({ success: false, reason: 'clipboard write failed: ' + err.message });
        });
      } catch (e) {
        log('Paste fallback error: ' + e.message);
        resolve({ success: false, reason: 'paste fallback error: ' + e.message });
      }
    });
  }

  function startBlobObserver(fileName) {
    stopBlobObserver();
    blobCache.clear();
    log('Starting blob observer for: ' + fileName);

    blobObserver = new MutationObserver(function (mutations) {
      var images = document.querySelectorAll('img[alt="Vectorized"]');
      for (var i = 0; i < images.length; i++) {
        var img = images[i];
        var src = img.getAttribute('src') || '';
        if (src.startsWith('blob:') && !blobCache.has(src)) {
          blobCache.add(src);
          log('New Vectorized blob detected: ' + src.substring(0, 60) + '...');
          captureBlob(fileName, src);
        }
      }
    });

    blobObserver.observe(document.body, {
      childList: true,
      subtree: true,
      attributes: true,
      attributeFilter: ['src', 'alt']
    });

    if (processTimeout) clearTimeout(processTimeout);
    processTimeout = setTimeout(function () {
      log('Blob wait timeout for: ' + fileName);
      stopBlobObserver();
      chrome.runtime.sendMessage({
        type: 'PROCESS_FAILED',
        fileName: fileName,
        reason: 'timeout'
      }).catch(function () {});
    }, 120000);
  }

  function stopBlobObserver() {
    if (blobObserver) {
      blobObserver.disconnect();
      blobObserver = null;
    }
    if (processTimeout) {
      clearTimeout(processTimeout);
      processTimeout = null;
    }
  }

  function captureBlob(fileName, blobUrl) {
    stopBlobObserver();
    log('Capturing blob: ' + blobUrl.substring(0, 60));

    fetch(blobUrl)
      .then(function (resp) { return resp.blob(); })
      .then(function (blob) {
        var reader = new FileReader();
        reader.onloadend = function () {
          var vectorizedData = reader.result;
          var blobUrlCopy = blobUrl;
          chrome.runtime.sendMessage({
            type: 'BLOB_CAPTURED',
            fileName: fileName,
            vectorizedData: vectorizedData,
            blobUrl: blobUrlCopy
          }).catch(function () {});
          log('Blob captured and sent: ' + fileName);
        };
        reader.readAsDataURL(blob);
      })
      .catch(function (err) {
        log('Blob fetch failed: ' + err.message);
        chrome.runtime.sendMessage({
          type: 'PROCESS_FAILED',
          fileName: fileName,
          reason: 'blob fetch failed: ' + err.message
        }).catch(function () {});
      });
  }

  async function processFile(file) {
    currentProcessing = file;
    log('Processing file: ' + file.fileName);

    var result = await uploadViaDropzone(file.fileName, file.originalData, file.fileType);
    if (!result.success) {
      log('Dropzone upload failed, trying paste fallback');
      result = await uploadViaPaste(file.fileName, file.originalData, file.fileType);
    }

    if (result.success) {
      startBlobObserver(file.fileName);
    } else {
      chrome.runtime.sendMessage({
        type: 'PROCESS_FAILED',
        fileName: file.fileName,
        reason: result.reason || 'upload failed'
      }).catch(function () {});
    }
  }

  chrome.runtime.onMessage.addListener(function (message, sender, sendResponse) {
    if (message.type === 'PROCESS_FILE' && message.file) {
      sendResponse({ received: true });
      processFile(message.file);
      return false;
    }
    if (message.type === 'STOP_PROCESSING') {
      stopBlobObserver();
      currentProcessing = null;
      sendResponse({ stopped: true });
      return true;
    }
    if (message.type === 'CHECK_READY') {
      var dz = findDropzone();
      sendResponse({ ready: !!dz });
      return true;
    }
  });

  log('Content script loaded');
})();
