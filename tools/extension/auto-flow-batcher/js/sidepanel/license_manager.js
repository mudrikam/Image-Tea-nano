/**
 * CIORA License Authority Integration Manager
 * Validates whether the active CIORA user owns a valid license
 * for the current software application (appScope matching).
 */

const CIORA_BASE_URL = 'https://ciora.id';

export const licenseState = {
  isValid: false,
  isExpired: false,
  status: null, // 'active', 'expired', 'no_license', 'unpaired', 'error'
  tier: null,
  appScope: null,
  licenseKey: null,
  licenseType: null, // 'lifetime', 'subscription', 'trial'
  expiresAt: null,
  isChecking: false,
  checkedAt: null,
  message: null,
};

/**
 * Checks if a license matches the target tool appScope.
 * Follows CIORA Universal License hierarchy:
 * 1. appScope === 'all' (Universal access)
 * 2. appScope === targetTool (Direct match)
 * 3. allowedScopes includes targetTool (Bundle suite match)
 */
export function isScopeMatching(lic, targetTool) {
  if (!lic) return false;
  const target = String(targetTool).toLowerCase().trim();
  const primaryScope = String(lic.appScope || '').toLowerCase().trim();

  // 1. Universal scope
  if (primaryScope === 'all') return true;

  // 2. Direct scope match
  if (primaryScope === target) return true;

  // 3. Multi-tool allowedScopes match
  const rawAllowed = lic.allowedScopes || (lic.metadata && (lic.metadata.allowedScopes || lic.metadata.allowed_scopes));
  if (Array.isArray(rawAllowed)) {
    return rawAllowed.some((s) => String(s).toLowerCase().trim() === target);
  }

  return false;
}

/**
 * Verifies whether the paired user owns a license for this tool.
 * Queries GET /api/v1/licenses/my using the Connected Device Token (cde_...).
 */
