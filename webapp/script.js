// Kloigos SPA (tabs, no routing) using Alpine + Fetch + Ace for Playbooks editor (no YAML linter yet).

window.app = function () {
  return {
    // Tabs
    view: "dashboard",
    apiBase: "/api",
    authChecked: false,
    isAuthenticated: false,
    authClaims: null,
    authLoginPath: "/api/auth/login",
    authDisplayNameClaim: "preferred_username",
    authSessionCookieName: "kloigos_session",
    authError: "",
    viewNotice: "",

    // Shared UTC timestamps

    // ---------- Servers state ----------
    servers: [],
    serversVisibleRows: [],
    serversFilterQuery: "",
    serversLastUpdatedUtc: null,
    serversSortIndex: null,
    serversSortDir: "asc",
    serversSortTypeByIndex: {
      0: "string", // hostname
      1: "ip", // ip
      2: "string", // user_id
      3: "string", // region
      4: "string", // zone
      5: "number", // cpu_count
      6: "number", // mem_gb
      7: "number", // disk_count
      8: "number", // disk_size_gb
      9: "string", // tags
      10: "string", // status
    },
    serversLoading: { list: false, action: false },
    serversAutoRefreshEnabled: true,
    _serversAutoTimer: null,

    // ---------- Events state ----------
    events: [],
    eventsVisibleRows: [],
    eventsFilterQuery: "",
    eventsLastUpdatedUtc: null,
    eventsSortIndex: 0,
    eventsSortDir: "desc",
    eventsSortTypeByIndex: {
      0: "date", // ts
      1: "string", // user_id
      2: "string", // action
      3: "string", // details
      4: "string", // request_id
    },
    eventsLoading: { list: false },
    eventsAutoRefreshEnabled: true,
    _eventsAutoTimer: null,

    // ---------- API keys state ----------
    apiKeys: [],
    apiKeysVisibleRows: [],
    apiKeysFilterQuery: "",
    apiKeysLastUpdatedUtc: null,
    apiKeysSortIndex: 2,
    apiKeysSortDir: "desc",
    apiKeysSortTypeByIndex: {
      0: "string", // access_key
      1: "string", // owner
      2: "date", // valid_until
      3: "string", // roles
    },
    apiKeysLoading: { list: false, create: false, delete: false },
    apiKeysAutoRefreshEnabled: true,
    _apiKeysAutoTimer: null,
    availableKloigosRoles: [
      "KLOIGOS_READONLY",
      "KLOIGOS_USER",
      "KLOIGOS_ADMIN",
    ],

    // ---------- Settings state ----------
    settings: [],
    settingsVisibleRows: [],
    settingsFilterQuery: "",
    settingsLastUpdatedUtc: null,
    settingsSortIndex: 1,
    settingsSortDir: "asc",
    settingsSortTypeByIndex: {
      0: "string", // key
      1: "string", // category
      2: "string", // value_type
      3: "string", // effective_value
      4: "string", // default_value
      5: "date", // updated_at
    },
    settingsLoading: { list: false, update: false, reset: false },
    settingsAutoRefreshEnabled: true,
    _settingsAutoTimer: null,
    settingsDrafts: {},
    settingsError: "",

    renderedAtUtc: "now",

    // ---------- Dashboard state ----------
    computeUnits: [],
    visibleRows: [],
    filterQuery: "",
    lastUpdatedUtc: null,

    inspector: null,
    inspectorFormat: "yaml",

    sortIndex: null,
    sortDir: "asc",
    sortTypeByIndex: {
      0: "string", // deployment_id
      1: "string", // compute_id
      2: "string", // region-zone
      3: "string", // hostname
      4: "ip",
      5: "number",
      6: "string",
      7: "string",
      8: "date",
      9: "string", // status
    },

    loading: {
      list: false,
      allocate: false,
      init: false,
      decommission: false,
      deallocateConfirm: false,
    },
    busyKey: null,
    autoRefreshEnabled: true,
    _autoTimer: null,

    modal: {
      allocate: {
        open: false,
        cpu_count: null,
        region: "",
        zone: "",
        compute_id: "",
        tagsText: "{}",
        ssh_public_key: "",
      },
      init: {
        open: false,
        ip: "",
        region: "",
        zone: "",
        hostname: "",
        cpuRangesText: '["0-3"]',
      },
      decommission: { open: false, hostname: "" },
      deallocateConfirm: { open: false, compute_id: "", hostname: "" },
      computeDetails: { open: false, row: null },
      userInfo: { open: false },
      serverActionConfirm: {
        open: false,
        hostname: "",
        action: "decommission",
      },
      serverDetails: { open: false, row: null },
      apiKeyCreate: {
        open: false,
        valid_until: "",
        roles: ["KLOIGOS_ADMIN"],
      },
      apiKeyDeleteConfirm: {
        open: false,
        access_key: "",
        owner: "",
      },
      apiKeySecret: {
        open: false,
        access_key: "",
        owner: "",
        valid_until: "",
        roles: [],
        secret_access_key: "",
        reveal: false,
        copied: false,
      },
      settingResetConfirm: {
        open: false,
        key: "",
        category: "",
        value_type: "",
        default_value: "",
        is_secret: false,
      },
    },
    modalErrors: {
      allocate: "",
      init: "",
      decommission: "",
      deallocateConfirm: "",
      serverActionConfirm: "",
      apiKeyCreate: "",
      apiKeyDeleteConfirm: "",
      settingResetConfirm: "",
    },

    // ---------- Playbooks state ----------
    playbooks: ["CU_ALLOCATE", "CU_DEALLOCATE", "SERVER_INIT", "SERVER_DECOMM"],
    selectedPlaybook: "",
    pbEditorReady: false,
    pbLoading: { list: false, save: false, load: false },
    pbToast: { message: "", ok: true },
    pbLastUpdatedUtc: null,

    // Ace
    _ace: null,
    _aceReady: false,

    // ---------- UTC helpers ----------
    utcNowString() {
      return new Date()
        .toISOString()
        .replace("T", " ")
        .replace(/\.\d{3}Z$/, "");
    },

    toUtcStringMaybe(value) {
      if (!value) return "-";
      const d = new Date(value);
      if (isNaN(d.getTime())) return String(value);
      return d
        .toISOString()
        .replace("T", " ")
        .replace(/\.\d{3}Z$/, "");
    },

    actionPillStyle(action) {
      const name = String(action || "").trim().toUpperCase();
      const palette = [
        {
          background: "rgba(30, 64, 175, 0.92)",
          borderColor: "rgba(147, 197, 253, 0.55)",
          color: "#eff6ff",
        },
        {
          background: "rgba(154, 52, 18, 0.92)",
          borderColor: "rgba(253, 186, 116, 0.55)",
          color: "#fff7ed",
        },
        {
          background: "rgba(6, 95, 70, 0.92)",
          borderColor: "rgba(110, 231, 183, 0.5)",
          color: "#ecfdf5",
        },
        {
          background: "rgba(91, 33, 182, 0.92)",
          borderColor: "rgba(196, 181, 253, 0.5)",
          color: "#f5f3ff",
        },
        {
          background: "rgba(190, 24, 93, 0.92)",
          borderColor: "rgba(251, 182, 206, 0.5)",
          color: "#fff1f2",
        },
        {
          background: "rgba(15, 23, 42, 0.96)",
          borderColor: "rgba(148, 163, 184, 0.45)",
          color: "#e5e7eb",
        },
        {
          background: "rgba(20, 83, 45, 0.92)",
          borderColor: "rgba(134, 239, 172, 0.45)",
          color: "#f0fdf4",
        },
        {
          background: "rgba(127, 29, 29, 0.92)",
          borderColor: "rgba(252, 165, 165, 0.45)",
          color: "#fef2f2",
        },
      ];

      const preferred = [
        {
          match: ["LOGIN", "_LOGIN"],
          style: palette[0],
        },
        {
          match: ["LOGOUT", "_LOGOUT"],
          style: palette[5],
        },
        {
          match: ["ALLOCATE", "ALLOCATION"],
          style: palette[1],
        },
        {
          match: ["DEALLOCATE", "DEALLOCATION"],
          style: palette[3],
        },
        {
          match: ["INIT", "CREATE"],
          style: palette[2],
        },
        {
          match: ["DECOMM", "DELETE", "REMOVE"],
          style: palette[7],
        },
        {
          match: ["UPDATE", "PATCH"],
          style: palette[4],
        },
      ];

      for (const entry of preferred) {
        if (entry.match.some((token) => name.includes(token))) {
          return entry.style;
        }
      }

      let hash = 0;
      for (let i = 0; i < name.length; i += 1) {
        hash = (hash * 31 + name.charCodeAt(i)) >>> 0;
      }
      return palette[hash % palette.length];
    },

    errorMessage(err, fallback = "Request failed.") {
      if (!err) return fallback;
      const msg =
        err?.message ||
        err?.detail ||
        err?.response?.data?.detail ||
        err?.response?.data?.message;
      return String(msg || fallback);
    },

    clearModalError(modalName) {
      if (!modalName) return;
      this.modalErrors[modalName] = "";
    },

    setModalError(modalName, err, fallback = "Request failed.") {
      this.modalErrors[modalName] = this.errorMessage(err, fallback);
    },

    // ---------- Auth ----------
    stopAutoRefreshTimers() {
      if (this._autoTimer) {
        clearInterval(this._autoTimer);
        this._autoTimer = null;
      }
      if (this._serversAutoTimer) {
        clearInterval(this._serversAutoTimer);
        this._serversAutoTimer = null;
      }
      if (this._eventsAutoTimer) {
        clearInterval(this._eventsAutoTimer);
        this._eventsAutoTimer = null;
      }
      if (this._apiKeysAutoTimer) {
        clearInterval(this._apiKeysAutoTimer);
        this._apiKeysAutoTimer = null;
      }
      if (this._settingsAutoTimer) {
        clearInterval(this._settingsAutoTimer);
        this._settingsAutoTimer = null;
      }
    },

    setAuthRequired(loginPath, errorMessage = "Not authenticated.") {
      this.isAuthenticated = false;
      this.authClaims = null;
      this.authDisplayNameClaim = "preferred_username";
      this.authSessionCookieName = "kloigos_session";
      this.authError = String(errorMessage || "Not authenticated.");
      this.stopAutoRefreshTimers();
      if (loginPath) this.authLoginPath = loginPath;
    },

    syncAuthMeta() {
      const meta =
        this.authClaims &&
        typeof this.authClaims === "object" &&
        this.authClaims._kloigos &&
        typeof this.authClaims._kloigos === "object"
          ? this.authClaims._kloigos
          : null;

      if (
        meta &&
        typeof meta.display_name_claim === "string" &&
        meta.display_name_claim.trim()
      ) {
        this.authDisplayNameClaim = meta.display_name_claim.trim();
      } else {
        this.authDisplayNameClaim = "preferred_username";
      }

      if (
        meta &&
        typeof meta.session_cookie_name === "string" &&
        meta.session_cookie_name.trim()
      ) {
        this.authSessionCookieName = meta.session_cookie_name.trim();
      } else {
        this.authSessionCookieName = "kloigos_session";
      }
    },

    authClaimsWithoutCookies() {
      const claims =
        this.authClaims && typeof this.authClaims === "object"
          ? this.authClaims
          : null;
      if (!claims) return {};
      return Object.fromEntries(
        Object.entries(claims).filter(
          ([key]) => key !== "cookies" && !String(key).startsWith("_"),
        ),
      );
    },

    authSessionCookieValue() {
      const claims =
        this.authClaims && typeof this.authClaims === "object"
          ? this.authClaims
          : null;
      if (!claims || typeof claims.cookies !== "object" || !claims.cookies) {
        return "(No cookie data captured yet)";
      }

      const cookieName = String(this.authSessionCookieName || "").trim();
      if (!cookieName) return "(No cookie data captured yet)";

      const value = claims.cookies[cookieName];
      return value ? String(value) : "(No cookie data captured yet)";
    },

    authIsUnauthenticatedMode() {
      return Boolean(this.authClaims && this.authClaims.auth_disabled);
    },

    authGroupsClaimName() {
      const claims =
        this.authClaims && typeof this.authClaims === "object"
          ? this.authClaims
          : null;
      const rawName = claims?._groups_claim_name;
      return typeof rawName === "string" && rawName.trim()
        ? rawName.trim()
        : "groups";
    },

    authGroups() {
      const claims =
        this.authClaims && typeof this.authClaims === "object"
          ? this.authClaims
          : null;
      if (!claims) return [];
      return this.normalizeClaimValues(claims[this.authGroupsClaimName()]);
    },

    authRoleGroups() {
      const roleGroups =
        this.authClaims &&
        typeof this.authClaims === "object" &&
        this.authClaims._role_groups &&
        typeof this.authClaims._role_groups === "object"
          ? this.authClaims._role_groups
          : {};
      return roleGroups;
    },

    normalizeClaimValues(input) {
      if (Array.isArray(input)) {
        return input.map((value) => String(value).trim()).filter(Boolean);
      }
      if (typeof input === "string") {
        return input
          .split(",")
          .map((value) => String(value).trim())
          .filter(Boolean);
      }
      return [];
    },

    authRoles() {
      const values = [];
      const roleGroups = this.authRoleGroups();
      const userGroups = new Set(this.authGroups());

      Object.entries(roleGroups).forEach(([roleName, groups]) => {
        const normalizedGroups = this.normalizeClaimValues(groups);
        if (
          normalizedGroups.some((group) => userGroups.has(String(group).trim()))
        ) {
          values.push(roleName);
        }
      });

      return [...new Set(values.map((value) => String(value).trim()).filter(Boolean))];
    },

    authRoleAnalysis() {
      const claimName = this.authGroupsClaimName();
      const claims =
        this.authClaims && typeof this.authClaims === "object"
          ? this.authClaims
          : null;
      return {
        groups_claim_name: claimName,
        groups_claim_value: claims ? claims[claimName] ?? null : null,
        normalized_groups: this.authGroups(),
        role_groups: this.authRoleGroups(),
        kloigos_roles: this.authRoles(),
      };
    },

    logRoleCheck({
      checkType = "role-check",
      requiredRole = "",
      viewName = this.view,
      result = false,
      detail = "",
    } = {}) {
      console.info("[kloigos role check]", {
        checkType,
        viewName: String(viewName || "").trim() || this.view,
        requiredRole: String(requiredRole || "").trim(),
        result: Boolean(result),
        detail: detail ? String(detail) : "",
        ...this.authRoleAnalysis(),
      });
    },

    hasRole(role, { viewName = this.view, checkType = "hasRole" } = {}) {
      if (this.authIsUnauthenticatedMode()) return true;
      const roleName = String(role || "").trim();
      if (!roleName) return false;

      const userRoles = this.authRoles();
      if (userRoles.includes(roleName)) {
        this.logRoleCheck({
          checkType,
          requiredRole: roleName,
          viewName,
          result: true,
          detail: "Matched direct or inferred effective role.",
        });
        return true;
      }

      const userGroups = this.authGroups();
      const roleGroups = this.normalizeClaimValues(
        this.authRoleGroups()[roleName],
      );
      if (roleGroups.length === 0) {
        this.logRoleCheck({
          checkType,
          requiredRole: roleName,
          viewName,
          result: false,
          detail: "No role-to-group mapping found for required role.",
        });
        return false;
      }

      const result = roleGroups.some((group) => userGroups.includes(group));
      this.logRoleCheck({
        checkType,
        requiredRole: roleName,
        viewName,
        result,
        detail: result
          ? "Matched required role through group membership."
          : "No matching user group found for required role.",
      });
      return result;
    },

    canManageCompute() {
      return (
        this.authIsUnauthenticatedMode() ||
        this.hasRole("KLOIGOS_USER", {
          viewName: this.view,
          checkType: "canManageCompute",
        }) ||
        this.hasRole("KLOIGOS_ADMIN", {
          viewName: this.view,
          checkType: "canManageCompute",
        })
      );
    },

    canViewAdmin(viewName = this.view) {
      return (
        this.authIsUnauthenticatedMode() ||
        this.hasRole("KLOIGOS_ADMIN", {
          viewName,
          checkType: "canViewAdmin",
        })
      );
    },

    isViewAccessible(viewName) {
      if (
        ["servers", "events", "playbooks", "api_keys", "settings"].includes(
          viewName,
        )
      ) {
        const result = this.canViewAdmin(viewName);
        this.logRoleCheck({
          checkType: "isViewAccessible",
          requiredRole: "KLOIGOS_ADMIN",
          viewName,
          result,
          detail: "Checking admin access for restricted view.",
        });
        return result;
      }
      this.logRoleCheck({
        checkType: "isViewAccessible",
        requiredRole: "",
        viewName,
        result: true,
        detail: "View does not require an admin role.",
      });
      return true;
    },

    unauthorizedViewMessage(viewName = this.view) {
      const labels = {
        servers: "Servers",
        events: "Events",
        playbooks: "Playbooks",
        api_keys: "API Keys",
        settings: "Settings",
      };
      const label = labels[viewName] || "This view";
      return `${label} is available only to admin users.`;
    },

    handleForbiddenView(viewName, { fallback = true } = {}) {
      this.viewNotice = this.unauthorizedViewMessage(viewName);
      if (!fallback) return;

      this.view = "dashboard";
      localStorage.setItem("kloigos_view", this.view);
    },

    clearViewNotice() {
      this.viewNotice = "";
    },

    userDisplayName() {
      const c =
        this.authClaims && typeof this.authClaims === "object"
          ? this.authClaims
          : {};
      const claim = String(this.authDisplayNameClaim || "preferred_username");
      const val =
        c[claim] || c.preferred_username || c.name || c.email || c.sub || "";
      if (this.authIsUnauthenticatedMode()) return "Unauthenticated";
      return String(val || "Unknown user");
    },

    userIconTitle() {
      return this.authIsUnauthenticatedMode()
        ? "Running in unauthenticated mode"
        : "Authenticated user";
    },

    async refreshAuthMeSnapshot() {
      try {
        const res = await fetch("/api/auth/me", { method: "GET" });
        const ct = res.headers.get("content-type") || "";
        const isJson = ct.includes("application/json");
        const data = isJson
          ? await res.json().catch(() => null)
          : await res.text().catch(() => null);
        if (res.ok && data && typeof data === "object") {
          this.authClaims = data;

          this.syncAuthMeta();
        }
      } catch (_e) {
        // keep last known authClaims in the modal when refresh fails
      }
    },

    async openUserInfoModal() {
      await this.refreshAuthMeSnapshot();
      this.modal.userInfo.open = true;
    },

    closeUserInfoModal() {
      this.modal.userInfo.open = false;
    },

    async checkAuthSession() {
      let res = null;
      let data = null;
      try {
        res = await fetch("/api/auth/me", { method: "GET" });
      } catch (e) {
        this.authError = this.errorMessage(e, "Unable to verify session.");
        this.authChecked = true;
        return false;
      }

      const ct = res.headers.get("content-type") || "";
      const isJson = ct.includes("application/json");
      data = isJson
        ? await res.json().catch(() => null)
        : await res.text().catch(() => null);

      if (!res.ok) {
        if (res.status === 401 || res.status === 403) {
          const loginPath =
            res.headers.get("x-auth-login-url") ||
            (data &&
              ((data.detail && data.detail.auth_login_url) ||
                data.auth_login_url)) ||
            "/api/auth/login";
          this.setAuthRequired(loginPath);
          this.authChecked = true;
          return false;
        }

        this.authError =
          (data && (data.detail || data.message)) ||
          (typeof data === "string" && data) ||
          `Auth check failed (${res.status})`;
        this.authChecked = true;
        return false;
      }

      this.isAuthenticated = true;
      this.authClaims = data && typeof data === "object" ? data : null;
      this.syncAuthMeta();
      this.authError = "";
      this.authChecked = true;
      this.clearViewNotice();
      return true;
    },

    loginWithSSO() {
      if (typeof window === "undefined") return;
      const loginPath = this.authLoginPath || "/api/auth/login";
      const next = encodeURIComponent(
        `${window.location.pathname}${window.location.search}${window.location.hash}`,
      );
      const sep = String(loginPath).includes("?") ? "&" : "?";
      window.location.assign(`${loginPath}${sep}next=${next}`);
    },

    // ---------- Init ----------
    async init() {
      const sIdx = localStorage.getItem("kloigos_sort_index");
      const sDir = localStorage.getItem("kloigos_sort_dir");
      const sFilter = localStorage.getItem("kloigos_filter");
      const sFmt = localStorage.getItem("kloigos_inspector_format");
      const sView = localStorage.getItem("kloigos_view");
      const ssIdx = localStorage.getItem("kloigos_servers_sort_index");
      const ssDir = localStorage.getItem("kloigos_servers_sort_dir");
      const ssFilter = localStorage.getItem("kloigos_servers_filter");
      const seIdx = localStorage.getItem("kloigos_events_sort_index");
      const seDir = localStorage.getItem("kloigos_events_sort_dir");
      const seFilter = localStorage.getItem("kloigos_events_filter");
      const sakIdx = localStorage.getItem("kloigos_api_keys_sort_index");
      const sakDir = localStorage.getItem("kloigos_api_keys_sort_dir");
      const sakFilter = localStorage.getItem("kloigos_api_keys_filter");
      const setIdx = localStorage.getItem("kloigos_settings_sort_index");
      const setDir = localStorage.getItem("kloigos_settings_sort_dir");
      const setFilter = localStorage.getItem("kloigos_settings_filter");

      if (sIdx !== null && !Number.isNaN(+sIdx)) this.sortIndex = +sIdx;
      if (sDir === "desc") this.sortDir = "desc";
      if (sFilter !== null) this.filterQuery = sFilter;
      if (ssFilter !== null) this.serversFilterQuery = ssFilter;
      if (seFilter !== null) this.eventsFilterQuery = seFilter;
      if (sakFilter !== null) this.apiKeysFilterQuery = sakFilter;
      if (setFilter !== null) this.settingsFilterQuery = setFilter;
      if (ssIdx !== null && !Number.isNaN(+ssIdx))
        this.serversSortIndex = +ssIdx;
      if (seIdx !== null && !Number.isNaN(+seIdx)) this.eventsSortIndex = +seIdx;
      if (sakIdx !== null && !Number.isNaN(+sakIdx))
        this.apiKeysSortIndex = +sakIdx;
      if (setIdx !== null && !Number.isNaN(+setIdx))
        this.settingsSortIndex = +setIdx;
      if (ssDir === "desc") this.serversSortDir = "desc";
      if (seDir === "asc" || seDir === "desc") this.eventsSortDir = seDir;
      if (sakDir === "asc" || sakDir === "desc") this.apiKeysSortDir = sakDir;
      if (setDir === "asc" || setDir === "desc") this.settingsSortDir = setDir;
      if (sFmt === "json" || sFmt === "yaml") this.inspectorFormat = sFmt;
      if (
        sView === "dashboard" ||
        sView === "playbooks" ||
        sView === "servers" ||
        sView === "events" ||
        sView === "api_keys" ||
        sView === "settings"
      )
        this.view = sView;

      this.renderedAtUtc = this.utcNowString();

      const hasSession = await this.checkAuthSession();
      if (!hasSession) return;

      if (!this.isViewAccessible(this.view)) {
        this.handleForbiddenView(this.view);
      }

      // Start dashboard timer (only refresh if dashboard tab is active)
      this._autoTimer = setInterval(() => {
        if (this.autoRefreshEnabled && this.view === "dashboard")
          this.refreshDashboard();
      }, 10_000);

      // Start servers timer (only refresh if servers tab is active)
      this._serversAutoTimer = setInterval(() => {
        if (this.serversAutoRefreshEnabled && this.view === "servers")
          this.refreshServers();
      }, 15_000);

      this._eventsAutoTimer = setInterval(() => {
        if (this.eventsAutoRefreshEnabled && this.view === "events")
          this.refreshEvents();
      }, 15_000);

      this._apiKeysAutoTimer = setInterval(() => {
        if (this.apiKeysAutoRefreshEnabled && this.view === "api_keys")
          this.refreshApiKeys();
      }, 20_000);

      this._settingsAutoTimer = setInterval(() => {
        if (this.settingsAutoRefreshEnabled && this.view === "settings")
          this.refreshSettings();
      }, 20_000);

      // Load the active tab
      if (this.view === "playbooks") this.ensurePlaybooksView();
      else if (this.view === "servers") this.ensureServersView();
      else if (this.view === "events") this.ensureEventsView();
      else if (this.view === "api_keys") this.ensureApiKeysView();
      else if (this.view === "settings") this.ensureSettingsView();
      else this.ensureDashboardView();
    },

    setView(next) {
      if (next === this.view) return;
      if (!this.isViewAccessible(next)) {
        this.handleForbiddenView(next, { fallback: false });
        return;
      }

      this.clearViewNotice();
      this.view = next;
      localStorage.setItem("kloigos_view", this.view);

      if (this.view === "playbooks") this.ensurePlaybooksView();
      else if (this.view === "servers") this.ensureServersView();
      else if (this.view === "events") this.ensureEventsView();
      else if (this.view === "api_keys") this.ensureApiKeysView();
      else if (this.view === "settings") this.ensureSettingsView();
      else this.ensureDashboardView();
    },

    async logout() {
      try {
        await fetch("/api/auth/logout", { method: "POST" });
      } catch (e) {
        console.error(e);
      } finally {
        this.setAuthRequired(this.authLoginPath, "");
        this.authChecked = true;
        if (typeof window !== "undefined") window.location.assign("/");
      }
    },

    // ---------- Shared API fetch (also feeds inspector on dashboard) ----------
    async apiFetch(path, { method = "GET", body = null } = {}) {
      const url = this.apiBase + path;
      const startedAtUtc = this.utcNowString();

      const opts = { method, headers: {} };
      if (body !== null && body !== undefined) {
        opts.headers["Content-Type"] = "application/json";
        opts.body = JSON.stringify(body);
      }

      const res = await fetch(url, opts);
      const ct = res.headers.get("content-type") || "";
      const isJson = ct.includes("application/json");
      const data = isJson
        ? await res.json().catch(() => null)
        : await res.text().catch(() => null);

      if (this.view === "dashboard") {
        this.inspector = {
          startedAtUtc,
          url,
          method,
          status: res.status,
          ok: res.ok,
          response: data,
        };
      }

      if (!res.ok) {
        if (res.status === 401 && typeof window !== "undefined") {
          const loginPath =
            res.headers.get("x-auth-login-url") ||
            (data &&
              ((data.detail && data.detail.auth_login_url) ||
                data.auth_login_url)) ||
            "/api/auth/login";
          this.setAuthRequired(loginPath);
          throw new Error("Not authenticated.");
        }

        const msg =
          (data && (data.detail || data.message)) ||
          (typeof data === "string" && data) ||
          `Request failed (${res.status})`;
        const error = new Error(msg);
        error.status = res.status;
        error.forbidden = res.status === 403;
        throw error;
      }

      return data;
    },

    // ---------- Servers lifecycle ----------
    async ensureServersView() {
      if (!this.canViewAdmin()) {
        this.handleForbiddenView("servers", { fallback: false });
        return;
      }
      if (this.servers.length === 0 && !this.serversLoading.list)
        await this.refreshServers();
      else this.applyServersFilterSort();
    },

    async ensureEventsView() {
      if (!this.canViewAdmin()) {
        this.handleForbiddenView("events", { fallback: false });
        return;
      }
      if (this.events.length === 0 && !this.eventsLoading.list)
        await this.refreshEvents();
      else this.applyEventsFilterSort();
    },

    async ensureApiKeysView() {
      if (!this.canViewAdmin()) {
        this.handleForbiddenView("api_keys", { fallback: false });
        return;
      }
      if (this.apiKeys.length === 0 && !this.apiKeysLoading.list)
        await this.refreshApiKeys();
      else this.applyApiKeysFilterSort();
    },

    async ensureSettingsView() {
      if (!this.canViewAdmin()) {
        this.handleForbiddenView("settings", { fallback: false });
        return;
      }
      if (this.settings.length === 0 && !this.settingsLoading.list)
        await this.refreshSettings();
      else this.applySettingsFilterSort();
    },

    serversRowText(s) {
      const tags =
        s.tags && typeof s.tags === "object"
          ? Object.entries(s.tags)
              .map(([k, v]) => `${k}:${Array.isArray(v) ? v.join(",") : v}`)
              .join(" ")
          : "";
      return [s.hostname, s.ip, s.user_id, s.region, s.zone, s.status, tags]
        .filter(Boolean)
        .join(" ")
        .toLowerCase();
    },

    serversCellText(s, colIndex) {
      switch (colIndex) {
        case 0:
          return s.hostname || "";
        case 1:
          return s.ip || "";
        case 2:
          return s.user_id || "";
        case 3:
          return s.region || "";
        case 4:
          return s.zone || "";
        case 5:
          return s.cpu_count ?? "";
        case 6:
          return s.mem_gb ?? "";
        case 7:
          return s.disk_count ?? "";
        case 8:
          return s.disk_size_gb ?? "";
        case 9:
          return this.serversTagsCompact(s.tags) || "";
        case 10:
          return s.status || "";
        default:
          return "";
      }
    },

    serversTagsCompact(tags) {
      if (!tags || typeof tags !== "object") return "";
      // compact "k=v" pairs (limit length a bit)
      const s = Object.entries(tags)
        .map(([k, v]) => `${k}=${Array.isArray(v) ? v.join(",") : v}`)
        .join(" ");
      return s.length > 60 ? s.slice(0, 60) + "…" : s;
    },

    serversStatusClass(status) {
      const s = String(status || "").toLowerCase();
      if (s === "ready") return "status-online";
      if (s === "decommissioned") return "status-muted";
      if (s.includes("ing")) return "status-pending status-pulse";
      if (!s || s === "unknown") return "status-muted";
      return "status-offline";
    },

    serversSortClass(index) {
      if (this.serversSortIndex !== index) return "";
      return this.serversSortDir === "asc" ? "sort-asc" : "sort-desc";
    },

    toggleServersSort(index) {
      if (this.serversSortIndex === index)
        this.serversSortDir = this.serversSortDir === "asc" ? "desc" : "asc";
      else {
        this.serversSortIndex = index;
        this.serversSortDir = "asc";
      }

      localStorage.setItem(
        "kloigos_servers_sort_index",
        String(this.serversSortIndex),
      );
      localStorage.setItem("kloigos_servers_sort_dir", this.serversSortDir);
      this.applyServersFilterSort();
    },

    applyServersFilterSort() {
      const q = (this.serversFilterQuery || "").toLowerCase().trim();
      let rows = this.servers.slice();
      if (q) rows = rows.filter((s) => this.serversRowText(s).includes(q));

      if (this.serversSortIndex !== null) {
        const type =
          this.serversSortTypeByIndex[this.serversSortIndex] || "string";
        const idx = this.serversSortIndex;
        const dir = this.serversSortDir;

        rows.sort((a, b) => {
          const av = this.parseValue(type, this.serversCellText(a, idx));
          const bv = this.parseValue(type, this.serversCellText(b, idx));
          if (av < bv) return dir === "asc" ? -1 : 1;
          if (av > bv) return dir === "asc" ? 1 : -1;
          return 0;
        });
      }

      this.serversVisibleRows = rows;
    },

    async refreshServers() {
      this.serversLoading.list = true;
      try {
        const data = await this.apiFetch("/admin/servers/", { method: "GET" });
        this.servers = Array.isArray(data) ? data : [];
        this.serversLastUpdatedUtc = this.utcNowString();
        this.applyServersFilterSort();
      } catch (e) {
        console.error(e);
        this.serversLastUpdatedUtc = this.utcNowString();
      } finally {
        this.serversLoading.list = false;
      }
    },

    eventsDetailsText(event) {
      return this.toYaml(event?.details ?? null);
    },

    eventsRowText(event) {
      return [
        event.ts,
        event.user_id,
        event.action,
        event.request_id,
        this.eventsDetailsText(event),
      ]
        .filter(Boolean)
        .join(" ")
        .toLowerCase();
    },

    eventsCellText(event, colIndex) {
      switch (colIndex) {
        case 0:
          return event.ts || "";
        case 1:
          return event.user_id || "";
        case 2:
          return event.action || "";
        case 3:
          return this.eventsDetailsText(event);
        case 4:
          return event.request_id || "";
        default:
          return "";
      }
    },

    eventsSortClass(index) {
      if (this.eventsSortIndex !== index) return "";
      return this.eventsSortDir === "asc" ? "sort-asc" : "sort-desc";
    },

    toggleEventsSort(index) {
      if (this.eventsSortIndex === index)
        this.eventsSortDir = this.eventsSortDir === "asc" ? "desc" : "asc";
      else {
        this.eventsSortIndex = index;
        this.eventsSortDir = index === 0 ? "desc" : "asc";
      }

      localStorage.setItem(
        "kloigos_events_sort_index",
        String(this.eventsSortIndex),
      );
      localStorage.setItem("kloigos_events_sort_dir", this.eventsSortDir);
      this.applyEventsFilterSort();
    },

    applyEventsFilterSort() {
      const q = (this.eventsFilterQuery || "").toLowerCase().trim();
      let rows = this.events.slice();
      if (q) rows = rows.filter((event) => this.eventsRowText(event).includes(q));

      if (this.eventsSortIndex !== null) {
        const type = this.eventsSortTypeByIndex[this.eventsSortIndex] || "string";
        const idx = this.eventsSortIndex;
        const dir = this.eventsSortDir;

        rows.sort((a, b) => {
          const av = this.parseValue(type, this.eventsCellText(a, idx));
          const bv = this.parseValue(type, this.eventsCellText(b, idx));
          if (av < bv) return dir === "asc" ? -1 : 1;
          if (av > bv) return dir === "asc" ? 1 : -1;
          return 0;
        });
      }

      this.eventsVisibleRows = rows;
    },

    async refreshEvents() {
      this.eventsLoading.list = true;
      try {
        const data = await this.apiFetch("/admin/events", { method: "GET" });
        this.events = Array.isArray(data) ? data : [];
        this.eventsLastUpdatedUtc = this.utcNowString();
        this.applyEventsFilterSort();
      } catch (e) {
        if (e?.forbidden) {
          this.handleForbiddenView("events", { fallback: false });
        }
        console.error(e);
        this.eventsLastUpdatedUtc = this.utcNowString();
      } finally {
        this.eventsLoading.list = false;
      }
    },

    apiKeysRolesText(row) {
      return Array.isArray(row?.roles) && row.roles.length
        ? row.roles.join(", ")
        : "-";
    },

    apiKeysRowText(row) {
      return [
        row?.access_key,
        row?.owner,
        row?.valid_until,
        this.apiKeysRolesText(row),
      ]
        .filter(Boolean)
        .join(" ")
        .toLowerCase();
    },

    apiKeysCellText(row, colIndex) {
      switch (colIndex) {
        case 0:
          return row?.access_key || "";
        case 1:
          return row?.owner || "";
        case 2:
          return row?.valid_until || "";
        case 3:
          return this.apiKeysRolesText(row);
        default:
          return "";
      }
    },

    apiKeysSortClass(index) {
      if (this.apiKeysSortIndex !== index) return "";
      return this.apiKeysSortDir === "asc" ? "sort-asc" : "sort-desc";
    },

    toggleApiKeysSort(index) {
      if (this.apiKeysSortIndex === index)
        this.apiKeysSortDir = this.apiKeysSortDir === "asc" ? "desc" : "asc";
      else {
        this.apiKeysSortIndex = index;
        this.apiKeysSortDir = index === 2 ? "desc" : "asc";
      }

      localStorage.setItem(
        "kloigos_api_keys_sort_index",
        String(this.apiKeysSortIndex),
      );
      localStorage.setItem("kloigos_api_keys_sort_dir", this.apiKeysSortDir);
      this.applyApiKeysFilterSort();
    },

    applyApiKeysFilterSort() {
      const q = (this.apiKeysFilterQuery || "").toLowerCase().trim();
      let rows = this.apiKeys.slice();
      if (q) rows = rows.filter((row) => this.apiKeysRowText(row).includes(q));

      if (this.apiKeysSortIndex !== null) {
        const type =
          this.apiKeysSortTypeByIndex[this.apiKeysSortIndex] || "string";
        const idx = this.apiKeysSortIndex;
        const dir = this.apiKeysSortDir;

        rows.sort((a, b) => {
          const av = this.parseValue(type, this.apiKeysCellText(a, idx));
          const bv = this.parseValue(type, this.apiKeysCellText(b, idx));
          if (av < bv) return dir === "asc" ? -1 : 1;
          if (av > bv) return dir === "asc" ? 1 : -1;
          return 0;
        });
      }

      this.apiKeysVisibleRows = rows;
    },

    persistApiKeysFilter() {
      localStorage.setItem(
        "kloigos_api_keys_filter",
        this.apiKeysFilterQuery || "",
      );
    },

    async refreshApiKeys() {
      this.apiKeysLoading.list = true;
      try {
        const data = await this.apiFetch("/admin/api_keys/", { method: "GET" });
        this.apiKeys = Array.isArray(data) ? data : [];
        this.apiKeysLastUpdatedUtc = this.utcNowString();
        this.applyApiKeysFilterSort();
      } catch (e) {
        if (e?.forbidden) {
          this.handleForbiddenView("api_keys", { fallback: false });
        }
        console.error(e);
        this.apiKeysLastUpdatedUtc = this.utcNowString();
      } finally {
        this.apiKeysLoading.list = false;
      }
    },

    defaultApiKeyValidUntilUtc() {
      return new Date(Date.now() + 24 * 60 * 60 * 1000)
        .toISOString()
        .replace(/\.\d{3}Z$/, "Z");
    },

    openApiKeyCreateModal() {
      this.clearModalError("apiKeyCreate");
      this.modal.apiKeyCreate.valid_until = this.defaultApiKeyValidUntilUtc();
      this.modal.apiKeyCreate.roles = ["KLOIGOS_ADMIN"];
      this.modal.apiKeyCreate.open = true;
    },

    closeApiKeyCreateModal() {
      this.modal.apiKeyCreate.open = false;
      this.clearModalError("apiKeyCreate");
    },

    openApiKeyDeleteConfirm(row) {
      this.modal.apiKeyDeleteConfirm.access_key = row?.access_key || "";
      this.modal.apiKeyDeleteConfirm.owner = row?.owner || "";
      this.clearModalError("apiKeyDeleteConfirm");
      this.modal.apiKeyDeleteConfirm.open = true;
    },

    closeApiKeyDeleteConfirm() {
      this.modal.apiKeyDeleteConfirm.open = false;
      this.clearModalError("apiKeyDeleteConfirm");
    },

    closeApiKeySecretModal() {
      this.modal.apiKeySecret.open = false;
      this.modal.apiKeySecret.access_key = "";
      this.modal.apiKeySecret.owner = "";
      this.modal.apiKeySecret.valid_until = "";
      this.modal.apiKeySecret.roles = [];
      this.modal.apiKeySecret.secret_access_key = "";
      this.modal.apiKeySecret.reveal = false;
      this.modal.apiKeySecret.copied = false;
    },

    toggleApiKeySecretVisibility() {
      this.modal.apiKeySecret.reveal = !this.modal.apiKeySecret.reveal;
      this.modal.apiKeySecret.copied = false;
    },

    maskedSecret(secret) {
      const value = String(secret || "");
      return value ? "•".repeat(Math.max(24, value.length)) : "";
    },

    async copyApiKeySecret() {
      if (!this.modal.apiKeySecret.reveal) return;
      const secret = String(this.modal.apiKeySecret.secret_access_key || "");
      if (!secret) return;

      if (
        typeof navigator !== "undefined" &&
        navigator.clipboard &&
        typeof navigator.clipboard.writeText === "function"
      ) {
        await navigator.clipboard.writeText(secret);
      } else if (typeof document !== "undefined") {
        const el = document.createElement("textarea");
        el.value = secret;
        el.setAttribute("readonly", "");
        el.style.position = "absolute";
        el.style.left = "-9999px";
        document.body.appendChild(el);
        el.select();
        document.execCommand("copy");
        document.body.removeChild(el);
      }

      this.modal.apiKeySecret.copied = true;
    },

    async createApiKey() {
      this.apiKeysLoading.create = true;
      this.clearModalError("apiKeyCreate");
      try {
        const validUntil = String(this.modal.apiKeyCreate.valid_until || "").trim();
        if (!validUntil) throw new Error("valid_until is required.");
        if (!validUntil.endsWith("Z")) {
          throw new Error("valid_until must be a UTC timestamp ending in Z.");
        }
        const parsedValidUntil = new Date(validUntil);
        if (Number.isNaN(parsedValidUntil.getTime())) {
          throw new Error("valid_until must be a valid UTC timestamp.");
        }

        const roles = Array.isArray(this.modal.apiKeyCreate.roles)
          ? this.modal.apiKeyCreate.roles.filter(Boolean)
          : [];
        if (roles.length === 0) throw new Error("Select at least one role.");

        const payload = {
          valid_until: parsedValidUntil.toISOString(),
          roles,
        };

        const created = await this.apiFetch("/admin/api_keys/", {
          method: "POST",
          body: payload,
        });

        this.closeApiKeyCreateModal();
        this.modal.apiKeySecret.access_key = created?.access_key || "";
        this.modal.apiKeySecret.owner = created?.owner || "";
        this.modal.apiKeySecret.valid_until = created?.valid_until || "";
        this.modal.apiKeySecret.roles = Array.isArray(created?.roles)
          ? created.roles
          : [];
        this.modal.apiKeySecret.secret_access_key =
          created?.secret_access_key || "";
        this.modal.apiKeySecret.reveal = false;
        this.modal.apiKeySecret.copied = false;
        this.modal.apiKeySecret.open = true;
        await this.refreshApiKeys();
      } catch (e) {
        this.setModalError("apiKeyCreate", e, "Failed to create API key.");
      } finally {
        this.apiKeysLoading.create = false;
      }
    },

    async confirmApiKeyDelete() {
      const accessKey = String(
        this.modal.apiKeyDeleteConfirm.access_key || "",
      ).trim();
      if (!accessKey) return;

      this.apiKeysLoading.delete = true;
      this.clearModalError("apiKeyDeleteConfirm");
      try {
        await this.apiFetch(`/admin/api_keys/${encodeURIComponent(accessKey)}`, {
          method: "DELETE",
        });
        this.closeApiKeyDeleteConfirm();
        await this.refreshApiKeys();
      } catch (e) {
        this.setModalError(
          "apiKeyDeleteConfirm",
          e,
          "Failed to delete API key.",
        );
      } finally {
        this.apiKeysLoading.delete = false;
      }
    },

    settingsRowText(row) {
      return [
        row?.key,
        row?.category,
        row?.value_type,
        row?.effective_value,
        row?.default_value,
        row?.updated_by,
      ]
        .filter(Boolean)
        .join(" ")
        .toLowerCase();
    },

    settingsCellText(row, colIndex) {
      switch (colIndex) {
        case 0:
          return row?.key || "";
        case 1:
          return row?.category || "";
        case 2:
          return row?.value_type || "";
        case 3:
          return row?.effective_value || "";
        case 4:
          return row?.default_value || "";
        case 5:
          return row?.updated_at || "";
        default:
          return "";
      }
    },

    settingsSortClass(index) {
      if (this.settingsSortIndex !== index) return "";
      return this.settingsSortDir === "asc" ? "sort-asc" : "sort-desc";
    },

    toggleSettingsSort(index) {
      if (this.settingsSortIndex === index)
        this.settingsSortDir = this.settingsSortDir === "asc" ? "desc" : "asc";
      else {
        this.settingsSortIndex = index;
        this.settingsSortDir = index === 5 ? "desc" : "asc";
      }

      localStorage.setItem(
        "kloigos_settings_sort_index",
        String(this.settingsSortIndex),
      );
      localStorage.setItem("kloigos_settings_sort_dir", this.settingsSortDir);
      this.applySettingsFilterSort();
    },

    applySettingsFilterSort() {
      const q = (this.settingsFilterQuery || "").toLowerCase().trim();
      let rows = this.settings.slice();
      if (q) rows = rows.filter((row) => this.settingsRowText(row).includes(q));

      if (this.settingsSortIndex !== null) {
        const type =
          this.settingsSortTypeByIndex[this.settingsSortIndex] || "string";
        const idx = this.settingsSortIndex;
        const dir = this.settingsSortDir;

        rows.sort((a, b) => {
          const av = this.parseValue(type, this.settingsCellText(a, idx));
          const bv = this.parseValue(type, this.settingsCellText(b, idx));
          if (av < bv) return dir === "asc" ? -1 : 1;
          if (av > bv) return dir === "asc" ? 1 : -1;
          return 0;
        });
      }

      this.settingsVisibleRows = rows;
    },

    persistSettingsFilter() {
      localStorage.setItem("kloigos_settings_filter", this.settingsFilterQuery || "");
    },

    settingDraftValue(row) {
      const key = row?.key;
      if (!key) return "";
      if (Object.prototype.hasOwnProperty.call(this.settingsDrafts, key)) {
        return this.settingsDrafts[key];
      }
      return row?.effective_value || "";
    },

    setSettingDraft(key, value) {
      if (!key) return;
      this.settingsDrafts = {
        ...this.settingsDrafts,
        [key]: String(value ?? ""),
      };
    },

    isSettingDirty(row) {
      return this.settingDraftValue(row) !== String(row?.effective_value || "");
    },

    settingValuePreview(row, value) {
      if (row?.is_secret) return "(hidden)";
      return String(value ?? "") || "-";
    },

    settingSourceLabel(row) {
      return row?.value === null || row?.value === undefined ? "Default" : "Override";
    },

    async refreshSettings() {
      this.settingsLoading.list = true;
      this.settingsError = "";
      try {
        const existingRowsByKey = Object.fromEntries(
          this.settings.map((row) => [row.key, row]),
        );
        const data = await this.apiFetch("/admin/settings", { method: "GET" });
        const rows = Array.isArray(data)
          ? data
          : Array.isArray(data?.items)
            ? data.items
            : Array.isArray(data?.settings)
              ? data.settings
              : [];
        this.settings = rows;
        this.settingsDrafts = Object.fromEntries(
          this.settings.map((row) => {
            const existing = existingRowsByKey[row.key];
            const existingDraft = this.settingsDrafts[row.key];
            const existingEffective = String(existing?.effective_value || "");
            const nextEffective = String(row.effective_value || "");
            if (
              existingDraft !== undefined &&
              existingDraft !== existingEffective
            ) {
              return [row.key, existingDraft];
            }
            return [row.key, nextEffective];
          }),
        );
        this.settingsLastUpdatedUtc = this.utcNowString();
        this.applySettingsFilterSort();
      } catch (e) {
        if (e?.forbidden) {
          this.handleForbiddenView("settings", { fallback: false });
        }
        this.settingsError = this.errorMessage(
          e,
          "Failed to load settings.",
        );
        console.error(e);
        this.settingsLastUpdatedUtc = this.utcNowString();
      } finally {
        this.settingsLoading.list = false;
      }
    },

    async saveSetting(row) {
      const key = row?.key;
      if (!key) return;

      this.settingsLoading.update = true;
      try {
        const updated = await this.apiFetch(
          `/admin/settings/${encodeURIComponent(key)}`,
          {
            method: "PATCH",
            body: { value: this.settingDraftValue(row) },
          },
        );
        this.settings = this.settings.map((entry) =>
          entry.key === updated.key ? updated : entry,
        );
        this.setSettingDraft(updated.key, updated.effective_value || "");
        this.settingsLastUpdatedUtc = this.utcNowString();
        this.applySettingsFilterSort();
      } catch (e) {
        console.error(e);
      } finally {
        this.settingsLoading.update = false;
      }
    },

    openSettingResetConfirm(row) {
      this.modal.settingResetConfirm.key = row?.key || "";
      this.modal.settingResetConfirm.category = row?.category || "";
      this.modal.settingResetConfirm.value_type = row?.value_type || "";
      this.modal.settingResetConfirm.default_value = row?.default_value || "";
      this.modal.settingResetConfirm.is_secret = Boolean(row?.is_secret);
      this.clearModalError("settingResetConfirm");
      this.modal.settingResetConfirm.open = true;
    },

    closeSettingResetConfirm() {
      this.modal.settingResetConfirm.open = false;
      this.clearModalError("settingResetConfirm");
    },

    async confirmSettingReset() {
      const key = String(this.modal.settingResetConfirm.key || "").trim();
      if (!key) return;

      this.settingsLoading.reset = true;
      try {
        const updated = await this.apiFetch(
          `/admin/settings/${encodeURIComponent(key)}`,
          { method: "PUT" },
        );
        this.settings = this.settings.map((entry) =>
          entry.key === updated.key ? updated : entry,
        );
        this.setSettingDraft(updated.key, updated.effective_value || "");
        this.closeSettingResetConfirm();
        this.settingsLastUpdatedUtc = this.utcNowString();
        this.applySettingsFilterSort();
      } catch (e) {
        this.setModalError(
          "settingResetConfirm",
          e,
          "Failed to reset setting.",
        );
      } finally {
        this.settingsLoading.reset = false;
      }
    },

    openServerActionConfirm(server, action) {
      this.modal.serverActionConfirm.hostname = server?.hostname || "";
      this.modal.serverActionConfirm.action = action || "decommission";
      this.clearModalError("serverActionConfirm");
      this.modal.serverActionConfirm.open = true;
    },

    closeServerActionConfirm() {
      this.modal.serverActionConfirm.open = false;
      this.clearModalError("serverActionConfirm");
    },

    async confirmServerAction() {
      const hostname = (this.modal.serverActionConfirm.hostname || "").trim();
      const action = this.modal.serverActionConfirm.action;
      if (!hostname) return;

      this.serversLoading.action = true;
      try {
        if (action === "delete") {
          await this.apiFetch(
            `/admin/servers/${encodeURIComponent(hostname)}`,
            {
              method: "DELETE",
            },
          );
        } else {
          await this.apiFetch(
            `/admin/servers/${encodeURIComponent(hostname)}`,
            {
              method: "PUT",
            },
          );
        }
        this.closeServerActionConfirm();
        await this.refreshServers();
      } catch (e) {
        this.setModalError(
          "serverActionConfirm",
          e,
          "Failed to run server action.",
        );
      } finally {
        this.serversLoading.action = false;
      }
    },

    // ---------- Dashboard lifecycle ----------
    async ensureDashboardView() {
      if (this.computeUnits.length === 0 && !this.loading.list)
        await this.refreshDashboard();
      if (typeof this.refreshServers === "function")
        await this.refreshServers();
      else this.applyFilterSort();
    },

    persistFilter() {
      localStorage.setItem("kloigos_filter", this.filterQuery || "");
    },

    persistServersFilter() {
      localStorage.setItem(
        "kloigos_servers_filter",
        this.serversFilterQuery || "",
      );
    },
    persistEventsFilter() {
      localStorage.setItem("kloigos_events_filter", this.eventsFilterQuery || "");
    },
    persistInspectorFormat() {
      localStorage.setItem("kloigos_inspector_format", this.inspectorFormat);
    },

    async refreshDashboard() {
      this.loading.list = true;
      try {
        const data = await this.apiFetch("/compute_units/");
        this.computeUnits = Array.isArray(data) ? data : [];
        this.computeUnits = this.computeUnits.map((row) => ({
          ...row,
          compute_id: `${row.hostname}_${row.cpu_range}`,
        }));
        this.lastUpdatedUtc = this.utcNowString();
        this.applyFilterSort();
      } catch (e) {
        console.error(e);
        this.lastUpdatedUtc = this.utcNowString();
      } finally {
        this.loading.list = false;
      }
    },

    // ---------- Dashboard sorting/filtering ----------
    rowText(row) {
      const parts = [
        row.compute_id,
        row.hostname,
        row.ip,
        row.region,
        row.zone,
        row.status,
        this.tagValue(row, "deployment_id"),
      ];
      const tags =
        row.tags && typeof row.tags === "object"
          ? Object.entries(row.tags).map(
              ([k, v]) => `${k}:${Array.isArray(v) ? v.join(",") : v}`,
            )
          : [];
      return parts.concat(tags).filter(Boolean).join(" ").toLowerCase();
    },

    parseValue(type, value) {
      const v = (value ?? "").toString().trim();
      if (type === "number") {
        const n = parseFloat(v);
        return Number.isFinite(n) ? n : Number.NEGATIVE_INFINITY;
      }
      if (type === "date") {
        const d = new Date(v);
        return isNaN(d.getTime()) ? 0 : d.getTime();
      }
      if (type === "ip") {
        return v
          .split(".")
          .map((o) => o.padStart(3, "0"))
          .join(".");
      }
      return v.toLowerCase();
    },

    cellText(row, colIndex) {
      switch (colIndex) {
        case 0:
          return this.tagValue(row, "deployment_id") || "";
        case 1:
          return row.compute_id;
        case 2:
          return `${row.region || "-"}-${row.zone || "-"}`;
        case 3:
          return row.hostname || "";
        case 4:
          return row.ip || "";
        case 5:
          return row.cpu_count;
        case 6:
          return row.cpu_range || "";
        case 7:
          return row.ports_range || "";
        case 8:
          return row.started_at || "";
        case 9:
          return row.status || "";
        default:
          return "";
      }
    },

    applyFilterSort() {
      const q = (this.filterQuery || "").toLowerCase().trim();
      let rows = this.computeUnits.slice();
      if (q) rows = rows.filter((r) => this.rowText(r).includes(q));

      if (this.sortIndex !== null) {
        const type = this.sortTypeByIndex[this.sortIndex] || "string";
        const idx = this.sortIndex;
        const dir = this.sortDir;

        rows.sort((a, b) => {
          const av = this.parseValue(type, this.cellText(a, idx));
          const bv = this.parseValue(type, this.cellText(b, idx));
          if (av < bv) return dir === "asc" ? -1 : 1;
          if (av > bv) return dir === "asc" ? 1 : -1;
          return 0;
        });
      }

      this.visibleRows = rows;
    },

    toggleSort(index) {
      if (this.sortIndex === index)
        this.sortDir = this.sortDir === "asc" ? "desc" : "asc";
      else {
        this.sortIndex = index;
        this.sortDir = "asc";
      }

      localStorage.setItem("kloigos_sort_index", String(this.sortIndex));
      localStorage.setItem("kloigos_sort_dir", this.sortDir);
      this.applyFilterSort();
    },

    sortClass(index) {
      if (this.sortIndex !== index) return "";
      return this.sortDir === "asc" ? "sort-asc" : "sort-desc";
    },

    tagValue(row, key) {
      const t = row.tags;
      if (!t || typeof t !== "object") return null;
      const v = t[key];
      if (v === undefined || v === null) return null;
      return Array.isArray(v) ? v.join(",") : String(v);
    },

    extraTags(row) {
      const t = row.tags;
      if (!t || typeof t !== "object") return [];
      return Object.entries(t).filter(
        ([k, _]) => !["deployment_id", "owner"].includes(k),
      );
    },

    formatTag(k, v) {
      if (Array.isArray(v)) return `${k}:[${v.join(",")}]`;
      return `${k}:${v}`;
    },

    statusClass(status) {
      const s = String(status || "").toLowerCase();
      if (s.includes("free")) return "status-online";
      if (s.includes("allocated")) return "status-warning";
      if (s.includes("decommissioned")) return "status-muted";
      if (s.includes("ing")) return "status-pending status-pulse";
      if (!s || s === "unknown") return "status-muted";
      return "status-offline";
    },

    // ---------- Inspector JSON -> YAML ----------
    inspectorText() {
      if (!this.inspector) return "No requests yet.";
      if (this.inspectorFormat === "json")
        return JSON.stringify(this.inspector, null, 2);
      return this.toYaml(this.inspector);
    },

    toYaml(value) {
      const isObj = (v) => v && typeof v === "object" && !Array.isArray(v);
      const needsQuotes = (s) =>
        s === "" ||
        /[:\-\?\[\]\{\},#&\*!|>'"%@`]/.test(s) ||
        /^\s|\s$/.test(s) ||
        /^(true|false|null|~|-?\d+(\.\d+)?)$/i.test(s);

      const quote = (s) =>
        `"${String(s).replace(/\\/g, "\\\\").replace(/"/g, '\\"')}"`;

      const scalar = (v) => {
        if (v === null) return "null";
        if (v === true) return "true";
        if (v === false) return "false";
        if (typeof v === "number")
          return Number.isFinite(v) ? String(v) : quote(String(v));
        if (typeof v === "string") return needsQuotes(v) ? quote(v) : v;
        return quote(String(v));
      };

      const indent = (n) => "  ".repeat(n);

      const render = (v, depth) => {
        if (Array.isArray(v)) {
          if (v.length === 0) return "[]";
          return v
            .map((item) => {
              if (isObj(item) || Array.isArray(item)) {
                return `${indent(depth)}- ${render(
                  item,
                  depth + 1,
                ).trimStart()}`;
              }
              return `${indent(depth)}- ${scalar(item)}`;
            })
            .join("\n");
        }

        if (isObj(v)) {
          const keys = Object.keys(v);
          if (keys.length === 0) return "{}";
          return keys
            .map((k) => {
              const val = v[k];
              const keyStr = needsQuotes(k) ? quote(k) : k;
              if (isObj(val) || Array.isArray(val)) {
                return `${indent(depth)}${keyStr}:\n${render(val, depth + 1)}`;
              }
              return `${indent(depth)}${keyStr}: ${scalar(val)}`;
            })
            .join("\n");
        }

        return scalar(v);
      };

      return render(value, 0);
    },

    // ---------- Dashboard actions ----------
    openAllocateModal(computeId = "") {
      this.modal.allocate.compute_id = computeId ? String(computeId) : "";
      this.clearModalError("allocate");
      this.modal.allocate.open = true;
    },
    closeAllocateModal() {
      this.modal.allocate.open = false;
      this.clearModalError("allocate");
    },

    async allocate() {
      this.loading.allocate = true;
      this.clearModalError("allocate");
      try {
        const tags = JSON.parse(
          (this.modal.allocate.tagsText || "{}").trim() || "{}",
        );

        const payload = {
          cpu_count: this.modal.allocate.cpu_count ?? null,
          region: this.modal.allocate.region || null,
          zone: this.modal.allocate.zone || null,
          compute_id: (this.modal.allocate.compute_id || "").trim() || null,
          tags,
          ssh_public_key: (this.modal.allocate.ssh_public_key || "").trim(),
        };

        const deployment_id = (this.modal.allocate.deployment_id || "").trim();
        if (deployment_id)
          payload.tags = { ...(payload.tags || {}), deployment_id };

        if (!payload.ssh_public_key)
          throw new Error("ssh_public_key is required.");
        if (tags === null || typeof tags !== "object" || Array.isArray(tags))
          throw new Error("tags must be a JSON object.");
        await this.apiFetch("/compute_units/allocate", {
          method: "POST",
          body: payload,
        });
        this.closeAllocateModal();
        await this.refreshDashboard();
        if (typeof this.refreshServers === "function")
          await this.refreshServers();
      } catch (err) {
        this.setModalError("allocate", err, "Allocation failed.");
      } finally {
        this.loading.allocate = false;
      }
    },

    openInitModal() {
      // Keep any existing values, but ensure step has a sane default.
      if (this.modal.init.cpuStep == null || this.modal.init.cpuStep <= 0)
        this.modal.init.cpuStep = null;

      this.clearModalError("init");
      this.modal.init.open = true;
      this.recomputeInitCpuRanges();
    },
    closeInitModal() {
      this.modal.init.open = false;
      this.clearModalError("init");
      this.modal.init.ip = "";
      this.modal.init.hostname = "";
      this.modal.init.user_id = "ubuntu";
      this.modal.init.region = "";
      this.modal.init.zone = "";
      this.modal.init.deployment_id = "";
      this.modal.init.cpuStart = 0;
      this.modal.init.cpuEnd = 0;
      this.modal.init.cpuStep = 0;
      this.modal.init.cpuRangesText = "";
      this.modal.init.cpuRangesPreview = "";
      this.modal.init.cpuSetPreview = "";
      this.modal.init.cpuRangesError = "";
    },

    recomputeInitCpuRanges(fromTextarea = false) {
      // If fromTextarea=true, parse cpuRangesText and just update previews.
      // Otherwise compute ranges from start/end/step and update cpuRangesText + previews.
      try {
        this.modal.init.cpuRangesError = "";

        let cpu_ranges = [];
        let cpu_set = [];

        if (fromTextarea) {
          const parsed = JSON.parse(
            (this.modal.init.cpuRangesText || "[]").trim() || "[]",
          );
          if (
            !Array.isArray(parsed) ||
            parsed.some((x) => typeof x !== "string")
          )
            throw new Error("cpu_ranges must be a JSON array of strings.");
          cpu_ranges = parsed;
        } else {
          const start = 0;
          const end = Number(this.modal.init.cpuEnd) - 1;
          const step = Number(this.modal.init.cpuStep);

          if (!Number.isInteger(end) || end < 0)
            throw new Error("end must be a non-negative integer.");
          if (!Number.isInteger(step) || step <= 0)
            throw new Error("step must be a positive integer.");
          if (end < start) throw new Error("end must be >= start.");

          // Build chunks: [start..min(start+step-1,end)], then advance by step.
          for (let cur = start; cur <= end; cur += step) {
            const chunkEnd = Math.min(cur + step - 1, end);
            cpu_ranges.push(`${cur}-${chunkEnd}`);
          }

          // Keep JSON textarea in sync for transparency / copy-paste.
          this.modal.init.cpuRangesText = JSON.stringify(cpu_ranges);
        }

        // Expand to a CPU set preview (best-effort)
        for (const r of cpu_ranges) {
          const m = String(r).match(/^\s*(\d+)\s*-\s*(\d+)\s*$/);
          if (!m) continue;
          const a = Number(m[1]);
          const b = Number(m[2]);
          if (!Number.isInteger(a) || !Number.isInteger(b) || b < a) continue;
          for (let i = a; i <= b; i++) cpu_set.push(i);
        }

        // De-dup + sort
        cpu_set = Array.from(new Set(cpu_set)).sort((a, b) => a - b);

        this.modal.init.cpuRangesPreview = JSON.stringify(cpu_ranges, null, 2);
        this.modal.init.cpuSetPreview = cpu_set.length
          ? `${cpu_set.join(", ")}\n(count: ${cpu_set.length})`
          : "-";
      } catch (e) {
        this.modal.init.cpuRangesPreview = "";
        this.modal.init.cpuSetPreview = "";
        this.modal.init.cpuRangesError = e.message || String(e);
      }
    },

    async initServer() {
      this.loading.init = true;
      this.clearModalError("init");
      try {
        const cpu_ranges = JSON.parse(
          (this.modal.init.cpuRangesText || "[]").trim() || "[]",
        );
        if (
          !Array.isArray(cpu_ranges) ||
          cpu_ranges.some((x) => typeof x !== "string")
        )
          throw new Error("cpu_ranges must be a JSON array of strings.");

        const payload = {
          ip: (this.modal.init.ip || "").trim(),
          region: (this.modal.init.region || "").trim(),
          zone: (this.modal.init.zone || "").trim(),
          hostname: (this.modal.init.hostname || "").trim(),
          user_id: (this.modal.init.user_id || "ubuntu").trim(),
          cpu_ranges,
        };
        for (const [k, v] of Object.entries(payload)) {
          if ((typeof v === "string" && !v) || v == null)
            throw new Error(`${k} is required.`);
        }

        await this.apiFetch("/admin/servers/", {
          method: "POST",
          body: payload,
        });
        this.closeInitModal();
        await this.refreshDashboard();
        if (typeof this.refreshServers === "function")
          await this.refreshServers();
      } catch (e) {
        this.setModalError("init", e, "Server init failed.");
      } finally {
        this.loading.init = false;
      }
    },

    openDecommissionModal() {
      this.clearModalError("decommission");
      this.modal.decommission.open = true;
    },
    closeDecommissionModal() {
      this.modal.decommission.open = false;
      this.clearModalError("decommission");
    },

    async decommissionByHostname() {
      this.loading.decommission = true;
      this.clearModalError("decommission");
      try {
        const payload = {
          hostname: (this.modal.decommission.hostname || "").trim(),
        };

        await this.apiFetch("/admin/servers/", {
          method: "PUT",
          body: payload,
        });

        this.closeDecommissionModal();
        await this.refreshDashboard();
        if (typeof this.refreshServers === "function")
          await this.refreshServers();
      } catch (e) {
        this.setModalError("decommission", e, "Server decommission failed.");
      } finally {
        this.loading.decommission = false;
      }
    },

    openDeallocateConfirm(row) {
      this.modal.deallocateConfirm.compute_id = row.compute_id;
      this.modal.deallocateConfirm.hostname = row.hostname || "";
      this.clearModalError("deallocateConfirm");
      this.modal.deallocateConfirm.open = true;
    },
    closeDeallocateConfirm() {
      this.modal.deallocateConfirm.open = false;
      this.clearModalError("deallocateConfirm");
    },

    openComputeDetails(row) {
      this.modal.computeDetails.row = row || null;
      this.modal.computeDetails.open = true;
    },
    closeComputeDetails() {
      this.modal.computeDetails.open = false;
      this.modal.computeDetails.row = null;
    },

    openServerDetails(row) {
      this.modal.serverDetails.row = row || null;
      this.modal.serverDetails.open = true;
    },

    closeServerDetails() {
      this.modal.serverDetails.open = false;
      this.modal.serverDetails.row = null;
    },

    async confirmDeallocate() {
      const computeId = this.modal.deallocateConfirm.compute_id;
      this.loading.deallocateConfirm = true;
      this.busyKey = computeId;
      this.clearModalError("deallocateConfirm");
      try {
        await this.apiFetch(
          `/compute_units/deallocate/${encodeURIComponent(computeId)}`,
          { method: "DELETE" },
        );
        this.closeDeallocateConfirm();
        await this.refreshDashboard();
        if (typeof this.refreshServers === "function")
          await this.refreshServers();
      } catch (e) {
        this.setModalError("deallocateConfirm", e, "Deallocate failed.");
      } finally {
        this.loading.deallocateConfirm = false;
        this.busyKey = null;
      }
    },

    // ---------- Playbooks lifecycle ----------
    async ensurePlaybooksView() {
      if (!this.canViewAdmin()) {
        this.handleForbiddenView("playbooks", { fallback: false });
        return;
      }
      this.ensureAce();
      if (this.playbooks.length === 0 && !this.pbLoading.list)
        await this.reloadPlaybooks();
    },

    ensureAce() {
      if (this._aceReady) return;

      if (!window.ace || !this.$refs.aceContainer) {
        this.pbToast = {
          ok: false,
          message: "Ace not loaded or container missing.",
        };
        return;
      }

      const editor = window.ace.edit(this.$refs.aceContainer);
      editor.setTheme("ace/theme/cobalt");
      editor.session.setMode("ace/mode/yaml");
      editor.setOptions({
        showPrintMargin: false,
        useSoftTabs: true,
        tabSize: 2,
        wrap: true,
      });

      // keep reference
      this._ace = editor;
      this._aceReady = true;
      this.pbEditorReady = true;
      this.pbToast = {
        ok: true,
        message: `${this.utcNowString()} - Editor ready.`,
      };
    },

    async reloadPlaybooks() {
      this.pbLoading.list = true;
      try {
        // Select first by default
        if (this.playbooks.length && !this.selectedPlaybook) {
          this.selectedPlaybook = this.playbooks[0];
        }
        if (this.selectedPlaybook) await this.onSelectPlaybook();

        this.pbToast = {
          ok: true,
          message: `${this.utcNowString()} - Loaded playbooks list (${
            this.playbooks.length
          }).`,
        };
      } catch (e) {
        this.pbToast = { ok: false, message: `List failed: ${e.message}` };
      } finally {
        this.pbLoading.list = false;
      }
    },

    async onSelectPlaybook() {
      if (!this.selectedPlaybook) return;
      if (!this._aceReady || !this._ace) {
        this.pbToast = { ok: false, message: "Editor not ready yet." };
        return;
      }
      await this.loadPlaybookContent(this.selectedPlaybook);
    },

    async loadPlaybookContent(name) {
      this.pbLoading.load = true;
      try {
        const payload = await this.apiFetch(
          `/admin/playbooks/${encodeURIComponent(name)}`,
          { method: "GET" },
        );

        let text = "";

        if (typeof payload === "string") {
          try {
            // base64 → UTF-8
            text = this.b64decode(payload);
          } catch {
            // fallback: assume it's already plain text
            text = payload;
          }
        } else {
          text = String(payload ?? "");
        }

        this._ace.setValue(text, -1); // -1 keeps cursor at start
        this.pbLastUpdatedUtc = this.utcNowString();
        this.pbToast = {
          ok: true,
          message: `${this.utcNowString()} - Loaded "${name}".`,
        };
      } catch (e) {
        this.pbToast = { ok: false, message: `Load failed: ${e.message}` };
      } finally {
        this.pbLoading.load = false;
      }
    },

    // Encode (String → Base64)
    b64encode(str) {
      return btoa(String.fromCodePoint(...new TextEncoder().encode(str)));
    },

    // Decode (Base64 → String)
    b64decode(b64) {
      return new TextDecoder().decode(
        Uint8Array.from(atob(b64), (c) => c.charCodeAt(0)),
      );
    },

    async savePlaybook() {
      if (!this.selectedPlaybook) {
        this.pbToast = { ok: false, message: "Select a playbook first." };
        return;
      }
      if (!this._aceReady || !this._ace) {
        this.pbToast = { ok: false, message: "Editor not ready yet." };
        return;
      }

      this.pbLoading.save = true;

      try {
        await this.apiFetch(
          `/admin/playbooks/${encodeURIComponent(this.selectedPlaybook)}`,
          {
            method: "PATCH",
            body: this.b64encode(this._ace.getValue()),
          },
        );

        this.pbToast = {
          ok: true,
          message: `${this.utcNowString()} - Saved "${this.selectedPlaybook}".`,
        };
      } catch (e) {
        this.pbToast = { ok: false, message: `Save failed: ${e.message}` };
      } finally {
        this.pbLoading.save = false;
      }
    },
  };
};
