window.cpkitWebappExtension = {
  htmlPath: "/app/extension.html",
  dashboardEnsure: "ensureKloigosDashboard",
  navItems: [
    { view: "allocations", label: "Allocations" },
    { view: "compute_units", label: "Compute" },
    { view: "kloigos_servers", label: "Servers" },
  ],
  adminItems: [
    {
      view: "ip_pool",
      label: "IP Pool",
      kicker: "Networking",
      description: "Manage floating IP addresses available to allocations.",
      icon: "network",
      countKey: "ipPool",
    },
  ],
  routes: {
    allocations: {
      path: "/allocations",
      label: "Allocations",
      subtitle: "Durable workload identities and lifecycle",
      ensure: "ensureAllocationsView",
    },
    compute_units: {
      path: "/compute-units",
      label: "Compute Units",
      subtitle: "Kloigos capacity inventory",
      ensure: "ensureComputeUnitsView",
    },
    kloigos_servers: {
      path: "/servers",
      label: "Servers",
      subtitle: "Kloigos server inventory and lifecycle",
      ensure: "ensureKloigosServersView",
    },
    ip_pool: {
      path: "/admin/ip-pool",
      label: "IP Pool",
      subtitle: "Floating IP address pool",
      ensure: "ensureIpPoolView",
      adminOnly: true,
    },
  },
  state: {
    allocations: [],
    allocationsVisibleRows: [],
    allocationsDeallocatedVisibleRows: [],
    allocationsFilterQuery: "",
    allocationsLastUpdatedUtc: null,
    allocationsSortIndex: null,
    allocationsSortDir: "asc",
    allocationsSortTypeByIndex: {
      0: "string",
      1: "ip",
      2: "string",
      3: "string",
      4: "string",
      5: "string",
      6: "string",
      7: "date",
    },
    allocationsLoading: {
      list: false,
      allocate: false,
      deallocateConfirm: false,
      scale: false,
    },
    allocationsBusyKey: null,
    allocationsAutoRefreshEnabled: true,
    _allocationsAutoTimer: null,
    servers: [],
    serversVisibleRows: [],
    serversFilterQuery: "",
    serversLastUpdatedUtc: null,
    serversSortIndex: null,
    serversSortDir: "asc",
    serversSortTypeByIndex: {
      0: "string",
      1: "ip",
      2: "string",
      3: "string",
      4: "string",
      5: "string",
      6: "number",
      7: "number",
      8: "number",
      9: "number",
      10: "string",
      11: "string",
      12: "string",
    },
    serversLoading: { list: false, action: false, init: false },
    serversAutoRefreshEnabled: true,
    _serversAutoTimer: null,
    computeUnits: [],
    computeVisibleRows: [],
    computeFilterQuery: "",
    computeLastUpdatedUtc: null,
    computeSortIndex: null,
    computeSortDir: "asc",
    computeSortTypeByIndex: {
      0: "string",
      1: "string",
      2: "string",
      3: "string",
      4: "number",
      5: "date",
      6: "string",
    },
    computeLoading: {
      list: false,
    },
    computeAutoRefreshEnabled: true,
    _computeAutoTimer: null,
    ipPool: [],
    ipPoolVisibleRows: [],
    ipPoolFilterQuery: "",
    ipPoolLastUpdatedUtc: null,
    ipPoolSortIndex: 0,
    ipPoolSortDir: "asc",
    ipPoolSortTypeByIndex: {
      0: "ip",
      1: "string",
      2: "string",
      3: "string",
      4: "date",
      5: "date",
    },
    ipPoolLoading: {
      list: false,
      insert: false,
      delete: false,
    },
    ipPoolAutoRefreshEnabled: true,
    _ipPoolAutoTimer: null,
    ipPoolBusyKey: null,
    _allocationDetailsAce: null,
    _serverDetailsAce: null,
    modal: {
      allocate: {
        open: false,
        allocation_id: "",
        login_user: "",
        cpu_count: "",
        location: "",
        tagPairs: [{ key: "", value: "" }],
        ssh_public_key: "",
      },
      allocationDetails: { open: false, row: null },
      allocationScale: {
        open: false,
        allocation_id: "",
        compute_id: "",
        cpu_count: null,
        region: "",
        zone: "",
      },
      deallocateConfirm: { open: false, allocation_id: "", compute_id: "" },
      computeDetails: { open: false, row: null },
      serverDetails: { open: false, row: null },
      serverActionConfirm: { open: false, hostname: "", action: "decommission" },
      serverInit: {
        open: false,
        mode: "init",
        step: 1,
        private_ip: "",
        public_ip: "",
        hostname: "",
        server_admin_user: "ubuntu",
        region: "",
        zone: "",
        runtime_profile: "standard",
        cpu_count: null,
        mem_gb: null,
        disk_count: null,
        disk_size_gb: null,
        tagPairs: [{ key: "", value: "" }],
        compute_units: [{ ordinal: 1, cpu_range: "0-3", cpus: [0, 1, 2, 3] }],
      },
      ipPoolAdd: { open: false, ipAddresses: [{ value: "" }] },
      ipPoolDeleteConfirm: { open: false, ip_address: "" },
    },
    modalError: {
      allocate: "",
      allocationScale: "",
      deallocateConfirm: "",
      serverActionConfirm: "",
      serverInit: "",
      ipPoolAdd: "",
      ipPoolDeleteConfirm: "",
    },
  },
  async init() {
    this.configureKloigosChrome();
    this.restoreAllocationsLocalState();
    this.restoreComputeLocalState();
    this.restoreServersLocalState();
    this.restoreIpPoolLocalState();
    if (this.view === "allocations") await this.ensureAllocationsView();
    if (this.view === "compute_units") await this.ensureComputeUnitsView();
    if (this.view === "kloigos_servers") await this.ensureKloigosServersView();
    if (this.view === "ip_pool") await this.ensureIpPoolView();
    this.setManagedInterval("_allocationsAutoTimer", () => {
      if (this.allocationsAutoRefreshEnabled && this.view === "allocations") {
        this.refreshAllocations();
      }
    }, 5000);
    this.setManagedInterval("_computeAutoTimer", () => {
      if (this.computeAutoRefreshEnabled && this.view === "compute_units") {
        this.refreshComputeUnits();
      }
    }, 5000);
    this.setManagedInterval("_serversAutoTimer", () => {
      if (this.serversAutoRefreshEnabled && (this.view === "kloigos_servers" || this.view === "dashboard")) {
        this.refreshServers();
      }
    }, 5000);
    this.setManagedInterval("_ipPoolAutoTimer", () => {
      if (this.ipPoolAutoRefreshEnabled && this.view === "ip_pool") {
        this.refreshIpPool();
      }
    }, 5000);
  },
  methods: {
    configureKloigosChrome() {
      this.removeOpenApiJsonLink();
      this.addDocsTopbarLink();
    },

    removeOpenApiJsonLink() {
      const openApiJsonLink = document.querySelector('a[href="/api/openapi.json"]');
      if (openApiJsonLink) openApiJsonLink.remove();
    },

    addDocsTopbarLink() {
      const nav = document.querySelector(".topbar-nav");
      if (!nav || nav.querySelector(".kloigos-docs-link")) return;
      const link = document.createElement("a");
      link.className = "pill kloigos-docs-link";
      link.href = "https://fabiog1901.github.io/kloigos/";
      link.target = "_blank";
      link.rel = "noopener noreferrer";
      link.title = "Open Kloigos docs";
      link.setAttribute("aria-label", "Open Kloigos docs in a new tab");
      link.innerHTML = `
        <svg viewBox="0 0 24 24" aria-hidden="true">
          <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"></path>
          <path d="M4 4.5A2.5 2.5 0 0 1 6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15Z" fill="none" stroke="currentColor" stroke-width="2" stroke-linejoin="round"></path>
          <path d="M8 6h8" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"></path>
          <path d="M8 10h6" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"></path>
        </svg>
        <span>Docs</span>
      `;
      nav.appendChild(link);
    },

    async apiFetch(path, options = {}) {
      const headers = { Accept: "application/json", ...(options.headers || {}) };
      const fetchOptions = { method: options.method || "GET", headers };
      if (options.body !== undefined) {
        headers["Content-Type"] = "application/json";
        fetchOptions.body = JSON.stringify(options.body);
      }
      const res = await fetch(`${this.apiBase}${path}`, fetchOptions);
      const data = await this.safeJson(res);
      if (res.status === 401) {
        this.setAuthRequired(res.headers.get("x-auth-login-url"), this.apiErrorMessage(data, "Not authenticated."));
        throw new Error("Not authenticated.");
      }
      if (!res.ok) throw new Error(this.apiErrorMessage(data, `HTTP ${res.status}`));
      return data;
    },

    apiErrorMessage(data, fallback) {
      if (!data) return fallback;
      if (typeof data === "string") return data;
      const detail = this.formatApiErrorDetail(data.detail);
      if (detail) return detail;
      const message = this.formatApiErrorDetail(data.message);
      if (message) return message;
      return fallback;
    },

    formatApiErrorDetail(detail) {
      if (!detail) return "";
      if (typeof detail === "string") return detail;
      if (Array.isArray(detail)) {
        return detail
          .map((item) => this.formatApiErrorDetail(item))
          .filter(Boolean)
          .join(" ");
      }
      if (typeof detail === "object") {
        const location = Array.isArray(detail.loc)
          ? detail.loc.filter((part) => part !== "body").join(".")
          : "";
        const message = detail.msg || detail.message || "";
        if (location && message) return `${location}: ${message}`;
        if (message) return String(message);
        try {
          return JSON.stringify(detail);
        } catch {
          return String(detail);
        }
      }
      return String(detail);
    },

    restoreAllocationsLocalState() {
      const sortIndex = localStorage.getItem("kloigos_allocations_sort_index");
      const sortDir = localStorage.getItem("kloigos_allocations_sort_dir");
      const filter = localStorage.getItem("kloigos_allocations_filter");

      if (sortIndex !== null && !Number.isNaN(Number(sortIndex))) {
        this.allocationsSortIndex = Number(sortIndex);
      }
      if (sortDir === "asc" || sortDir === "desc") this.allocationsSortDir = sortDir;
      if (filter !== null) this.allocationsFilterQuery = filter;
    },

    restoreServersLocalState() {
      const sortIndex = localStorage.getItem("kloigos_servers_sort_index");
      const sortDir = localStorage.getItem("kloigos_servers_sort_dir");
      const filter = localStorage.getItem("kloigos_servers_filter");

      if (sortIndex !== null && !Number.isNaN(Number(sortIndex))) {
        this.serversSortIndex = Number(sortIndex);
      }
      if (sortDir === "asc" || sortDir === "desc") this.serversSortDir = sortDir;
      if (filter !== null) this.serversFilterQuery = filter;
    },

    restoreComputeLocalState() {
      const sortIndex = localStorage.getItem("kloigos_compute_sort_index");
      const sortDir = localStorage.getItem("kloigos_compute_sort_dir");
      const filter = localStorage.getItem("kloigos_compute_filter");

      if (sortIndex !== null && !Number.isNaN(Number(sortIndex))) {
        this.computeSortIndex = Number(sortIndex);
      }
      if (sortDir === "asc" || sortDir === "desc") this.computeSortDir = sortDir;
      if (filter !== null) this.computeFilterQuery = filter;
    },

    restoreIpPoolLocalState() {
      const sortIndex = localStorage.getItem("kloigos_ip_pool_sort_index");
      const sortDir = localStorage.getItem("kloigos_ip_pool_sort_dir");
      const filter = localStorage.getItem("kloigos_ip_pool_filter");

      if (sortIndex !== null && !Number.isNaN(Number(sortIndex))) {
        this.ipPoolSortIndex = Number(sortIndex);
      }
      if (sortDir === "asc" || sortDir === "desc") this.ipPoolSortDir = sortDir;
      if (filter !== null) this.ipPoolFilterQuery = filter;
    },

    async ensureAllocationsView() {
      if (!this.allocationsLoading.list) {
        await this.refreshAllocations();
      } else {
        this.applyAllocationsFilterSort();
      }
      if (!this.computeLoading.list) {
        await this.refreshComputeUnits();
      }
      if (this.canViewKloigosAdmin() && !this.serversLoading.list) {
        await this.refreshServers();
      }
    },

    async ensureComputeUnitsView() {
      if (!this.computeLoading.list) {
        await this.refreshComputeUnits();
      } else {
        this.applyComputeFilterSort();
      }
    },

    async ensureIpPoolView() {
      if (!this.canViewKloigosAdmin()) {
        this.showNotice("IP Pool requires CP_ADMIN.");
        return;
      }
      if (!this.ipPoolLoading.list) {
        await this.refreshIpPool();
      } else {
        this.applyIpPoolFilterSort();
      }
    },

    async refreshAllocations() {
      this.allocationsLoading.list = true;
      try {
        const data = await this.apiFetch("/allocations/", { method: "GET" });
        this.allocations = Array.isArray(data)
          ? data.map((row) => ({
              ...row,
              allocation_id: row.allocation_id === undefined || row.allocation_id === null ? "" : String(row.allocation_id),
            }))
          : [];
        this.allocationsLastUpdatedUtc = this.utcNowString();
        this.applyAllocationsFilterSort();
      } catch (error) {
        this.showNotice(this.errorMessage(error, "Failed to load allocations."));
      } finally {
        this.allocationsLoading.list = false;
      }
    },

    async refreshIpPool() {
      this.ipPoolLoading.list = true;
      try {
        const data = await this.apiFetch("/admin/ip_pool/", { method: "GET" });
        this.ipPool = Array.isArray(data)
          ? data.map((row) => ({
              ...row,
              ip_address: row.ip_address === undefined || row.ip_address === null ? "" : String(row.ip_address),
            }))
          : [];
        this.ipPoolLastUpdatedUtc = this.utcNowString();
        this.applyIpPoolFilterSort();
      } catch (error) {
        this.showNotice(this.errorMessage(error, "Failed to load IP pool."));
      } finally {
        this.ipPoolLoading.list = false;
      }
    },

    async ensureKloigosServersView() {
      if (!this.canViewKloigosAdmin()) {
        this.showNotice("Servers requires CP_ADMIN.");
        return;
      }
      if (!this.serversLoading.list) {
        await this.refreshServers();
      } else {
        this.applyServersFilterSort();
      }
    },

    async ensureKloigosDashboard({ onlyIfEmpty = false } = {}) {
      if (!this.canViewKloigosAdmin()) return;
      if (!onlyIfEmpty || this.servers.length === 0) {
        await this.refreshServers();
      }
    },

    async refreshComputeUnits() {
      this.computeLoading.list = true;
      try {
        const data = await this.apiFetch("/compute_units/", { method: "GET" });
        this.computeUnits = Array.isArray(data)
          ? data.map((row) => ({
              ...row,
              compute_id: row.compute_id === undefined || row.compute_id === null ? "" : String(row.compute_id),
            }))
          : [];
        this.computeLastUpdatedUtc = this.utcNowString();
        this.applyComputeFilterSort();
      } catch (error) {
        this.showNotice(this.errorMessage(error, "Failed to load compute units."));
      } finally {
        this.computeLoading.list = false;
      }
    },

    canManageAllocations() {
      return this.authIsUnauthenticatedMode() || this.hasRole("CP_USER") || this.hasRole("CP_ADMIN");
    },

    canViewKloigosAdmin() {
      return this.authIsUnauthenticatedMode() || this.hasRole("CP_ADMIN");
    },

    allocationCpuCountOptions() {
      const counts = new Set();
      for (const row of this.computeUnits || []) {
        const status = String(row.status || "").toLowerCase();
        if (status !== "free") continue;
        const count = Number(row.cpu_count);
        if (Number.isFinite(count) && count > 0) counts.add(count);
      }
      return Array.from(counts).sort((left, right) => left - right);
    },

    allocationLocationOptions() {
      const options = new Map();
      for (const server of this.servers || []) {
        const status = String(server.status || "").toLowerCase();
        const health = String(server.health_status || "unknown").toLowerCase();
        const region = String(server.region || "").trim();
        const zone = String(server.zone || "").trim();
        if (status !== "ready" || health !== "healthy" || !region || !zone) continue;
        const value = `${region}|${zone}`;
        if (!options.has(value)) options.set(value, { value, label: `${region}-${zone}` });
      }
      return Array.from(options.values()).sort((left, right) => left.label.localeCompare(right.label));
    },

    parseAllocationLocation(value) {
      const [region = "", zone = ""] = String(value || "").split("|", 2);
      return {
        region: region.trim() || null,
        zone: zone.trim() || null,
      };
    },

    persistServersFilter() {
      localStorage.setItem("kloigos_servers_filter", this.serversFilterQuery || "");
    },

    persistAllocationsFilter() {
      localStorage.setItem("kloigos_allocations_filter", this.allocationsFilterQuery || "");
    },

    allocationsRowText(row) {
      const tags = row.tags && typeof row.tags === "object"
        ? Object.entries(row.tags).map(([key, value]) => `${key}:${Array.isArray(value) ? value.join(",") : value}`)
        : [];
      return [
        row.allocation_id,
        row.ip_address,
        row.login_user,
        row.compute_id,
        row.current_host,
        row.status,
        ...tags,
      ].filter(Boolean).join(" ").toLowerCase();
    },

    allocationsCellText(row, colIndex) {
      switch (colIndex) {
        case 0:
          return row.allocation_id || "";
        case 1:
          return row.ip_address || "";
        case 2:
          return row.login_user || "";
        case 3:
          return row.compute_id || "";
        case 4:
          return row.current_host || "";
        case 5:
          return this.serversTagsCompact(row.tags);
        case 6:
          return row.status || "";
        case 7:
          return row.updated_at || "";
        default:
          return "";
      }
    },

    allocationsStatusClass(status) {
      const normalized = String(status || "").toLowerCase();
      if (normalized === "allocated") return "success";
      if (normalized.includes("ing") || normalized === "requested") return "pending";
      if (normalized.includes("deallocated")) return "neutral";
      if (!normalized || normalized === "unknown") return "neutral";
      return "danger";
    },

    allocationCanDeallocate(row) {
      return ["allocated", "allocation_fail", "deallocation_fail"].includes(String(row?.status || "").toLowerCase());
    },

    allocationCanScale(row) {
      return String(row?.status || "").toLowerCase() === "allocated";
    },

    allocationSortClass(index) {
      if (this.allocationsSortIndex !== index) return "";
      return this.allocationsSortDir === "asc" ? "sort-asc" : "sort-desc";
    },

    toggleAllocationsSort(index) {
      if (this.allocationsSortIndex === index) {
        this.allocationsSortDir = this.allocationsSortDir === "asc" ? "desc" : "asc";
      } else {
        this.allocationsSortIndex = index;
        this.allocationsSortDir = "asc";
      }
      localStorage.setItem("kloigos_allocations_sort_index", String(this.allocationsSortIndex));
      localStorage.setItem("kloigos_allocations_sort_dir", this.allocationsSortDir);
      this.applyAllocationsFilterSort();
    },

    applyAllocationsFilterSort() {
      const query = (this.allocationsFilterQuery || "").toLowerCase().trim();
      let rows = this.allocations.slice();
      if (query) rows = rows.filter((row) => this.allocationsRowText(row).includes(query));

      if (this.allocationsSortIndex !== null) {
        const index = this.allocationsSortIndex;
        const dir = this.allocationsSortDir;
        const type = this.allocationsSortTypeByIndex[index] || "string";
        rows.sort((left, right) => {
          const leftValue = this.parseComputeSortValue(type, this.allocationsCellText(left, index));
          const rightValue = this.parseComputeSortValue(type, this.allocationsCellText(right, index));
          if (leftValue < rightValue) return dir === "asc" ? -1 : 1;
          if (leftValue > rightValue) return dir === "asc" ? 1 : -1;
          return 0;
        });
      }

      this.allocationsVisibleRows = rows.filter((row) => String(row?.status || "").toLowerCase() !== "deallocated");
      this.allocationsDeallocatedVisibleRows = rows.filter((row) => String(row?.status || "").toLowerCase() === "deallocated");
    },

    serversRowText(server) {
      const tags = server.tags && typeof server.tags === "object"
        ? Object.entries(server.tags).map(([key, value]) => `${key}:${Array.isArray(value) ? value.join(",") : value}`)
        : [];
      return [
        server.hostname,
        server.private_ip,
        server.public_ip,
        server.server_admin_user,
        server.region,
        server.zone,
        server.runtime_profile,
        server.status,
        server.health_status,
        server.last_health_error,
        ...tags,
      ].filter(Boolean).join(" ").toLowerCase();
    },

    serversCellText(server, colIndex) {
      switch (colIndex) {
        case 0:
          return server.hostname || "";
        case 1:
          return server.private_ip || "";
        case 2:
          return server.server_admin_user || "";
        case 3:
          return server.region || "";
        case 4:
          return server.zone || "";
        case 5:
          return server.runtime_profile || "";
        case 6:
          return server.cpu_count ?? "";
        case 7:
          return server.mem_gb ?? "";
        case 8:
          return server.disk_count ?? "";
        case 9:
          return server.disk_size_gb ?? "";
        case 10:
          return this.serversTagsCompact(server.tags);
        case 11:
          return server.status || "";
        case 12:
          return server.health_status || "";
        default:
          return "";
      }
    },

    serversTagsCompact(tags) {
      if (!tags || typeof tags !== "object") return "";
      const text = Object.entries(tags)
        .filter(([key]) => !String(key).startsWith("_kloigos_"))
        .map(([key, value]) => `${key}=${Array.isArray(value) ? value.join(",") : value}`)
        .join(" ");
      return text.length > 60 ? `${text.slice(0, 60)}...` : text;
    },

    serversStatusClass(status) {
      const normalized = String(status || "").toLowerCase();
      if (normalized === "ready") return "success";
      if (normalized === "decommissioned") return "neutral";
      if (normalized.includes("ing")) return "pending";
      if (!normalized || normalized === "unknown") return "neutral";
      return "danger";
    },

    serverHealthAlerts() {
      return (this.servers || []).filter((server) => {
        const lifecycle = String(server?.status || "").toLowerCase();
        const health = String(server?.health_status || "unknown").toLowerCase();
        return lifecycle === "ready" && health !== "healthy";
      });
    },

    healthyServerCount() {
      return (this.servers || []).filter((server) => (
        String(server?.status || "").toLowerCase() === "ready"
        && String(server?.health_status || "").toLowerCase() === "healthy"
      )).length;
    },

    unknownHealthServerCount() {
      return (this.servers || []).filter((server) => (
        String(server?.status || "").toLowerCase() === "ready"
        && ["", "unknown"].includes(String(server?.health_status || "").toLowerCase())
      )).length;
    },

    serverHealthLabel(status) {
      const normalized = String(status || "unknown").toLowerCase();
      if (normalized === "healthy") return "Healthy";
      if (normalized === "degraded") return "Degraded";
      if (normalized === "unreachable") return "Unreachable";
      return "Unknown";
    },

    serverHealthClass(status) {
      const normalized = String(status || "unknown").toLowerCase();
      if (normalized === "healthy") return "healthy";
      if (normalized === "degraded") return "degraded";
      if (normalized === "unreachable") return "unreachable";
      return "unknown";
    },

    serverHealthIcon(status) {
      const normalized = String(status || "unknown").toLowerCase();
      const iconAttrs = "viewBox=\"0 0 24 24\" aria-hidden=\"true\"";
      if (normalized === "healthy") {
        return `<svg ${iconAttrs}><path d="M20 6 9 17l-5-5" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"></path></svg>`;
      }
      if (normalized === "degraded") {
        return `<svg ${iconAttrs}><path d="M12 3 2.6 20h18.8L12 3Z" fill="none" stroke="currentColor" stroke-width="2" stroke-linejoin="round"></path><path d="M12 9v5" fill="none" stroke="currentColor" stroke-width="2.3" stroke-linecap="round"></path><path d="M12 17.5h.01" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round"></path></svg>`;
      }
      if (normalized === "unreachable") {
        return `<svg ${iconAttrs}><circle cx="12" cy="12" r="9" fill="none" stroke="currentColor" stroke-width="2"></circle><path d="m15 9-6 6" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round"></path><path d="m9 9 6 6" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round"></path></svg>`;
      }
      return `<svg ${iconAttrs}><circle cx="12" cy="12" r="9" fill="none" stroke="currentColor" stroke-width="2"></circle><path d="M9.2 9a3 3 0 1 1 4.9 2.3c-1.1.8-1.7 1.4-1.7 2.7" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"></path><path d="M12 17.5h.01" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round"></path></svg>`;
    },

    serverHealthTitle(server) {
      const label = this.serverHealthLabel(server?.health_status);
      const checked = this.formatDateTime(server?.last_health_check_at);
      const error = server?.last_health_error ? `: ${server.last_health_error}` : "";
      return `${label} - checked ${checked}${error}`;
    },

    runtimeProfileClass(profile) {
      const normalized = String(profile || "standard").toLowerCase();
      return ["minimal", "build"].includes(normalized) ? normalized : "";
    },

    serverCanDelete(server) {
      return ["decommissioned", "init_fail", "decommission_fail"].includes(String(server?.status || "").toLowerCase());
    },

    serverCanDecommission(server) {
      const status = String(server?.status || "").toLowerCase();
      return !["decommissioning", "decommissioned"].includes(status);
    },

    serverCanRecommission(server) {
      return String(server?.status || "").toLowerCase() === "decommissioned";
    },

    serversSortClass(index) {
      if (this.serversSortIndex !== index) return "";
      return this.serversSortDir === "asc" ? "sort-asc" : "sort-desc";
    },

    toggleServersSort(index) {
      if (this.serversSortIndex === index) {
        this.serversSortDir = this.serversSortDir === "asc" ? "desc" : "asc";
      } else {
        this.serversSortIndex = index;
        this.serversSortDir = "asc";
      }
      localStorage.setItem("kloigos_servers_sort_index", String(this.serversSortIndex));
      localStorage.setItem("kloigos_servers_sort_dir", this.serversSortDir);
      this.applyServersFilterSort();
    },

    applyServersFilterSort() {
      const query = (this.serversFilterQuery || "").toLowerCase().trim();
      let rows = this.servers.slice();
      if (query) rows = rows.filter((server) => this.serversRowText(server).includes(query));

      if (this.serversSortIndex !== null) {
        const index = this.serversSortIndex;
        const dir = this.serversSortDir;
        const type = this.serversSortTypeByIndex[index] || "string";
        rows.sort((left, right) => {
          const leftValue = this.parseComputeSortValue(type, this.serversCellText(left, index));
          const rightValue = this.parseComputeSortValue(type, this.serversCellText(right, index));
          if (leftValue < rightValue) return dir === "asc" ? -1 : 1;
          if (leftValue > rightValue) return dir === "asc" ? 1 : -1;
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
      } catch (error) {
        this.showNotice(this.errorMessage(error, "Failed to load servers."));
      } finally {
        this.serversLoading.list = false;
      }
    },

    persistComputeFilter() {
      localStorage.setItem("kloigos_compute_filter", this.computeFilterQuery || "");
    },

    persistIpPoolFilter() {
      localStorage.setItem("kloigos_ip_pool_filter", this.ipPoolFilterQuery || "");
    },

    ipPoolRowText(row) {
      return [
        row.ip_address,
        row.status,
        row.allocation_id,
        row.current_host,
        row.created_at,
        row.updated_at,
      ].filter(Boolean).join(" ").toLowerCase();
    },

    ipPoolCellText(row, colIndex) {
      switch (colIndex) {
        case 0:
          return row.ip_address || "";
        case 1:
          return row.status || "";
        case 2:
          return row.allocation_id || "";
        case 3:
          return row.current_host || "";
        case 4:
          return row.created_at || "";
        case 5:
          return row.updated_at || "";
        default:
          return "";
      }
    },

    ipPoolSortClass(index) {
      if (this.ipPoolSortIndex !== index) return "";
      return this.ipPoolSortDir === "asc" ? "sort-asc" : "sort-desc";
    },

    toggleIpPoolSort(index) {
      if (this.ipPoolSortIndex === index) {
        this.ipPoolSortDir = this.ipPoolSortDir === "asc" ? "desc" : "asc";
      } else {
        this.ipPoolSortIndex = index;
        this.ipPoolSortDir = "asc";
      }
      localStorage.setItem("kloigos_ip_pool_sort_index", String(this.ipPoolSortIndex));
      localStorage.setItem("kloigos_ip_pool_sort_dir", this.ipPoolSortDir);
      this.applyIpPoolFilterSort();
    },

    applyIpPoolFilterSort() {
      const query = (this.ipPoolFilterQuery || "").toLowerCase().trim();
      let rows = this.ipPool.slice();
      if (query) rows = rows.filter((row) => this.ipPoolRowText(row).includes(query));

      if (this.ipPoolSortIndex !== null) {
        const index = this.ipPoolSortIndex;
        const dir = this.ipPoolSortDir;
        const type = this.ipPoolSortTypeByIndex[index] || "string";
        rows.sort((left, right) => {
          const leftValue = this.parseComputeSortValue(type, this.ipPoolCellText(left, index));
          const rightValue = this.parseComputeSortValue(type, this.ipPoolCellText(right, index));
          if (leftValue < rightValue) return dir === "asc" ? -1 : 1;
          if (leftValue > rightValue) return dir === "asc" ? 1 : -1;
          return 0;
        });
      }

      this.ipPoolVisibleRows = rows;
    },

    ipPoolStatusClass(status) {
      const normalized = String(status || "").toLowerCase();
      if (normalized === "free") return "success";
      if (normalized === "reserved" || normalized === "allocated") return "pending";
      if (normalized === "unavailable") return "neutral";
      if (!normalized || normalized === "unknown") return "neutral";
      return "danger";
    },

    ipPoolCanDelete(row) {
      return String(row?.status || "").toLowerCase() === "free";
    },

    openIpPoolAddModal() {
      this.modal.ipPoolAdd.ipAddresses = [{ value: "" }];
      this.modalError.ipPoolAdd = "";
      this.modal.ipPoolAdd.open = true;
    },

    closeIpPoolAddModal() {
      this.modal.ipPoolAdd.open = false;
      this.modalError.ipPoolAdd = "";
    },

    addIpPoolAddressRow() {
      this.modal.ipPoolAdd.ipAddresses.push({ value: "" });
    },

    removeIpPoolAddressRow(index) {
      this.modal.ipPoolAdd.ipAddresses.splice(index, 1);
      if (this.modal.ipPoolAdd.ipAddresses.length === 0) {
        this.addIpPoolAddressRow();
      }
    },

    buildIpPoolAddressList() {
      const addresses = [];
      const seen = new Set();
      for (const [index, row] of this.modal.ipPoolAdd.ipAddresses.entries()) {
        const value = String(row?.value || "").trim();
        if (!value) continue;
        if (seen.has(value)) throw new Error(`Duplicate IP address in row ${index + 1}: ${value}`);
        seen.add(value);
        addresses.push(value);
      }
      return addresses;
    },

    async insertIpPoolAddresses() {
      this.ipPoolLoading.insert = true;
      this.modalError.ipPoolAdd = "";
      try {
        const ipAddresses = this.buildIpPoolAddressList();
        if (ipAddresses.length === 0) throw new Error("Enter at least one IP address.");
        await this.apiFetch("/admin/ip_pool/", {
          method: "POST",
          body: { ip_addresses: ipAddresses },
        });
        this.closeIpPoolAddModal();
        await this.refreshIpPool();
      } catch (error) {
        this.modalError.ipPoolAdd = this.errorMessage(error, "Failed to add IP addresses.");
      } finally {
        this.ipPoolLoading.insert = false;
      }
    },

    openIpPoolDeleteConfirm(row) {
      this.modal.ipPoolDeleteConfirm.ip_address = String(row?.ip_address || "");
      this.modalError.ipPoolDeleteConfirm = "";
      this.modal.ipPoolDeleteConfirm.open = true;
    },

    closeIpPoolDeleteConfirm() {
      this.modal.ipPoolDeleteConfirm.open = false;
      this.modalError.ipPoolDeleteConfirm = "";
    },

    async deleteIpPoolAddress() {
      const ipAddress = String(this.modal.ipPoolDeleteConfirm.ip_address || "").trim();
      this.ipPoolLoading.delete = true;
      this.ipPoolBusyKey = ipAddress;
      this.modalError.ipPoolDeleteConfirm = "";
      try {
        if (!ipAddress) throw new Error("IP address is required.");
        await this.apiFetch(`/admin/ip_pool/${encodeURIComponent(ipAddress)}`, { method: "DELETE" });
        this.closeIpPoolDeleteConfirm();
        await this.refreshIpPool();
      } catch (error) {
        this.modalError.ipPoolDeleteConfirm = this.errorMessage(error, "Failed to delete IP address.");
      } finally {
        this.ipPoolLoading.delete = false;
        this.ipPoolBusyKey = null;
      }
    },

    computeRowText(row) {
      const tags = row.tags && typeof row.tags === "object"
        ? Object.entries(row.tags).map(([key, value]) => `${key}:${Array.isArray(value) ? value.join(",") : value}`)
        : [];
      return [
        row.compute_id,
        row.hostname,
        row.server_private_ip,
        row.server_public_ip,
        row.region,
        row.zone,
        row.status,
        this.allocationTagValue(row),
        ...tags,
      ].filter(Boolean).join(" ").toLowerCase();
    },

    computeCellText(row, colIndex) {
      switch (colIndex) {
        case 0:
          return this.allocationTagValue(row) || "";
        case 1:
          return row.compute_id || "";
        case 2:
          return `${row.region || "-"}-${row.zone || "-"}`;
        case 3:
          return row.hostname || "";
        case 4:
          return row.cpu_count ?? "";
        case 5:
          return row.started_at || "";
        case 6:
          return row.status || "";
        default:
          return "";
      }
    },

    parseComputeSortValue(type, value) {
      const raw = (value ?? "").toString().trim();
      if (type === "number") {
        const parsed = Number(raw);
        return Number.isFinite(parsed) ? parsed : Number.NEGATIVE_INFINITY;
      }
      if (type === "date") {
        const parsed = Date.parse(raw);
        return Number.isNaN(parsed) ? 0 : parsed;
      }
      if (type === "ip") {
        return raw.split(".").map((part) => part.padStart(3, "0")).join(".");
      }
      return raw.toLowerCase();
    },

    applyComputeFilterSort() {
      const query = (this.computeFilterQuery || "").toLowerCase().trim();
      let rows = this.computeUnits.slice();
      if (query) rows = rows.filter((row) => this.computeRowText(row).includes(query));

      if (this.computeSortIndex !== null) {
        const index = this.computeSortIndex;
        const dir = this.computeSortDir;
        const type = this.computeSortTypeByIndex[index] || "string";
        rows.sort((left, right) => {
          const leftValue = this.parseComputeSortValue(type, this.computeCellText(left, index));
          const rightValue = this.parseComputeSortValue(type, this.computeCellText(right, index));
          if (leftValue < rightValue) return dir === "asc" ? -1 : 1;
          if (leftValue > rightValue) return dir === "asc" ? 1 : -1;
          return 0;
        });
      }

      this.computeVisibleRows = rows;
    },

    toggleComputeSort(index) {
      if (this.computeSortIndex === index) {
        this.computeSortDir = this.computeSortDir === "asc" ? "desc" : "asc";
      } else {
        this.computeSortIndex = index;
        this.computeSortDir = "asc";
      }
      localStorage.setItem("kloigos_compute_sort_index", String(this.computeSortIndex));
      localStorage.setItem("kloigos_compute_sort_dir", this.computeSortDir);
      this.applyComputeFilterSort();
    },

    computeSortClass(index) {
      if (this.computeSortIndex !== index) return "";
      return this.computeSortDir === "asc" ? "sort-asc" : "sort-desc";
    },

    tagValue(row, key) {
      const tags = row.tags;
      if (!tags || typeof tags !== "object") return null;
      const value = tags[key];
      if (value === undefined || value === null) return null;
      return Array.isArray(value) ? value.join(",") : String(value);
    },

    allocationTagValue(row) {
      return this.tagValue(row, "allocation_id") || this.tagValue(row, "deployment_id");
    },

    computeStatusClass(status) {
      const normalized = String(status || "").toLowerCase();
      if (normalized.includes("free")) return "success";
      if (normalized.includes("allocated") || normalized.includes("ing")) return "pending";
      if (normalized.includes("decommissioned")) return "neutral";
      if (!normalized || normalized === "unknown") return "neutral";
      return "danger";
    },

    openAllocationCreateModal() {
      this.modal.allocate.allocation_id = "";
      this.modal.allocate.login_user = "";
      this.modal.allocate.cpu_count = "";
      this.modal.allocate.location = "";
      this.modal.allocate.tagPairs = [{ key: "", value: "" }];
      this.modal.allocate.ssh_public_key = "";
      this.modalError.allocate = "";
      this.modal.allocate.open = true;
    },

    closeAllocateModal() {
      this.modal.allocate.open = false;
      this.modalError.allocate = "";
    },

    addAllocationTagPair() {
      this.modal.allocate.tagPairs.push({ key: "", value: "" });
    },

    removeAllocationTagPair(index) {
      this.modal.allocate.tagPairs.splice(index, 1);
      if (this.modal.allocate.tagPairs.length === 0) {
        this.addAllocationTagPair();
      }
    },

    buildAllocationTags() {
      const tags = {};
      for (const [index, pair] of this.modal.allocate.tagPairs.entries()) {
        const key = String(pair?.key || "").trim();
        const value = String(pair?.value || "").trim();
        if (!key && !value) continue;
        if (!key) throw new Error(`Tag row ${index + 1} is missing a key.`);
        if (Object.prototype.hasOwnProperty.call(tags, key)) {
          throw new Error(`Duplicate tag key: ${key}`);
        }
        tags[key] = value;
      }
      return tags;
    },

    async createAllocation() {
      this.allocationsLoading.allocate = true;
      this.modalError.allocate = "";
      try {
        const tags = this.buildAllocationTags();
        const allocationId = (this.modal.allocate.allocation_id || "").trim();
        const location = this.parseAllocationLocation(this.modal.allocate.location);
        const rawCpuCount = this.modal.allocate.cpu_count;
        const cpuCount = rawCpuCount === "" || rawCpuCount === null
          ? null
          : Number(rawCpuCount);
        const sshPublicKey = (this.modal.allocate.ssh_public_key || "").trim();
        if (!sshPublicKey) {
          throw new Error("SSH Public Key is required.");
        }
        const payload = {
          allocation_id: allocationId || null,
          login_user: (this.modal.allocate.login_user || "").trim() || null,
          cpu_count: Number.isFinite(cpuCount) ? cpuCount : null,
          region: location.region,
          zone: location.zone,
          tags,
          ssh_public_key: sshPublicKey,
        };
        const result = await this.apiFetch("/allocations/", { method: "POST", body: payload });
        this.closeAllocateModal();
        this.showNotice("Allocation queued.", { jobId: result?.job_id });
        await this.refreshAllocations();
        await this.refreshComputeUnits();
      } catch (error) {
        this.modalError.allocate = this.errorMessage(error, "Allocation failed.");
      } finally {
        this.allocationsLoading.allocate = false;
      }
    },

    openAllocationDeallocateConfirm(row) {
      this.modal.deallocateConfirm.allocation_id = String(row.allocation_id || "");
      this.modal.deallocateConfirm.compute_id = row.compute_id || "";
      this.modalError.deallocateConfirm = "";
      this.modal.deallocateConfirm.open = true;
    },

    closeDeallocateConfirm() {
      this.modal.deallocateConfirm.open = false;
      this.modalError.deallocateConfirm = "";
    },

    async confirmDeallocateAllocation() {
      const allocationId = String(this.modal.deallocateConfirm.allocation_id || "");
      this.allocationsLoading.deallocateConfirm = true;
      this.allocationsBusyKey = allocationId;
      this.modalError.deallocateConfirm = "";
      try {
        const result = await this.apiFetch(`/allocations/${encodeURIComponent(allocationId)}`, { method: "DELETE" });
        this.closeDeallocateConfirm();
        this.showNotice("Deallocation queued.", { jobId: result?.job_id });
        await this.refreshAllocations();
        await this.refreshComputeUnits();
      } catch (error) {
        this.modalError.deallocateConfirm = this.errorMessage(error, "Deallocate failed.");
      } finally {
        this.allocationsLoading.deallocateConfirm = false;
        this.allocationsBusyKey = null;
      }
    },

    openAllocationScaleModal(row) {
      this.modal.allocationScale.allocation_id = String(row?.allocation_id || "");
      this.modal.allocationScale.compute_id = "";
      this.modal.allocationScale.cpu_count = null;
      this.modal.allocationScale.region = "";
      this.modal.allocationScale.zone = "";
      this.modalError.allocationScale = "";
      this.modal.allocationScale.open = true;
    },

    closeAllocationScaleModal() {
      this.modal.allocationScale.open = false;
      this.modalError.allocationScale = "";
    },

    async scaleAllocation() {
      const allocationId = String(this.modal.allocationScale.allocation_id || "").trim();
      this.allocationsLoading.scale = true;
      this.allocationsBusyKey = allocationId;
      this.modalError.allocationScale = "";
      try {
        const payload = {
          compute_id: (this.modal.allocationScale.compute_id || "").trim() || null,
          cpu_count: this.modal.allocationScale.cpu_count ?? null,
          region: (this.modal.allocationScale.region || "").trim() || null,
          zone: (this.modal.allocationScale.zone || "").trim() || null,
        };
        if (!payload.compute_id && !payload.cpu_count && !payload.region && !payload.zone) {
          throw new Error("Provide at least one target constraint.");
        }
        const result = await this.apiFetch(`/allocations/${encodeURIComponent(allocationId)}/scale`, {
          method: "POST",
          body: payload,
        });
        this.closeAllocationScaleModal();
        this.showNotice("Scale queued.", { jobId: result?.job_id });
        await this.refreshAllocations();
        await this.refreshComputeUnits();
      } catch (error) {
        this.modalError.allocationScale = this.errorMessage(error, "Scale failed.");
      } finally {
        this.allocationsLoading.scale = false;
        this.allocationsBusyKey = null;
      }
    },

    openAllocationDetails(row) {
      this.modal.allocationDetails.row = row || null;
      this.modal.allocationDetails.open = true;
      this.renderAllocationDetailsYaml();
    },

    closeAllocationDetails() {
      this.modal.allocationDetails.open = false;
      this.modal.allocationDetails.row = null;
      this.destroyDetailsYamlEditor("_allocationDetailsAce");
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
      this.renderServerDetailsYaml();
    },

    closeServerDetails() {
      this.modal.serverDetails.open = false;
      this.modal.serverDetails.row = null;
      this.destroyDetailsYamlEditor("_serverDetailsAce");
    },

    renderAllocationDetailsYaml() {
      this.renderDetailsYamlEditor(
        "allocationDetailsYamlEditor",
        "_allocationDetailsAce",
        this.formatYaml(this.modal.allocationDetails.row || {}),
      );
    },

    renderServerDetailsYaml() {
      this.renderDetailsYamlEditor(
        "serverDetailsYamlEditor",
        "_serverDetailsAce",
        this.formatYaml(this.modal.serverDetails.row || {}),
      );
    },

    renderDetailsYamlEditor(refName, editorKey, yaml) {
      if (!this.isAceAvailable()) return;
      setTimeout(() => {
        const element = this.$refs?.[refName];
        if (!element) return;
        if (!this[editorKey]) {
          this[editorKey] = this.createAceEditor(element, {
            mode: "yaml",
            theme: "cobalt",
            readOnly: true,
            wrap: true,
            value: yaml,
            minLines: 18,
            maxLines: 34,
          });
        } else {
          this.setAceValue(this[editorKey], yaml);
        }
        if (this[editorKey] && typeof this[editorKey].resize === "function") {
          this[editorKey].resize();
        }
      }, 0);
    },

    destroyDetailsYamlEditor(editorKey) {
      if (!this[editorKey]) return;
      this.destroyAceEditor(this[editorKey]);
      this[editorKey] = null;
    },

    formatYaml(value, indent = 0) {
      const pad = " ".repeat(indent);
      if (Array.isArray(value)) {
        if (value.length === 0) return `${pad}[]`;
        return value.map((item) => {
          if (item && typeof item === "object") {
            return `${pad}-\n${this.formatYaml(item, indent + 2)}`;
          }
          return `${pad}- ${this.formatYamlScalar(item)}`;
        }).join("\n");
      }
      if (value && typeof value === "object") {
        const entries = Object.entries(value);
        if (entries.length === 0) return `${pad}{}`;
        return entries.map(([key, item]) => {
          if (item && typeof item === "object") {
            return `${pad}${key}:\n${this.formatYaml(item, indent + 2)}`;
          }
          return `${pad}${key}: ${this.formatYamlScalar(item)}`;
        }).join("\n");
      }
      return `${pad}${this.formatYamlScalar(value)}`;
    },

    formatYamlScalar(value) {
      if (value === null || value === undefined) return "null";
      if (value instanceof Date) return JSON.stringify(this.formatDateTime(value));
      if (typeof value === "boolean" || typeof value === "number") return String(value);
      const text = this.formatYamlDateTimeScalar(String(value));
      if (text === "") return "\"\"";
      if (/^\s|\s$|[:#\n]|^(true|false|null|yes|no|on|off)$/i.test(text) || /^[-+]?\d/.test(text)) {
        return JSON.stringify(text);
      }
      return text;
    },

    formatYamlDateTimeScalar(value) {
      const text = String(value || "");
      if (!/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}/.test(text)) return text;
      const date = new Date(text);
      if (Number.isNaN(date.getTime())) return text;
      return this.formatDateTime(date);
    },

    openServerActionConfirm(server, action) {
      this.modal.serverActionConfirm.hostname = server?.hostname || "";
      this.modal.serverActionConfirm.action = action || "decommission";
      this.modalError.serverActionConfirm = "";
      this.modal.serverActionConfirm.open = true;
    },

    closeServerActionConfirm() {
      this.modal.serverActionConfirm.open = false;
      this.modalError.serverActionConfirm = "";
    },

    async confirmServerAction() {
      const hostname = String(this.modal.serverActionConfirm.hostname || "").trim();
      const action = this.modal.serverActionConfirm.action;
      if (!hostname) return;

      this.serversLoading.action = true;
      this.modalError.serverActionConfirm = "";
      try {
        if (action === "delete") {
          await this.apiFetch(`/admin/servers/${encodeURIComponent(hostname)}`, { method: "DELETE" });
        } else {
          await this.apiFetch("/admin/servers/", { method: "PUT", body: { hostname } });
        }
        this.closeServerActionConfirm();
        await this.refreshServers();
        await this.refreshAllocations();
        await this.refreshComputeUnits();
      } catch (error) {
        this.modalError.serverActionConfirm = this.errorMessage(error, "Failed to run server action.");
      } finally {
        this.serversLoading.action = false;
      }
    },

    openServerInitModal() {
      this.resetServerInitModal();
      this.modal.serverInit.mode = "init";
      this.modal.serverInit.open = true;
    },

    openServerRecommissionModal(server) {
      this.resetServerInitModal();
      this.modal.serverInit.mode = "recommission";
      this.modal.serverInit.hostname = server?.hostname || "";
      this.modal.serverInit.private_ip = server?.private_ip || "";
      this.modal.serverInit.public_ip = server?.public_ip || "";
      this.modal.serverInit.server_admin_user = server?.server_admin_user || "ubuntu";
      this.modal.serverInit.region = server?.region || "";
      this.modal.serverInit.zone = server?.zone || "";
      this.modal.serverInit.runtime_profile = server?.runtime_profile || "standard";
      this.modal.serverInit.cpu_count = server?.cpu_count ?? null;
      this.modal.serverInit.mem_gb = server?.mem_gb ?? null;
      this.modal.serverInit.disk_count = server?.disk_count ?? null;
      this.modal.serverInit.disk_size_gb = server?.disk_size_gb ?? null;
      this.modal.serverInit.tagPairs = this.serverInitTagPairsFromServer(server);
      this.modal.serverInit.compute_units = this.serverInitComputeUnitsFromServer(server);
      this.modal.serverInit.open = true;
    },

    resetServerInitModal() {
      this.modal.serverInit.step = 1;
      this.modalError.serverInit = "";
      this.modal.serverInit.mode = "init";
      this.modal.serverInit.private_ip = "";
      this.modal.serverInit.public_ip = "";
      this.modal.serverInit.hostname = "";
      this.modal.serverInit.server_admin_user = "ubuntu";
      this.modal.serverInit.region = "";
      this.modal.serverInit.zone = "";
      this.modal.serverInit.runtime_profile = "standard";
      this.modal.serverInit.cpu_count = null;
      this.modal.serverInit.mem_gb = null;
      this.modal.serverInit.disk_count = null;
      this.modal.serverInit.disk_size_gb = null;
      this.modal.serverInit.tagPairs = [{ key: "", value: "" }];
      this.modal.serverInit.compute_units = [{ ordinal: 1, cpu_range: "0-3", cpus: [0, 1, 2, 3] }];
    },

    serverInitTagPairsFromServer(server) {
      const tags = server?.tags && typeof server.tags === "object" ? server.tags : {};
      const pairs = Object.entries(tags)
        .filter(([key]) => !String(key).startsWith("_kloigos_"))
        .map(([key, value]) => ({ key, value: String(value ?? "") }));
      return pairs.length ? pairs : [{ key: "", value: "" }];
    },

    serverInitComputeUnitsFromServer(server) {
      const specs = Array.isArray(server?.tags?._kloigos_compute_units)
        ? server.tags._kloigos_compute_units
        : [];
      const units = specs
        .map((unit, index) => {
          const cpuRange = String(unit?.cpu_range || "").trim();
          return {
            ordinal: Number(unit?.ordinal) || index + 1,
            cpu_range: cpuRange,
            cpus: this.parseServerInitCpuRange(cpuRange),
          };
        })
        .filter((unit) => unit.cpu_range && unit.cpus.length > 0);
      if (units.length > 0) {
        return units.sort((left, right) => left.ordinal - right.ordinal);
      }

      const cpuCount = Number(server?.cpu_count);
      const cpus = Number.isInteger(cpuCount) && cpuCount > 0
        ? Array.from({ length: cpuCount }, (_, index) => index)
        : [0, 1, 2, 3];
      return [{
        ordinal: 1,
        cpu_range: cpus.length === 1 ? String(cpus[0]) : `${cpus[0]}-${cpus[cpus.length - 1]}`,
        cpus,
      }];
    },

    closeServerInitModal() {
      this.modal.serverInit.open = false;
      this.modalError.serverInit = "";
    },

    validateServerInitStep(step) {
      if (step === 1) {
        for (const key of ["hostname", "private_ip", "server_admin_user", "region", "zone"]) {
          if (!String(this.modal.serverInit[key] || "").trim()) {
            throw new Error(`${key} is required.`);
          }
        }
      }
      if (step === 2) {
        const cpuCount = Number(this.modal.serverInit.cpu_count);
        if (!Number.isInteger(cpuCount) || cpuCount <= 0) {
          throw new Error("CPU Count is required.");
        }
      }
      if (step === 3) {
        if (this.serverInitCpuOptions().length === 0) {
          throw new Error("CPU Count is required before selecting Compute Unit CPUs.");
        }
        if (this.modal.serverInit.compute_units.length === 0) {
          throw new Error("At least one compute unit is required.");
        }
        for (const [index, unit] of this.modal.serverInit.compute_units.entries()) {
          this.serverInitCpuRange(unit, index);
        }
      }
    },

    nextServerInitStep() {
      try {
        this.validateServerInitStep(this.modal.serverInit.step);
        this.modalError.serverInit = "";
        this.modal.serverInit.step = Math.min(3, this.modal.serverInit.step + 1);
      } catch (error) {
        this.modalError.serverInit = this.errorMessage(error, "Unable to continue.");
      }
    },

    previousServerInitStep() {
      this.modalError.serverInit = "";
      this.modal.serverInit.step = Math.max(1, this.modal.serverInit.step - 1);
    },

    serverInitCpuOptions() {
      const count = Number(this.modal.serverInit.cpu_count);
      if (!Number.isInteger(count) || count <= 0) return [];
      return Array.from({ length: count }, (_, index) => index);
    },

    parseServerInitCpuRange(cpuRange) {
      const text = String(cpuRange || "").trim();
      if (!text) return [];
      const match = text.match(/^(\d+)(?:-(\d+))?$/);
      if (!match) return [];
      const start = Number(match[1]);
      const end = match[2] === undefined ? start : Number(match[2]);
      if (!Number.isInteger(start) || !Number.isInteger(end) || end < start) return [];
      return Array.from({ length: end - start + 1 }, (_, offset) => start + offset);
    },

    serverInitUnitCpus(unit) {
      if (Array.isArray(unit?.cpus)) {
        return unit.cpus.map((cpu) => Number(cpu)).filter((cpu) => Number.isInteger(cpu));
      }
      return this.parseServerInitCpuRange(unit?.cpu_range);
    },

    serverInitUnitHasCpu(unit, cpu) {
      return this.serverInitUnitCpus(unit).includes(cpu);
    },

    serverInitCpuAssignedToOther(unitIndex, cpu) {
      return this.modal.serverInit.compute_units.some((unit, index) => (
        index !== unitIndex && this.serverInitUnitHasCpu(unit, cpu)
      ));
    },

    serverInitCpuButtonClass(unitIndex, unit, cpu) {
      if (this.serverInitUnitHasCpu(unit, cpu)) return "selected";
      if (this.serverInitCpuAssignedToOther(unitIndex, cpu)) return "disabled";
      return "";
    },

    toggleServerInitUnitCpu(unitIndex, cpu) {
      if (this.serverInitCpuAssignedToOther(unitIndex, cpu)) return;
      const unit = this.modal.serverInit.compute_units[unitIndex];
      const cpus = new Set(this.serverInitUnitCpus(unit));
      if (cpus.has(cpu)) cpus.delete(cpu);
      else cpus.add(cpu);
      unit.cpus = Array.from(cpus).sort((left, right) => left - right);
      try {
        unit.cpu_range = unit.cpus.length ? this.serverInitCpuRange(unit, unitIndex) : "";
      } catch {
        unit.cpu_range = unit.cpus.join(",");
      }
    },

    serverInitCpuRange(unit, index) {
      const cpus = this.serverInitUnitCpus(unit).sort((left, right) => left - right);
      if (cpus.length === 0) {
        throw new Error(`Compute unit ${index + 1} needs at least one CPU.`);
      }
      const available = new Set(this.serverInitCpuOptions());
      for (const cpu of cpus) {
        if (available.size > 0 && !available.has(cpu)) {
          throw new Error(`Compute unit ${index + 1} includes CPU ${cpu}, which is outside the server CPU count.`);
        }
      }
      for (let idx = 1; idx < cpus.length; idx += 1) {
        if (cpus[idx] !== cpus[idx - 1] + 1) {
          throw new Error(`Compute unit ${index + 1} CPUs must be contiguous.`);
        }
      }
      const start = cpus[0];
      const end = cpus[cpus.length - 1];
      return start === end ? String(start) : `${start}-${end}`;
    },

    addServerInitTagPair() {
      this.modal.serverInit.tagPairs.push({ key: "", value: "" });
    },

    removeServerInitTagPair(index) {
      this.modal.serverInit.tagPairs.splice(index, 1);
      if (this.modal.serverInit.tagPairs.length === 0) {
        this.addServerInitTagPair();
      }
    },

    buildServerInitTags() {
      const tags = {};
      for (const [index, pair] of this.modal.serverInit.tagPairs.entries()) {
        const key = String(pair?.key || "").trim();
        const value = String(pair?.value || "").trim();
        if (!key && !value) continue;
        if (!key) throw new Error(`Tag row ${index + 1} is missing a key.`);
        if (Object.prototype.hasOwnProperty.call(tags, key)) {
          throw new Error(`Duplicate tag key: ${key}`);
        }
        tags[key] = value;
      }
      return tags;
    },

    addServerInitComputeUnit() {
      const ordinal = this.modal.serverInit.compute_units.length + 1;
      this.modal.serverInit.compute_units.push({
        ordinal,
        cpu_range: "",
        cpus: [],
      });
    },

    removeServerInitComputeUnit(index) {
      if (this.modal.serverInit.compute_units.length <= 1) return;
      this.modal.serverInit.compute_units.splice(index, 1);
      this.modal.serverInit.compute_units.forEach((unit, idx) => {
        unit.ordinal = idx + 1;
      });
    },

    buildServerInitPayload() {
      const tags = this.buildServerInitTags();
      const numberOrNull = (value) => {
        if (value === "" || value === null || value === undefined) return null;
        const parsed = Number(value);
        return Number.isFinite(parsed) ? parsed : null;
      };

      const payload = {
        hostname: String(this.modal.serverInit.hostname || "").trim(),
        private_ip: String(this.modal.serverInit.private_ip || "").trim(),
        public_ip: String(this.modal.serverInit.public_ip || "").trim() || null,
        server_admin_user: String(this.modal.serverInit.server_admin_user || "ubuntu").trim(),
        region: String(this.modal.serverInit.region || "").trim(),
        zone: String(this.modal.serverInit.zone || "").trim(),
        runtime_profile: String(this.modal.serverInit.runtime_profile || "standard").trim(),
        cpu_count: numberOrNull(this.modal.serverInit.cpu_count),
        mem_gb: numberOrNull(this.modal.serverInit.mem_gb),
        disk_count: numberOrNull(this.modal.serverInit.disk_count),
        disk_size_gb: numberOrNull(this.modal.serverInit.disk_size_gb),
        tags,
        compute_units: this.modal.serverInit.compute_units.map((unit, index) => ({
          ordinal: index + 1,
          cpu_range: this.serverInitCpuRange(unit, index),
        })),
      };

      this.validateServerInitStep(1);
      this.validateServerInitStep(2);
      if (payload.compute_units.length === 0) throw new Error("At least one compute unit is required.");
      for (const unit of payload.compute_units) {
        if (!unit.cpu_range) {
          throw new Error("Each compute unit needs a CPU range.");
        }
      }
      return payload;
    },

    async initServer() {
      this.serversLoading.init = true;
      this.modalError.serverInit = "";
      try {
        await this.apiFetch("/admin/servers/", {
          method: "POST",
          body: this.buildServerInitPayload(),
        });
        this.closeServerInitModal();
        await this.refreshServers();
        await this.refreshAllocations();
        await this.refreshComputeUnits();
      } catch (error) {
        this.modalError.serverInit = this.errorMessage(error, "Server init failed.");
      } finally {
        this.serversLoading.init = false;
      }
    },
  },
};