export async function verifyAppLicense(token, targetTool = 'auto-flow-batcher') {
  if (!token) {
    licenseState.isValid = false;
    licenseState.isExpired = false;
    licenseState.status = 'unpaired';
    licenseState.tier = null;
    licenseState.appScope = null;
    licenseState.licenseKey = null;
    licenseState.licenseType = null;
    licenseState.expiresAt = null;
    licenseState.isChecking = false;
    licenseState.message = 'Connect your CIORA account to validate software license.';
    return { valid: false, reason: 'unpaired' };
  }

  licenseState.isChecking = true;

  try {
    const res = await fetch(`${CIORA_BASE_URL}/api/v1/licenses/my`, {
      method: 'GET',
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json',
      },
    });

    if (!res.ok) {
      licenseState.isValid = false;
      licenseState.isExpired = false;
      licenseState.status = 'error';
      licenseState.tier = null;
      licenseState.isChecking = false;
      licenseState.message = `License verification failed (HTTP ${res.status}).`;
      return { valid: false, reason: 'api_error', status: res.status };
    }

    const data = await res.json();
    const licenses = Array.isArray(data.licenses) ? data.licenses : [];

    // Filter all licenses matching this tool scope
    const matchingLicenses = licenses.filter((lic) => isScopeMatching(lic, targetTool));

    // Prioritize direct appScope match over secondary bundle scopes
    matchingLicenses.sort((a, b) => {
      const aDirect = String(a.appScope || '').toLowerCase().trim() === targetTool.toLowerCase().trim() ? 1 : 0;
      const bDirect = String(b.appScope || '').toLowerCase().trim() === targetTool.toLowerCase().trim() ? 1 : 0;
      return bDirect - aDirect;
    });

    if (matchingLicenses.length > 0) {
      // 1. Check if there's any active & non-expired license
      const activeLicense = matchingLicenses.find((lic) => {
        const isActive = lic.status === 'active';
        const isNotExpired = !lic.expiresAt || new Date(lic.expiresAt).getTime() > Date.now();
        return isActive && isNotExpired;
      });

      if (activeLicense) {
        const days = activeLicense.expiresAt
          ? Math.max(0, Math.ceil((new Date(activeLicense.expiresAt).getTime() - Date.now()) / (1000 * 60 * 60 * 24)))
          : null;
        const dateStr = activeLicense.expiresAt
          ? new Date(activeLicense.expiresAt).toLocaleDateString('en-US', { day: 'numeric', month: 'short', year: 'numeric' })
          : null;

        licenseState.isValid = true;
        licenseState.isExpired = false;
        licenseState.status = 'active';
        licenseState.tier = (activeLicense.tier || 'pro').toLowerCase();
        licenseState.appScope = activeLicense.appScope;
        licenseState.licenseKey = activeLicense.licenseCode || activeLicense.licenseKey;
        licenseState.licenseType = activeLicense.licenseType || 'subscription';
        licenseState.expiresAt = activeLicense.expiresAt || null;
        licenseState.daysRemaining = days;
        licenseState.formattedExpiresAt = dateStr;
        licenseState.checkedAt = Date.now();
        licenseState.isChecking = false;
        licenseState.message = null;

        // Cache verified license info
        if (typeof chrome !== 'undefined' && chrome.storage && chrome.storage.local) {
          chrome.storage.local.set({
            ciora_license_cache: {
              isValid: true,
              isExpired: false,
              status: 'active',
              tier: licenseState.tier,
              appScope: licenseState.appScope,
              licenseKey: licenseState.licenseKey,
              licenseType: licenseState.licenseType,
              expiresAt: licenseState.expiresAt,
              daysRemaining: days,
              formattedExpiresAt: dateStr,
              cachedAt: Date.now(),
            },
          });
        }

        return { valid: true, license: activeLicense };
      }

      // 2. Matching license exists, but ALL are expired or inactive
      const expiredOrInactive = matchingLicenses[0];
      const isPastDate = expiredOrInactive.expiresAt && new Date(expiredOrInactive.expiresAt).getTime() <= Date.now();
      const licType = expiredOrInactive.licenseType || 'subscription';

      licenseState.isValid = false;
      licenseState.isExpired = true;
      licenseState.status = 'expired';
      licenseState.tier = (expiredOrInactive.tier || 'pro').toLowerCase();
      licenseState.appScope = expiredOrInactive.appScope;
      licenseState.licenseKey = expiredOrInactive.licenseCode || expiredOrInactive.licenseKey;
      licenseState.licenseType = licType;
      licenseState.expiresAt = expiredOrInactive.expiresAt || null;
      licenseState.checkedAt = Date.now();
      licenseState.isChecking = false;

      const dateStr = expiredOrInactive.expiresAt
        ? new Date(expiredOrInactive.expiresAt).toLocaleDateString('en-US', { day: 'numeric', month: 'short', year: 'numeric' })
        : '';

      const typeLabel = licType === 'trial' ? 'Trial period' : 'Subscription period';
      licenseState.message = dateStr
        ? `Your license ${typeLabel.toLowerCase()} expired on ${dateStr}.`
        : `Your license ${typeLabel.toLowerCase()} has expired.`;

      if (typeof chrome !== 'undefined' && chrome.storage && chrome.storage.local) {
        chrome.storage.local.remove('ciora_license_cache');
      }

      return { valid: false, reason: 'expired', license: expiredOrInactive };
    }

    // 3. No matching license found at all
    licenseState.isValid = false;
    licenseState.isExpired = false;
    licenseState.status = 'no_license';
    licenseState.tier = null;
    licenseState.appScope = null;
    licenseState.licenseKey = null;
    licenseState.licenseType = null;
    licenseState.expiresAt = null;
    licenseState.isChecking = false;
    licenseState.message = 'Account does not have a license for Auto Flow Batcher.';

    if (typeof chrome !== 'undefined' && chrome.storage && chrome.storage.local) {
      chrome.storage.local.remove('ciora_license_cache');
    }

    return { valid: false, reason: 'no_matching_license' };
  } catch (err) {
    licenseState.isChecking = false;

    // Fallback to cache if network fails
    if (typeof chrome !== 'undefined' && chrome.storage && chrome.storage.local) {
      const cached = await new Promise((r) =>
        chrome.storage.local.get(['ciora_license_cache'], (d) => r(d?.ciora_license_cache))
      );
      if (cached && cached.isValid && cached.cachedAt && Date.now() - cached.cachedAt < 24 * 3600 * 1000) {
        // Also check if cached license expired in the meantime
        if (cached.expiresAt && new Date(cached.expiresAt).getTime() <= Date.now()) {
          licenseState.isValid = false;
          licenseState.isExpired = true;
          licenseState.status = 'expired';
          licenseState.tier = cached.tier;
          licenseState.appScope = cached.appScope;
          licenseState.licenseKey = cached.licenseKey;
          licenseState.licenseType = cached.licenseType || 'subscription';
          licenseState.expiresAt = cached.expiresAt;
          licenseState.message = 'Your license period has expired.';
          return { valid: false, reason: 'expired', cached: true };
        }

        licenseState.isValid = true;
        licenseState.isExpired = false;
        licenseState.status = 'active';
        licenseState.tier = cached.tier;
        licenseState.appScope = cached.appScope;
        licenseState.licenseKey = cached.licenseKey;
        licenseState.licenseType = cached.licenseType;
        licenseState.expiresAt = cached.expiresAt;
        licenseState.message = null;
        return { valid: true, cached: true };
      }
    }

    licenseState.status = 'error';
    licenseState.message = 'Failed to connect to CIORA license server.';
    return { valid: false, reason: 'network_error', error: err?.message };
  }
}
