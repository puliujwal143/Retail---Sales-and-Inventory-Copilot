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
        compareSelectedStores: ["STR001", "STR002", "STR003"]
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

    // Load Stores Dropdown Options
    async function loadStores() {
        try {
            const res = await fetch("/api/stores");
            const data = await res.json();
            state.storesData = data;

            if (globalStoreSelect) {
                globalStoreSelect.innerHTML = '<option value="all">All Stores (5)</option>';
                data.forEach(s => {
                    const opt = document.createElement("option");
                    opt.value = s.store_id;
                    opt.textContent = `${s.store_name} (${s.location})`;
                    globalStoreSelect.appendChild(opt);
                });
            }

            const salesStoreSel = document.getElementById("sales-store-select");
            if (salesStoreSel) {
                salesStoreSel.innerHTML = '<option value="all">All Store Locations</option>';
                data.forEach(s => {
                    const opt = document.createElement("option");
                    opt.value = s.store_id;
                    opt.textContent = s.store_name;
                    salesStoreSel.appendChild(opt);
                });
            }

            setupStoreComparison();
        } catch (err) {
            console.error("Failed to load stores:", err);
        }
    }

    // Load Executive Dashboard Data
    async function loadDashboard() {
        try {
            let url = `/api/dashboard?store_id=${state.selectedStore}`;
            if (state.selectedDate) url += `&date=${state.selectedDate}`;

            const res = await fetch(url);
            const data = await res.json();
            // Out-of-range date check
            let noDataBanner = document.getElementById("date-no-data-banner");
            if (data.no_data) {
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

            if (revEl) revEl.textContent = `$${data.total_revenue.toLocaleString('en-US', {minimumFractionDigits: 2})}`;
            if (unitsEl) unitsEl.textContent = data.total_units_sold.toLocaleString();
            
            const lowStockTotal = data.critical_low_stock_count + data.warning_low_stock_count;
            if (alertsEl) alertsEl.textContent = lowStockTotal;
            if (overstockEl) overstockEl.textContent = data.overstock_count;
            if (growthEl) growthEl.textContent = "+21.6%";

            // Render mini sparklines cleanly inside KPI cards
            renderMiniSparkline("sparkline-revenue", [12000, 14500, 13200, 16800, 18500, 21000, data.total_revenue], "#16A34A");
            renderMiniSparkline("sparkline-units", [420, 480, 450, 520, 590, 610, data.total_units_sold], "#8B5CF6");
            renderMiniSparkline("sparkline-lowstock", [8, 12, 10, 14, 9, 11, lowStockTotal], "#F59E0B");
            renderMiniSparkline("sparkline-overstock", [15, 18, 14, 16, 20, 19, data.overstock_count], "#2563EB");
            renderMiniSparkline("sparkline-growth", [4, 6, 8, 7, 10, 11, 21.6], "#16A34A");

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
            renderSVGChart("dashboard-sales-chart", data.revenue_trend);
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
                container.innerHTML = '<div class="alert-subtext" style="padding:10px;">No priority actions required today. All stock levels healthy!</div>';
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

        const total = data.total_inventory_units || 120;
        const critical = data.critical_low_stock_count || 3;
        const warning = data.warning_low_stock_count || 8;
        const overstock = data.overstock_count || 12;
        const healthy = Math.max(0, total - critical - warning - overstock);

        const pctH = (healthy / total) * 100;
        const pctW = (warning / total) * 100;
        const pctC = (critical / total) * 100;
        const pctO = (overstock / total) * 100;

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
                        <div style="font-size:10px; color:#64748B; font-weight:600;">Products</div>
                    </div>
                </div>

                <div style="width:100%; display:flex; flex-direction:column; gap:4px; font-size:11px;">
                    <div style="display:flex; justify-content:space-between; padding:2px 0;">
                        <span><span style="color:#16A34A;">●</span> Healthy Stock</span>
                        <strong>${healthy} (${Math.round(pctH)}%)</strong>
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
        if (!tbody || !products) return;

        tbody.innerHTML = products.slice(0, 5).map((p, idx) => `
            <tr>
                <td><strong>#${idx + 1}</strong></td>
                <td><strong>${p.product_name}</strong></td>
                <td class="text-right"><strong>${p.units_sold}</strong></td>
                <td class="text-right"><strong>$${p.revenue.toLocaleString('en-US', {minimumFractionDigits: 2})}</strong></td>
                <td class="text-right"><span class="badge badge-success">+18.5%</span></td>
            </tr>
        `).join("");
    }

    // Render Store Performance Table
    function renderStorePerformanceTable(stores) {
        const tbody = document.getElementById("store-performance-tbody");
        if (!tbody || !stores) return;

        tbody.innerHTML = stores.map(s => {
            const rev = s.total_revenue || 42500;
            const targetPct = Math.min(100, Math.round((rev / 50000) * 100));
            return `
                <tr>
                    <td><strong>${s.store_name}</strong></td>
                    <td class="text-right"><strong>$${rev.toLocaleString('en-US', {minimumFractionDigits: 2})}</strong></td>
                    <td class="text-right"><strong>${Math.round(rev / 150)}</strong></td>
                    <td class="text-right"><span class="badge badge-success">+${targetPct}%</span></td>
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
            tbody.innerHTML = '<tr><td colspan="8" style="text-align: center; color: var(--text-muted); padding:20px;">No matching inventory records found.</td></tr>';
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
            document.getElementById("modal-revenue-val").textContent = `$${data.metrics["30d_revenue"].toLocaleString('en-US', {minimumFractionDigits: 2})}`;

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
                datasets: [{ label: "Daily Revenue ($)", data: revs, color: "#087F80" }]
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

            if (salesRevEl) salesRevEl.textContent = `$${revSum.toLocaleString('en-US', {minimumFractionDigits: 2})}`;
            if (salesUnitsEl) salesUnitsEl.textContent = unitSum.toLocaleString();
            if (salesDailyEl) salesDailyEl.textContent = `$${dailyAvg.toLocaleString('en-US', {minimumFractionDigits: 2})}`;
            if (salesTopCatEl) salesTopCatEl.textContent = data.category_chart?.labels?.[0] || "Computers";

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
                if (seasonData && seasonData.seasonality_chart) {
                    renderSVGChart("chart-sales-seasonality", seasonData.seasonality_chart);
                }
            } catch (errYearly) {
                console.error("Yearly chart render error:", errYearly);
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

    // SVG Chart Render Engine (Supports line, area, bar, horizontal_bar)
    function renderSVGChart(containerId, chartSpec) {
        const container = document.getElementById(containerId);
        if (!container) return;
        
        if (!chartSpec || !chartSpec.labels || chartSpec.labels.length === 0) {
            container.innerHTML = '<div style="color:var(--text-muted); font-size:12px; padding:20px; text-align:center;">No chart data available.</div>';
            return;
        }

        const width = container.clientWidth || 500;
        const height = container.clientHeight || 200;
        const padding = 35;

        const type = chartSpec.type || "line";
        const labels = chartSpec.labels;
        const datasets = chartSpec.datasets || [];
        if (datasets.length === 0) {
            container.innerHTML = '<div style="color:var(--text-muted); font-size:12px; padding:20px; text-align:center;">No chart data available.</div>';
            return;
        }

        if (type === "line" || type === "area") {
            let maxVal = 10;
            datasets.forEach(ds => {
                const vals = (ds.data || []).filter(v => v !== null && v !== undefined);
                if (vals.length > 0) {
                    const m = Math.max(...vals);
                    if (m > maxVal) maxVal = m;
                }
            });

            const polylinesHTML = datasets.map(ds => {
                const color = ds.color || "#087F80";
                const points = (ds.data || []).map((v, i) => {
                    if (v === null || v === undefined) return null;
                    const x = padding + (i / Math.max(1, labels.length - 1)) * (width - 2 * padding);
                    const y = height - padding - (v / maxVal) * (height - 2 * padding);
                    return `${x},${y}`;
                }).filter(p => p !== null).join(" ");

                return `<polyline fill="none" stroke="${color}" stroke-width="2.5" stroke-linecap="round" points="${points}" />`;
            }).join("");

            const svgHTML = `
                <svg viewBox="0 0 ${width} ${height}" style="width: 100%; height: 100%; overflow: hidden;">
                    <line x1="${padding}" y1="${height - padding}" x2="${width - padding}" y2="${height - padding}" stroke="#E5EAF0" stroke-width="1" />
                    <line x1="${padding}" y1="${padding}" x2="${width - padding}" y2="${padding}" stroke="#E5EAF0" stroke-dasharray="4" stroke-width="1" />
                    ${polylinesHTML}
                    <text x="${padding}" y="${padding - 8}" fill="#64748B" font-size="10" font-weight="600">$${Math.round(maxVal).toLocaleString()}</text>
                    <text x="${padding}" y="${height - 6}" fill="#64748B" font-size="10">${labels[0] || ''}</text>
                    <text x="${width - padding - 45}" y="${height - 6}" fill="#64748B" font-size="10">${labels[labels.length - 1] || ''}</text>
                </svg>
            `;
            container.innerHTML = svgHTML;

        } else if (type === "bar") {
            const dataVals = datasets[0].data || [];
            const maxVal = Math.max(...dataVals.filter(v => v !== null && v !== undefined), 10);
            const barWidth = (width - 2 * padding) / Math.max(1, dataVals.length);

            const barsHTML = dataVals.map((v, i) => {
                const val = v || 0;
                const barHeight = (val / maxVal) * (height - 2 * padding);
                const x = padding + i * barWidth + barWidth * 0.15;
                const y = height - padding - barHeight;
                const w = Math.max(2, barWidth * 0.7);
                return `
                    <rect x="${x}" y="${y}" width="${w}" height="${barHeight}" fill="${datasets[0].color || '#087F80'}" rx="3" />
                    <text x="${x + w/2}" y="${height - 6}" fill="#64748B" font-size="9" text-anchor="middle">${labels[i] ? String(labels[i]).substring(0, 8) : ''}</text>
                `;
            }).join("");

            container.innerHTML = `
                <svg viewBox="0 0 ${width} ${height}" style="width: 100%; height: 100%;">
                    <line x1="${padding}" y1="${height - padding}" x2="${width - padding}" y2="${height - padding}" stroke="#E5EAF0" stroke-width="1" />
                    ${barsHTML}
                </svg>
            `;
        } else if (type === "horizontal_bar") {
            const dataVals = datasets[0].data || [];
            const maxVal = Math.max(...dataVals.filter(v => v !== null && v !== undefined), 10);
            const rowHeight = (height - 2 * padding) / Math.max(1, dataVals.length);

            const barsHTML = dataVals.map((v, i) => {
                const val = v || 0;
                const barWidth = (val / maxVal) * (width - 160);
                const y = padding + i * rowHeight + rowHeight * 0.15;
                const h = Math.max(4, rowHeight * 0.7);
                return `
                    <text x="${padding}" y="${y + h/1.3}" fill="#334155" font-size="10" font-weight="600">${labels[i] ? String(labels[i]).substring(0, 18) : ''}</text>
                    <rect x="140" y="${y}" width="${barWidth}" height="${h}" fill="${datasets[0].color || '#06b6d4'}" rx="3" />
                    <text x="${145 + barWidth}" y="${y + h/1.3}" fill="#64748B" font-size="10" font-weight="600">$${Math.round(val).toLocaleString()}</text>
                `;
            }).join("");

            container.innerHTML = `
                <svg viewBox="0 0 ${width} ${height}" style="width: 100%; height: 100%;">
                    ${barsHTML}
                </svg>
            `;
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
                tbody.innerHTML = '<tr><td colspan="8" style="text-align:center; padding:20px; color:var(--text-muted);">No items match reorder criteria. All stock levels healthy!</td></tr>';
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
                container.innerHTML = '<div style="padding:20px; color:var(--text-muted);">No critical operational decisions required.</div>';
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

            const tableRowsHTML = data.comparison_table.map(s => `
                <tr>
                    <td><strong>${s.store_name}</strong><br><span style="font-size:10px; color:var(--text-muted);">${s.location}</span></td>
                    <td class="text-right"><strong>$${s.total_revenue.toLocaleString('en-US', {minimumFractionDigits:2})}</strong></td>
                    <td class="text-right">${s.units_sold.toLocaleString()} units</td>
                    <td class="text-right">$${s.avg_daily_revenue.toLocaleString('en-US', {minimumFractionDigits:2})}/day</td>
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

            const kpis = rep.kpis;
            container.innerHTML = `
                <div style="border-bottom:2px solid var(--brand-teal); padding-bottom:12px; margin-bottom:16px;">
                    <h2 style="font-size:20px; color:var(--text-primary);">${rep.report_title}</h2>
                    <div style="font-size:12px; color:var(--text-muted); margin-top:2px;">
                        Date Context: <strong>${rep.generated_date}</strong> | Store Scope: <strong>${rep.store_scope}</strong>
                    </div>
                </div>

                <div class="kpi-grid" style="margin-bottom:20px;">
                    <div class="kpi-card"><div class="kpi-title">TOTAL REVENUE</div><div class="kpi-value">$${kpis.total_revenue.toLocaleString('en-US', {minimumFractionDigits:2})}</div></div>
                    <div class="kpi-card"><div class="kpi-title">UNITS SOLD</div><div class="kpi-value">${kpis.total_units_sold.toLocaleString()}</div></div>
                    <div class="kpi-card"><div class="kpi-title">VALUATION</div><div class="kpi-value">$${kpis.total_inventory_valuation.toLocaleString('en-US', {minimumFractionDigits:2})}</div></div>
                    <div class="kpi-card highlight-critical"><div class="kpi-title">CRITICAL SKUs</div><div class="kpi-value">${kpis.critical_low_stock_count}</div></div>
                </div>

                <div style="display:grid; grid-template-columns:1fr 1fr; gap:16px; margin-bottom:16px;">
                    <div>
                        <h4 style="font-size:13px; font-weight:700; margin-bottom:8px;">Top Performing SKUs</h4>
                        <ul style="font-size:12px; line-height:1.6; padding-left:16px;">
                            ${rep.top_products.map(p => `<li><strong>${p.product_name}</strong>: $${p.revenue.toLocaleString()} (${p.units_sold} units)</li>`).join("")}
                        </ul>
                    </div>
                    <div>
                        <h4 style="font-size:13px; font-weight:700; margin-bottom:8px;">Operational Reorder Recommendations</h4>
                        <ul style="font-size:12px; line-height:1.6; padding-left:16px;">
                            ${rep.recommended_reorders.slice(0, 4).map(r => `<li><strong>${r.product_name}</strong> (${r.store_name}): +${r.recommended_reorder} units</li>`).join("")}
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

    // SVG Chart Render Engine (Supports multi-dataset, line, bar, horizontal_bar, donut)
    function renderSVGChart(containerId, chartSpec) {
        const container = document.getElementById(containerId);
        if (!container || !chartSpec || !chartSpec.labels || chartSpec.labels.length === 0) {
            if (container) container.innerHTML = '<div style="color:var(--text-muted); font-size:12px; padding:20px; text-align:center;">No chart data available for this query.</div>';
            return;
        }

        const width = 500;
        const height = 200;
        const padding = 30;

        const type = chartSpec.type || "line";
        const labels = chartSpec.labels;
        const datasets = chartSpec.datasets && chartSpec.datasets.length > 0 ? chartSpec.datasets : [{ label: "Data", data: [], color: "#087F80" }];

        if (type === "line" || type === "area") {
            let maxVal = 10;
            datasets.forEach(ds => {
                const m = Math.max(...ds.data.filter(v => v !== null && v !== undefined && !isNaN(v)));
                if (m > maxVal) maxVal = m;
            });

            const polylinesHTML = datasets.map(ds => {
                const color = ds.color || "#087F80";
                const points = ds.data.map((v, i) => {
                    if (v === null || v === undefined || isNaN(v)) return null;
                    const x = padding + (i / Math.max(1, labels.length - 1)) * (width - 2 * padding);
                    const y = height - padding - (v / maxVal) * (height - 2 * padding);
                    return `${x},${y}`;
                }).filter(p => p !== null).join(" ");

                return `<polyline fill="none" stroke="${color}" stroke-width="2.5" stroke-linecap="round" points="${points}" />`;
            }).join("");

            const svgHTML = `
                <svg viewBox="0 0 ${width} ${height}" style="width: 100%; height: 100%; overflow: hidden;">
                    <line x1="${padding}" y1="${height - padding}" x2="${width - padding}" y2="${height - padding}" stroke="#E5EAF0" stroke-width="1" />
                    <line x1="${padding}" y1="${padding}" x2="${width - padding}" y2="${padding}" stroke="#E5EAF0" stroke-dasharray="4" stroke-width="1" />
                    ${polylinesHTML}
                    <text x="${padding}" y="${padding - 8}" fill="#64748B" font-size="10" font-weight="600">$${Math.round(maxVal).toLocaleString()}</text>
                    <text x="${padding}" y="${height - 6}" fill="#64748B" font-size="10">${labels[0] || ''}</text>
                    <text x="${width - padding - 45}" y="${height - 6}" fill="#64748B" font-size="10">${labels[labels.length - 1] || ''}</text>
                </svg>
            `;
            container.innerHTML = svgHTML;

        } else if (type === "horizontal_bar") {
            const dataVals = datasets[0].data;
            const maxVal = Math.max(...dataVals.filter(v => typeof v === 'number' && !isNaN(v))) || 100;
            const barHeight = (height - 2 * padding) / Math.max(1, dataVals.length);

            const barsHTML = dataVals.map((v, i) => {
                const valNum = typeof v === 'number' ? v : 0;
                const barW = Math.max(2, (valNum / maxVal) * (width - 2 * padding - 120));
                const y = padding + i * barHeight + barHeight * 0.15;
                const h = Math.max(4, barHeight * 0.7);
                const color = datasets[0].color || '#f59e0b';
                const lbl = labels[i] ? String(labels[i]).substring(0, 16) : '';
                const valStr = valNum >= 1000 ? '$' + Math.round(valNum).toLocaleString() : valNum;
                return `
                    <text x="${padding}" y="${y + h/2 + 3}" fill="#64748B" font-size="9" font-weight="600" text-anchor="start">${lbl}</text>
                    <rect x="${padding + 110}" y="${y}" width="${barW}" height="${h}" fill="${color}" rx="3" />
                    <text x="${padding + 115 + barW}" y="${y + h/2 + 3}" fill="#1E293B" font-size="9" font-weight="600" text-anchor="start">${valStr}</text>
                `;
            }).join("");

            container.innerHTML = `
                <svg viewBox="0 0 ${width} ${height}" style="width: 100%; height: 100%;">
                    ${barsHTML}
                </svg>
            `;

        } else if (type === "donut" || type === "pie") {
            const dataVals = datasets[0].data.map(v => (typeof v === 'number' && !isNaN(v)) ? v : 0);
            const total = dataVals.reduce((a, b) => a + b, 0) || 1;
            const palette = ["#087F80", "#2B6CB0", "#D69E2E", "#E53E3E", "#805AD5", "#319795", "#DD6B20"];

            let cumulativeAngle = 0;
            const cx = 100;
            const cy = height / 2;
            const r = Math.min(cx, cy) - 15;
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
                const ly = 25 + i * 20;
                if (ly > height - 10) return '';
                const valStr = val >= 1000 ? '$' + Math.round(val).toLocaleString() : val;
                return `
                    <rect x="220" y="${ly}" width="10" height="10" fill="${color}" rx="2" />
                    <text x="236" y="${ly + 9}" fill="#475569" font-size="10">${lbl ? String(lbl).substring(0, 20) : ''}: ${valStr}</text>
                `;
            }).join("");

            container.innerHTML = `
                <svg viewBox="0 0 ${width} ${height}" style="width: 100%; height: 100%;">
                    ${slicesHTML}
                    ${legendHTML}
                </svg>
            `;

        } else {
            // Default Bar Chart
            const dataVals = datasets[0].data;
            const maxVal = Math.max(...dataVals.filter(v => typeof v === 'number' && !isNaN(v))) || 100;
            const barWidth = (width - 2 * padding) / Math.max(1, dataVals.length);

            const barsHTML = dataVals.map((v, i) => {
                const valNum = typeof v === 'number' ? v : 0;
                const barHeight = (valNum / maxVal) * (height - 2 * padding);
                const x = padding + i * barWidth + barWidth * 0.15;
                const y = height - padding - barHeight;
                const w = Math.max(2, barWidth * 0.7);
                return `
                    <rect x="${x}" y="${y}" width="${w}" height="${barHeight}" fill="${datasets[0].color || '#087F80'}" rx="3" />
                    <text x="${x + w/2}" y="${height - 6}" fill="#64748B" font-size="9" text-anchor="middle">${labels[i] ? String(labels[i]).substring(0, 8) : ''}</text>
                `;
            }).join("");

            container.innerHTML = `
                <svg viewBox="0 0 ${width} ${height}" style="width: 100%; height: 100%;">
                    <line x1="${padding}" y1="${height - padding}" x2="${width - padding}" y2="${height - padding}" stroke="#E5EAF0" stroke-width="1" />
                    ${barsHTML}
                </svg>
            `;
        }
    }

    // AI COPILOT CHAT QUERY FUNCTION
    async function sendChatQuery(userQuery) {
        const messagesContainer = document.getElementById("chat-messages-container");
        const welcomeCard = document.getElementById("copilot-welcome-card");
        const loadingCard = document.getElementById("ai-loading-indicator");

        if (!messagesContainer) return;
        if (welcomeCard) welcomeCard.style.display = "none";

        // User Message
        const userMsgDiv = document.createElement("div");
        userMsgDiv.className = "chat-message user-message";
        userMsgDiv.innerHTML = `<div>${userQuery}</div>`;
        messagesContainer.appendChild(userMsgDiv);

        if (loadingCard) loadingCard.classList.remove("hidden");
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
            const res = await fetch("/api/chat", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ question: userQuery, store_id: state.selectedStore, target_date: state.selectedDate })
            });

            const data = await res.json();
            if (loadingCard) loadingCard.classList.add("hidden");
            renderCopilotResponse(assistantMsgDiv, data);

        } catch (err) {
            if (loadingCard) loadingCard.classList.add("hidden");
            assistantMsgDiv.querySelector(".message-body").innerHTML = `
                <div style="color: var(--status-critical);">Error executing AI query. Please check server logs.</div>
            `;
        }
        messagesContainer.scrollTop = messagesContainer.scrollHeight;
    }

    // Render Grounded BI Executive Response in Chat
    function renderCopilotResponse(msgElement, data) {
        const isSufficient = data.data_sufficiency === "sufficient";
        const sufficiencyBadge = isSufficient ?
            `<span class="badge badge-success">✔ Data Grounded & Sufficient</span>` :
            `<span class="badge badge-warning">⚠️ Data Insufficient - Cause Unverified</span>`;

        let scopeHTML = "";
        if (data.data_scope) {
            scopeHTML = `<div style="font-size:11px; font-weight:700; color:var(--brand-teal); background:#ECFDF5; border:1px solid #A7F3D0; padding:4px 8px; border-radius:4px; margin-bottom:8px; display:inline-block;">📊 ${data.data_scope}</div>`;
        }

        let metricsHTML = "";
        if (data.key_metrics && data.key_metrics.length > 0) {
            metricsHTML = `
                <div style="display:flex; flex-wrap:wrap; gap:8px; margin: 10px 0;">
                    ${data.key_metrics.map(m => `
                        <div style="background:#FFFFFF; border:1px solid var(--border-color); padding:6px 12px; border-radius:6px; font-size:11px;">
                            <div style="color:var(--text-muted); font-size:10px;">${m.label}</div>
                            <div style="font-weight:700; color:var(--text-primary);">${m.value}</div>
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
                        ${data.recommendations.map(r => `<li>${r}</li>`).join("")}
                    </ul>
                </div>
            `;
        }

        let chartContainerId = `chat-chart-${Date.now()}`;
        let chartHTML = data.chart ? `
            <div style="background:#FFFFFF; border:1px solid var(--border-color); padding:14px; border-radius:8px; margin:12px 0;">
                <div style="font-size:12px; font-weight:700; color:var(--text-primary); margin-bottom:8px;">${data.chart.title}</div>
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
                            if (typeof e === 'string') return `<div style="background:#FFFFFF; border:1px solid var(--border-color); padding:4px 8px; border-radius:4px;">${e}</div>`;
                            return `
                            <div style="background:#FFFFFF; border:1px solid var(--border-color); padding:6px 10px; border-radius:4px; display:flex; flex-wrap:wrap; gap:8px;">
                                ${e.year ? `<div><strong>Year:</strong> ${e.year}</div>` : ''}
                                ${e.product_name ? `<div><strong>Product:</strong> ${e.product_name}</div>` : ''}
                                ${e.store_name ? `<div><strong>Store:</strong> ${e.store_name}</div>` : ''}
                                ${e.revenue !== undefined ? `<div><strong>Revenue:</strong> ${typeof e.revenue === 'number' ? '$' + Math.round(e.revenue).toLocaleString() : e.revenue}</div>` : ''}
                                ${e.units_sold !== undefined ? `<div><strong>Units:</strong> ${typeof e.units_sold === 'number' ? e.units_sold.toLocaleString() : e.units_sold}</div>` : ''}
                                ${e.current_stock !== undefined && e.current_stock !== "N/A" ? `<div><strong>Stock:</strong> ${e.current_stock}</div>` : ''}
                                ${e.avg_daily_sales !== undefined && e.avg_daily_sales !== 0 ? `<div><strong>Avg Daily:</strong> ${e.avg_daily_sales}</div>` : ''}
                                ${e.source ? `<div><strong>Source:</strong> ${e.source}</div>` : ''}
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
                ${data.answer}
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
