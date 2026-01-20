// Kloigos SPA (tabs, no routing) using Alpine + Fetch + Ace for Playbooks editor (no YAML linter yet).

window.app = function () {
  return {
    // Tabs
    view: "dashboard",
    apiBase: "/api",

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
      serverActionConfirm: {
        open: false,
        hostname: "",
        action: "decommission",
      },
      serverDetails: { open: false, row: null },
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
        .replace(/\.\d{3}Z$/, "Z");
    },

    // ---------- Init ----------
    init() {
      const sIdx = localStorage.getItem("kloigos_sort_index");
      const sDir = localStorage.getItem("kloigos_sort_dir");
      const sFilter = localStorage.getItem("kloigos_filter");
      const sFmt = localStorage.getItem("kloigos_inspector_format");
      const sView = localStorage.getItem("kloigos_view");
      const ssIdx = localStorage.getItem("kloigos_servers_sort_index");
      const ssDir = localStorage.getItem("kloigos_servers_sort_dir");
      const ssFilter = localStorage.getItem("kloigos_servers_filter");

      if (sIdx !== null && !Number.isNaN(+sIdx)) this.sortIndex = +sIdx;
      if (sDir === "desc") this.sortDir = "desc";
      if (sFilter !== null) this.filterQuery = sFilter;
      if (ssFilter !== null) this.serversFilterQuery = ssFilter;
      if (ssIdx !== null && !Number.isNaN(+ssIdx))
        this.serversSortIndex = +ssIdx;
      if (ssDir === "desc") this.serversSortDir = "desc";
      if (sFmt === "json" || sFmt === "yaml") this.inspectorFormat = sFmt;
      if (sView === "dashboard" || sView === "playbooks" || sView === "servers")
        this.view = sView;

      this.renderedAtUtc = this.utcNowString();

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

      // Load the active tab
      if (this.view === "playbooks") this.ensurePlaybooksView();
      else if (this.view === "servers") this.ensureServersView();
      else this.ensureDashboardView();
    },

    setView(next) {
      if (next === this.view) return;
      this.view = next;
      localStorage.setItem("kloigos_view", this.view);

      if (this.view === "playbooks") this.ensurePlaybooksView();
      else if (this.view === "servers") this.ensureServersView();
      else this.ensureDashboardView();
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
        const msg =
          (data && (data.detail || data.message)) ||
          (typeof data === "string" && data) ||
          `Request failed (${res.status})`;
        throw new Error(msg);
      }

      return data;
    },

    // ---------- Servers lifecycle ----------
    async ensureServersView() {
      if (this.servers.length === 0 && !this.serversLoading.list)
        await this.refreshServers();
      else this.applyServersFilterSort();
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

    openServerActionConfirm(server, action) {
      this.modal.serverActionConfirm.hostname = server?.hostname || "";
      this.modal.serverActionConfirm.action = action || "decommission";
      this.modal.serverActionConfirm.open = true;
    },

    closeServerActionConfirm() {
      this.modal.serverActionConfirm.open = false;
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
      this.modal.allocate.open = true;
    },
    closeAllocateModal() {
      this.modal.allocate.open = false;
    },

    async allocate() {
      this.loading.allocate = true;
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
      } catch (err) {
        console.log(err);
      } finally {
        this.loading.allocate = false;
        this.closeAllocateModal();
        await this.refreshDashboard();
        if (typeof this.refreshServers === "function")
          await this.refreshServers();
      }
    },

    openInitModal() {
      // Keep any existing values, but ensure step has a sane default.
      if (this.modal.init.cpuStep == null || this.modal.init.cpuStep <= 0)
        this.modal.init.cpuStep = null;

      this.modal.init.open = true;
      this.recomputeInitCpuRanges();
    },
    closeInitModal() {
      this.modal.init.open = false;
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
      } finally {
        this.loading.init = false;
      }
    },

    openDecommissionModal() {
      this.modal.decommission.open = true;
    },
    closeDecommissionModal() {
      this.modal.decommission.open = false;
    },

    async decommissionByHostname() {
      this.loading.decommission = true;
      try {
        const hostname = (this.modal.decommission.hostname || "").trim();
        if (!hostname) throw new Error("hostname is required.");
        await this.apiFetch(`/admin/servers/${encodeURIComponent(hostname)}`, {
          method: "PUT",
        });
        this.closeDecommissionModal();
        await this.refreshDashboard();
        if (typeof this.refreshServers === "function")
          await this.refreshServers();
      } finally {
        this.loading.decommission = false;
      }
    },

    openDeallocateConfirm(row) {
      this.modal.deallocateConfirm.compute_id = row.compute_id;
      this.modal.deallocateConfirm.hostname = row.hostname || "";
      this.modal.deallocateConfirm.open = true;
    },
    closeDeallocateConfirm() {
      this.modal.deallocateConfirm.open = false;
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
      try {
        await this.apiFetch(
          `/compute_units/deallocate/${encodeURIComponent(computeId)}`,
          { method: "DELETE" },
        );
        this.closeDeallocateConfirm();
        await this.refreshDashboard();
        if (typeof this.refreshServers === "function")
          await this.refreshServers();
      } finally {
        this.loading.deallocateConfirm = false;
        this.busyKey = null;
      }
    },

    // ---------- Playbooks lifecycle ----------
    async ensurePlaybooksView() {
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
