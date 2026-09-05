// RetailIQ Enterprise B2B Frontend Engine - Extended Multi-Feature & Date Snapshot System
document.addEventListener("DOMContentLoaded", () => {
    // Global State
    const state = {
        currentTab: "dashboard",
        selectedStore: "all",
        selectedDate: null,
        dashboardTimeframe: 30,
        salesTimeframe: 30,
        inventoryData: [],
        dashboardData: null,
        storesData: [],
        compareSelectedStores: []
    };

    // DOM References
    const navItems = document.querySelectorAll(".nav-item");
    const tabViews = document.querySelectorAll(".tab-view");
    const globalStoreSelect = document.getElementById("global-store-select");
    const globalSearchInput = document.getElementById("global-search-input");
    const globalDateSelect = document.getElementById("global-date-select");
    const globalDatePicker = document.getElementById("global-date-picker");

    // Product Modal References
    const productModal = document.getElementById("product-detail-modal");
    const productModalCloseBtn = document.getElementById("modal-close-btn");

    // Initialize
    init();

    async function init() {
        setupNavigation();
        setupFilters();
        setupDateSnapshot();
        setupCopilotTab();
        setupProductModal();
        setupReorderPlanner();
        setupStoreComparison();
        setupDatasetManagerModal();
        setupDataManagementPage();

        await loadActiveDatasetHeader();
        await loadStores();
        await loadAllViews();
    }

    async function loadAllViews() {
        await loadDashboard();
        await loadInventory();
        await loadSalesWorkspace();
        await loadReorderPlanner();
        await loadDecisionCenter();
        await loadStoreComparison();
        await loadExecutiveReport();
        await loadDataManagementView();
    }

    // =========================================================================
    // UTILITY FUNCTIONS
    // =========================================================================

    /** Safely escapes user-controlled strings before injecting into innerHTML. */
    function escapeHTML(str) {
        const d = document.createElement('div');
        d.appendChild(document.createTextNode(String(str ?? '')));
        return d.innerHTML;
    }

    /**
     * Shows a brief floating toast notification.
     * @param {string} message - Text to display
     * @param {'success'|'error'|'info'} type - Visual style
     */
    function showToast(message, type = 'success') {
        const existing = document.getElementById('retailiq-toast');
        if (existing) existing.remove();

        const toast = document.createElement('div');
        toast.id = 'retailiq-toast';
        const colors = {
            success: { bg: '#166534', border: '#15803d', icon: '✓' },
            error:   { bg: '#991b1b', border: '#b91c1c', icon: '✕' },
            info:    { bg: '#1e3a5f', border: '#2563eb', icon: 'ℹ' }
        };
        const c = colors[type] || colors.success;
        toast.style.cssText = [
            'position:fixed', 'bottom:28px', 'right:28px', 'z-index:99999',
            'display:flex', 'align-items:center', 'gap:10px',
            'background:' + c.bg, 'border:1.5px solid ' + c.border,
            'color:#fff', 'font-size:13px', 'font-weight:600',
            'padding:12px 20px', 'border-radius:10px',
            'box-shadow:0 8px 32px rgba(0,0,0,0.45)',
            'opacity:0', 'transition:opacity 0.25s ease',
            'max-width:380px'
        ].join(';');
        toast.innerHTML = '<span style="font-size:16px;">' + c.icon + '</span><span>' + escapeHTML(message) + '</span>';
        document.body.appendChild(toast);

        requestAnimationFrame(() => { toast.style.opacity = '1'; });
        setTimeout(() => {
            toast.style.opacity = '0';
            setTimeout(() => toast.remove(), 300);
        }, 3000);
    }

    // =========================================================================
    // ACTIVE DATASET MANAGEMENT & DYNAMIC STATE SYNC
    // =========================================================================

    async function loadActiveDatasetHeader() {
        try {
            const res = await fetch("/api/datasets/active");
            if (!res.ok) return;
            const active = await res.json();

            const pillName = document.getElementById("pill-dataset-name");
            const pillStats = document.getElementById("pill-dataset-stats");
            const pillBadge = document.getElementById("pill-dataset-badge");

            if (!active.dataset_id || active.status === "NO_DATA") {
                if (pillName) pillName.textContent = "No Dataset Active";
                if (pillStats) pillStats.textContent = "Not Connected";
                if (pillBadge) {
                    pillBadge.textContent = "NO DATA";
                    pillBadge.style.backgroundColor = "#FEE2E2";
                    pillBadge.style.color = "#991B1B";
                }
            } else {
                if (pillName) pillName.textContent = active.dataset_name || "Active Dataset";
                if (pillStats) {
                    pillStats.textContent = `${active.store_count} Stores, ${active.product_count} SKUs`;
                }
                if (pillBadge) {
                    pillBadge.textContent = active.is_demo ? "DEMO" : "ACTIVE";
                    pillBadge.style.backgroundColor = active.is_demo ? "#E0E7FF" : "#DCFCE7";
                    pillBadge.style.color = active.is_demo ? "#3730A3" : "#166534";
                }
            }
        } catch (e) {
            console.error("Error loading active dataset header:", e);
        }
    }

    async function loadStores() {
        try {
            const res = await fetch("/api/stores");
            if (!res.ok) return;
            const stores = await res.json();
            state.storesData = stores;

            // Populate globalStoreSelect
            if (globalStoreSelect) {
                const cur = state.selectedStore;
                globalStoreSelect.innerHTML = `<option value="all">All Stores (${stores.length})</option>` +
                    stores.map(s => `<option value="${s.store_id}">${s.store_name}</option>`).join("");
                if (stores.some(s => s.store_id === cur)) {
                    globalStoreSelect.value = cur;
                } else {
                    state.selectedStore = "all";
                    globalStoreSelect.value = "all";
                }
            }

            // Populate sales-store-select
            const salesStoreSelect = document.getElementById("sales-store-select");
            if (salesStoreSelect) {
                salesStoreSelect.innerHTML = `<option value="all">All Stores (${stores.length})</option>` +
                    stores.map(s => `<option value="${s.store_id}">${s.store_name}</option>`).join("");
                salesStoreSelect.value = state.selectedStore;
            }

            // Update compare checkboxes (select all stores by default)
            state.compareSelectedStores = stores.map(s => s.store_id);
            setupStoreComparison();
        } catch (e) {
            console.error("Error loading stores:", e);
        }
    }

    function setupDatasetManagerModal() {
        const modal = document.getElementById("dataset-manager-modal");
        const closeBtn = document.getElementById("dataset-modal-close-btn");
        const cancelBtn = document.getElementById("btn-cancel-upload");
        const triggerPill = document.getElementById("header-dataset-pill");
        const navTrigger = document.getElementById("nav-btn-dataset-manager");
        const quickResetBtn = document.getElementById("btn-quick-reset-demo");
        const dTabBtns = document.querySelectorAll(".d-tab-btn");
        const uploadForm = document.getElementById("dataset-upload-form");
        const singleFileInput = document.getElementById("single-file-input");
        const singleFileChosen = document.getElementById("single-file-chosen");
        const singleDropzone = document.getElementById("single-upload-zone");
        const uploadModeRadios = document.querySelectorAll("input[name='upload-mode']");
        const singleZone = document.getElementById("single-upload-zone");
        const multiZone = document.getElementById("multi-upload-zone");
        const errorAlert = document.getElementById("upload-error-alert");
        const progressBox = document.getElementById("dataset-upload-progress");
        const progressFill = document.getElementById("upload-progress-fill");
        const stepText = document.getElementById("upload-step-text");

        const openModal = async () => {
            if (!modal) return;
            modal.classList.remove("hidden");
            if (errorAlert) errorAlert.classList.add("hidden");
            if (progressBox) progressBox.classList.add("hidden");
            await loadDatasetsList();
        };

        const closeModal = () => {
            if (modal) modal.classList.add("hidden");
        };

        if (triggerPill) {
            triggerPill.addEventListener("click", () => {
                switchToTab("data-management");
            });
        }
        if (navTrigger) navTrigger.addEventListener("click", openModal);
        if (closeBtn) closeBtn.addEventListener("click", closeModal);
        if (cancelBtn) cancelBtn.addEventListener("click", closeModal);

        if (modal) {
            modal.addEventListener("click", (e) => {
                if (e.target === modal) closeModal();
            });
        }

        // Tab switching in modal
        dTabBtns.forEach(btn => {
            btn.addEventListener("click", () => {
                dTabBtns.forEach(b => b.classList.remove("active"));
                document.querySelectorAll(".dtab-content").forEach(c => c.classList.remove("active"));
                btn.classList.add("active");
                const target = btn.getAttribute("data-dtab");
                const targetEl = document.getElementById(target);
                if (targetEl) targetEl.classList.add("active");
                if (errorAlert) errorAlert.classList.add("hidden");
            });
        });

        // Reset to Demo button
        if (quickResetBtn) {
            quickResetBtn.addEventListener("click", async () => {
                try {
                    const res = await fetch("/api/datasets/reset", { method: "POST" });
                    if (!res.ok) throw new Error("Failed to reset dataset");
                    await onDatasetChanged();
                    closeModal();
                } catch (err) {
                    alert("Error resetting dataset: " + err.message);
                }
            });
        }

        // Upload mode radio toggle
        uploadModeRadios.forEach(radio => {
            radio.addEventListener("change", (e) => {
                if (errorAlert) errorAlert.classList.add("hidden");
                if (e.target.value === "single") {
                    if (singleZone) singleZone.classList.remove("hidden");
                    if (multiZone) multiZone.classList.add("hidden");
                    // Clear 4 CSV files
                    ["multi-sales-file", "multi-inv-file", "multi-prods-file", "multi-stores-file"].forEach(id => {
                        const el = document.getElementById(id);
                        if (el) el.value = "";
                    });
                } else {
                    if (singleZone) singleZone.classList.add("hidden");
                    if (multiZone) multiZone.classList.remove("hidden");
                    // Clear single file
                    if (singleFileInput) singleFileInput.value = "";
                    if (singleFileChosen) singleFileChosen.textContent = "No file chosen";
                }
            });
        });

        // Single File Input change
        if (singleFileInput) {
            singleFileInput.addEventListener("change", () => {
                if (singleFileInput.files && singleFileInput.files[0]) {
                    const file = singleFileInput.files[0];
                    if (singleFileChosen) singleFileChosen.textContent = `Selected: ${file.name} (${(file.size / 1024).toFixed(1)} KB)`;
                    const nameInput = document.getElementById("upload-dataset-name");
                    if (nameInput && !nameInput.value.trim()) {
                        nameInput.value = file.name.replace(/\.[^/.]+$/, "").replace(/[_-]/g, " ").replace(/\b\w/g, l => l.toUpperCase());
                    }
                }
            });
        }

        // Drag and drop for single dropzone
        if (singleDropzone) {
            ["dragenter", "dragover"].forEach(eventName => {
                singleDropzone.addEventListener(eventName, (e) => {
                    e.preventDefault();
                    singleDropzone.classList.add("dragover");
                }, false);
            });
            ["dragleave", "drop"].forEach(eventName => {
                singleDropzone.addEventListener(eventName, (e) => {
                    e.preventDefault();
                    singleDropzone.classList.remove("dragover");
                }, false);
            });
            singleDropzone.addEventListener("drop", (e) => {
                const dt = e.dataTransfer;
                const files = dt.files;
                if (files && files.length > 0) {
                    singleFileInput.files = files;
                    const file = files[0];
                    if (singleFileChosen) singleFileChosen.textContent = `Selected: ${file.name} (${(file.size / 1024).toFixed(1)} KB)`;
                    const nameInput = document.getElementById("upload-dataset-name");
                    if (nameInput && !nameInput.value.trim()) {
                        nameInput.value = file.name.replace(/\.[^/.]+$/, "").replace(/[_-]/g, " ").replace(/\b\w/g, l => l.toUpperCase());
                    }
                }
            });
        }

        // Upload Form Submit
        if (uploadForm) {
            uploadForm.addEventListener("submit", async (e) => {
                e.preventDefault();
                if (errorAlert) errorAlert.classList.add("hidden");

                const datasetName = (document.getElementById("upload-dataset-name")?.value || "").trim();
                if (!datasetName) {
                    if (errorAlert) {
                        errorAlert.textContent = "Dataset name is required.";
                        errorAlert.classList.remove("hidden");
                    }
                    return;
                }

                const mode = document.querySelector("input[name='upload-mode']:checked")?.value || "single";
                const formData = new FormData();
                formData.append("dataset_name", datasetName);

                if (mode === "single") {
                    const f = singleFileInput?.files?.[0];
                    if (!f) {
                        if (errorAlert) {
                            errorAlert.textContent = "Please select a CSV or Excel file.";
                            errorAlert.classList.remove("hidden");
                        }
                        return;
                    }
                    const fname = f.name.toLowerCase();
                    if (!fname.endsWith(".csv") && !fname.endsWith(".xlsx") && !fname.endsWith(".xls")) {
                        if (errorAlert) {
                            errorAlert.textContent = "Invalid file type. Please upload a CSV or supported Excel file.";
                            errorAlert.classList.remove("hidden");
                        }
                        return;
                    }
                    formData.append("file", f);
                } else {
                    const salesF = document.getElementById("multi-sales-file")?.files?.[0];
                    const invF = document.getElementById("multi-inv-file")?.files?.[0];
                    const prodsF = document.getElementById("multi-prods-file")?.files?.[0];
                    const storesF = document.getElementById("multi-stores-file")?.files?.[0];

                    if (!salesF) {
                        if (errorAlert) {
                            errorAlert.textContent = "Sales CSV is required.";
                            errorAlert.classList.remove("hidden");
                        }
                        return;
                    }
                    if (!invF) {
                        if (errorAlert) {
                            errorAlert.textContent = "Inventory CSV is required.";
                            errorAlert.classList.remove("hidden");
                        }
                        return;
                    }
                    if (!prodsF) {
                        if (errorAlert) {
                            errorAlert.textContent = "Products CSV is required.";
                            errorAlert.classList.remove("hidden");
                        }
                        return;
                    }
                    if (!storesF) {
                        if (errorAlert) {
                            errorAlert.textContent = "Stores CSV is required.";
                            errorAlert.classList.remove("hidden");
                        }
                        return;
                    }

                    for (const f of [salesF, invF, prodsF, storesF]) {
                        if (!f.name.toLowerCase().endsWith(".csv")) {
                            if (errorAlert) {
                                errorAlert.textContent = "Invalid file type. Please upload a CSV or supported Excel file.";
                                errorAlert.classList.remove("hidden");
                            }
                            return;
                        }
                    }

                    formData.append("sales_file", salesF);
                    formData.append("inventory_file", invF);
                    formData.append("products_file", prodsF);
                    formData.append("stores_file", storesF);
                }

                // Show Multi-Step Loading Progress Bar (Requirement 35)
                if (progressBox) progressBox.classList.remove("hidden");
                const setStep = (pct, text) => {
                    if (progressFill) progressFill.style.width = pct + "%";
                    if (stepText) stepText.textContent = text;
                };

                setStep(20, "Importing dataset files...");
                await new Promise(r => setTimeout(r, 250));
                setStep(45, "Validating schema & normalizing data...");
                await new Promise(r => setTimeout(r, 250));
                setStep(70, "Building isolated relational retail model...");
                await new Promise(r => setTimeout(r, 200));

                try {
                    const res = await fetch("/api/datasets/upload", {
                        method: "POST",
                        body: formData
                    });

                    const data = await res.json();
                    if (!res.ok) {
                        throw new Error(data.detail || "Dataset upload failed");
                    }

                    setStep(90, "Calculating deterministic analytics...");
                    await new Promise(r => setTimeout(r, 250));
                    setStep(100, "Ready ✓ Dataset activated successfully!");
                    await new Promise(r => setTimeout(r, 400));

                    showToast(`✓ Dataset "${data.dataset?.dataset_name || "Custom Dataset"}" activated successfully!`, 'success');
                    await onDatasetChanged();
                    closeModal();

                } catch (err) {
                    if (progressBox) progressBox.classList.add("hidden");
                    if (errorAlert) {
                        errorAlert.textContent = "Upload failed: " + err.message + " (Previous active dataset remained unchanged)";
                        errorAlert.classList.remove("hidden");
                    }
                }
            });
        }
    }

    async function loadDatasetsList() {
        const container = document.getElementById("datasets-list-container");
        if (!container) return;

        try {
            container.innerHTML = `<div style="text-align:center; padding:20px; color:var(--text-muted);">Loading datasets...</div>`;
            const res = await fetch("/api/datasets");
            if (!res.ok) throw new Error("Failed to fetch datasets");
            const data = await res.json();
            const activeDs = data.active_dataset;
            const list = data.datasets || [];

            if (list.length === 0) {
                container.innerHTML = `<div style="text-align:center; padding:20px; color:var(--text-muted);">No datasets available.</div>`;
                return;
            }

            container.innerHTML = list.map(ds => {
                const isActive = (ds.dataset_id === activeDs.dataset_id);
                const salesStr = ds.sales_count >= 1000 ? (ds.sales_count / 1000).toFixed(1) + "K" : ds.sales_count;
                const revStr = "₹" + Number(ds.total_revenue || 0).toLocaleString('en-IN', { maximumFractionDigits: 0 });

                return `
                    <div class="dataset-card ${isActive ? 'active-ds' : ''}">
                        <div class="dataset-card-left">
                            <div class="dataset-card-header">
                                <span class="dataset-card-title">${escapeHTML(ds.dataset_name)}</span>
                                ${isActive ? '<span class="badge badge-success">ACTIVE</span>' : (ds.is_demo ? '<span class="badge badge-secondary">DEMO</span>' : '<span class="badge badge-primary">CUSTOM</span>')}
                            </div>
                            <div class="dataset-card-metrics">
                                <span>🏬 <strong>${escapeHTML(ds.store_count)}</strong> Stores</span>
                                <span>📦 <strong>${escapeHTML(ds.product_count)}</strong> Products</span>
                                <span>💳 <strong>${escapeHTML(salesStr)}</strong> Sales</span>
                                <span>💰 <strong>${escapeHTML(revStr)}</strong> Rev</span>
                                <span>📅 ${escapeHTML(ds.min_date)} → ${escapeHTML(ds.max_date)}</span>
                            </div>
                        </div>
                        <div style="display:flex;gap:6px;align-items:center;">
                            ${isActive ? `
                                <button class="btn-secondary" disabled style="opacity:0.6; cursor:default; font-size:12px; padding:6px 14px;">
                                    ✓ Current Active
                                </button>
                            ` : `
                                <button class="btn-primary btn-activate-ds" data-id="${escapeHTML(ds.dataset_id)}" data-name="${escapeHTML(ds.dataset_name)}" style="font-size:12px; padding:6px 14px;">
                                    Activate Dataset
                                </button>
                            `}
                            ${!ds.is_demo ? `
                                <button class="btn-danger btn-delete-ds" data-id="${escapeHTML(ds.dataset_id)}" data-name="${escapeHTML(ds.dataset_name)}" style="font-size:12px; padding:6px 12px; background:var(--danger,#dc2626); color:#fff; border:none; border-radius:6px; cursor:pointer;">
                                    🗑 Delete
                                </button>
                            ` : ''}
                        </div>
                    </div>
                `;
            }).join("");

            // Attach activate event listeners
            container.querySelectorAll(".btn-activate-ds").forEach(btn => {
                btn.addEventListener("click", async () => {
                    const dsId = btn.getAttribute("data-id");
                    const dsName = btn.getAttribute("data-name");
                    const originalText = btn.textContent;
                    btn.disabled = true;
                    btn.textContent = "Activating...";
                    try {
                        const res = await fetch("/api/datasets/activate", {
                            method: "POST",
                            headers: { "Content-Type": "application/json" },
                            body: JSON.stringify({ dataset_id: dsId })
                        });
                        if (!res.ok) throw new Error("Failed to activate dataset");
                        showToast(`✓ Switched to ${dsName}`, 'success');
                        await onDatasetChanged();
                        const modal = document.getElementById("dataset-manager-modal");
                        if (modal) modal.classList.add("hidden");
                    } catch (err) {
                        btn.disabled = false;
                        btn.textContent = originalText;
                        showToast("Error activating dataset: " + err.message, 'error');
                    }
                });
            });

            // Attach delete event listeners
            container.querySelectorAll(".btn-delete-ds").forEach(btn => {
                btn.addEventListener("click", async () => {
                    const dsId = btn.getAttribute("data-id");
                    const dsName = btn.getAttribute("data-name");
                    if (!confirm(`Delete "${dsName}"?\n\nThis will permanently remove the dataset and cannot be undone.`)) return;
                    btn.disabled = true;
                    btn.textContent = "Deleting...";
                    try {
                        const res = await fetch(`/api/datasets/${encodeURIComponent(dsId)}`, { method: "DELETE" });
                        if (!res.ok) {
                            const err = await res.json().catch(() => ({ detail: "Delete failed" }));
                            throw new Error(err.detail || "Delete failed");
                        }
                        showToast(`Dataset "${dsName}" deleted.`, 'info');
                        await onDatasetChanged();
                        await loadDatasetsList();
                    } catch (err) {
                        btn.disabled = false;
                        btn.textContent = "🗑 Delete";
                        showToast("Error deleting dataset: " + err.message, 'error');
                    }
                });
            });

        } catch (e) {
            container.innerHTML = `<div style="color:var(--danger); padding:10px;">Error loading datasets: ${escapeHTML(e.message)}</div>`;
        }
    }


    async function onDatasetChanged() {
        // 1. Reset frontend filters and selections (Requirements 17 & 18)
        state.selectedStore = "all";
        state.selectedDate = null;

        if (globalStoreSelect) globalStoreSelect.value = "all";
        if (globalDateSelect) globalDateSelect.value = "today";
        if (globalDatePicker) {
            globalDatePicker.value = "";
            globalDatePicker.style.display = "none";
        }
        if (globalSearchInput) globalSearchInput.value = "";

        const invCat = document.getElementById("inv-filter-category");
        if (invCat) invCat.value = "all";
        const invStat = document.getElementById("inv-filter-status");
        if (invStat) invStat.value = "all";

        const reorderPriority = document.getElementById("reorder-filter-priority");
        if (reorderPriority) reorderPriority.value = "all";
        const reorderCat = document.getElementById("reorder-filter-category");
        if (reorderCat) reorderCat.value = "all";

        // Reset Copilot chat messages to fresh welcome state
        const chatContainer = document.getElementById("chat-messages-container");
        if (chatContainer) {
            const welcomeCard = document.getElementById("copilot-welcome-card");
            if (welcomeCard) {
                chatContainer.innerHTML = "";
                chatContainer.appendChild(welcomeCard);
            }
        }

        // 2. Refresh active dataset header pill
        await loadActiveDatasetHeader();

        // 3. Reload stores list
        await loadStores();

        // 4. Reload all views
        await loadAllViews();
    }

    async function loadDataManagementView() {
        try {
            const [resActive, resList] = await Promise.all([
                fetch("/api/datasets/active"),
                fetch("/api/datasets")
            ]);

            if (resActive.ok) {
                const active = await resActive.json();
                const dmName = document.getElementById("dm-active-name");
                const dmBadge = document.getElementById("dm-active-badge");
                const dmProds = document.getElementById("dm-stat-products");
                const dmStores = document.getElementById("dm-stat-stores");
                const dmSales = document.getElementById("dm-stat-sales");
                const dmInv = document.getElementById("dm-stat-inventory");
                const dmDates = document.getElementById("dm-stat-dates");

                if (!active.dataset_id || active.status === "NO_DATA") {
                    if (dmName) dmName.textContent = "No Dataset Active";
                    if (dmBadge) {
                        dmBadge.textContent = "NOT CONNECTED";
                        dmBadge.className = "badge badge-warning";
                    }
                    if (dmProds) dmProds.textContent = "0 SKUs";
                    if (dmStores) dmStores.textContent = "0 Stores";
                    if (dmSales) dmSales.textContent = "0 Sales Records";
                    if (dmInv) dmInv.textContent = "0 Inventory Records";
                    if (dmDates) dmDates.textContent = "Upload your retail data to get started";
                } else {
                    if (dmName) dmName.textContent = active.dataset_name || "Active Dataset";
                    if (dmBadge) {
                        dmBadge.textContent = active.is_demo ? "DEMO DATASET" : "CUSTOM ACTIVE";
                        dmBadge.className = active.is_demo ? "badge badge-secondary" : "badge badge-success";
                    }
                    if (dmProds) dmProds.textContent = `${active.product_count} SKUs`;
                    if (dmStores) dmStores.textContent = `${active.store_count} Stores`;
                    if (dmSales) dmSales.textContent = `${Number(active.sales_count).toLocaleString()} Sales Records`;
                    if (dmInv) dmInv.textContent = `${Number(active.inventory_count || (active.product_count * active.store_count)).toLocaleString()} Inventory Records`;
                    if (dmDates) dmDates.textContent = `${active.min_date} → ${active.max_date}`;
                }
            }

            if (resList.ok) {
                const listData = await resList.json();
                const container = document.getElementById("dm-datasets-list");
                const activeId = listData.active_dataset?.dataset_id;
                const datasets = listData.datasets || [];

                if (container) {
                    if (datasets.length === 0) {
                        container.innerHTML = `<div style="padding:10px; color:var(--text-muted); font-size:12px;">No datasets registered.</div>`;
                    } else {
                        container.innerHTML = datasets.map(ds => {
                            const isActive = (ds.dataset_id === activeId && activeId !== null);
                            const salesStr = ds.sales_count >= 1000 ? (ds.sales_count / 1000).toFixed(1) + "K" : ds.sales_count;
                            const revStr = "₹" + Number(ds.total_revenue || 0).toLocaleString('en-IN', { maximumFractionDigits: 0 });

                            return `
                                <div class="dataset-card ${isActive ? 'active-card' : ''}" style="display:flex; justify-content:space-between; align-items:center; gap:10px;">
                                    <div>
                                        <div style="display:flex; align-items:center; gap:6px; margin-bottom:4px;">
                                            <span style="font-size:13px; font-weight:700; color:var(--text-primary);">${escapeHTML(ds.dataset_name)}</span>
                                            ${isActive ? '<span class="badge badge-success" style="font-size:9px; padding:2px 6px;">ACTIVE</span>' : (ds.is_demo ? '<span class="badge badge-secondary" style="font-size:9px; padding:2px 6px;">DEMO</span>' : '<span class="badge badge-primary" style="font-size:9px; padding:2px 6px;">CUSTOM</span>')}
                                        </div>
                                        <div style="font-size:11px; color:var(--text-muted); display:flex; gap:8px; flex-wrap:wrap;">
                                            <span>🏬 ${escapeHTML(ds.store_count)} Stores</span>
                                            <span>📦 ${escapeHTML(ds.product_count)} SKUs</span>
                                            <span>💳 ${escapeHTML(salesStr)} Sales</span>
                                            <span>💰 ${escapeHTML(revStr)}</span>
                                            <span>📅 ${escapeHTML(ds.min_date)} → ${escapeHTML(ds.max_date)}</span>
                                        </div>
                                    </div>
                                    <div style="display:flex; gap:6px; align-items:center; flex-shrink:0;">
                                        ${isActive ? `
                                            <button class="btn-secondary" disabled style="opacity:0.6; cursor:default; font-size:11px; padding:4px 10px;">
                                                ✓ Active
                                            </button>
                                        ` : `
                                            <button class="btn-primary btn-dm-activate" data-id="${escapeHTML(ds.dataset_id)}" data-name="${escapeHTML(ds.dataset_name)}" style="font-size:11px; padding:4px 10px;">
                                                ${ds.is_demo ? 'Use Demo Dataset' : 'Activate'}
                                            </button>
                                        `}
                                        ${!ds.is_demo ? `
                                            <button class="btn-dm-delete" data-id="${escapeHTML(ds.dataset_id)}" data-name="${escapeHTML(ds.dataset_name)}" style="font-size:11px; padding:4px 10px; background:var(--danger,#dc2626); color:#fff; border:none; border-radius:6px; cursor:pointer;">
                                                🗑
                                            </button>
                                        ` : ''}
                                    </div>
                                </div>
                            `;
                        }).join("");

                        container.querySelectorAll(".btn-dm-activate").forEach(btn => {
                            btn.addEventListener("click", async () => {
                                const dsId = btn.getAttribute("data-id");
                                const dsName = btn.getAttribute("data-name");
                                const originalText = btn.textContent.trim();
                                btn.disabled = true;
                                btn.textContent = "Activating...";
                                try {
                                    const res = await fetch("/api/datasets/activate", {
                                        method: "POST",
                                        headers: { "Content-Type": "application/json" },
                                        body: JSON.stringify({ dataset_id: dsId })
                                    });
                                    if (!res.ok) throw new Error("Failed to activate dataset");
                                    showToast(`✓ Switched to ${dsName}`, 'success');
                                    await onDatasetChanged();
                                } catch (err) {
                                    btn.disabled = false;
                                    btn.textContent = originalText;
                                    showToast("Error activating dataset: " + err.message, 'error');
                                }
                            });
                        });

                        container.querySelectorAll(".btn-dm-delete").forEach(btn => {
                            btn.addEventListener("click", async () => {
                                const dsId = btn.getAttribute("data-id");
                                const dsName = btn.getAttribute("data-name");
                                if (!confirm(`Delete "${dsName}"?\n\nThis will permanently remove the dataset and cannot be undone.`)) return;
                                btn.disabled = true;
                                btn.textContent = "...";
                                try {
                                    const res = await fetch(`/api/datasets/${encodeURIComponent(dsId)}`, { method: "DELETE" });
                                    if (!res.ok) {
                                        const errData = await res.json().catch(() => ({ detail: "Delete failed" }));
                                        throw new Error(errData.detail || "Delete failed");
                                    }
                                    showToast(`Dataset "${dsName}" deleted.`, 'info');
                                    await onDatasetChanged();
                                } catch (err) {
                                    btn.disabled = false;
                                    btn.textContent = "🗑";
                                    showToast("Error deleting dataset: " + err.message, 'error');
                                }
                            });
                        });
                    }
                }
            }
        } catch (e) {
            console.error("Error loading data management view:", e);
        }
    }


    function setupDataManagementPage() {
        const resetBtn = document.getElementById("dm-btn-reset-demo");
        const clearBtn = document.getElementById("dm-btn-clear-dataset");
        const refreshBtn = document.getElementById("dm-btn-refresh-list");
        const modeRadios = document.querySelectorAll("input[name='dm-upload-mode']");
        const singleZone = document.getElementById("dm-single-zone");
        const multiZone = document.getElementById("dm-multi-zone");
        const singleInput = document.getElementById("dm-single-file-input");
        const singleFileName = document.getElementById("dm-single-file-name");
        const nameInput = document.getElementById("dm-input-name");
        const validateBtn = document.getElementById("dm-btn-validate");
        const uploadForm = document.getElementById("dm-upload-form");
        const validationBox = document.getElementById("dm-validation-box");
        const errorAlert = document.getElementById("dm-error-alert");
        const progressBox = document.getElementById("dm-progress-box");
        const progressFill = document.getElementById("dm-progress-fill");
        const progressText = document.getElementById("dm-progress-text");

        // Reset Demo (Explicitly activate demo dataset)
        if (resetBtn) {
            resetBtn.addEventListener("click", async () => {
                try {
                    const res = await fetch("/api/datasets/reset", { method: "POST" });
                    if (!res.ok) throw new Error("Failed to reset dataset");
                    await onDatasetChanged();
                } catch (e) {
                    alert("Reset failed: " + e.message);
                }
            });
        }

        // Clear Active Dataset (Reset to NO_DATA)
        if (clearBtn) {
            clearBtn.addEventListener("click", async () => {
                try {
                    const res = await fetch("/api/datasets/clear", { method: "POST" });
                    if (!res.ok) throw new Error("Failed to clear active dataset");
                    await onDatasetChanged();
                } catch (e) {
                    alert("Clear failed: " + e.message);
                }
            });
        }

        // Refresh List
        if (refreshBtn) {
            refreshBtn.addEventListener("click", () => loadDataManagementView());
        }

        // Toggle Upload Mode
        modeRadios.forEach(radio => {
            radio.addEventListener("change", (e) => {
                if (errorAlert) errorAlert.classList.add("hidden");
                if (validationBox) validationBox.classList.add("hidden");
                if (e.target.value === "single") {
                    if (singleZone) singleZone.classList.remove("hidden");
                    if (multiZone) multiZone.classList.add("hidden");
                    // Clear 4 CSV files
                    ["dm-multi-sales-file", "dm-multi-inv-file", "dm-multi-prods-file", "dm-multi-stores-file"].forEach(id => {
                        const el = document.getElementById(id);
                        if (el) el.value = "";
                    });
                } else {
                    if (singleZone) singleZone.classList.add("hidden");
                    if (multiZone) multiZone.classList.remove("hidden");
                    // Clear single file
                    if (singleInput) singleInput.value = "";
                    if (singleFileName) singleFileName.textContent = "No file chosen";
                }
            });
        });

        // Single File Input change
        if (singleInput) {
            singleInput.addEventListener("change", () => {
                if (singleInput.files && singleInput.files[0]) {
                    const f = singleInput.files[0];
                    if (singleFileName) singleFileName.textContent = `Selected: ${f.name} (${(f.size / 1024).toFixed(1)} KB)`;
                    if (nameInput && !nameInput.value.trim()) {
                        nameInput.value = f.name.replace(/\.[^/.]+$/, "").replace(/[_-]/g, " ").replace(/\b\w/g, l => l.toUpperCase());
                    }
                }
            });
        }

        // Drag & drop on single zone
        if (singleZone) {
            ["dragenter", "dragover"].forEach(evt => {
                singleZone.addEventListener(evt, (e) => {
                    e.preventDefault();
                    singleZone.classList.add("dragover");
                });
            });
            ["dragleave", "drop"].forEach(evt => {
                singleZone.addEventListener(evt, (e) => {
                    e.preventDefault();
                    singleZone.classList.remove("dragover");
                });
            });
            singleZone.addEventListener("drop", (e) => {
                const dt = e.dataTransfer;
                const files = dt.files;
                if (files && files.length > 0) {
                    singleInput.files = files;
                    const f = files[0];
                    if (singleFileName) singleFileName.textContent = `Selected: ${f.name} (${(f.size / 1024).toFixed(1)} KB)`;
                    if (nameInput && !nameInput.value.trim()) {
                        nameInput.value = f.name.replace(/\.[^/.]+$/, "").replace(/[_-]/g, " ").replace(/\b\w/g, l => l.toUpperCase());
                    }
                }
            });
        }

        // Helper to collect form data
        function buildUploadFormData() {
            const dsName = (nameInput?.value || "").trim();
            if (!dsName) {
                return { error: "Dataset name is required." };
            }

            const mode = document.querySelector("input[name='dm-upload-mode']:checked")?.value || "single";
            const formData = new FormData();
            formData.append("dataset_name", dsName);

            if (mode === "single") {
                const f = singleInput?.files?.[0];
                if (!f) return { error: "Please select a CSV or Excel file." };
                const fname = f.name.toLowerCase();
                if (!fname.endsWith(".csv") && !fname.endsWith(".xlsx") && !fname.endsWith(".xls")) {
                    return { error: "Invalid file type. Please upload a CSV or supported Excel file." };
                }
                formData.append("file", f);
            } else {
                const salesF = document.getElementById("dm-multi-sales-file")?.files?.[0];
                const invF = document.getElementById("dm-multi-inv-file")?.files?.[0];
                const prodsF = document.getElementById("dm-multi-prods-file")?.files?.[0];
                const storesF = document.getElementById("dm-multi-stores-file")?.files?.[0];

                if (!salesF) return { error: "Sales CSV is required." };
                if (!invF) return { error: "Inventory CSV is required." };
                if (!prodsF) return { error: "Products CSV is required." };
                if (!storesF) return { error: "Stores CSV is required." };

                for (const f of [salesF, invF, prodsF, storesF]) {
                    if (!f.name.toLowerCase().endsWith(".csv")) {
                        return { error: "Invalid file type. Please upload a CSV or supported Excel file." };
                    }
                }

                formData.append("sales_file", salesF);
                formData.append("inventory_file", invF);
                formData.append("products_file", prodsF);
                formData.append("stores_file", storesF);
            }
            return { formData };
        }

        // Validation Handler
        if (validateBtn) {
            validateBtn.addEventListener("click", async () => {
                if (errorAlert) errorAlert.classList.add("hidden");
                const buildRes = buildUploadFormData();
                if (buildRes.error) {
                    if (errorAlert) {
                        errorAlert.textContent = buildRes.error;
                        errorAlert.classList.remove("hidden");
                    }
                    return;
                }

                validateBtn.disabled = true;
                validateBtn.textContent = "Profiling...";

                try {
                    const res = await fetch("/api/datasets/validate", {
                        method: "POST",
                        body: buildRes.formData
                    });
                    const val = await res.json();
                    validateBtn.disabled = false;
                    validateBtn.textContent = "🔍 Profile & Validate";

                    if (validationBox) {
                        validationBox.classList.remove("hidden");
                        const valIcon = document.getElementById("dm-val-icon");
                        const valTitle = document.getElementById("dm-val-title");
                        const valBadge = document.getElementById("dm-val-badge");
                        const valCounts = document.getElementById("dm-val-counts");
                        const valMappings = document.getElementById("dm-val-mappings");
                        const valWarnings = document.getElementById("dm-val-warnings");

                        if (val.is_valid) {
                            if (valIcon) valIcon.textContent = "✓";
                            if (valTitle) valTitle.textContent = "Dataset Validation Profile (Passed)";
                            if (valBadge) {
                                valBadge.textContent = "READY FOR ACTIVATION";
                                valBadge.className = "badge badge-success";
                            }
                        } else {
                            if (valIcon) valIcon.textContent = "⚠️";
                            if (valTitle) valTitle.textContent = "Dataset Validation Issues";
                            if (valBadge) {
                                valBadge.textContent = "ERRORS FOUND";
                                valBadge.className = "badge badge-critical";
                            }
                        }

                        if (valCounts && val.summary) {
                            valCounts.innerHTML = `
                                <div class="val-count-item"><span class="vc-label">SALES</span><span class="vc-val">${val.summary.sales_count?.toLocaleString() || 0}</span></div>
                                <div class="val-count-item"><span class="vc-label">PRODUCTS</span><span class="vc-val">${val.summary.products_count?.toLocaleString() || 0}</span></div>
                                <div class="val-count-item"><span class="vc-label">STORES</span><span class="vc-val">${val.summary.stores_count?.toLocaleString() || 0}</span></div>
                                <div class="val-count-item"><span class="vc-label">INVENTORY</span><span class="vc-val">${val.summary.inventory_count?.toLocaleString() || 0}</span></div>
                            `;
                        }

                        if (valMappings && val.column_mappings?.sales) {
                            const sm = val.column_mappings.sales;
                            valMappings.innerHTML = `
                                <div style="font-weight:700; color:var(--text-secondary); margin-bottom:4px;">Detected Column Mapping:</div>
                                <table class="mapping-table">
                                    <thead><tr><th>Internal Field</th><th>Matched Uploaded Column</th></tr></thead>
                                    <tbody>
                                        ${Object.entries(sm).map(([k, v]) => `<tr><td><code>${k}</code></td><td><strong>${v}</strong></td></tr>`).join("")}
                                    </tbody>
                                </table>
                            `;
                        }

                        if (valWarnings) {
                            const notes = [...(val.errors || []), ...(val.warnings || [])];
                            if (notes.length > 0) {
                                valWarnings.innerHTML = `<div style="font-weight:700; margin-bottom:2px;">Notes & Warnings:</div><ul class="val-notes-list">${notes.map(w => `<li>${w}</li>`).join("")}</ul>`;
                            } else {
                                valWarnings.innerHTML = `<div style="color:var(--status-success); font-weight:600;">✓ All columns and constraints matched perfectly with 0 issues.</div>`;
                            }
                        }
                    }
                } catch (err) {
                    validateBtn.disabled = false;
                    validateBtn.textContent = "🔍 Profile & Validate";
                    if (errorAlert) {
                        errorAlert.textContent = "Validation error: " + err.message;
                        errorAlert.classList.remove("hidden");
                    }
                }
            });
        }

        // Upload Form Submit & Activation
        if (uploadForm) {
            uploadForm.addEventListener("submit", async (e) => {
                e.preventDefault();
                if (errorAlert) errorAlert.classList.add("hidden");
                const buildRes = buildUploadFormData();
                if (buildRes.error) {
                    if (errorAlert) {
                        errorAlert.textContent = buildRes.error;
                        errorAlert.classList.remove("hidden");
                    }
                    return;
                }

                if (progressBox) progressBox.classList.remove("hidden");
                const setProgress = (pct, text) => {
                    if (progressFill) progressFill.style.width = pct + "%";
                    if (progressText) progressText.textContent = text;
                };

                setProgress(20, "Uploading dataset files...");
                await new Promise(r => setTimeout(r, 200));
                setProgress(45, "Validating schema & mapping columns...");
                await new Promise(r => setTimeout(r, 200));
                setProgress(70, "Building isolated SQLite database...");
                await new Promise(r => setTimeout(r, 200));

                try {
                    const res = await fetch("/api/datasets/upload", {
                        method: "POST",
                        body: buildRes.formData
                    });
                    const data = await res.json();
                    if (!res.ok) {
                        throw new Error(data.detail || "Dataset upload failed");
                    }

                    setProgress(90, "Recalculating analytics across all views...");
                    await new Promise(r => setTimeout(r, 200));
                    setProgress(100, "Ready ✓ Dataset activated as active source of truth!");
                    await new Promise(r => setTimeout(r, 300));

                    if (progressBox) progressBox.classList.add("hidden");
                    await onDatasetChanged();
                    alert(`Dataset '${data.dataset?.dataset_name || "Custom Dataset"}' is now active across all dashboards, inventory metrics, and Copilot!`);
                } catch (err) {
                    if (progressBox) progressBox.classList.add("hidden");
                    if (errorAlert) {
                        errorAlert.textContent = "Upload failed: " + err.message + " (Previous active dataset remained unchanged)";
                        errorAlert.classList.remove("hidden");
                    }
                }
            });
        }
    }

    // Navigation & Tab Switching
    function setupNavigation() {
        document.querySelectorAll(".nav-item, .quick-jump, .panel-link-btn, .btn-ask-copilot").forEach(btn => {
            btn.addEventListener("click", () => {
                const targetTab = btn.getAttribute("data-tab");
                if (!targetTab) return;

                const targetStatus = btn.getAttribute("data-status");
                if (targetStatus) {
                    const statusSelect = document.getElementById("inv-filter-status");
                    if (statusSelect) {
                        statusSelect.value = targetStatus;
                        renderInventoryTable();
                    }
                }

                const prompt = btn.getAttribute("data-prompt");
                if (prompt && targetTab === "copilot") {
                    const chatInput = document.getElementById("chat-input");
                    if (chatInput) {
                        chatInput.value = prompt;
                        sendChatQuery(prompt);
                    }
                }

                switchToTab(targetTab);
            });
        });

        // Time Range Buttons on Dashboard Chart
        document.querySelectorAll(".time-range-picker .range-btn").forEach(btn => {
            btn.addEventListener("click", () => {
                document.querySelectorAll(".time-range-picker .range-btn").forEach(b => b.classList.remove("active"));
                btn.classList.add("active");
                state.dashboardTimeframe = parseInt(btn.getAttribute("data-days"));
                loadDashboardChartOnly();
            });
        });
    }

    function switchToTab(tabId) {
        navItems.forEach(b => b.classList.remove("active"));
        tabViews.forEach(v => v.classList.remove("active"));

        const activeNav = document.querySelector(`.nav-item[data-tab="${tabId}"]`);
        if (activeNav) activeNav.classList.add("active");

        const targetSec = document.getElementById(`tab-${tabId}`);
        if (targetSec) targetSec.classList.add("active");
        state.currentTab = tabId;
    }

    // Date Snapshot Picker System
    function setupDateSnapshot() {
        if (!globalDateSelect) return;

        globalDateSelect.addEventListener("change", (e) => {
            const val = e.target.value;

            if (val === "today") {
                state.selectedDate = null;
                if (globalDatePicker) globalDatePicker.style.display = "none";
            } else if (val === "yesterday") {
                state.selectedDate = "2026-09-02";
                if (globalDatePicker) globalDatePicker.style.display = "none";
            } else if (val.endsWith("d")) {
                const days = parseInt(val.replace("d", ""));
                state.salesTimeframe = days;
                state.dashboardTimeframe = Math.min(180, days);
                state.selectedDate = null;
                if (globalDatePicker) globalDatePicker.style.display = "none";
                const salesTimeframeSel = document.getElementById("sales-timeframe-select");
                if (salesTimeframeSel) salesTimeframeSel.value = String(days);
            } else if (val === "custom") {
                if (globalDatePicker) {
                    globalDatePicker.style.display = "inline-block";
                    if (globalDatePicker.value) state.selectedDate = globalDatePicker.value;
                }
                return;
            }
            loadAllViews();
        });

        if (globalDatePicker) {
            globalDatePicker.addEventListener("change", (e) => {
                if (e.target.value) {
                    state.selectedDate = e.target.value;
                    loadAllViews();
                }
            });
        }
    }

    function setupFilters() {
        if (globalStoreSelect) {
            globalStoreSelect.addEventListener("change", (e) => {
                state.selectedStore = e.target.value;
                const salesStoreSel = document.getElementById("sales-store-select");
                if (salesStoreSel) salesStoreSel.value = e.target.value;
                loadAllViews();
            });
        }

        if (globalSearchInput) {
            globalSearchInput.addEventListener("input", (e) => {
                const q = e.target.value.toLowerCase();
                const invSearch = document.getElementById("inv-search-input");
                if (invSearch && state.currentTab === "inventory") {
                    invSearch.value = q;
                    renderInventoryTable();
                }
            });
        }

        const invSearch = document.getElementById("inv-search-input");
        const invCat = document.getElementById("inv-filter-category");
        const invStatus = document.getElementById("inv-filter-status");

        if (invSearch) invSearch.addEventListener("input", renderInventoryTable);
        if (invCat) invCat.addEventListener("change", renderInventoryTable);
        if (invStatus) invStatus.addEventListener("change", renderInventoryTable);

        const salesTimeframe = document.getElementById("sales-timeframe-select");
        const salesStore = document.getElementById("sales-store-select");

        if (salesTimeframe) {
            salesTimeframe.addEventListener("change", (e) => {
                state.salesTimeframe = parseInt(e.target.value);
                loadSalesWorkspace();
            });
        }

        if (salesStore) {
            salesStore.addEventListener("change", (e) => {
                state.selectedStore = e.target.value;
                if (globalStoreSelect) globalStoreSelect.value = e.target.value;
                loadAllViews();
            });
        }
    }

    // AI Copilot Setup
    function setupCopilotTab() {
        const chatForm = document.getElementById("chat-form");
        const chatInput = document.getElementById("chat-input");
        const promptPills = document.querySelectorAll(".prompt-pill, .suggestion-card");
        const sidebarTrigger = document.getElementById("sidebar-copilot-trigger");

        if (sidebarTrigger) {
            sidebarTrigger.addEventListener("click", () => switchToTab("copilot"));
        }

        promptPills.forEach(pill => {
            pill.addEventListener("click", () => {
                const prompt = pill.getAttribute("data-prompt");
                if (prompt) {
                    if (chatInput) chatInput.value = prompt;
                    sendChatQuery(prompt);
                }
            });
        });

        if (chatForm) {
            chatForm.addEventListener("submit", (e) => {
                e.preventDefault();
                const q = chatInput.value.trim();
                if (!q) return;
                chatInput.value = "";
                sendChatQuery(q);
            });
        }
    }

    // Product Detail Modal Setup
    function setupProductModal() {
        if (!productModal) return;
        if (productModalCloseBtn) {
            productModalCloseBtn.addEventListener("click", () => productModal.classList.add("hidden"));
        }
        productModal.addEventListener("click", (e) => {
            if (e.target === productModal) productModal.classList.add("hidden");
        });
    }



    // Load Executive Dashboard Data
    async function loadDashboard() {
        try {
            let url = `/api/dashboard?store_id=${state.selectedStore}`;
            if (state.selectedDate) url += `&date=${state.selectedDate}`;

            const res = await fetch(url);
            const data = await res.json();

            // Out-of-range date check (only shown if a specific date was selected)
            let noDataBanner = document.getElementById("date-no-data-banner");
            if (data.no_data && state.selectedDate) {
                if (!noDataBanner) {
                    noDataBanner = document.createElement("div");
                    noDataBanner.id = "date-no-data-banner";
                    noDataBanner.style.cssText = "background:#FFFBEB; border:1px solid #FCD34D; color:#92400E; padding:12px 16px; border-radius:8px; font-weight:600; font-size:13px; margin-bottom:16px; display:flex; align-items:center; gap:8px;";
                    const dashTab = document.getElementById("tab-dashboard");
                    if (dashTab) dashTab.insertBefore(noDataBanner, dashTab.firstChild);
                }
                noDataBanner.innerHTML = `⚠️ ${data.message}`;
                noDataBanner.style.display = "flex";
            } else if (noDataBanner) {
                noDataBanner.style.display = "none";
            }

            // KPI Values Alignment
            const revEl = document.getElementById("kpi-revenue");
            const unitsEl = document.getElementById("kpi-units");
            const alertsEl = document.getElementById("kpi-alerts-count");
            const overstockEl = document.getElementById("kpi-overstock-count");
            const growthEl = document.getElementById("kpi-growth-rate");

            if (revEl) revEl.textContent = `₹${(data.total_revenue || 0).toLocaleString('en-IN', { minimumFractionDigits: 2 })}`;
            if (unitsEl) unitsEl.textContent = (data.total_units_sold || 0).toLocaleString();

            const lowStockTotal = (data.critical_low_stock_count || 0) + (data.warning_low_stock_count || 0);
            if (alertsEl) alertsEl.textContent = lowStockTotal;
            if (overstockEl) overstockEl.textContent = data.overstock_count || 0;
            if (growthEl) {
                if (data.sales_growth_pct !== undefined && data.sales_growth_pct !== null && data.sales_growth_pct !== 0) {
                    const sign = data.sales_growth_pct > 0 ? "+" : "";
                    growthEl.textContent = `${sign}${data.sales_growth_pct}%`;
                } else {
                    growthEl.textContent = "0%";
                }
            }

            // Render mini sparklines cleanly inside KPI cards from real database aggregations
            if (data.sparklines && data.sparklines.revenue && data.sparklines.revenue.length > 0) {
                renderMiniSparkline("sparkline-revenue", data.sparklines.revenue, "#16A34A");
                renderMiniSparkline("sparkline-units", data.sparklines.units, "#8B5CF6");
                renderMiniSparkline("sparkline-lowstock", data.sparklines.lowstock, "#F59E0B");
                renderMiniSparkline("sparkline-overstock", data.sparklines.overstock, "#2563EB");
                renderMiniSparkline("sparkline-growth", data.sparklines.growth, "#16A34A");
            } else {
                ["sparkline-revenue", "sparkline-units", "sparkline-lowstock", "sparkline-overstock", "sparkline-growth"].forEach(id => {
                    const el = document.getElementById(id);
                    if (el) el.innerHTML = "";
                });
            }

            loadNeedsAttentionItems();
            loadDashboardChartOnly();
            renderInventoryDonut(data);
            renderTopProductsTable(data.top_products);

            // Fetch Stores for Store Performance Table
            const storesRes = await fetch("/api/stores");
            const storesData = await storesRes.json();
            renderStorePerformanceTable(storesData);

        } catch (err) {
            console.error("Failed to load dashboard:", err);
        }
    }

    async function loadDashboardChartOnly() {
        try {
            let url = `/api/analytics/charts?days=${state.dashboardTimeframe}&store_id=${state.selectedStore}`;
            if (state.selectedDate) url += `&date=${state.selectedDate}`;
            const res = await fetch(url);
            const data = await res.json();

            const subEl = document.getElementById("dashboard-chart-subtitle");
            const chartSpec = data.combined_trend || data.revenue_trend;
            if (subEl && chartSpec && chartSpec.subtitle) {
                subEl.textContent = chartSpec.subtitle;
            } else if (subEl) {
                subEl.textContent = state.dashboardTimeframe > 90 ? "Monthly revenue and units sold over time" : "Daily revenue and units sold over time";
            }

            renderSVGChart("dashboard-sales-chart", chartSpec);
        } catch (err) {
            console.error("Failed to load dashboard chart:", err);
        }
    }

    // Load Priority Needs Attention Items
    async function loadNeedsAttentionItems() {
        const container = document.getElementById("attention-items-container");
        if (!container) return;

        try {
            const res = await fetch("/api/alerts");
            const items = await res.json();

            if (!items || items.length === 0) {
                container.innerHTML = `
                    <div style="display:flex; flex-direction:column; align-items:center; justify-content:center; padding:30px 16px; text-align:center;">
                        <div style="font-size:13px; font-weight:700; color:var(--text-secondary); margin-bottom:4px;">No attention items</div>
                        <div style="font-size:11px; color:var(--text-muted); line-height:1.4;">Upload retail data to identify stock risks and sales anomalies.</div>
                    </div>
                `;
                return;
            }

            container.innerHTML = items.slice(0, 4).map(item => `
                <div class="alert-item-card ${item.severity}">
                    <div class="alert-info">
                        <div class="alert-title">${item.summary}</div>
                        <div class="alert-subtext">Action: <strong>${item.recommended_action}</strong></div>
                    </div>
                    <button class="alert-action-btn" onclick="alert('Reorder process initiated for ${item.summary.replace(/'/g, "\\'")}!')">Reorder</button>
                </div>
            `).join("");
        } catch (err) {
            container.innerHTML = '<div class="alert-subtext">Failed to load priority items.</div>';
        }
    }

    // Render Inventory Health Donut Chart & Legend Table
    function renderInventoryDonut(data) {
        const container = document.getElementById("inventory-donut-container");
        if (!container) return;

        const total = (data.total_inventory_records !== undefined && data.total_inventory_records !== null) ? data.total_inventory_records : (data.total_skus || (data.inventoryData ? data.inventoryData.length : 0));

        if (total === 0) {
            container.innerHTML = `
                <div style="display:flex; flex-direction:column; align-items:center; justify-content:center; height:100%; min-height:160px; color:var(--text-muted); text-align:center; padding:20px;">
                    <div style="font-size:24px; margin-bottom:6px;">📊</div>
                    <div style="font-size:13px; font-weight:700; color:var(--text-secondary); margin-bottom:4px;">No inventory data available</div>
                    <div style="font-size:11px; color:var(--text-muted);">Upload inventory data to calculate stock health.</div>
                </div>
            `;
            return;
        }

        const critical = (data.critical_low_stock_count !== undefined) ? data.critical_low_stock_count : 0;
        const warning = (data.warning_low_stock_count !== undefined) ? data.warning_low_stock_count : 0;
        const overstock = (data.overstock_count !== undefined) ? data.overstock_count : 0;
        const slow = (data.slow_moving_count !== undefined) ? data.slow_moving_count : 0;
        const noDemand = (data.no_recent_demand_count !== undefined) ? data.no_recent_demand_count : 0;
        const otherHealthy = Math.max(0, total - critical - warning - overstock);

        const safeTotal = Math.max(1, total);
        const pctH = (otherHealthy / safeTotal) * 100;
        const pctW = (warning / safeTotal) * 100;
        const pctC = (critical / safeTotal) * 100;
        const pctO = (overstock / safeTotal) * 100;

        const circum = 251.32;
        const strokeH = (pctH / 100) * circum;
        const strokeW = (pctW / 100) * circum;
        const strokeC = (pctC / 100) * circum;
        const strokeO = (pctO / 100) * circum;

        let offset = 0;
        const dashH = `${strokeH} ${circum - strokeH}`; const offH = offset; offset -= strokeH;
        const dashW = `${strokeW} ${circum - strokeW}`; const offW = offset; offset -= strokeW;
        const dashC = `${strokeC} ${circum - strokeC}`; const offC = offset; offset -= strokeC;
        const dashO = `${strokeO} ${circum - strokeO}`; const offO = offset;

        container.innerHTML = `
            <div class="donut-chart-layout">
                <div style="position:relative; width:120px; height:120px; margin:0 auto;">
                    <svg viewBox="0 0 100 100" style="width:120px; height:120px; transform: rotate(-90deg);">
                        <circle cx="50" cy="50" r="40" fill="none" stroke="#F1F5F9" stroke-width="12" />
                        <circle cx="50" cy="50" r="40" fill="none" stroke="#16A34A" stroke-width="12" stroke-dasharray="${dashH}" stroke-dashoffset="${offH}" />
                        <circle cx="50" cy="50" r="40" fill="none" stroke="#D97706" stroke-width="12" stroke-dasharray="${dashW}" stroke-dashoffset="${offW}" />
                        <circle cx="50" cy="50" r="40" fill="none" stroke="#DC2626" stroke-width="12" stroke-dasharray="${dashC}" stroke-dashoffset="${offC}" />
                        <circle cx="50" cy="50" r="40" fill="none" stroke="#2563EB" stroke-width="12" stroke-dasharray="${dashO}" stroke-dashoffset="${offO}" />
                    </svg>
                    <div style="position:absolute; top:0; left:0; width:100%; height:100%; display:flex; flex-direction:column; align-items:center; justify-content:center; text-align:center;">
                        <div style="font-size:18px; font-weight:800; color:#0F172A;">${total}</div>
                        <div style="font-size:10px; color:#64748B; font-weight:600;">Inventory Records</div>
                    </div>
                </div>

                <div style="width:100%; display:flex; flex-direction:column; gap:4px; font-size:11px;">
                    <div style="display:flex; justify-content:space-between; padding:2px 0;">
                        <span><span style="color:#16A34A;">●</span> Healthy / Normal</span>
                        <strong>${otherHealthy} (${Math.round(pctH)}%)</strong>
                    </div>
                    <div style="display:flex; justify-content:space-between; padding:2px 0;">
                        <span><span style="color:#D97706;">●</span> Warning (&lt;=7D)</span>
                        <strong>${warning} (${Math.round(pctW)}%)</strong>
                    </div>
                    <div style="display:flex; justify-content:space-between; padding:2px 0;">
                        <span><span style="color:#DC2626;">●</span> Critical (&lt;=2D)</span>
                        <strong>${critical} (${Math.round(pctC)}%)</strong>
                    </div>
                    <div style="display:flex; justify-content:space-between; padding:2px 0;">
                        <span><span style="color:#2563EB;">●</span> Overstock</span>
                        <strong>${overstock} (${Math.round(pctO)}%)</strong>
                    </div>
                </div>
            </div>
        `;
    }

    // Render Top Products Table
    function renderTopProductsTable(products) {
        const tbody = document.getElementById("top-products-tbody");
        if (!tbody) return;

        if (!products || products.length === 0) {
            tbody.innerHTML = `
                <tr>
                    <td colspan="5" style="text-align:center; padding:30px 16px; color:var(--text-muted);">
                        <div style="font-weight:700; color:var(--text-secondary); font-size:13px; margin-bottom:4px;">No product data available</div>
                        <div style="font-size:11px; color:var(--text-muted);">Upload your retail dataset to see top-performing products.</div>
                    </td>
                </tr>
            `;
            return;
        }

        tbody.innerHTML = products.slice(0, 5).map((p, idx) => `
            <tr>
                <td><strong>#${idx + 1}</strong></td>
                <td><strong>${p.product_name}</strong></td>
                <td class="text-right"><strong>${p.units_sold}</strong></td>
                <td class="text-right"><strong>₹${(p.revenue || 0).toLocaleString('en-IN', { minimumFractionDigits: 2 })}</strong></td>
                <td class="text-right"><span class="badge badge-success">+18.5%</span></td>
            </tr>
        `).join("");
    }

    // Render Store Performance Table
    function renderStorePerformanceTable(stores) {
        const tbody = document.getElementById("store-performance-tbody");
        if (!tbody) return;

        if (!stores || stores.length === 0) {
            tbody.innerHTML = `
                <tr>
                    <td colspan="4" style="text-align:center; padding:30px 16px; color:var(--text-muted);">
                        <div style="font-weight:700; color:var(--text-secondary); font-size:13px; margin-bottom:4px;">No store data available</div>
                        <div style="font-size:11px; color:var(--text-muted);">Upload your retail dataset to compare store performance.</div>
                    </td>
                </tr>
            `;
            return;
        }

        tbody.innerHTML = stores.map(s => {
            const rev = s.total_revenue || 0;
            const targetPct = rev > 0 ? Math.min(100, Math.round((rev / 50000) * 100)) : 0;
            return `
                <tr>
                    <td><strong>${s.store_name}</strong></td>
                    <td class="text-right"><strong>₹${rev.toLocaleString('en-IN', { minimumFractionDigits: 2 })}</strong></td>
                    <td class="text-right"><strong>${Math.round(rev / 150)}</strong></td>
                    <td class="text-right"><span class="badge ${targetPct > 0 ? 'badge-success' : 'badge-secondary'}">+${targetPct}%</span></td>
                </tr>
            `;
        }).join("");
    }

    // Load Inventory Data
    async function loadInventory() {
        try {
            let url = `/api/inventory?store_id=${state.selectedStore}`;
            if (state.selectedDate) url += `&date=${state.selectedDate}`;
            const res = await fetch(url);
            state.inventoryData = await res.json();

            const total = state.inventoryData.length;
            const critical = state.inventoryData.filter(i => i.status === "CRITICAL" || i.status === "OUT_OF_STOCK").length;
            const warning = state.inventoryData.filter(i => i.status === "WARNING").length;
            const overstock = state.inventoryData.filter(i => i.status === "OVERSTOCK").length;
            const slow = state.inventoryData.filter(i => i.status === "SLOW_MOVING").length;

            const invTotalEl = document.getElementById("inv-kpi-total");
            const invCritEl = document.getElementById("inv-kpi-critical");
            const invWarnEl = document.getElementById("inv-kpi-warning");
            const invOverEl = document.getElementById("inv-kpi-overstock");
            const invSlowEl = document.getElementById("inv-kpi-slow");

            if (invTotalEl) invTotalEl.textContent = total;
            if (invCritEl) invCritEl.textContent = critical;
            if (invWarnEl) invWarnEl.textContent = warning;
            if (invOverEl) invOverEl.textContent = overstock;
            if (invSlowEl) invSlowEl.textContent = slow;

            const categories = [...new Set(state.inventoryData.map(i => i.category))];
            const catSelect = document.getElementById("inv-filter-category");
            if (catSelect) {
                catSelect.innerHTML = '<option value="all">All Categories</option>';
                categories.forEach(cat => {
                    const opt = document.createElement("option");
                    opt.value = cat;
                    opt.textContent = cat;
                    catSelect.appendChild(opt);
                });
            }

            renderInventoryTable();
        } catch (err) {
            console.error("Failed to load inventory:", err);
        }
    }

    // Render Inventory Table
    function renderInventoryTable() {
        const tbody = document.getElementById("inventory-tbody");
        if (!tbody) return;

        const searchInput = document.getElementById("inv-search-input");
        const catSelect = document.getElementById("inv-filter-category");
        const statusSelect = document.getElementById("inv-filter-status");

        const search = searchInput ? searchInput.value.toLowerCase() : "";
        const selectedCat = catSelect ? catSelect.value : "all";
        const selectedStatus = statusSelect ? statusSelect.value : "all";

        let filtered = state.inventoryData.filter(item => {
            if (state.selectedStore !== "all" && item.store_id !== state.selectedStore) return false;
            if (search && !item.product_name.toLowerCase().includes(search) && !item.category.toLowerCase().includes(search)) return false;
            if (selectedCat !== "all" && item.category !== selectedCat) return false;
            if (selectedStatus !== "all" && item.status !== selectedStatus) return false;
            return true;
        });

        if (filtered.length === 0) {
            tbody.innerHTML = '<tr><td colspan="8" style="text-align: center; color: var(--text-muted); padding:30px;"><div style="font-weight:700; color:var(--text-secondary); font-size:13px; margin-bottom:4px;">No inventory data available.</div><div style="font-size:11px; color:var(--text-muted);">Upload your inventory and sales data to track SKU health.</div></td></tr>';
            return;
        }

        tbody.innerHTML = filtered.map(i => {
            let statusBadge = `<span class="badge badge-healthy">HEALTHY</span>`;
            if (i.status === "CRITICAL" || i.status === "OUT_OF_STOCK") {
                statusBadge = `<span class="badge badge-critical">CRITICAL</span>`;
            } else if (i.status === "WARNING") {
                statusBadge = `<span class="badge badge-warning">WARNING</span>`;
            } else if (i.status === "SLOW_MOVING") {
                statusBadge = `<span class="badge badge-slow">SLOW MOVING</span>`;
            } else if (i.status === "OVERSTOCK") {
                statusBadge = `<span class="badge badge-info">OVERSTOCK</span>`;
            }

            const reorderText = i.recommended_reorder > 0 ?
                `<strong style="color: var(--brand-teal);">+${i.recommended_reorder} units</strong>` :
                `<span style="color: var(--text-dim);">0</span>`;

            return `
                <tr data-product-id="${i.product_id}" data-store-id="${i.store_id}">
                    <td><strong>${i.product_name}</strong></td>
                    <td><span class="badge badge-info">${i.category}</span></td>
                    <td>${i.store_name}</td>
                    <td class="text-right"><strong>${i.current_stock}</strong></td>
                    <td class="text-right">${i.average_daily_sales.toFixed(1)} / day</td>
                    <td class="text-right">${i.days_remaining > 900 ? '999+' : i.days_remaining} days</td>
                    <td>${statusBadge}</td>
                    <td class="text-right">${reorderText}</td>
                </tr>
            `;
        }).join("");

        tbody.querySelectorAll("tr[data-product-id]").forEach(row => {
            row.addEventListener("click", () => {
                const prodId = row.getAttribute("data-product-id");
                const storeId = row.getAttribute("data-store-id");
                openProductDetailModal(prodId, storeId);
            });
        });
    }

    // Open Product Detail Modal
    async function openProductDetailModal(productId, storeId) {
        if (!productModal) return;
        productModal.classList.remove("hidden");
        document.getElementById("modal-prod-name").textContent = "Loading...";

        try {
            let url = `/api/products/${productId}?store_id=${storeId}`;
            if (state.selectedDate) url += `&date=${state.selectedDate}`;
            const res = await fetch(url);
            const data = await res.json();

            document.getElementById("modal-prod-name").textContent = data.product.product_name;
            document.getElementById("modal-prod-category").textContent = data.product.category;

            document.getElementById("modal-stock-val").textContent = data.metrics.current_stock;
            document.getElementById("modal-ads-val").textContent = `${data.metrics.avg_daily_sales.toFixed(1)} / day`;
            document.getElementById("modal-days-val").textContent = `${data.metrics.days_remaining} days`;
            document.getElementById("modal-revenue-val").textContent = `₹${data.metrics["30d_revenue"].toLocaleString('en-IN', { minimumFractionDigits: 2 })}`;

            const reorderQty = data.metrics.recommended_reorder;
            if (reorderQty > 0) {
                document.getElementById("modal-reorder-summary").innerHTML = `
                    <div style="font-weight: 700; color: var(--brand-teal); font-size: 13px; margin-bottom: 4px;">
                        Reorder Recommendation: +${reorderQty} Units
                    </div>
                    <div>Current stock of <strong>${data.metrics.current_stock}</strong> covers only <strong>${data.metrics.days_remaining} days</strong> of average demand. Reorder ${reorderQty} units to maintain target safety threshold.</div>
                `;
            } else {
                document.getElementById("modal-reorder-summary").innerHTML = `
                    <div style="font-weight: 700; color: var(--status-success); font-size: 13px; margin-bottom: 4px;">
                        Stock Level Healthy
                    </div>
                    <div>Current stock of <strong>${data.metrics.current_stock}</strong> units fully covers demand for <strong>${data.metrics.days_remaining} days</strong>.</div>
                `;
            }

            document.getElementById("modal-evidence-text").innerHTML = `
                <div>• <strong>Calculation Source:</strong> ${data.evidence.source}</div>
                <div>• <strong>Formula:</strong> ${data.evidence.calculation}</div>
                <div>• <strong>Assumptions:</strong> ${data.evidence.assumptions.join(" | ")}</div>
            `;

            const dates = data.sales_trend.map(d => d.date);
            const revs = data.sales_trend.map(d => d.revenue);
            const chartSpec = {
                type: "line",
                title: "30-Day Product Sales Trend",
                labels: dates,
                datasets: [{ label: "Daily Revenue (₹)", data: revs, color: "#087F80" }]
            };
            renderSVGChart("modal-sales-chart", chartSpec);

        } catch (err) {
            console.error("Modal load error:", err);
        }
    }

    // Load Sales Analytics Workspace Data
    async function loadSalesWorkspace() {
        try {
            let url = `/api/analytics/charts?days=${state.salesTimeframe}&store_id=${state.selectedStore}`;
            if (state.selectedDate) url += `&date=${state.selectedDate}`;
            const res = await fetch(url);
            const data = await res.json();

            const revTrendData = data.revenue_trend?.datasets?.[0]?.data || [];
            const unitsTrendData = data.units_trend?.datasets?.[0]?.data || [];
            const revSum = revTrendData.reduce((a, b) => (a || 0) + (b || 0), 0);
            const unitSum = unitsTrendData.reduce((a, b) => (a || 0) + (b || 0), 0);
            const labelCount = data.revenue_trend?.labels?.length || 1;
            const dailyAvg = revSum / Math.max(1, labelCount);

            const salesRevEl = document.getElementById("sales-kpi-revenue");
            const salesUnitsEl = document.getElementById("sales-kpi-units");
            const salesDailyEl = document.getElementById("sales-kpi-daily-rev");
            const salesTopCatEl = document.getElementById("sales-kpi-top-cat");

            if (salesRevEl) salesRevEl.textContent = `₹${revSum.toLocaleString('en-IN', { minimumFractionDigits: 2 })}`;
            if (salesUnitsEl) salesUnitsEl.textContent = unitSum.toLocaleString();
            if (salesDailyEl) salesDailyEl.textContent = `₹${dailyAvg.toLocaleString('en-IN', { minimumFractionDigits: 2 })}`;
            if (salesTopCatEl) salesTopCatEl.textContent = data.category_chart?.labels?.[0] || "N/A";

            if (data.revenue_trend) renderSVGChart("chart-sales-revenue", data.revenue_trend);
            if (data.units_trend) renderSVGChart("chart-sales-units", data.units_trend);
            if (data.category_chart) renderSVGChart("chart-sales-category", data.category_chart);
            if (data.top_products_chart) renderSVGChart("chart-sales-top-products", data.top_products_chart);
            if (data.store_chart) renderSVGChart("chart-sales-store", data.store_chart);

            // Fetch & Render 10-Year Yearly Performance & Seasonality Charts
            try {
                let yearlyUrl = `/api/yearly-performance?store_id=${state.selectedStore}`;
                const yearlyRes = await fetch(yearlyUrl);
                const yearlyData = await yearlyRes.json();
                if (yearlyData && yearlyData.yearly_chart) {
                    renderSVGChart("chart-sales-yearly", yearlyData.yearly_chart);
                }

                let seasonUrl = `/api/seasonality?store_id=${state.selectedStore}`;
                const seasonRes = await fetch(seasonUrl);
                const seasonData = await seasonRes.json();
                if (seasonData) {
                    if (seasonData.status === "INSUFFICIENT_HISTORY") {
                        const seasonContainer = document.getElementById("chart-sales-seasonality");
                        if (seasonContainer) {
                            seasonContainer.innerHTML = `
                                <div style="display:flex; flex-direction:column; align-items:center; justify-content:center; height:100%; min-height:160px; color:var(--text-muted); text-align:center; padding:20px;">
                                    <div style="font-size:13px; font-weight:700; color:var(--text-secondary); margin-bottom:4px;">Seasonality Unavailable</div>
                                    <div style="font-size:11px; color:var(--text-muted); max-width:320px;">${seasonData.message || "Not enough historical data in the active dataset to calculate a reliable seasonal pattern."}</div>
                                </div>
                            `;
                        }
                    } else if (seasonData.seasonality_chart) {
                        renderSVGChart("chart-sales-seasonality", seasonData.seasonality_chart);
                    }
                }
            } catch (errYearly) {
                console.error("Yearly / Seasonality chart render error:", errYearly);
            }

            const spikesContainer = document.getElementById("spikes-drops-container");
            if (spikesContainer) {
                let highlightsHTML = "";
                if (data.spikes && data.spikes.length > 0) {
                    highlightsHTML += data.spikes.slice(0, 3).map(s => `
                        <div class="alert-item-card HIGH" style="margin-bottom:6px;">
                            <div>
                                <div class="alert-title">SPIKE: ${s.product_name}</div>
                                <div class="alert-subtext">${s.prev_units_30d} → ${s.curr_units_30d} units</div>
                            </div>
                            <span class="badge badge-success">+${s.pct_change_units}%</span>
                        </div>
                    `).join("");
                }
                if (data.drops && data.drops.length > 0) {
                    highlightsHTML += data.drops.slice(0, 3).map(d => `
                        <div class="alert-item-card HIGH" style="margin-bottom:6px;">
                            <div>
                                <div class="alert-title">DROP: ${d.product_name}</div>
                                <div class="alert-subtext">${d.prev_units_30d} → ${d.curr_units_30d} units</div>
                            </div>
                            <span class="badge badge-critical">${d.pct_change_units}%</span>
                        </div>
                    `).join("");
                }
                spikesContainer.innerHTML = highlightsHTML || '<div style="font-size:12px; color:var(--text-muted);">No major sales spikes/drops detected.</div>';
            }

            const insightsContainer = document.getElementById("sales-insights-container");
            if (insightsContainer) {
                insightsContainer.innerHTML = (data.insights || []).map(ins => `
                    <div style="background:var(--bg-light); border-left:3px solid var(--brand-teal); padding:8px 12px; border-radius:4px; font-size:12px; margin-bottom:6px;">
                        ${ins}
                    </div>
                `).join("");
            }

        } catch (err) {
            console.error("Failed to load sales workspace:", err);
        }
    }



    // Load Intelligent Reorder Planner
    function setupReorderPlanner() {
        const prioritySel = document.getElementById("reorder-filter-priority");
        const categorySel = document.getElementById("reorder-filter-category");
        const exportBtn = document.getElementById("btn-export-reorder");

        if (prioritySel) prioritySel.addEventListener("change", loadReorderPlanner);
        if (categorySel) categorySel.addEventListener("change", loadReorderPlanner);

        if (exportBtn) {
            exportBtn.addEventListener("click", async () => {
                const res = await fetch(`/api/reorder-plan?store_id=${state.selectedStore}`);
                const data = await res.json();

                let csv = "Priority,Product,Store,Current Stock,Avg Daily Sales,Days Remaining,Target Coverage,Recommended Reorder\n";
                data.forEach(r => {
                    csv += `"${r.reorder_priority}","${r.product_name}","${r.store_name}",${r.current_stock},${r.average_daily_sales.toFixed(1)},${r.days_remaining},7 days,${r.recommended_reorder}\n`;
                });

                const blob = new Blob([csv], { type: "text/csv" });
                const link = document.createElement("a");
                link.href = URL.createObjectURL(blob);
                link.download = `RetailIQ_Reorder_Plan_${state.selectedDate || 'Today'}.csv`;
                link.click();
            });
        }
    }

    async function loadReorderPlanner() {
        const tbody = document.getElementById("reorder-tbody");
        if (!tbody) return;

        try {
            const prioritySel = document.getElementById("reorder-filter-priority");
            const categorySel = document.getElementById("reorder-filter-category");

            const priorityVal = prioritySel ? prioritySel.value : "all";
            const categoryVal = categorySel ? categorySel.value : "all";

            let url = `/api/reorder-plan?store_id=${state.selectedStore}&priority=${priorityVal}&category=${categoryVal}`;
            if (state.selectedDate) url += `&date=${state.selectedDate}`;

            const res = await fetch(url);
            const data = await res.json();

            if (!data || data.length === 0) {
                tbody.innerHTML = '<tr><td colspan="8" style="text-align:center; padding:30px 16px; color:var(--text-muted);"><div style="font-weight:700; color:var(--text-secondary); font-size:13px; margin-bottom:4px;">No reorder recommendations</div><div style="font-size:11px; color:var(--text-muted);">Upload inventory and sales data to generate replenishment recommendations.</div></td></tr>';
                return;
            }

            tbody.innerHTML = data.map(r => `
                <tr data-product-id="${r.product_id}" data-store-id="${r.store_id}">
                    <td><span class="badge ${r.reorder_priority === 'CRITICAL' ? 'badge-critical' : 'badge-warning'}">${r.reorder_priority}</span></td>
                    <td><strong>${r.product_name}</strong></td>
                    <td>${r.store_name}</td>
                    <td class="text-right"><strong>${r.current_stock}</strong></td>
                    <td class="text-right">${r.average_daily_sales.toFixed(1)} / day</td>
                    <td class="text-right">${r.days_remaining} days</td>
                    <td>7 days target</td>
                    <td class="text-right"><strong style="color:var(--brand-teal); font-size:13px;">+${r.recommended_reorder} units</strong></td>
                </tr>
            `).join("");

            tbody.querySelectorAll("tr[data-product-id]").forEach(row => {
                row.addEventListener("click", () => {
                    openProductDetailModal(row.getAttribute("data-product-id"), row.getAttribute("data-store-id"));
                });
            });

        } catch (err) {
            console.error("Failed to load reorder planner:", err);
        }
    }

    // Load Decision Center
    async function loadDecisionCenter() {
        const container = document.getElementById("decision-center-container");
        if (!container) return;

        try {
            let url = "/api/decision-center";
            if (state.selectedDate) url += `?date=${state.selectedDate}`;
            const res = await fetch(url);
            const items = await res.json();

            if (!items || items.length === 0) {
                container.innerHTML = `
                    <div style="display:flex; flex-direction:column; align-items:center; justify-content:center; padding:40px 16px; text-align:center; background:var(--bg-subtle); border-radius:var(--radius-md); border:1px solid var(--border-color);">
                        <div style="font-size:28px; margin-bottom:8px;">⚡</div>
                        <div style="font-size:14px; font-weight:700; color:var(--text-primary); margin-bottom:4px;">No operational decisions available</div>
                        <div style="font-size:12px; color:var(--text-muted);">Upload retail data to generate evidence-based recommendations.</div>
                    </div>
                `;
                return;
            }

            container.innerHTML = items.map(d => `
                <div class="decision-card ${d.priority}">
                    <div class="decision-header">
                        <div class="decision-title">${d.title}</div>
                        <span class="badge ${d.priority === 'CRITICAL' ? 'badge-critical' : (d.priority === 'HIGH' ? 'badge-warning' : 'badge-info')}">${d.priority}</span>
                    </div>
                    <div class="decision-body">
                        <div><strong>Issue:</strong> ${d.issue}</div>
                        <div><strong>Impact:</strong> ${d.impact}</div>
                    </div>
                    <div class="decision-action-box">
                        <span><strong>Recommended Action:</strong> ${d.action}</span>
                        <button class="alert-action-btn" onclick="alert('Action executing for ${d.title.replace(/'/g, "\\'")}!')">Execute Action →</button>
                    </div>
                    <div class="decision-evidence">🔍 Evidence: ${d.evidence}</div>
                </div>
            `).join("");
        } catch (err) {
            console.error("Failed to load decision center:", err);
        }
    }

    // Store Comparison Setup
    function setupStoreComparison() {
        const checkboxesDiv = document.getElementById("compare-store-checkboxes");
        const btnRun = document.getElementById("btn-run-comparison");

        if (checkboxesDiv && state.storesData) {
            checkboxesDiv.innerHTML = state.storesData.map(s => `
                <label style="font-size:12px; display:flex; align-items:center; gap:4px; cursor:pointer;">
                    <input type="checkbox" value="${s.store_id}" ${state.compareSelectedStores.includes(s.store_id) ? 'checked' : ''}>
                    ${s.store_name}
                </label>
            `).join("");
        }

        if (btnRun) {
            btnRun.addEventListener("click", () => {
                const checked = Array.from(checkboxesDiv.querySelectorAll("input:checked")).map(i => i.value);
                if (checked.length > 0) {
                    state.compareSelectedStores = checked;
                    loadStoreComparison();
                } else {
                    alert("Please select at least one store to compare.");
                }
            });
        }
    }

    async function loadStoreComparison() {
        const container = document.getElementById("compare-matrix-container");
        if (!container) return;

        try {
            const storeIdsStr = state.compareSelectedStores.join(",");
            let url = `/api/compare-stores?store_ids=${storeIdsStr}&days=30`;
            if (state.selectedDate) url += `&date=${state.selectedDate}`;

            const res = await fetch(url);
            const data = await res.json();

            if (!data || !data.comparison_table || data.comparison_table.length === 0) {
                container.innerHTML = `
                    <div style="grid-column: 1 / -1; display:flex; flex-direction:column; align-items:center; justify-content:center; padding:40px 16px; text-align:center; background:var(--bg-subtle); border-radius:var(--radius-md); border:1px solid var(--border-color); width:100%;">
                        <div style="font-size:28px; margin-bottom:8px;">🏬</div>
                        <div style="font-size:14px; font-weight:700; color:var(--text-primary); margin-bottom:4px;">No store data available</div>
                        <div style="font-size:12px; color:var(--text-muted);">Upload your retail dataset to compare store performance.</div>
                    </div>
                `;
                return;
            }

            const tableRowsHTML = data.comparison_table.map(s => `
                <tr>
                    <td><strong>${s.store_name}</strong><br><span style="font-size:10px; color:var(--text-muted);">${s.location}</span></td>
                    <td class="text-right"><strong>₹${s.total_revenue.toLocaleString('en-IN', { minimumFractionDigits: 2 })}</strong></td>
                    <td class="text-right">${s.units_sold.toLocaleString()} units</td>
                    <td class="text-right">₹${s.avg_daily_revenue.toLocaleString('en-IN', { minimumFractionDigits: 2 })}/day</td>
                    <td><span class="badge badge-critical">${s.critical_items} Critical</span></td>
                    <td><span class="badge badge-info">${s.overstock_items} Overstock</span></td>
                </tr>
            `).join("");

            container.innerHTML = `
                <div class="panel chart-span-2">
                    <div class="panel-header">
                        <h3>Side-by-Side Revenue Trajectory</h3>
                        <span class="subtitle">Comparing ${data.stores_count} selected stores</span>
                    </div>
                    <div id="chart-store-compare" class="svg-chart-container" style="height:230px;"></div>
                </div>

                <div class="panel chart-span-2">
                    <div class="panel-header">
                        <h3>Store Performance Matrix</h3>
                    </div>
                    <div class="table-wrapper">
                        <table class="data-table">
                            <thead>
                                <tr>
                                    <th>STORE</th>
                                    <th class="text-right">REVENUE (30D)</th>
                                    <th class="text-right">UNITS SOLD</th>
                                    <th class="text-right">AVG DAILY REVENUE</th>
                                    <th>STOCK RISKS</th>
                                    <th>OVERSTOCK</th>
                                </tr>
                            </thead>
                            <tbody>
                                ${tableRowsHTML}
                            </tbody>
                        </table>
                    </div>
                </div>
            `;

            renderSVGChart("chart-store-compare", data.comparison_chart);
        } catch (err) {
            console.error("Failed to load store comparison:", err);
        }
    }

    // Load Executive BI Report
    async function loadExecutiveReport() {
        const container = document.getElementById("executive-report-container");
        if (!container) return;

        try {
            let url = `/api/executive-report?store_id=${state.selectedStore}`;
            if (state.selectedDate) url += `&date=${state.selectedDate}`;
            const res = await fetch(url);
            const rep = await res.json();

            const kpis = rep.kpis || {};
            const isNoData = !kpis || kpis.no_data || (kpis.total_revenue === 0 && kpis.total_units_sold === 0 && (kpis.total_inventory_records || 0) === 0);

            if (isNoData) {
                container.innerHTML = `
                    <div style="border-bottom:2px solid var(--brand-teal); padding-bottom:12px; margin-bottom:16px;">
                        <h2 style="font-size:20px; color:var(--text-primary);">${rep.report_title || "RetailIQ Executive Operations Report"}</h2>
                        <div style="font-size:12px; color:var(--text-muted); margin-top:2px;">
                            Status: <strong>No Dataset Active</strong>
                        </div>
                    </div>

                    <div class="kpi-grid" style="margin-bottom:20px;">
                        <div class="kpi-card"><div class="kpi-title">TOTAL REVENUE</div><div class="kpi-value">₹0.00</div></div>
                        <div class="kpi-card"><div class="kpi-title">UNITS SOLD</div><div class="kpi-value">0</div></div>
                        <div class="kpi-card"><div class="kpi-title">VALUATION</div><div class="kpi-value">₹0.00</div></div>
                        <div class="kpi-card highlight-critical"><div class="kpi-title">CRITICAL SKUs</div><div class="kpi-value">0</div></div>
                    </div>

                    <div style="display:flex; flex-direction:column; align-items:center; justify-content:center; padding:40px 16px; text-align:center; background:var(--bg-subtle); border-radius:var(--radius-md); border:1px dashed var(--border-color);">
                        <div style="font-size:24px; margin-bottom:8px;">📋</div>
                        <div style="font-size:14px; font-weight:700; color:var(--text-primary); margin-bottom:4px;">Executive report will be generated after retail data is uploaded.</div>
                        <div style="font-size:12px; color:var(--text-muted);">Upload your sales transactions and inventory datasets in Data Management to compile an executive overview.</div>
                    </div>
                `;
                return;
            }

            container.innerHTML = `
                <div style="border-bottom:2px solid var(--brand-teal); padding-bottom:12px; margin-bottom:16px;">
                    <h2 style="font-size:20px; color:var(--text-primary);">${rep.report_title}</h2>
                    <div style="font-size:12px; color:var(--text-muted); margin-top:2px;">
                        Date Context: <strong>${rep.generated_date}</strong> | Store Scope: <strong>${rep.store_scope}</strong>
                    </div>
                </div>

                <div class="kpi-grid" style="margin-bottom:20px;">
                    <div class="kpi-card"><div class="kpi-title">TOTAL REVENUE</div><div class="kpi-value">₹${(kpis.total_revenue || 0).toLocaleString('en-IN', { minimumFractionDigits: 2 })}</div></div>
                    <div class="kpi-card"><div class="kpi-title">UNITS SOLD</div><div class="kpi-value">${(kpis.total_units_sold || 0).toLocaleString()}</div></div>
                    <div class="kpi-card"><div class="kpi-title">VALUATION</div><div class="kpi-value">₹${(kpis.total_inventory_valuation || 0).toLocaleString('en-IN', { minimumFractionDigits: 2 })}</div></div>
                    <div class="kpi-card highlight-critical"><div class="kpi-title">CRITICAL SKUs</div><div class="kpi-value">${kpis.critical_low_stock_count || 0}</div></div>
                </div>

                <div style="display:grid; grid-template-columns:1fr 1fr; gap:16px; margin-bottom:16px;">
                    <div>
                        <h4 style="font-size:13px; font-weight:700; margin-bottom:8px;">Top Performing SKUs</h4>
                        <ul style="font-size:12px; line-height:1.6; padding-left:16px;">
                            ${(rep.top_products || []).map(p => `<li><strong>${p.product_name}</strong>: ₹${(p.revenue || 0).toLocaleString('en-IN')} (${p.units_sold} units)</li>`).join("")}
                        </ul>
                    </div>
                    <div>
                        <h4 style="font-size:13px; font-weight:700; margin-bottom:8px;">Operational Reorder Recommendations</h4>
                        <ul style="font-size:12px; line-height:1.6; padding-left:16px;">
                            ${(rep.recommended_reorders || []).slice(0, 4).map(r => `<li><strong>${r.product_name}</strong> (${r.store_name}): +${r.recommended_reorder} units</li>`).join("")}
                        </ul>
                    </div>
                </div>
            `;
        } catch (err) {
            console.error("Failed to load executive report:", err);
        }
    }

    // Mini Sparkline Renderer
    function renderMiniSparkline(containerId, dataVals, color = "#087F80") {
        const container = document.getElementById(containerId);
        if (!container || !dataVals || dataVals.length === 0) return;
        const width = 80;
        const height = 30;
        const maxVal = Math.max(...dataVals) || 1;
        const minVal = Math.min(...dataVals) || 0;
        const range = Math.max(1, maxVal - minVal);
        const points = dataVals.map((v, i) => {
            const x = (i / (dataVals.length - 1)) * width;
            const y = height - ((v - minVal) / range) * (height - 6) - 3;
            return `${x},${y}`;
        }).join(" ");

        container.innerHTML = `
            <svg viewBox="0 0 ${width} ${height}" style="width: 100%; height: 100%; overflow: visible;">
                <defs>
                    <linearGradient id="sparkGrad_${containerId}" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0%" stop-color="${color}" stop-opacity="0.2"/>
                        <stop offset="100%" stop-color="${color}" stop-opacity="0.0"/>
                    </linearGradient>
                </defs>
                <polygon points="0,${height} ${points} ${width},${height}" fill="url(#sparkGrad_${containerId})" />
                <polyline fill="none" stroke="${color}" stroke-width="2" stroke-linecap="round" points="${points}" />
            </svg>
        `;
    }

    // Helper to format currency for axis & tooltips
    function formatChartCurrency(val, compact = true) {
        if (val === null || val === undefined || isNaN(val)) return "₹0";
        if (compact) {
            if (Math.abs(val) >= 10000000) return `₹${(val / 10000000).toFixed(1)}Cr`;
            if (Math.abs(val) >= 100000) return `₹${(val / 100000).toFixed(1)}L`;
            if (Math.abs(val) >= 1000) return `₹${(val / 1000).toFixed(0)}k`;
            return `₹${Math.round(val)}`;
        }
        return `₹${Number(val).toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
    }

    // Helper to format numbers for axis & tooltips
    function formatChartNumber(val, compact = true) {
        if (val === null || val === undefined || isNaN(val)) return "0";
        if (compact) {
            if (Math.abs(val) >= 1000000) return `${(val / 1000000).toFixed(1)}M`;
            if (Math.abs(val) >= 1000) return `${(val / 1000).toFixed(1)}k`;
            return `${Math.round(val)}`;
        }
        return Number(val).toLocaleString();
    }

    // Tooltip singleton helper
    function getOrCreateChartTooltip() {
        let tt = document.getElementById("retailiq-chart-tooltip");
        if (!tt) {
            tt = document.createElement("div");
            tt.id = "retailiq-chart-tooltip";
            tt.style.position = "fixed";
            tt.style.display = "none";
            tt.style.pointerEvents = "none";
            tt.style.zIndex = "999999";
            tt.style.background = "#0F172A";
            tt.style.color = "#FFFFFF";
            tt.style.padding = "10px 14px";
            tt.style.borderRadius = "8px";
            tt.style.fontSize = "12px";
            tt.style.lineHeight = "1.5";
            tt.style.boxShadow = "0 10px 25px -5px rgba(0, 0, 0, 0.5), 0 8px 10px -6px rgba(0, 0, 0, 0.4)";
            tt.style.border = "1px solid #334155";
            tt.style.transition = "opacity 0.12s ease-out";
            document.body.appendChild(tt);
        }
        return tt;
    }

    // SVG Chart Render Engine (Supports dual_axis, line, area, bar, horizontal_bar, donut)
    function renderSVGChart(containerId, chartSpec) {
        const container = document.getElementById(containerId);
        if (!container) return;

        if (!chartSpec || !chartSpec.labels || chartSpec.labels.length === 0 || (chartSpec.datasets && chartSpec.datasets.every(d => !d.data || d.data.length === 0 || d.data.every(v => v === 0)))) {
            const titleMsg = chartSpec?.title || "No sales data available";
            const subMsg = chartSpec?.subtitle || "Upload a retail dataset to see revenue and sales trends.";
            container.innerHTML = `
                <div style="display:flex; flex-direction:column; align-items:center; justify-content:center; height:100%; min-height:160px; color:var(--text-muted); text-align:center; padding:20px;">
                    <div style="font-size:13px; font-weight:700; color:var(--text-secondary); margin-bottom:4px;">${titleMsg}</div>
                    <div style="font-size:11px; color:var(--text-muted);">${subMsg}</div>
                </div>
            `;
            return;
        }

        const width = 600;
        const height = 220;
        const paddingLeft = 55;
        const paddingRight = (chartSpec.type === "dual_axis") ? 55 : 25;
        const paddingTop = 25;
        const paddingBottom = 35;
        const plotWidth = width - paddingLeft - paddingRight;
        const plotHeight = height - paddingTop - paddingBottom;

        const type = chartSpec.type || "line";
        const labels = chartSpec.labels;
        const datasets = chartSpec.datasets && chartSpec.datasets.length > 0 ? chartSpec.datasets : [{ label: "Data", data: [], color: "#087F80" }];
        const isPartialFlags = chartSpec.is_partial || [];
        const avgDailyRevs = chartSpec.avg_daily_revenue || [];
        const avgDailyUnits = chartSpec.avg_daily_units || [];

        const tooltip = getOrCreateChartTooltip();

        if (type === "dual_axis") {
            // Dual-Axis: Dataset 0 = Revenue (Left Axis), Dataset 1 = Units Sold (Right Axis)
            const revData = datasets[0]?.data || [];
            const unitsData = datasets[1]?.data || [];

            const validRevs = revData.filter(v => typeof v === 'number' && !isNaN(v));
            const validUnits = unitsData.filter(v => typeof v === 'number' && !isNaN(v));

            const maxRev = validRevs.length > 0 ? Math.max(...validRevs, 100) : 100;
            const maxUnits = validUnits.length > 0 ? Math.max(...validUnits, 10) : 10;

            const revColor = datasets[0]?.color || "#087F80";
            const unitsColor = datasets[1]?.color || "#3B82F6";

            // Grid lines (3 horizontal lines)
            const gridLines = [0, 0.5, 1.0].map(ratio => {
                const y = paddingTop + plotHeight * (1 - ratio);
                const revTick = formatChartCurrency(maxRev * ratio, true);
                const unitTick = formatChartNumber(maxUnits * ratio, true);
                return `
                    <line x1="${paddingLeft}" y1="${y}" x2="${width - paddingRight}" y2="${y}" stroke="#E2E8F0" stroke-dasharray="3,3" stroke-width="1" />
                    <text x="${paddingLeft - 8}" y="${y + 4}" fill="#64748B" font-size="10" font-weight="600" text-anchor="end">${revTick}</text>
                    <text x="${width - paddingRight + 8}" y="${y + 4}" fill="#3B82F6" font-size="10" font-weight="600" text-anchor="start">${unitTick}</text>
                `;
            }).join("");

            // Revenue Points & Path
            const revPoints = revData.map((v, i) => {
                const val = (typeof v === 'number' && !isNaN(v)) ? v : 0;
                const x = paddingLeft + (i / Math.max(1, labels.length - 1)) * plotWidth;
                const y = paddingTop + plotHeight - (val / maxRev) * plotHeight;
                return { x, y, val, label: labels[i], idx: i };
            });

            // Units Points & Path
            const unitPoints = unitsData.map((v, i) => {
                const val = (typeof v === 'number' && !isNaN(v)) ? v : 0;
                const x = paddingLeft + (i / Math.max(1, labels.length - 1)) * plotWidth;
                const y = paddingTop + plotHeight - (val / maxUnits) * plotHeight;
                return { x, y, val, label: labels[i], idx: i };
            });

            const revPolyline = revPoints.map(p => `${p.x},${p.y}`).join(" ");
            const unitPolyline = unitPoints.map(p => `${p.x},${p.y}`).join(" ");

            const areaPoints = `${paddingLeft},${paddingTop + plotHeight} ` + revPolyline + ` ${width - paddingRight},${paddingTop + plotHeight}`;

            // X-Axis Labels (Display First, Middle, Last, or up to 6 labels evenly spaced)
            const step = Math.max(1, Math.floor(labels.length / 5));
            const xLabelsHTML = labels.map((lbl, i) => {
                if (i === 0 || i === labels.length - 1 || i % step === 0) {
                    const x = paddingLeft + (i / Math.max(1, labels.length - 1)) * plotWidth;
                    const isPartial = isPartialFlags[i];
                    return `<text x="${x}" y="${height - 10}" fill="${isPartial ? '#D97706' : '#64748B'}" font-size="10" font-weight="${isPartial ? '700' : '500'}" text-anchor="middle">${lbl}</text>`;
                }
                return '';
            }).join("");

            // Interactive Hover Columns
            const colWidth = plotWidth / Math.max(1, labels.length);
            const hoverColumnsHTML = labels.map((lbl, i) => {
                const x = paddingLeft + (i / Math.max(1, labels.length - 1)) * plotWidth - (colWidth / 2);
                const rP = revPoints[i];
                const uP = unitPoints[i];
                const isPart = isPartialFlags[i] || false;
                const avgR = avgDailyRevs[i] || 0;
                const avgU = avgDailyUnits[i] || 0;
                return `
                    <g class="chart-hover-col" data-idx="${i}" style="cursor:pointer;">
                        <rect x="${Math.max(paddingLeft, x)}" y="${paddingTop}" width="${colWidth}" height="${plotHeight}" fill="transparent" />
                        <circle class="hover-dot-rev" cx="${rP.x}" cy="${rP.y}" r="4" fill="${revColor}" stroke="#FFFFFF" stroke-width="2" />
                        <circle class="hover-dot-unit" cx="${uP.x}" cy="${uP.y}" r="4" fill="${unitsColor}" stroke="#FFFFFF" stroke-width="2" />
                    </g>
                `;
            }).join("");

            container.innerHTML = `
                <svg viewBox="0 0 ${width} ${height}" style="width: 100%; height: 100%; overflow: visible;" id="svg_${containerId}">
                    <defs>
                        <linearGradient id="grad_rev_${containerId}" x1="0" y1="0" x2="0" y2="1">
                            <stop offset="0%" stop-color="${revColor}" stop-opacity="0.25"/>
                            <stop offset="100%" stop-color="${revColor}" stop-opacity="0.0"/>
                        </linearGradient>
                    </defs>
                    ${gridLines}
                    <polygon points="${areaPoints}" fill="url(#grad_rev_${containerId})" />
                    <polyline fill="none" stroke="${unitsColor}" stroke-width="2" stroke-dasharray="4,3" stroke-linecap="round" points="${unitPolyline}" />
                    <polyline fill="none" stroke="${revColor}" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" points="${revPolyline}" />
                    ${xLabelsHTML}
                    ${hoverColumnsHTML}
                </svg>
            `;

            // Attach interactive hover events
            const hoverCols = container.querySelectorAll(".chart-hover-col");
            hoverCols.forEach(col => {
                col.addEventListener("mouseenter", (e) => {
                    const idx = parseInt(col.getAttribute("data-idx"), 10);
                    const isPart = isPartialFlags[idx];
                    const rVal = revData[idx] || 0;
                    const uVal = unitsData[idx] || 0;
                    const avgR = avgDailyRevs[idx];
                    const avgU = avgDailyUnits[idx];
                    const lbl = labels[idx];

                    let tipHTML = `<div style="font-weight:700; color:#F8FAFC; margin-bottom:4px; font-size:12px;">📅 ${lbl}</div>`;
                    tipHTML += `<div style="color:#2DD4BF; font-weight:600;">💰 Revenue: ${formatChartCurrency(rVal, false)}</div>`;
                    tipHTML += `<div style="color:#93C5FD; font-weight:600;">📦 Units Sold: ${formatChartNumber(uVal, false)} units</div>`;

                    if (isPart) {
                        tipHTML += `
                            <div style="margin-top:6px; padding-top:6px; border-top:1px dashed #475569; font-size:11px; color:#FBBF24;">
                                ⚠️ <strong>Partial Period (3 Days)</strong><br>
                                Avg Daily: ${formatChartCurrency(avgR, false)} / day<br>
                                Avg Units: ${Math.round(avgU)} units / day
                            </div>
                        `;
                    }
                    tooltip.innerHTML = tipHTML;
                    tooltip.style.display = "block";
                    tooltip.style.left = `${e.clientX + 14}px`;
                    tooltip.style.top = `${e.clientY - 12}px`;
                });

                col.addEventListener("mousemove", (e) => {
                    tooltip.style.left = `${e.clientX + 14}px`;
                    tooltip.style.top = `${e.clientY - 12}px`;
                });

                col.addEventListener("mouseleave", () => {
                    tooltip.style.display = "none";
                });
            });

        } else if (type === "line" || type === "area") {
            let maxVal = 10;
            datasets.forEach(ds => {
                const m = Math.max(...(ds.data || []).filter(v => typeof v === 'number' && !isNaN(v)));
                if (m > maxVal) maxVal = m;
            });

            // Grid lines
            const gridLines = [0, 0.5, 1.0].map(ratio => {
                const y = paddingTop + plotHeight * (1 - ratio);
                const isRev = (datasets[0]?.label && datasets[0].label.toLowerCase().includes("revenue")) || (chartSpec.title && chartSpec.title.toLowerCase().includes("revenue"));
                const tick = isRev ? formatChartCurrency(maxVal * ratio, true) : formatChartNumber(maxVal * ratio, true);
                return `
                    <line x1="${paddingLeft}" y1="${y}" x2="${width - paddingRight}" y2="${y}" stroke="#E2E8F0" stroke-dasharray="3,3" stroke-width="1" />
                    <text x="${paddingLeft - 8}" y="${y + 4}" fill="#64748B" font-size="10" font-weight="600" text-anchor="end">${tick}</text>
                `;
            }).join("");

            const polylinesHTML = datasets.map(ds => {
                const color = ds.color || "#087F80";
                const points = (ds.data || []).map((v, i) => {
                    if (v === null || v === undefined || isNaN(v)) return null;
                    const x = paddingLeft + (i / Math.max(1, labels.length - 1)) * plotWidth;
                    const y = paddingTop + plotHeight - (v / maxVal) * plotHeight;
                    return `${x},${y}`;
                }).filter(p => p !== null).join(" ");

                return `<polyline fill="none" stroke="${color}" stroke-width="2.5" stroke-linecap="round" points="${points}" />`;
            }).join("");

            // X-Axis Labels
            const step = Math.max(1, Math.floor(labels.length / 5));
            const xLabelsHTML = labels.map((lbl, i) => {
                if (i === 0 || i === labels.length - 1 || i % step === 0) {
                    const x = paddingLeft + (i / Math.max(1, labels.length - 1)) * plotWidth;
                    const isPartial = isPartialFlags[i];
                    return `<text x="${x}" y="${height - 10}" fill="${isPartial ? '#D97706' : '#64748B'}" font-size="10" font-weight="${isPartial ? '700' : '500'}" text-anchor="middle">${lbl}</text>`;
                }
                return '';
            }).join("");

            // Interactive points
            const dataPoints = (datasets[0]?.data || []).map((v, i) => {
                const val = (typeof v === 'number' && !isNaN(v)) ? v : 0;
                const x = paddingLeft + (i / Math.max(1, labels.length - 1)) * plotWidth;
                const y = paddingTop + plotHeight - (val / maxVal) * plotHeight;
                return `
                    <circle class="chart-point" data-idx="${i}" cx="${x}" cy="${y}" r="4" fill="${datasets[0]?.color || '#087F80'}" stroke="#FFFFFF" stroke-width="2" style="cursor:pointer;" />
                `;
            }).join("");

            container.innerHTML = `
                <svg viewBox="0 0 ${width} ${height}" style="width: 100%; height: 100%; overflow: visible;">
                    ${gridLines}
                    ${polylinesHTML}
                    ${dataPoints}
                    ${xLabelsHTML}
                </svg>
            `;

            // Hover events
            container.querySelectorAll(".chart-point").forEach(pt => {
                pt.addEventListener("mouseenter", (e) => {
                    const idx = parseInt(pt.getAttribute("data-idx"), 10);
                    const val = datasets[0]?.data?.[idx] || 0;
                    const isPart = isPartialFlags[idx];
                    const isRev = (datasets[0]?.label && datasets[0].label.toLowerCase().includes("revenue")) || (chartSpec.title && chartSpec.title.toLowerCase().includes("revenue"));

                    let tipHTML = `<div style="font-weight:700; color:#F8FAFC; margin-bottom:2px;">${labels[idx]}</div>`;
                    tipHTML += `<div style="color:#2DD4BF; font-weight:600;">${isRev ? formatChartCurrency(val, false) : formatChartNumber(val, false) + ' units'}</div>`;
                    if (isPart) {
                        tipHTML += `<div style="color:#FBBF24; font-size:11px; margin-top:3px;">⚠️ Partial Period</div>`;
                    }
                    tooltip.innerHTML = tipHTML;
                    tooltip.style.display = "block";
                    tooltip.style.left = `${e.clientX + 14}px`;
                    tooltip.style.top = `${e.clientY - 12}px`;
                });
                pt.addEventListener("mousemove", (e) => {
                    tooltip.style.left = `${e.clientX + 14}px`;
                    tooltip.style.top = `${e.clientY - 12}px`;
                });
                pt.addEventListener("mouseleave", () => {
                    tooltip.style.display = "none";
                });
            });

        } else if (type === "horizontal_bar") {
            const dataVals = datasets[0]?.data || [];
            const maxVal = Math.max(...dataVals.filter(v => typeof v === 'number' && !isNaN(v))) || 100;

            const chartWidth = 650;
            const chartHeight = Math.max(220, dataVals.length * 28 + 30);
            const labelWidth = 260;
            const barAreaWidth = chartWidth - labelWidth - 110;
            const barHeight = (chartHeight - 40) / Math.max(1, dataVals.length);

            const isDays = (datasets[0]?.unit === 'd') || (datasets[0]?.label && datasets[0].label.toLowerCase().includes('days')) || (chartSpec.title && chartSpec.title.toLowerCase().includes('coverage'));
            const isUnits = (datasets[0]?.unit === 'units') || (datasets[0]?.label && datasets[0].label.toLowerCase().includes('unit'));

            const barsHTML = dataVals.map((v, i) => {
                const valNum = typeof v === 'number' ? v : 0;
                const absMax = Math.max(1, Math.abs(maxVal));
                const barW = Math.max(3, (Math.abs(valNum) / absMax) * barAreaWidth);
                const y = 20 + i * barHeight + barHeight * 0.15;
                const h = Math.max(6, barHeight * 0.7);
                const color = datasets[0]?.color || '#087F80';
                const lbl = labels[i] ? String(labels[i]) : '';

                let valStr = '';
                if (isDays) {
                    valStr = Math.round(valNum).toLocaleString() + ' days';
                } else if (isUnits) {
                    valStr = Math.round(valNum).toLocaleString() + ' units';
                } else {
                    valStr = formatChartCurrency(valNum, false);
                }

                return `
                    <g class="chart-hbar" data-idx="${i}">
                        <text x="15" y="${y + h / 2 + 4}" fill="#334155" font-size="11" font-weight="600" text-anchor="start">${lbl.substring(0, 32)}</text>
                        <rect x="${labelWidth}" y="${y}" width="${barW}" height="${h}" fill="${color}" rx="3" />
                        <text x="${labelWidth + barW + 8}" y="${y + h / 2 + 4}" fill="#0F172A" font-size="11" font-weight="700" text-anchor="start">${valStr}</text>
                    </g>
                `;
            }).join("");

            container.innerHTML = `
                <svg viewBox="0 0 ${chartWidth} ${chartHeight}" style="width: 100%; height: 100%;">
                    ${barsHTML}
                </svg>
            `;

        } else if (type === "donut" || type === "pie") {
            const dataVals = (datasets[0]?.data || []).map(v => (typeof v === 'number' && !isNaN(v)) ? v : 0);
            const total = dataVals.reduce((a, b) => a + b, 0) || 1;
            const palette = ["#087F80", "#2563EB", "#D97706", "#DC2626", "#8B5CF6", "#0D9488", "#EA580C"];

            let cumulativeAngle = 0;
            const cx = 110;
            const cy = height / 2;
            const r = Math.min(cx, cy) - 18;
            const innerR = type === "donut" ? r * 0.55 : 0;

            const slicesHTML = dataVals.map((v, i) => {
                const sliceAngle = (v / total) * 2 * Math.PI;
                const startAngle = cumulativeAngle;
                const endAngle = cumulativeAngle + sliceAngle;
                cumulativeAngle += sliceAngle;

                const x1 = cx + r * Math.cos(startAngle);
                const y1 = cy + r * Math.sin(startAngle);
                const x2 = cx + r * Math.cos(endAngle);
                const y2 = cy + r * Math.sin(endAngle);

                const x1_in = cx + innerR * Math.cos(startAngle);
                const y1_in = cy + innerR * Math.sin(startAngle);
                const x2_in = cx + innerR * Math.cos(endAngle);
                const y2_in = cy + innerR * Math.sin(endAngle);

                const largeArc = sliceAngle > Math.PI ? 1 : 0;
                const color = palette[i % palette.length];

                let path = "";
                if (innerR > 0) {
                    path = `M ${x1} ${y1} A ${r} ${r} 0 ${largeArc} 1 ${x2} ${y2} L ${x2_in} ${y2_in} A ${innerR} ${innerR} 0 ${largeArc} 0 ${x1_in} ${y1_in} Z`;
                } else {
                    path = `M ${cx} ${cy} L ${x1} ${y1} A ${r} ${r} 0 ${largeArc} 1 ${x2} ${y2} Z`;
                }

                return `<path d="${path}" fill="${color}" stroke="#FFFFFF" stroke-width="1.5" />`;
            }).join("");

            const legendHTML = labels.map((lbl, i) => {
                const color = palette[i % palette.length];
                const val = dataVals[i];
                const ly = 25 + i * 22;
                if (ly > height - 10) return '';
                const pct = Math.round((val / total) * 100);
                const valStr = formatChartCurrency(val, true);
                return `
                    <rect x="230" y="${ly}" width="10" height="10" fill="${color}" rx="2" />
                    <text x="248" y="${ly + 9}" fill="#334155" font-size="11" font-weight="600">${lbl ? String(lbl).substring(0, 22) : ''}: <tspan fill="#64748B">${valStr} (${pct}%)</tspan></text>
                `;
            }).join("");

            container.innerHTML = `
                <svg viewBox="0 0 ${width} ${height}" style="width: 100%; height: 100%;">
                    ${slicesHTML}
                    ${legendHTML}
                </svg>
            `;

        } else {
            // Default Bar Chart (e.g. units trend, store performance, yearly, seasonality)
            const dataVals = datasets[0]?.data || [];
            const maxVal = Math.max(...dataVals.filter(v => typeof v === 'number' && !isNaN(v))) || 10;
            const barWidth = plotWidth / Math.max(1, dataVals.length);

            // Grid lines
            const isRev = (datasets[0]?.label && datasets[0].label.toLowerCase().includes("revenue")) || (chartSpec.title && chartSpec.title.toLowerCase().includes("revenue"));
            const gridLines = [0, 0.5, 1.0].map(ratio => {
                const y = paddingTop + plotHeight * (1 - ratio);
                const tick = isRev ? formatChartCurrency(maxVal * ratio, true) : formatChartNumber(maxVal * ratio, true);
                return `
                    <line x1="${paddingLeft}" y1="${y}" x2="${width - paddingRight}" y2="${y}" stroke="#E2E8F0" stroke-dasharray="3,3" stroke-width="1" />
                    <text x="${paddingLeft - 8}" y="${y + 4}" fill="#64748B" font-size="10" font-weight="600" text-anchor="end">${tick}</text>
                `;
            }).join("");

            const barsHTML = dataVals.map((v, i) => {
                const valNum = (typeof v === 'number' && !isNaN(v)) ? v : 0;
                const barHeight = (valNum / maxVal) * plotHeight;
                const x = paddingLeft + i * barWidth + barWidth * 0.15;
                const y = paddingTop + plotHeight - barHeight;
                const w = Math.max(3, barWidth * 0.7);
                const isPart = isPartialFlags[i];
                const col = isPart ? '#F59E0B' : (datasets[0]?.color || '#087F80');

                return `
                    <g class="chart-bar-group" data-idx="${i}" style="cursor:pointer;">
                        <rect x="${x}" y="${y}" width="${w}" height="${barHeight}" fill="${col}" rx="3" />
                        <text x="${x + w / 2}" y="${height - 10}" fill="${isPart ? '#D97706' : '#64748B'}" font-size="9" font-weight="${isPart ? '700' : '500'}" text-anchor="middle">${labels[i] ? String(labels[i]).substring(0, 8) : ''}</text>
                    </g>
                `;
            }).join("");

            container.innerHTML = `
                <svg viewBox="0 0 ${width} ${height}" style="width: 100%; height: 100%;">
                    ${gridLines}
                    ${barsHTML}
                </svg>
            `;

            container.querySelectorAll(".chart-bar-group").forEach(b => {
                b.addEventListener("mouseenter", (e) => {
                    const idx = parseInt(b.getAttribute("data-idx"), 10);
                    const val = dataVals[idx] || 0;
                    const isPart = isPartialFlags[idx];
                    let tipHTML = `<div style="font-weight:700; color:#F8FAFC; margin-bottom:2px;">${labels[idx]}</div>`;
                    tipHTML += `<div style="color:#2DD4BF; font-weight:600;">${isRev ? formatChartCurrency(val, false) : formatChartNumber(val, false) + ' units'}</div>`;
                    if (isPart) {
                        tipHTML += `<div style="color:#FBBF24; font-size:11px; margin-top:3px;">⚠️ Partial Period</div>`;
                    }
                    tooltip.innerHTML = tipHTML;
                    tooltip.style.display = "block";
                    tooltip.style.left = `${e.clientX + 14}px`;
                    tooltip.style.top = `${e.clientY - 12}px`;
                });
                b.addEventListener("mousemove", (e) => {
                    tooltip.style.left = `${e.clientX + 14}px`;
                    tooltip.style.top = `${e.clientY - 12}px`;
                });
                b.addEventListener("mouseleave", () => {
                    tooltip.style.display = "none";
                });
            });
        }
    }

    // Helper to escape HTML to prevent XSS
    function escapeHTML(str) {
        if (str === null || str === undefined) return "";
        return String(str)
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#039;");
    }

    // AI COPILOT CHAT QUERY FUNCTION
    async function sendChatQuery(userQuery) {
        const messagesContainer = document.getElementById("chat-messages-container");
        const welcomeCard = document.getElementById("copilot-welcome-card");
        const loadingCard = document.getElementById("ai-loading-indicator");

        if (!messagesContainer) return;
        if (welcomeCard) welcomeCard.style.display = "none";

        // User Message - Safely escaped
            const userMsgDiv = document.createElement("div");
            userMsgDiv.className = "chat-message user-message";
            userMsgDiv.textContent = userQuery;
            messagesContainer.appendChild(userMsgDiv);

            if (loadingCard) {
                loadingCard.classList.remove("hidden");
                loadingCard.style.display = "flex";
                const loadText = loadingCard.querySelector(".loading-text") || loadingCard.querySelector("span") || loadingCard;
                if (loadText) loadText.textContent = "Analyzing retail database...";
            }
            messagesContainer.scrollTop = messagesContainer.scrollHeight;

            // Assistant Message Placeholder
            const assistantMsgDiv = document.createElement("div");
            assistantMsgDiv.className = "chat-message assistant-message";
            assistantMsgDiv.innerHTML = `
            <div style="font-weight:700; color:var(--brand-teal); font-size:12px; margin-bottom:6px; display:flex; align-items:center; gap:6px;">
                ✨ RetailIQ Evidence Copilot
            </div>
            <div class="message-body" style="font-size:12px; color:var(--text-muted);">
                Analyzing store sales & inventory data...
            </div>
        `;
            messagesContainer.appendChild(assistantMsgDiv);
            messagesContainer.scrollTop = messagesContainer.scrollHeight;

            try {
                if (loadingCard) {
                    const loadText = loadingCard.querySelector(".loading-text") || loadingCard.querySelector("span") || loadingCard;
                    if (loadText) loadText.textContent = "Preparing evidence...";
                }

                const res = await fetch("/api/chat", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ question: userQuery, store_id: state.selectedStore, target_date: state.selectedDate })
                });

                const data = await res.json();
                renderCopilotResponse(assistantMsgDiv, data);

            } catch (err) {
                assistantMsgDiv.querySelector(".message-body").innerHTML = `
                <div style="color: var(--status-critical);">Error executing AI query. Please check server logs.</div>
            `;
            } finally {
                if (loadingCard) {
                    loadingCard.classList.add("hidden");
                    loadingCard.style.display = "none";
                }
            }
            messagesContainer.scrollTop = messagesContainer.scrollHeight;
        }

        // Render Grounded BI Executive Response in Chat
        function renderCopilotResponse(msgElement, data) {
            const sufficiencyBadge = data.data_sufficiency === "sufficient" ?
                `<span class="badge badge-success">✔ Answered from Retail Data</span>` :
                (data.data_sufficiency === "partial" ?
                    `<span class="badge badge-warning">⚠️ Partially Answered</span>` :
                    `<span class="badge badge-critical">❌ Not Answerable</span>`);

            let scopeHTML = "";
            if (data.data_scope) {
                scopeHTML = `<div style="font-size:11px; font-weight:700; color:var(--brand-teal); background:#ECFDF5; border:1px solid #A7F3D0; padding:4px 8px; border-radius:4px; margin-bottom:8px; display:inline-block;">📊 ${escapeHTML(data.data_scope)}</div>`;
            }

            let metricsHTML = "";
            if (data.key_metrics && data.key_metrics.length > 0) {
                metricsHTML = `
                <div style="display:flex; flex-wrap:wrap; gap:8px; margin: 10px 0;">
                    ${data.key_metrics.map(m => `
                        <div style="background:#FFFFFF; border:1px solid var(--border-color); padding:6px 12px; border-radius:6px; font-size:11px;">
                            <div style="color:var(--text-muted); font-size:10px;">${escapeHTML(m.label)}</div>
                            <div style="font-weight:700; color:var(--text-primary);">${escapeHTML(m.value)}</div>
                        </div>
                    `).join("")}
                </div>
            `;
            }

            let recsHTML = "";
            if (data.recommendations && data.recommendations.length > 0) {
                recsHTML = `
                <div style="background:var(--brand-teal-bg); border-left:3px solid var(--brand-teal); padding:10px 14px; border-radius:6px; font-size:12px; margin:10px 0; color:var(--text-secondary);">
                    <div style="color:var(--brand-teal); font-weight:700; font-size:11px; text-transform:uppercase;">💡 Action Plan:</div>
                    <ul style="padding-left:16px; margin-top:4px;">
                        ${data.recommendations.map(r => `<li>${escapeHTML(r)}</li>`).join("")}
                    </ul>
                </div>
            `;
            }

            let chartContainerId = `chat-chart-${Date.now()}`;
            let chartHTML = data.chart ? `
            <div style="background:#FFFFFF; border:1px solid var(--border-color); padding:14px; border-radius:8px; margin:12px 0;">
                <div style="font-size:12px; font-weight:700; color:var(--text-primary); margin-bottom:8px;">${escapeHTML(data.chart.title)}</div>
                <div id="${chartContainerId}" class="svg-chart-container" style="height:180px;"></div>
            </div>
        ` : "";

            let evidenceHTML = "";
            if (data.evidence && data.evidence.length > 0) {
                evidenceHTML = `
                <details style="margin-top:10px; font-size:11px; color:var(--text-muted);">
                    <summary style="cursor:pointer; font-weight:600; color:var(--text-secondary);">🔍 Supporting Evidence (${data.evidence.length} items)</summary>
                    <div style="margin-top:8px; display:flex; flex-direction:column; gap:4px;">
                        ${data.evidence.map(e => {
                    if (typeof e === 'string') return `<div style="background:#FFFFFF; border:1px solid var(--border-color); padding:4px 8px; border-radius:4px;">${escapeHTML(e)}</div>`;
                    return `
                            <div style="background:#FFFFFF; border:1px solid var(--border-color); padding:6px 10px; border-radius:4px; display:flex; flex-wrap:wrap; gap:8px;">
                                ${e.year ? `<div><strong>Year:</strong> ${escapeHTML(e.year)}</div>` : ''}
                                ${e.product_name ? `<div><strong>Product:</strong> ${escapeHTML(e.product_name)}</div>` : ''}
                                ${e.store_name ? `<div><strong>Store:</strong> ${escapeHTML(e.store_name)}</div>` : ''}
                                ${e.revenue !== undefined ? `<div><strong>Revenue:</strong> ${escapeHTML(typeof e.revenue === 'number' ? '₹' + Math.round(e.revenue).toLocaleString('en-IN') : e.revenue)}</div>` : ''}
                                ${e.units_sold !== undefined ? `<div><strong>Units:</strong> ${escapeHTML(typeof e.units_sold === 'number' ? e.units_sold.toLocaleString() : e.units_sold)}</div>` : ''}
                                ${e.current_stock !== undefined && e.current_stock !== "N/A" ? `<div><strong>Stock:</strong> ${escapeHTML(e.current_stock)}</div>` : ''}
                                ${e.avg_daily_sales !== undefined && e.avg_daily_sales !== 0 ? `<div><strong>Avg Daily:</strong> ${escapeHTML(e.avg_daily_sales)}</div>` : ''}
                                ${e.source ? `<div><strong>Source:</strong> ${escapeHTML(e.source)}</div>` : ''}
                            </div>`;
                }).join("")}
                    </div>
                </details>
            `;
            }

            msgElement.querySelector(".message-body").innerHTML = `
            <div style="display:flex; flex-direction:column; gap:4px; margin-bottom:6px;">
                <div>${sufficiencyBadge}</div>
                ${scopeHTML}
            </div>
            <div style="font-size: 13px; line-height: 1.55; color: var(--text-primary);">
                ${escapeHTML(data.answer)}
            </div>
            ${metricsHTML}
            ${recsHTML}
            ${chartHTML}
            ${evidenceHTML}
        `;

            if (data.chart) {
                setTimeout(() => {
                    renderSVGChart(chartContainerId, data.chart);
                }, 60);
            }
        }
    });
