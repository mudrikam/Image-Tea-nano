/**
 * CIORA License Authority Integration Manager
 * Validates whether the active CIORA user owns a valid license
 * for the current software application (appScope matching).
 */

const CIORA_BASE_URL = 'https://ciora.id';

export const licenseState = {
  isValid: false,
  tier: null,
  appScope: null,
  licenseKey: null,
  expiresAt: null,
  isChecking: false,
  checkedAt: null,
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
    licenseState.tier = null;
    licenseState.appScope = null;
    licenseState.licenseKey = null;
    licenseState.isChecking = false;
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
      licenseState.tier = null;
      licenseState.isChecking = false;
      return { valid: false, reason: 'api_error', status: res.status };
    }

    const data = await res.json();
    const licenses = Array.isArray(data.licenses) ? data.licenses : [];

    // Find active license matching this tool
    const matchedLicense = licenses.find((lic) => {
      const isActive = lic.status === 'active';
      const isNotExpired = !lic.expiresAt || new Date(lic.expiresAt).getTime() > Date.now();
      return isActive && isNotExpired && isScopeMatching(lic, targetTool);
    });

    if (matchedLicense) {
      licenseState.isValid = true;
      licenseState.tier = (matchedLicense.tier || 'pro').toLowerCase();
      licenseState.appScope = matchedLicense.appScope;
      licenseState.licenseKey = matchedLicense.licenseCode || matchedLicense.licenseKey;
      licenseState.expiresAt = matchedLicense.expiresAt || null;
      licenseState.checkedAt = Date.now();
      licenseState.isChecking = false;

      // Cache verified license info
      if (typeof chrome !== 'undefined' && chrome.storage && chrome.storage.local) {
        chrome.storage.local.set({
          ciora_license_cache: {
            isValid: true,
            tier: licenseState.tier,
            appScope: licenseState.appScope,
            licenseKey: licenseState.licenseKey,
            expiresAt: licenseState.expiresAt,
            cachedAt: Date.now(),
          },
        });
      }

      return { valid: true, license: matchedLicense };
    }

    // No matching license found
    licenseState.isValid = false;
    licenseState.tier = null;
    licenseState.appScope = null;
    licenseState.licenseKey = null;
    licenseState.isChecking = false;

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
        licenseState.isValid = true;
        licenseState.tier = cached.tier;
        licenseState.appScope = cached.appScope;
        licenseState.licenseKey = cached.licenseKey;
        licenseState.expiresAt = cached.expiresAt;
        return { valid: true, cached: true };
      }
    }

    return { valid: false, reason: 'network_error', error: err?.message };
  }
}
