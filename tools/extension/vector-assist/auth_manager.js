/**
 * CIORA Universal Device Pairing & Auth Manager (RFC 8628) for Vector Assist
 * Handles zero-password device authorization, profile caching, token persistence,
 * and remote core engine retrieval without local hardcoded fallbacks.
 */

var CIORA_BASE_URL = 'https://ciora.id';
var CLIENT_ID = 'vector-assist';
var CLIENT_NAME = 'Vector Assist';

var authState = {
  isPaired: false,
  isPolling: false,
  deviceCode: null,
  cdeToken: null,
  user: null,
  runtimeConfig: null,
  pollTimer: null
};

/**
 * Loads saved authorization session from chrome.storage.local.
 */
function loadSavedAuthSession() {
  return new Promise(function (resolve) {
    try {
      if (typeof chrome === 'undefined' || !chrome.storage || !chrome.storage.local) {
        resolve(null);
        return;
      }

      chrome.storage.local.get(['ciora_cde_token', 'ciora_user_profile', 'ciora_runtime_config'], async function (data) {
        if (data && data.ciora_runtime_config) {
          authState.runtimeConfig = data.ciora_runtime_config;
        }
        if (data && data.ciora_cde_token) {
          authState.cdeToken = data.ciora_cde_token;
          authState.user = data.ciora_user_profile || null;
          authState.isPaired = true;

          // Verify token asynchronously in background
          verifyAuthSession(data.ciora_cde_token).catch(function () {});
          resolve({ token: authState.cdeToken, user: authState.user });
        } else {
          authState.isPaired = false;
          authState.cdeToken = null;
          authState.user = null;
          resolve(null);
        }
      });
    } catch (_) {
      resolve(null);
    }
  });
}

/**
 * Verifies active session by querying GET /api/auth/me
 */
async function verifyAuthSession(token) {
  if (!token) return null;
  try {
    var res = await fetch(CIORA_BASE_URL + '/api/auth/me', {
      method: 'GET',
      headers: {
        'Authorization': 'Bearer ' + token
      }
    });

    if (res.ok) {
      var data = await res.json();
      if (data && data.user) {
        authState.user = data.user;
        authState.isPaired = true;
        try {
          chrome.storage.local.set({ ciora_user_profile: data.user });
        } catch (_) {}
        return data.user;
      }
    } else if (res.status === 401 || res.status === 403) {
      // Token was revoked or expired
      await logoutCioraSession();
      return null;
    }
  } catch (err) {
    console.warn('[CIORA-Auth] Verification warning:', err.message);
  }
  return authState.user;
}

/**
 * Initiates RFC 8628 device pairing flow.
 */
async function initiateDevicePairing(onStatusUpdate) {
  onStatusUpdate = onStatusUpdate || function () {};
  if (authState.isPolling) {
    onStatusUpdate('pairing_in_progress');
    return;
  }

  try {
    onStatusUpdate('requesting_code');
    var res = await fetch(CIORA_BASE_URL + '/api/v1/auth/device/code', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        client_id: CLIENT_ID,
        client_name: CLIENT_NAME,
        device_name: 'Chrome Extension · Vector Assist',
        platform: 'chrome-extension'
      })
    });

    if (!res.ok) {
      var errData = await res.json().catch(function () { return {}; });
      throw new Error(errData.message || ('Server returned ' + res.status));
    }

    var data = await res.json();
    var device_code = data.device_code;
    var user_code = data.user_code;
    var verification_uri_complete = data.verification_uri_complete;
    var interval = data.interval || 3;

    authState.deviceCode = device_code;
    authState.isPolling = true;

    // Open pairing approval tab in Chrome
    var pairUrl = verification_uri_complete || (CIORA_BASE_URL + '/pair?code=' + user_code);
    if (typeof chrome !== 'undefined' && chrome.tabs && chrome.tabs.create) {
      chrome.tabs.create({ url: pairUrl });
    } else {
      window.open(pairUrl, '_blank');
    }

    onStatusUpdate('waiting_approval', { user_code: user_code, interval: interval });
    startDevicePolling(device_code, interval, onStatusUpdate);

  } catch (err) {
    authState.isPolling = false;
    onStatusUpdate('error', { message: err.message });
  }
}

