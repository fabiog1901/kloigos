// Kloigos SPA (tabs, no routing) using Alpine + Fetch + Ace for Playbooks editor (no YAML linter yet).

window.app = function () {
  return {
    // Tabs
    view: "dashboard",
    apiBase: "/api",

    // Shared UTC timestamps
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
      0: "string",
      1: "string",
      2: "string",
      3: "ip",
      4: "number",
      5: "string",
      6: "string",
      7: "date",
      8: "string",
      9: "string",
      10: "string",
      11: "string",
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
        cpu_count: 4,
        region: "",
        zone: "",
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
    },

    // ---------- Playbooks state ----------
    playbooks: ["cu_allocate", "cu_deallocate", "server_init", "server_decomm"],
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
        .replace(/\.\d{3}Z$/, "Z");
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

      if (sIdx !== null && !Number.isNaN(+sIdx)) this.sortIndex = +sIdx;
      if (sDir === "desc") this.sortDir = "desc";
      if (sFilter !== null) this.filterQuery = sFilter;
      if (sFmt === "json" || sFmt === "yaml") this.inspectorFormat = sFmt;
      if (sView === "dashboard" || sView === "playbooks") this.view = sView;

      this.renderedAtUtc = this.utcNowString();

      // Start dashboard timer (only refresh if dashboard tab is active)
      this._autoTimer = setInterval(() => {
        if (this.autoRefreshEnabled && this.view === "dashboard")
          this.refreshDashboard();
      }, 10_000);

      // Load the active tab
      if (this.view === "playbooks") this.ensurePlaybooksView();
      else this.ensureDashboardView();
    },

    setView(next) {
      if (next === this.view) return;
      this.view = next;
      localStorage.setItem("kloigos_view", this.view);

      if (this.view === "playbooks") this.ensurePlaybooksView();
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

    // ---------- Dashboard lifecycle ----------
    async ensureDashboardView() {
      if (this.computeUnits.length === 0 && !this.loading.list)
        await this.refreshDashboard();
      else this.applyFilterSort();
    },

    persistFilter() {
      localStorage.setItem("kloigos_filter", this.filterQuery || "");
    },
    persistInspectorFormat() {
      localStorage.setItem("kloigos_inspector_format", this.inspectorFormat);
    },

    async refreshDashboard() {
      this.loading.list = true;
      try {
        const data = await this.apiFetch("/compute_units/");
        this.computeUnits = Array.isArray(data) ? data : [];
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
        this.tagValue(row, "owner"),
        this.tagValue(row, "deployment_id"),
      ];
      const tags =
        row.tags && typeof row.tags === "object"
          ? Object.entries(row.tags).map(
              ([k, v]) => `${k}:${Array.isArray(v) ? v.join(",") : v}`
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
          return row.compute_id;
        case 1:
          return `${row.region || "-"}-${row.zone || "-"}`;
        case 2:
          return row.hostname || "";
        case 3:
          return row.ip || "";
        case 4:
          return row.cpu_count;
        case 5:
          return row.cpu_range || "";
        case 6:
          return row.ports_range || "";
        case 7:
          return row.started_at || "";
        case 8:
          return this.tagValue(row, "deployment_id") || "";
        case 9:
          return this.tagValue(row, "owner") || "";
        case 10:
          return row.tags && typeof row.tags === "object"
            ? Object.entries(row.tags)
                .map(([k, v]) => `${k}:${Array.isArray(v) ? v.join(",") : v}`)
                .join(" ")
            : "";
        case 11:
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
        ([k, _]) => !["deployment_id", "owner"].includes(k)
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
      if (s.includes("terminating")) return "status-muted";
      if (!s || s === "unknown") return "status-default";
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
                  depth + 1
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
    openAllocateModal() {
      this.modal.allocate.open = true;
    },
    closeAllocateModal() {
      this.modal.allocate.open = false;
    },

    async allocate() {
      this.loading.allocate = true;
      try {
        const tags = JSON.parse(
          (this.modal.allocate.tagsText || "{}").trim() || "{}"
        );
        const payload = {
          cpu_count: this.modal.allocate.cpu_count ?? 4,
          region: this.modal.allocate.region || null,
          zone: this.modal.allocate.zone || null,
          tags,
          ssh_public_key: (this.modal.allocate.ssh_public_key || "").trim(),
        };
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
      }
    },

    openInitModal() {
      this.modal.init.open = true;
    },
    closeInitModal() {
      this.modal.init.open = false;
    },

    async initServer() {
      this.loading.init = true;
      try {
        const cpu_ranges = JSON.parse(
          (this.modal.init.cpuRangesText || "[]").trim() || "[]"
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
          cpu_ranges,
        };
        for (const [k, v] of Object.entries(payload)) {
          if ((typeof v === "string" && !v) || v == null)
            throw new Error(`${k} is required.`);
        }

        await this.apiFetch("/admin/init_server", {
          method: "POST",
          body: payload,
        });
        this.closeInitModal();
        await this.refreshDashboard();
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
        await this.apiFetch(
          `/admin/decommission_server/${encodeURIComponent(hostname)}`,
          { method: "DELETE" }
        );
        this.closeDecommissionModal();
        await this.refreshDashboard();
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

    async confirmDeallocate() {
      const computeId = this.modal.deallocateConfirm.compute_id;
      this.loading.deallocateConfirm = true;
      this.busyKey = computeId;
      try {
        await this.apiFetch(
          `/compute_units/deallocate/${encodeURIComponent(computeId)}`,
          { method: "DELETE" }
        );
        this.closeDeallocateConfirm();
        await this.refreshDashboard();
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
          { method: "GET" }
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
        Uint8Array.from(atob(b64), (c) => c.charCodeAt(0))
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
          }
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
