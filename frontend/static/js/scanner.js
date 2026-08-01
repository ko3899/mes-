(function (root, factory) {
  var api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  root.MESCollector = Object.assign(root.MESCollector || {}, api);
}(typeof globalThis !== 'undefined' ? globalThis : this, function () {
  'use strict';

  function createScanner(options) {
    options = options || {};
    var nav = options.navigator || {};
    var Detector = options.BarcodeDetector;
    var requestFrame = options.requestFrame || function (fn) { return requestAnimationFrame(fn); };
    var cancelFrame = options.cancelFrame || function (id) { cancelAnimationFrame(id); };
    var input = null;
    var onCode = function () {};
    var stream = null;
    var frame = null;
    var detector = null;

    function handleKeydown(event) {
      if (event.key !== 'Enter') return;
      var code = String(input && input.value || '').trim();
      if (!code) return;
      onCode(code);
      input.value = '';
    }

    function mount(nextInput, nextOnCode) {
      onCode = nextOnCode || function () {};
      if (input === nextInput) return;
      if (input) input.removeEventListener('keydown', handleKeydown);
      input = nextInput;
      if (input) input.addEventListener('keydown', handleKeydown);
    }

    async function scanFrame(video) {
      if (!stream || !detector) return;
      try {
        var results = await detector.detect(video);
        if (results && results[0] && results[0].rawValue) onCode(results[0].rawValue);
      } catch (ignore) {}
      if (stream) frame = requestFrame(function () { scanFrame(video); });
    }

    async function startCamera(video) {
      if (!Detector || !nav.mediaDevices || !nav.mediaDevices.getUserMedia) {
        return {supported: false};
      }
      stopCamera();
      stream = await nav.mediaDevices.getUserMedia({video: {facingMode: 'environment'}, audio: false});
      video.srcObject = stream;
      if (typeof video.play === 'function') await video.play();
      detector = new Detector({formats: ['qr_code', 'code_128', 'ean_13', 'ean_8']});
      frame = requestFrame(function () { scanFrame(video); });
      return {supported: true};
    }

    function stopCamera() {
      if (frame != null) cancelFrame(frame);
      frame = null;
      if (stream && typeof stream.getTracks === 'function') {
        stream.getTracks().forEach(function (track) { track.stop(); });
      }
      stream = null;
      detector = null;
    }

    function unmount() {
      if (input) input.removeEventListener('keydown', handleKeydown);
      input = null;
      onCode = function () {};
      stopCamera();
    }

    return {mount: mount, startCamera: startCamera, stopCamera: stopCamera, unmount: unmount};
  }

  return {createScanner: createScanner};
}));