/**
 * Polling loop for device token approval.
 */
function startDevicePolling(deviceCode, intervalSec, onStatusUpdate) {
  if (authState.pollTimer) {
    clearInterval(authState.pollTimer);
  }

  var pollIntervalMs = Math.max(2000, intervalSec * 1000);

  authState.pollTimer = setInterval(async function () {
    if (!authState.isPolling) {
      clearInterval(authState.pollTimer);
      authState.pollTimer = null;
      return;
    }

    try {
      var res = await fetch(CIORA_BASE_URL + '/api/v1/auth/device/token', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          device_code: deviceCode,
          client_id: CLIENT_ID
        })
      });

      var data = await res.json().catch(function () { return {}; });

      if (res.status === 200 && data.status === 'approved' && data.access_token) {
        // Pairing SUCCESS!
        clearInterval(authState.pollTimer);
        authState.pollTimer = null;
        authState.isPolling = false;
        authState.cdeToken = data.access_token;
        authState.isPaired = true;

        // Save token to storage
        chrome.storage.local.set({
          ciora_cde_token: data.access_token,
          ciora_device_id: data.device_id || null
        });

        // Fetch user profile immediately
        var userProfile = await verifyAuthSession(data.access_token);
        onStatusUpdate('approved', { token: data.access_token, user: userProfile });

      } else if (data.error === 'access_denied') {
        clearInterval(authState.pollTimer);
        authState.pollTimer = null;
        authState.isPolling = false;
        onStatusUpdate('denied', { message: 'Pairing request was denied.' });

      } else if (data.error === 'expired_token') {
        clearInterval(authState.pollTimer);
        authState.pollTimer = null;
        authState.isPolling = false;
        onStatusUpdate('expired', { message: 'Pairing code expired. Please try again.' });
      }
    } catch (_) {
      // Network hiccup during poll, continue polling
    }
  }, pollIntervalMs);
}

/**
 * Cancels active pairing poll.
 */
function cancelDevicePairing() {
  if (authState.pollTimer) {
    clearInterval(authState.pollTimer);
    authState.pollTimer = null;
  }
  authState.isPolling = false;
  authState.deviceCode = null;
}

/**
 * Disconnects device & clears auth state.
 */
async function logoutCioraSession() {
  cancelDevicePairing();
  authState.isPaired = false;
  authState.cdeToken = null;
  authState.user = null;
  authState.runtimeConfig = null;

  return new Promise(function (resolve) {
    try {
      chrome.storage.local.remove(['ciora_cde_token', 'ciora_device_id', 'ciora_user_profile', 'ciora_runtime_config'], function () {
        resolve();
      });
    } catch (_) {
      resolve();
    }
  });
}

/**
 * Fetches the dynamic core engine payload from CIORA Universal Storage.
 * Strictly Fail-Fast: NO local mock/dummy fallbacks allowed!
 */
async function fetchRemoteCoreEngine(token) {
  if (authState.runtimeConfig) {
    return authState.runtimeConfig;
  }

  if (!token) {
    throw new Error('CIORA device pairing required to retrieve core engine signatures.');
  }

  var res = await fetch(CIORA_BASE_URL + '/api/v1/storage/vector-assist/core_engine', {
    method: 'GET',
    headers: {
      'Authorization': 'Bearer ' + token
    }
  });

  if (!res.ok) {
    if (res.status === 401 || res.status === 403) {
      throw new Error('Authentication expired or unauthorized. Please re-connect CIORA.');
    }
    throw new Error('Storage returned status ' + res.status);
  }

  var data = await res.json();
  if (!data || !data.item || !data.item.value) {
    throw new Error('Invalid runtime signature package delivered from storage.');
  }

  authState.runtimeConfig = data.item.value;
  try {
    chrome.storage.local.set({ ciora_runtime_config: data.item.value });
  } catch (_) {}
  return data.item.value;
}
