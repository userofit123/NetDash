/**
 * speedtest_frontend.js
 * Drop this into your index.html (or import it).
 * Requires speedtest.js + speedtest_worker.js in your static/ folder.
 *
 * LibreSpeed docs: https://github.com/librespeed/speedtest/wiki/Making-a-custom-front-end
 */

let _st = null;

function startSpeedtest() {
  if (_st) return; // already running

  _st = new Speedtest();

  // Point the worker at your Flask backend endpoints
  _st.setParameter('url_dl',     '/backend/garbage');
  _st.setParameter('url_ul',     '/backend/upload');
  _st.setParameter('url_ping',   '/backend/ping');
  _st.setParameter('url_getIp',  '/backend/getIp');

  // Tuning — increase streams for higher accuracy on fast connections
  _st.setParameter('dl_parallelStreams', 6);   // parallel download connections
  _st.setParameter('ul_parallelStreams', 4);   // parallel upload connections
  _st.setParameter('time_dl_max',        15);  // seconds
  _st.setParameter('time_ul_max',        15);

  // Called repeatedly during the test with live progress
  _st.onupdate = (data) => {
    // data fields: testState, dlStatus, ulStatus, pingStatus, jitter, clientIp, progress
    // testState: 0=idle, 1=dl, 2=ping, 3=ul, 4=done, 5=aborted

    updateUI({
      phase:    ['idle', 'download', 'ping', 'upload', 'complete', 'aborted'][data.testState],
      download: data.dlStatus  ? `${parseFloat(data.dlStatus).toFixed(2)} Mbps`  : null,
      upload:   data.ulStatus  ? `${parseFloat(data.ulStatus).toFixed(2)} Mbps`  : null,
      ping:     data.pingStatus ? `${parseFloat(data.pingStatus).toFixed(0)} ms`  : null,
      jitter:   data.jitter    ? `${parseFloat(data.jitter).toFixed(1)} ms`       : null,
    });
  };

  // Called once when the test finishes
  _st.onend = (aborted) => {
    if (!aborted) {
      const result = _st.getState();  // same shape as onupdate data

      // Persist to your Flask history endpoint
      fetch('/api/speedtest/history/save', {
        method:  'POST',
        headers: { 'Content-Type': 'application/json' },
        body:    JSON.stringify({
          dlStatus: result.dlStatus,
          ulStatus: result.ulStatus,
          ping:     result.pingStatus,
          jitter:   result.jitter,
          // attach any network info you already have from /api/stats
        }),
      });
    }
    _st = null; // allow re-run
  };

  _st.start();
}

function abortSpeedtest() {
  if (_st) _st.abort();
  _st = null;
}

/**
 * Replace this with however your existing dashboard updates the DOM.
 * e.g. set innerHTML, update Vue/React state, etc.
 */
function updateUI({ phase, download, upload, ping, jitter }) {
  if (download) document.getElementById('dl-result').textContent = download;
  if (upload)   document.getElementById('ul-result').textContent = upload;
  if (ping)     document.getElementById('ping-result').textContent = ping;
  if (jitter)   document.getElementById('jitter-result').textContent = jitter;
  document.getElementById('st-phase').textContent = phase ?? '';
}
