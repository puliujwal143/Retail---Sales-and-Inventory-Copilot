// RetailIQ Enterprise B2B Frontend Engine - Fixed Layout & ID Matching
document.addEventListener("DOMContentLoaded", () => {
    // Global State
    const state = {
        currentTab: "dashboard",
        selectedStore: "all",
        dashboardTimeframe: 30,
        salesTimeframe: 30,
        inventoryData: [],
        dashboardData: null,
        storesData: []
    };

    // DOM References
    const navItems = document.querySelectorAll(".nav-item");
    const tabViews = document.querySelectorAll(".tab-view");
    const globalStoreSelect = document.getElementById("global-store-select");
    const globalSearchInput = document.getElementById("global-search-input");

    // Product Modal References
    const productModal = document.getElementById("product-detail-modal");
    const productModalCloseBtn = document.getElementById("modal-close-btn");

    // Initialize
    init();

    async function init() {
        setupNavigation();
        setupFilters();
        setupCopilotTab();
        setupProductModal();

        await loadStores();
        await loadDashboard();
        await loadInventory();
        await loadSalesWorkspace();
    }

    // Navigation & Tab Switching
    function setupNavigation() {
        // Navigation buttons & Quick jump buttons
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

    function setupFilters() {
        if (globalStoreSelect) {
            globalStoreSelect.addEventListener("change", (e) => {
                state.selectedStore = e.target.value;
                const salesStoreSel = document.getElementById("sales-store-select");
                if (salesStoreSel) salesStoreSel.value = e.target.value;
                loadDashboard();
                renderInventoryTable();
                loadSalesWorkspace();
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
                loadSalesWorkspace();
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
        } catch (err) {
            console.error("Failed to load stores:", err);
        }
    }

    // Load Executive Dashboard Data
    async function loadDashboard() {
        try {
            const url = `/api/dashboard?store_id=${state.selectedStore}`;
            const res = await fetch(url);
            const data = await res.json();
            state.dashboardData = data;

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
            const res = await fetch(`/api/analytics/charts?days=${state.dashboardTimeframe}&store_id=${state.selectedStore}`);
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
            const res = await fetch("/api/inventory");
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
            const res = await fetch(`/api/products/${productId}?store_id=${storeId}`);
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
            const res = await fetch(`/api/analytics/charts?days=${state.salesTimeframe}&store_id=${state.selectedStore}`);
            const data = await res.json();

            const revSum = data.revenue_trend.datasets[0].data.reduce((a, b) => a + b, 0);
            const unitSum = data.units_trend.datasets[0].data.reduce((a, b) => a + b, 0);
            const dailyAvg = revSum / Math.max(1, data.revenue_trend.labels.length);

            const salesRevEl = document.getElementById("sales-kpi-revenue");
            const salesUnitsEl = document.getElementById("sales-kpi-units");
            const salesDailyEl = document.getElementById("sales-kpi-daily-rev");
            const salesTopCatEl = document.getElementById("sales-kpi-top-cat");

            if (salesRevEl) salesRevEl.textContent = `$${revSum.toLocaleString('en-US', {minimumFractionDigits: 2})}`;
            if (salesUnitsEl) salesUnitsEl.textContent = unitSum.toLocaleString();
            if (salesDailyEl) salesDailyEl.textContent = `$${dailyAvg.toLocaleString('en-US', {minimumFractionDigits: 2})}`;
            if (salesTopCatEl) salesTopCatEl.textContent = data.category_chart.labels[0] || "Computers";

            renderSVGChart("chart-sales-revenue", data.revenue_trend);
            renderSVGChart("chart-sales-units", data.units_trend);
            renderSVGChart("chart-sales-category", data.category_chart);
            renderSVGChart("chart-sales-top-products", data.top_products_chart);
            renderSVGChart("chart-sales-store", data.store_chart);

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
                insightsContainer.innerHTML = data.insights.map(ins => `
                    <div style="background:var(--bg-light); border-left:3px solid var(--brand-teal); padding:8px 12px; border-radius:4px; font-size:12px; margin-bottom:6px;">
                        ${ins}
                    </div>
                `).join("");
            }

        } catch (err) {
            console.error("Failed to load sales workspace:", err);
        }
    }

    // Mini Sparkline Renderer inside KPI cards
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

    // SVG Chart Render Engine (Strict Height & Responsive Contained Specs)
    function renderSVGChart(containerId, chartSpec) {
        const container = document.getElementById(containerId);
        if (!container || !chartSpec || !chartSpec.labels || chartSpec.labels.length === 0) {
            if (container) container.innerHTML = '<div style="color:var(--text-muted); font-size:12px; padding:20px;">No chart data available.</div>';
            return;
        }

        const width = 500;
        const height = 200;
        const padding = 30;

        const type = chartSpec.type || "line";
        const labels = chartSpec.labels;
        const dataset = chartSpec.datasets[0];
        const dataVals = dataset.data;
        const mainColor = "#087F80";

        if (type === "line" || type === "area") {
            const maxVal = Math.max(...dataVals) || 100;
            const points = dataVals.map((v, i) => {
                const x = padding + (i / Math.max(1, dataVals.length - 1)) * (width - 2 * padding);
                const y = height - padding - (v / maxVal) * (height - 2 * padding);
                return `${x},${y}`;
            }).join(" ");

            const fillHTML = `
                <defs>
                    <linearGradient id="areaGrad_${containerId}" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0%" stop-color="${mainColor}" stop-opacity="0.2"/>
                        <stop offset="100%" stop-color="${mainColor}" stop-opacity="0.0"/>
                    </linearGradient>
                </defs>
                <polygon points="${padding},${height - padding} ${points} ${width - padding},${height - padding}" fill="url(#areaGrad_${containerId})" />
            `;

            const svgHTML = `
                <svg viewBox="0 0 ${width} ${height}" style="width: 100%; height: 100%; overflow: hidden;">
                    <line x1="${padding}" y1="${height - padding}" x2="${width - padding}" y2="${height - padding}" stroke="#E5EAF0" stroke-width="1" />
                    <line x1="${padding}" y1="${padding}" x2="${width - padding}" y2="${padding}" stroke="#E5EAF0" stroke-dasharray="4" stroke-width="1" />
                    ${fillHTML}
                    <polyline fill="none" stroke="${mainColor}" stroke-width="2.5" stroke-linecap="round" points="${points}" />
                    <text x="${padding}" y="${padding - 8}" fill="#64748B" font-size="10" font-weight="600">$${Math.round(maxVal).toLocaleString()}</text>
                    <text x="${padding}" y="${height - 6}" fill="#64748B" font-size="10">${labels[0]}</text>
                    <text x="${width - padding - 45}" y="${height - 6}" fill="#64748B" font-size="10">${labels[labels.length - 1]}</text>
                </svg>
            `;
            container.innerHTML = svgHTML;

        } else if (type === "bar") {
            const maxVal = Math.max(...dataVals) || 100;
            const barWidth = (width - 2 * padding) / dataVals.length;

            const barsHTML = dataVals.map((v, i) => {
                const barHeight = (v / maxVal) * (height - 2 * padding);
                const x = padding + i * barWidth + barWidth * 0.15;
                const y = height - padding - barHeight;
                const w = barWidth * 0.7;
                return `
                    <rect x="${x}" y="${y}" width="${w}" height="${barHeight}" fill="${mainColor}" rx="3" />
                    <text x="${x + w/2}" y="${height - 6}" fill="#64748B" font-size="9" text-anchor="middle">${labels[i] ? labels[i].substring(0, 8) : ''}</text>
                `;
            }).join("");

            container.innerHTML = `
                <svg viewBox="0 0 ${width} ${height}" style="width: 100%; height: 100%;">
                    <line x1="${padding}" y1="${height - padding}" x2="${width - padding}" y2="${height - padding}" stroke="#E5EAF0" stroke-width="1" />
                    ${barsHTML}
                </svg>
            `;

        } else if (type === "horizontal_bar") {
            const maxVal = Math.max(...dataVals) || 100;
            const barHeight = (height - 2 * padding) / dataVals.length;

            const barsHTML = dataVals.map((v, i) => {
                const barWidth = (v / maxVal) * (width - 170);
                const y = padding + i * barHeight + barHeight * 0.15;
                const h = barHeight * 0.7;
                const displayLabel = labels[i] ? (labels[i].length > 18 ? labels[i].substring(0, 16) + "..." : labels[i]) : '';
                return `
                    <text x="10" y="${y + h/1.4}" fill="#334155" font-size="10" font-weight="500">${displayLabel}</text>
                    <rect x="150" y="${y}" width="${barWidth}" height="${h}" fill="${mainColor}" rx="3" />
                    <text x="${156 + barWidth}" y="${y + h/1.4}" fill="#0F172A" font-size="10" font-weight="700">${typeof v === 'number' ? '$' + Math.round(v).toLocaleString() : v}</text>
                `;
            }).join("");

            container.innerHTML = `
                <svg viewBox="0 0 ${width} ${height}" style="width: 100%; height: 100%;">
                    ${barsHTML}
                </svg>
            `;
        }
    }

    // AI Copilot Chat Execution
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

        // Assistant Placeholder Message
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
                body: JSON.stringify({ question: userQuery, store_id: state.selectedStore })
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

    // Format Structured Executive BI Response inside Chat Message Box
    function renderCopilotResponse(msgElement, data) {
        const isSufficient = data.data_sufficiency === "sufficient";
        const sufficiencyBadge = isSufficient ?
            `<span class="badge badge-success">✔ Data Grounded & Sufficient</span>` :
            `<span class="badge badge-warning">⚠️ Data Insufficient - Cause Unverified</span>`;

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
                <div id="${chartContainerId}" class="svg-chart-container" style="height:160px;"></div>
            </div>
        ` : "";

        let evidenceHTML = "";
        if (data.evidence && data.evidence.length > 0) {
            evidenceHTML = `
                <details style="margin-top:10px; font-size:11px; color:var(--text-muted);">
                    <summary style="cursor:pointer; font-weight:600; color:var(--text-secondary);">🔍 Supporting Evidence (${data.evidence.length} items)</summary>
                    <div style="margin-top:8px; display:flex; flex-direction:column; gap:4px;">
                        ${data.evidence.map(e => `
                            <div style="background:#FFFFFF; border:1px solid var(--border-color); padding:6px 10px; border-radius:4px; display:grid; grid-template-columns:repeat(auto-fit, minmax(120px, 1fr)); gap:4px;">
                                <div><strong>Product:</strong> ${e.product_name}</div>
                                <div><strong>Store:</strong> ${e.store_name}</div>
                                <div><strong>Stock:</strong> ${e.current_stock}</div>
                                <div><strong>Avg Daily:</strong> ${e.avg_daily_sales}</div>
                                <div><strong>Days Remaining:</strong> ${e.days_remaining}</div>
                            </div>
                        `).join("")}
                    </div>
                </details>
            `;
        }

        msgElement.querySelector(".message-body").innerHTML = `
            <div style="margin-bottom:6px;">${sufficiencyBadge}</div>
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
            }, 50);
        }
    }
});
