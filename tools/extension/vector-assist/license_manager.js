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
    isExpired: false,
    status: null, // 'active', 'expired', 'no_license', 'unpaired', 'error'
    tier: null,
    appScope: null,
    licenseKey: null,
    licenseType: null, // 'lifetime', 'subscription', 'trial'
    expiresAt: null,
    daysRemaining: null,
    formattedExpiresAt: null,
    isChecking: false,
    checkedAt: null,
    message: null,

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
        this.isExpired = false;
        this.status = 'unpaired';
        this.tier = null;
        this.appScope = null;
        this.licenseKey = null;
        this.licenseType = null;
        this.expiresAt = null;
        this.daysRemaining = null;
        this.formattedExpiresAt = null;
        this.isChecking = false;
        this.message = 'Connect your CIORA account to validate software license.';
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
          this.isExpired = false;
          this.status = 'error';
          this.tier = null;
          this.isChecking = false;
          this.message = `License verification failed (HTTP ${res.status}).`;
          return { valid: false, reason: 'api_error', status: res.status };
        }

        const data = await res.json();
        const licenses = Array.isArray(data.licenses) ? data.licenses : [];

        // Filter all licenses matching this tool scope
        const matchingLicenses = licenses.filter((lic) => this.isScopeMatching(lic, targetTool));

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

            this.isValid = true;
            this.isExpired = false;
            this.status = 'active';
            this.tier = (activeLicense.tier || 'pro').toLowerCase();
            this.appScope = activeLicense.appScope;
            this.licenseKey = activeLicense.licenseCode || activeLicense.licenseKey;
            this.licenseType = activeLicense.licenseType || 'subscription';
            this.expiresAt = activeLicense.expiresAt || null;
            this.daysRemaining = days;
            this.formattedExpiresAt = dateStr;
            this.checkedAt = Date.now();
            this.isChecking = false;
            this.message = null;

            // Cache verified license info
            if (typeof chrome !== 'undefined' && chrome.storage && chrome.storage.local) {
              chrome.storage.local.set({
                ciora_license_cache: {
                  isValid: true,
                  isExpired: false,
                  status: 'active',
                  tier: this.tier,
                  appScope: this.appScope,
                  licenseKey: this.licenseKey,
                  licenseType: this.licenseType,
                  expiresAt: this.expiresAt,
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
          const licType = expiredOrInactive.licenseType || 'subscription';

          this.isValid = false;
          this.isExpired = true;
          this.status = 'expired';
          this.tier = (expiredOrInactive.tier || 'pro').toLowerCase();
          this.appScope = expiredOrInactive.appScope;
          this.licenseKey = expiredOrInactive.licenseCode || expiredOrInactive.licenseKey;
          this.licenseType = licType;
          this.expiresAt = expiredOrInactive.expiresAt || null;
          this.checkedAt = Date.now();
          this.isChecking = false;

          const dateStr = expiredOrInactive.expiresAt
            ? new Date(expiredOrInactive.expiresAt).toLocaleDateString('en-US', { day: 'numeric', month: 'short', year: 'numeric' })
            : '';

          const typeLabel = licType === 'trial' ? 'Trial period' : 'Subscription period';
          this.message = dateStr
            ? `Your license ${typeLabel.toLowerCase()} expired on ${dateStr}.`
            : `Your license ${typeLabel.toLowerCase()} has expired.`;

          if (typeof chrome !== 'undefined' && chrome.storage && chrome.storage.local) {
            chrome.storage.local.remove('ciora_license_cache');
          }

          return { valid: false, reason: 'expired', license: expiredOrInactive };
        }

        // 3. No matching license found at all
        this.isValid = false;
        this.isExpired = false;
        this.status = 'no_license';
        this.tier = null;
        this.appScope = null;
        this.licenseKey = null;
        this.licenseType = null;
        this.expiresAt = null;
        this.daysRemaining = null;
        this.formattedExpiresAt = null;
        this.isChecking = false;
        this.message = 'Account does not have a license for Vector Assist.';

        if (typeof chrome !== 'undefined' && chrome.storage && chrome.storage.local) {
          chrome.storage.local.remove('ciora_license_cache');
        }

        return { valid: false, reason: 'no_matching_license' };
      } catch (err) {
        this.isChecking = false;

        // Fallback to cache if network fails
        if (typeof chrome !== 'undefined' && chrome.storage && chrome.storage.local) {
          const cached = await new Promise((r) =>
            chrome.storage.local.get(['ciora_license_cache'], (d) => r(d?.ciora_license_cache))
          );
          if (cached && cached.isValid && cached.cachedAt && Date.now() - cached.cachedAt < 24 * 3600 * 1000) {
            // Also check if cached license expired in the meantime
            if (cached.expiresAt && new Date(cached.expiresAt).getTime() <= Date.now()) {
              this.isValid = false;
              this.isExpired = true;
              this.status = 'expired';
              this.tier = cached.tier;
              this.appScope = cached.appScope;
              this.licenseKey = cached.licenseKey;
              this.licenseType = cached.licenseType || 'subscription';
              this.expiresAt = cached.expiresAt;
              this.daysRemaining = 0;
              this.formattedExpiresAt = cached.formattedExpiresAt;
              this.message = 'Your license period has expired.';
              return { valid: false, reason: 'expired', cached: true };
            }

            this.isValid = true;
            this.isExpired = false;
            this.status = 'active';
            this.tier = cached.tier;
            this.appScope = cached.appScope;
            this.licenseKey = cached.licenseKey;
            this.licenseType = cached.licenseType;
            this.expiresAt = cached.expiresAt;
            this.daysRemaining = cached.daysRemaining;
            this.formattedExpiresAt = cached.formattedExpiresAt;
            this.message = null;
            return { valid: true, cached: true };
          }
        }

        this.status = 'error';
        this.message = 'Failed to connect to CIORA license server.';
        return { valid: false, reason: 'network_error', error: err?.message };
      }
    },
  };
})();
