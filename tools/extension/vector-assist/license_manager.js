/**
 * CIORA License Authority Integration Manager
 * Validates whether the active CIORA user owns a valid license
 * for the current software application (appScope matching).
 * Script-compatible version for non-ESM extension scripts.
 */

(function () {
  const CIORA_BASE_URL = 'https://ciora.id';

  window.cioraLicense = {
    isValid: false,
    tier: null,
    appScope: null,
    licenseKey: null,
    expiresAt: null,
    isChecking: false,
    checkedAt: null,

    /**
     * Checks if a license matches the target tool appScope.
     */
    isScopeMatching: function (lic, targetTool) {
      if (!lic) return false;
      const target = String(targetTool).toLowerCase().trim();
      const primaryScope = String(lic.appScope || '').toLowerCase().trim();

      if (primaryScope === 'all') return true;
      if (primaryScope === target) return true;

      const rawAllowed = lic.allowedScopes || (lic.metadata && (lic.metadata.allowedScopes || lic.metadata.allowed_scopes));
      if (Array.isArray(rawAllowed)) {
        return rawAllowed.some((s) => String(s).toLowerCase().trim() === target);
      }

      return false;
    },

    /**
     * Verifies whether the paired user owns a license for this tool.
     */
    verifyAppLicense: async function (token, targetTool = 'vector-assist') {
      if (!token) {
        this.isValid = false;
        this.tier = null;
        this.appScope = null;
        this.licenseKey = null;
        this.isChecking = false;
        return { valid: false, reason: 'unpaired' };
      }

      this.isChecking = true;

      try {
        const res = await fetch(`${CIORA_BASE_URL}/api/v1/licenses/my`, {
          method: 'GET',
          headers: {
            'Authorization': `Bearer ${token}`,
            'Content-Type': 'application/json',
          },
        });

        if (!res.ok) {
          this.isValid = false;
          this.tier = null;
          this.isChecking = false;
          return { valid: false, reason: 'api_error', status: res.status };
        }

        const data = await res.json();
        const licenses = Array.isArray(data.licenses) ? data.licenses : [];

        const matchedLicense = licenses.find((lic) => {
          const isActive = lic.status === 'active';
          const isNotExpired = !lic.expiresAt || new Date(lic.expiresAt).getTime() > Date.now();
          return isActive && isNotExpired && this.isScopeMatching(lic, targetTool);
        });

        if (matchedLicense) {
          this.isValid = true;
          this.tier = (matchedLicense.tier || 'pro').toLowerCase();
          this.appScope = matchedLicense.appScope;
          this.licenseKey = matchedLicense.licenseCode || matchedLicense.licenseKey;
          this.expiresAt = matchedLicense.expiresAt || null;
          this.checkedAt = Date.now();
          this.isChecking = false;

          if (typeof chrome !== 'undefined' && chrome.storage && chrome.storage.local) {
            chrome.storage.local.set({
              ciora_license_cache: {
                isValid: true,
                tier: this.tier,
                appScope: this.appScope,
                licenseKey: this.licenseKey,
                expiresAt: this.expiresAt,
                cachedAt: Date.now(),
              },
            });
          }

          return { valid: true, license: matchedLicense };
        }

        this.isValid = false;
        this.tier = null;
        this.appScope = null;
        this.licenseKey = null;
        this.isChecking = false;

        if (typeof chrome !== 'undefined' && chrome.storage && chrome.storage.local) {
          chrome.storage.local.remove('ciora_license_cache');
        }

        return { valid: false, reason: 'no_matching_license' };
      } catch (err) {
        this.isChecking = false;

        if (typeof chrome !== 'undefined' && chrome.storage && chrome.storage.local) {
          const cached = await new Promise((r) =>
            chrome.storage.local.get(['ciora_license_cache'], (d) => r(d?.ciora_license_cache))
          );
          if (cached && cached.isValid && cached.cachedAt && Date.now() - cached.cachedAt < 24 * 3600 * 1000) {
            this.isValid = true;
            this.tier = cached.tier;
            this.appScope = cached.appScope;
            this.licenseKey = cached.licenseKey;
            this.expiresAt = cached.expiresAt;
            return { valid: true, cached: true };
          }
        }

        return { valid: false, reason: 'network_error', error: err?.message };
      }
    },
  };
})();
