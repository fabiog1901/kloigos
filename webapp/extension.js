window.cpkitWebappExtension = {
  htmlPath: "/app/extension.html",
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
    {
      view: "license_status",
      label: "View License",
      kicker: "Enterprise",
      description: "Decoded enterprise license status and enabled feature data.",
      icon: "license",
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
    license_status: {
      path: "/admin/license",
      label: "View License",
      subtitle: "Decoded enterprise license status",
      ensure: "ensureLicenseStatusAdminCard",
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
      5: "number",
      6: "number",
      7: "number",
      8: "number",
      9: "string",
      10: "string",
    },
    serversLoading: { list: false, action: false, init: false, license: false },
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
    _kloigosNoticeTimer: null,
    modal: {
      allocate: {
        open: false,
        allocation_id: "",
        login_user: "",
        ip_address: "",
        cpu_count: null,
        region: "",
        zone: "",
        compute_id: "",
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
        private_ip: "",
        public_ip: "",
        hostname: "",
        server_admin_user: "ubuntu",
        region: "",
        zone: "",
        cpu_count: null,
        mem_gb: null,
        disk_count: null,
        disk_size_gb: null,
        tagsText: "{}",
        compute_units: [{ ordinal: 1, cpu_range: "0-3" }],
      },
      licenseStatus: { open: false, yaml: "" },
      ipPoolAdd: { open: false, ipAddressesText: "" },
      ipPoolDeleteConfirm: { open: false, ip_address: "" },
    },
    modalError: {
      allocate: "",
      allocationScale: "",
      deallocateConfirm: "",
      serverActionConfirm: "",
      serverInit: "",
      licenseStatus: "",
      ipPoolAdd: "",
      ipPoolDeleteConfirm: "",
    },
  },
  async init() {
    this.kloigosInstallNoticeHooks();
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
    }, 10000);
    this.setManagedInterval("_computeAutoTimer", () => {
      if (this.computeAutoRefreshEnabled && this.view === "compute_units") {
        this.refreshComputeUnits();
      }
    }, 10000);
    this.setManagedInterval("_serversAutoTimer", () => {
      if (this.serversAutoRefreshEnabled && this.view === "kloigos_servers") {
        this.refreshServers();
      }
    }, 15000);
    this.setManagedInterval("_ipPoolAutoTimer", () => {
      if (this.ipPoolAutoRefreshEnabled && this.view === "ip_pool") {
        this.refreshIpPool();
      }
    }, 5000);
  },
  methods: {
    kloigosInstallNoticeHooks() {
      if (this._kloigosNoticeHooksInstalled) return;

      const originalSetView = this.setView.bind(this);
      this.setView = async (...args) => {
        this.kloigosClearNotice();
        return originalSetView(...args);
      };

      const originalApplyRouteFromHash = this.applyRouteFromHash.bind(this);
      this.applyRouteFromHash = async (...args) => {
        const previousView = this.view;
        const previousJobId = this.selectedJobId;
        const result = await originalApplyRouteFromHash(...args);
        if (this.view !== previousView || this.selectedJobId !== previousJobId) {
          this.kloigosClearNotice();
        }
        return result;
      };

      const originalOpenJob = this.openJob.bind(this);
      this.openJob = (...args) => {
        this.kloigosClearNotice();
        return originalOpenJob(...args);
      };

      this._kloigosNoticeHooksInstalled = true;
    },

    kloigosShowNotice(message, jobId = "") {
      if (this._kloigosNoticeTimer) clearTimeout(this._kloigosNoticeTimer);
      this.viewNotice = message;
      this.viewNoticeJobId = jobId ? String(jobId) : "";
      this._kloigosNoticeTimer = setTimeout(() => {
        this.kloigosClearNotice();
      }, 7000);
    },

    kloigosClearNotice() {
      if (this._kloigosNoticeTimer) clearTimeout(this._kloigosNoticeTimer);
      this._kloigosNoticeTimer = null;
      this.viewNotice = "";
      this.viewNoticeJobId = "";
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
      if (this.allocations.length === 0 && !this.allocationsLoading.list) {
        await this.refreshAllocations();
      } else {
        this.applyAllocationsFilterSort();
      }
    },

    async ensureComputeUnitsView() {
      if (this.computeUnits.length === 0 && !this.computeLoading.list) {
        await this.refreshComputeUnits();
      } else {
        this.applyComputeFilterSort();
      }
    },

    async ensureIpPoolView() {
      if (!this.canViewKloigosAdmin()) {
        this.kloigosShowNotice("IP Pool requires CP_ADMIN.");
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
        this.kloigosShowNotice(this.errorMessage(error, "Failed to load allocations."));
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
        this.kloigosShowNotice(this.errorMessage(error, "Failed to load IP pool."));
      } finally {
        this.ipPoolLoading.list = false;
      }
    },

    async ensureKloigosServersView() {
      if (!this.canViewKloigosAdmin()) {
        this.kloigosShowNotice("Servers requires CP_ADMIN.");
        return;
      }
      if (this.servers.length === 0 && !this.serversLoading.list) {
        await this.refreshServers();
      } else {
        this.applyServersFilterSort();
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
        this.kloigosShowNotice(this.errorMessage(error, "Failed to load compute units."));
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

    async ensureLicenseStatusAdminCard() {
      this.view = "admin";
      window.location.hash = this.routeForView("admin");
      await this.openLicenseStatusModal();
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
        server.status,
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
          return server.cpu_count ?? "";
        case 6:
          return server.mem_gb ?? "";
        case 7:
          return server.disk_count ?? "";
        case 8:
          return server.disk_size_gb ?? "";
        case 9:
          return this.serversTagsCompact(server.tags);
        case 10:
          return server.status || "";
        default:
          return "";
      }
    },

    serversTagsCompact(tags) {
      if (!tags || typeof tags !== "object") return "";
      const text = Object.entries(tags)
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

    serverCanDelete(server) {
      return ["decommissioned", "init_fail", "decommission_fail"].includes(String(server?.status || "").toLowerCase());
    },

    serverCanDecommission(server) {
      return String(server?.status || "").toLowerCase() === "ready";
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
        this.kloigosShowNotice(this.errorMessage(error, "Failed to load servers."));
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
      this.modal.ipPoolAdd.ipAddressesText = "";
      this.modalError.ipPoolAdd = "";
      this.modal.ipPoolAdd.open = true;
    },

    closeIpPoolAddModal() {
      this.modal.ipPoolAdd.open = false;
      this.modalError.ipPoolAdd = "";
    },

    parseIpPoolAddressesInput(text) {
      return String(text || "")
        .split(/[\s,]+/)
        .map((item) => item.trim())
        .filter(Boolean);
    },

    async insertIpPoolAddresses() {
      this.ipPoolLoading.insert = true;
      this.modalError.ipPoolAdd = "";
      try {
        const ipAddresses = this.parseIpPoolAddressesInput(this.modal.ipPoolAdd.ipAddressesText);
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

    openAllocationCreateModal(computeId = "") {
      this.modal.allocate.allocation_id = "";
      this.modal.allocate.login_user = "";
      this.modal.allocate.ip_address = "";
      this.modal.allocate.cpu_count = null;
      this.modal.allocate.region = "";
      this.modal.allocate.zone = "";
      this.modal.allocate.compute_id = computeId ? String(computeId) : "";
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
        const payload = {
          allocation_id: allocationId || null,
          login_user: (this.modal.allocate.login_user || "").trim() || null,
          ip_address: (this.modal.allocate.ip_address || "").trim() || null,
          cpu_count: this.modal.allocate.cpu_count ?? null,
          region: (this.modal.allocate.region || "").trim() || null,
          zone: (this.modal.allocate.zone || "").trim() || null,
          compute_id: (this.modal.allocate.compute_id || "").trim() || null,
          tags,
          ssh_public_key: (this.modal.allocate.ssh_public_key || "").trim(),
        };

        if (!payload.ssh_public_key) throw new Error("SSH public key is required.");

        const result = await this.apiFetch("/allocations/", { method: "POST", body: payload });
        this.closeAllocateModal();
        this.kloigosShowNotice("Allocation queued.", result?.job_id);
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
        this.kloigosShowNotice("Deallocation queued.", result?.job_id);
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
        this.kloigosShowNotice("Scale queued.", result?.job_id);
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
    },

    closeAllocationDetails() {
      this.modal.allocationDetails.open = false;
      this.modal.allocationDetails.row = null;
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

    async openLicenseStatusModal() {
      this.modal.licenseStatus.yaml = "";
      this.modalError.licenseStatus = "";
      this.modal.licenseStatus.open = true;
      this.serversLoading.license = true;
      try {
        const data = await this.apiFetch("/license/status", { method: "GET" });
        this.modal.licenseStatus.yaml = this.formatYaml(data || {});
      } catch (error) {
        this.modalError.licenseStatus = this.errorMessage(error, "Failed to load license status.");
      } finally {
        this.serversLoading.license = false;
      }
    },

    closeLicenseStatusModal() {
      this.modal.licenseStatus.open = false;
      this.modalError.licenseStatus = "";
      this.modal.licenseStatus.yaml = "";
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
      if (typeof value === "boolean" || typeof value === "number") return String(value);
      const text = String(value);
      if (text === "") return "\"\"";
      if (/^\s|\s$|[:#\n]|^(true|false|null|yes|no|on|off)$/i.test(text) || /^[-+]?\d/.test(text)) {
        return JSON.stringify(text);
      }
      return text;
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
      this.modalError.serverInit = "";
      this.modal.serverInit.open = true;
    },

    closeServerInitModal() {
      this.modal.serverInit.open = false;
      this.modalError.serverInit = "";
    },

    addServerInitComputeUnit() {
      const ordinal = this.modal.serverInit.compute_units.length + 1;
      const start = (ordinal - 1) * 4;
      this.modal.serverInit.compute_units.push({
        ordinal,
        cpu_range: `${start}-${start + 3}`,
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
      const tags = JSON.parse((this.modal.serverInit.tagsText || "{}").trim() || "{}");
      if (tags === null || typeof tags !== "object" || Array.isArray(tags)) {
        throw new Error("Tags must be a JSON object.");
      }
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
        cpu_count: numberOrNull(this.modal.serverInit.cpu_count),
        mem_gb: numberOrNull(this.modal.serverInit.mem_gb),
        disk_count: numberOrNull(this.modal.serverInit.disk_count),
        disk_size_gb: numberOrNull(this.modal.serverInit.disk_size_gb),
        tags,
        compute_units: this.modal.serverInit.compute_units.map((unit, index) => ({
          ordinal: index + 1,
          cpu_range: String(unit.cpu_range || "").trim(),
        })),
      };

      for (const key of ["hostname", "private_ip", "server_admin_user", "region", "zone"]) {
        if (!payload[key]) throw new Error(`${key} is required.`);
      }
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
