window.cpkitWebappExtension = {
  htmlPath: "/app/extension.html",
  navItems: [
    { view: "allocations", label: "Allocations" },
    { view: "compute_units", label: "Compute" },
    { view: "kloigos_servers", label: "Servers" },
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
  },
  state: {
    allocations: [],
    allocationsVisibleRows: [],
    allocationsFilterQuery: "",
    allocationsLastUpdatedUtc: null,
    allocationsSortIndex: null,
    allocationsSortDir: "asc",
    allocationsSortTypeByIndex: {
      0: "string",
      1: "string",
      2: "ip",
      3: "string",
      4: "string",
      5: "string",
      6: "string",
      7: "string",
      8: "date",
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
      4: "ip",
      5: "number",
      6: "string",
      8: "date",
      9: "string",
    },
    computeLoading: {
      list: false,
    },
    computeAutoRefreshEnabled: true,
    _computeAutoTimer: null,
    modal: {
      allocate: {
        open: false,
        allocation_id: "",
        name: "",
        ip_address: "",
        cpu_count: null,
        region: "",
        zone: "",
        compute_id: "",
        tagsText: "{}",
        ssh_public_key: "",
      },
      allocationDetails: { open: false, row: null },
      allocationScale: {
        open: false,
        allocation_id: "",
        name: "",
        compute_id: "",
        cpu_count: null,
        region: "",
        zone: "",
      },
      deallocateConfirm: { open: false, allocation_id: "", name: "", compute_id: "" },
      computeDetails: { open: false, row: null },
      serverDetails: { open: false, row: null },
      serverActionConfirm: { open: false, hostname: "", action: "decommission" },
      serverInit: {
        open: false,
        private_ip: "",
        public_ip: "",
        hostname: "",
        user_id: "ubuntu",
        region: "",
        zone: "",
        cpu_count: null,
        mem_gb: null,
        disk_count: null,
        disk_size_gb: null,
        tagsText: "{}",
        compute_units: [{ ordinal: 1, cpu_range: "0-3", private_ip: "", public_ip: "" }],
      },
    },
    modalError: {
      allocate: "",
      allocationScale: "",
      deallocateConfirm: "",
      serverActionConfirm: "",
      serverInit: "",
    },
  },
  async init() {
    this.restoreAllocationsLocalState();
    this.restoreComputeLocalState();
    this.restoreServersLocalState();
    if (this.view === "allocations") await this.ensureAllocationsView();
    if (this.view === "compute_units") await this.ensureComputeUnitsView();
    if (this.view === "kloigos_servers") await this.ensureKloigosServersView();
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
  },
  methods: {
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
        this.viewNotice = this.errorMessage(error, "Failed to load allocations.");
      } finally {
        this.allocationsLoading.list = false;
      }
    },

    async ensureKloigosServersView() {
      if (!this.canViewKloigosAdmin()) {
        this.viewNotice = "Servers requires CP_ADMIN.";
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
        this.viewNotice = this.errorMessage(error, "Failed to load compute units.");
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
        row.name,
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
          return row.name || "";
        case 2:
          return row.ip_address || "";
        case 3:
          return row.login_user || "";
        case 4:
          return row.compute_id || "";
        case 5:
          return row.current_host || "";
        case 6:
          return this.serversTagsCompact(row.tags);
        case 7:
          return row.status || "";
        case 8:
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

      this.allocationsVisibleRows = rows;
    },

    serversRowText(server) {
      const tags = server.tags && typeof server.tags === "object"
        ? Object.entries(server.tags).map(([key, value]) => `${key}:${Array.isArray(value) ? value.join(",") : value}`)
        : [];
      return [
        server.hostname,
        server.private_ip,
        server.public_ip,
        server.user_id,
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
          return server.user_id || "";
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
        this.viewNotice = this.errorMessage(error, "Failed to load servers.");
      } finally {
        this.serversLoading.list = false;
      }
    },

    persistComputeFilter() {
      localStorage.setItem("kloigos_compute_filter", this.computeFilterQuery || "");
    },

    computeRowText(row) {
      const tags = row.tags && typeof row.tags === "object"
        ? Object.entries(row.tags).map(([key, value]) => `${key}:${Array.isArray(value) ? value.join(",") : value}`)
        : [];
      return [
        row.compute_id,
        row.hostname,
        row.private_ip,
        row.system_user,
        row.public_ip,
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
          return row.private_ip || "";
        case 5:
          return row.cpu_count ?? "";
        case 6:
          return row.system_user || "";
        case 8:
          return row.started_at || "";
        case 9:
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
      this.modal.allocate.name = "";
      this.modal.allocate.ip_address = "";
      this.modal.allocate.cpu_count = null;
      this.modal.allocate.region = "";
      this.modal.allocate.zone = "";
      this.modal.allocate.compute_id = computeId ? String(computeId) : "";
      this.modal.allocate.tagsText = "{}";
      this.modal.allocate.ssh_public_key = "";
      this.modalError.allocate = "";
      this.modal.allocate.open = true;
    },

    closeAllocateModal() {
      this.modal.allocate.open = false;
      this.modalError.allocate = "";
    },

    async createAllocation() {
      this.allocationsLoading.allocate = true;
      this.modalError.allocate = "";
      try {
        const tags = JSON.parse((this.modal.allocate.tagsText || "{}").trim() || "{}");
        if (tags === null || typeof tags !== "object" || Array.isArray(tags)) {
          throw new Error("Tags must be a JSON object.");
        }

        const allocationId = (this.modal.allocate.allocation_id || "").trim();
        const allocationName = (this.modal.allocate.name || "").trim();
        const payload = {
          allocation_id: allocationId || null,
          name: allocationName || allocationId || null,
          ip_address: (this.modal.allocate.ip_address || "").trim() || null,
          cpu_count: this.modal.allocate.cpu_count ?? null,
          region: (this.modal.allocate.region || "").trim() || null,
          zone: (this.modal.allocate.zone || "").trim() || null,
          compute_id: (this.modal.allocate.compute_id || "").trim() || null,
          tags: allocationId ? { ...tags, allocation_id: allocationId } : tags,
          ssh_public_key: (this.modal.allocate.ssh_public_key || "").trim(),
        };

        if (!payload.ssh_public_key) throw new Error("SSH public key is required.");

        const result = await this.apiFetch("/allocations/", { method: "POST", body: payload });
        this.closeAllocateModal();
        this.viewNotice = result?.job_id ? `Allocation queued as job ${result.job_id}.` : "Allocation queued.";
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
      this.modal.deallocateConfirm.name = row.name || "";
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
        this.viewNotice = result?.job_id ? `Deallocation queued as job ${result.job_id}.` : "Deallocation queued.";
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
      this.modal.allocationScale.name = row?.name || "";
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
        this.viewNotice = result?.job_id ? `Scale queued as job ${result.job_id}.` : "Scale queued.";
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
        private_ip: "",
        public_ip: "",
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
        user_id: String(this.modal.serverInit.user_id || "ubuntu").trim(),
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
          private_ip: String(unit.private_ip || "").trim(),
          public_ip: String(unit.public_ip || "").trim() || null,
        })),
      };

      for (const key of ["hostname", "private_ip", "user_id", "region", "zone"]) {
        if (!payload[key]) throw new Error(`${key} is required.`);
      }
      if (payload.compute_units.length === 0) throw new Error("At least one compute unit is required.");
      for (const unit of payload.compute_units) {
        if (!unit.cpu_range || !unit.private_ip) {
          throw new Error("Each compute unit needs a CPU range and private IP.");
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
