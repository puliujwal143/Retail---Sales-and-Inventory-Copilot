// RetailIQ Enterprise B2B Frontend Engine
document.addEventListener("DOMContentLoaded", () => {
    // Global Application State
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
    const storeSelect = document.getElementById("global-store-select");
    const tabTitle = document.getElementById("current-tab-title");
    const tabSubtitle = document.getElementById("current-tab-subtitle");

    // Modal References
    const modal = document.getElementById("product-detail-modal");
    const modalCloseBtn = document.getElementById("modal-close-btn");

    // Initialize App
    init();

    async function init() {
        setupNavigation();
        setupFilters();
        setupCopilot();
        setupModal();

        await loadStores();
        await loadDashboard();
        await loadInventory();
        await loadSalesWorkspace();
    }

    // Navigation setup
    function setupNavigation() {
        navItems.forEach(btn => {
            btn.addEventListener("click", () => {
                const targetTab = btn.getAttribute("data-tab");
                if (!targetTab) return;

                const targetStatus = btn.getAttribute("data-status");
                if (targetStatus) {
                    document.getElementById("inv-filter-status").value = targetStatus;
                    renderInventoryTable();
                }

                navItems.forEach(b => b.classList.remove("active"));
                tabViews.forEach(v => v.classList.remove("active"));

                const activeNav = document.querySelector(`.nav-item[data-tab="${targetTab}"]`);
                if (activeNav) activeNav.classList.add("active");
                
                const targetSec = document.getElementById(`tab-${targetTab}`);
                if (targetSec) targetSec.classList.add("active");
                state.currentTab = targetTab;

                // Update headers
                switch (targetTab) {
                    case "dashboard":
                        tabTitle.textContent = "Dashboard";
                        tabSubtitle.textContent = "Retail performance overview across all store locations";
                        break;
                    case "inventory":
                        tabTitle.textContent = "Inventory Intelligence";
                        tabSubtitle.textContent = "Monitor stock health and identify products requiring action";
                        break;
                    case "sales":
                        tabTitle.textContent = "Sales Analytics Workspace";
                        tabSubtitle.textContent = "Track revenue, demand, product performance and store trends";
                        break;
                    case "copilot":
                        tabTitle.textContent = "AI Copilot";
                        tabSubtitle.textContent = "Ask questions about sales, inventory and retail performance";
                        break;
                }
            });
        });

        // Dashboard Time Range Buttons
        document.querySelectorAll(".time-range-picker .range-btn").forEach(btn => {
            btn.addEventListener("click", () => {
                document.querySelectorAll(".time-range-picker .range-btn").forEach(b => b.classList.remove("active"));
                btn.classList.add("active");
                state.dashboardTimeframe = parseInt(btn.getAttribute("data-days"));
                loadDashboardChartOnly();
            });
        });
    }

    function setupFilters() {
        storeSelect.addEventListener("change", (e) => {
            state.selectedStore = e.target.value;
            loadDashboard();
            renderInventoryTable();
            loadSalesWorkspace();
        });

        document.getElementById("inv-search-input").addEventListener("input", renderInventoryTable);
        document.getElementById("inv-filter-category").addEventListener("change", renderInventoryTable);
        document.getElementById("inv-filter-status").addEventListener("change", renderInventoryTable);

        document.getElementById("sales-timeframe-select").addEventListener("change", (e) => {
            state.salesTimeframe = parseInt(e.target.value);
            loadSalesWorkspace();
        });

        document.getElementById("sales-store-select").addEventListener("change", (e) => {
            state.selectedStore = e.target.value;
            storeSelect.value = e.target.value;
            loadSalesWorkspace();
        });
    }

    // Modal Setup
    function setupModal() {
        modalCloseBtn.addEventListener("click", () => modal.classList.add("hidden"));
        modal.addEventListener("click", (e) => {
            if (e.target === modal) modal.classList.add("hidden");
        });
    }

    // Load Stores dropdown
    async function loadStores() {
        try {
            const res = await fetch("/api/stores");
            const data = await res.json();
            state.storesData = data;
            
            storeSelect.innerHTML = '<option value="all">All Stores (5)</option>';
            const salesStoreSel = document.getElementById("sales-store-select");
            salesStoreSel.innerHTML = '<option value="all">All Store Locations</option>';

            data.forEach(s => {
                const opt1 = document.createElement("option");
                opt1.value = s.store_id;
                opt1.textContent = `${s.store_name} (${s.location})`;
                storeSelect.appendChild(opt1);

                const opt2 = document.createElement("option");
                opt2.value = s.store_id;
                opt2.textContent = `${s.store_name}`;
                salesStoreSel.appendChild(opt2);
            });
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

            document.getElementById("kpi-revenue").textContent = `$${data.total_revenue.toLocaleString('en-US', {minimumFractionDigits: 2})}`;
            document.getElementById("kpi-units").textContent = data.total_units_sold.toLocaleString();
            document.getElementById("kpi-valuation").textContent = `$${data.total_inventory_valuation.toLocaleString('en-US', {minimumFractionDigits: 2})}`;
            document.getElementById("kpi-inv-units").textContent = `${data.total_inventory_units.toLocaleString()} Total Units in Stock`;

            const totalAlerts = data.critical_low_stock_count + data.warning_low_stock_count;
            document.getElementById("kpi-alerts-count").textContent = totalAlerts;
            document.getElementById("kpi-alerts-breakdown").textContent = `Critical: ${data.critical_low_stock_count} | Warning: ${data.warning_low_stock_count}`;
            document.getElementById("kpi-overstock-count").textContent = data.overstock_count;

            loadAttentionItems();
            loadDashboardChartOnly();
            renderInventoryHealthBreakdown(data);
            renderTopProductsTable(data.top_products);

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

    // Load Attention Items
    async function loadAttentionItems() {
        const container = document.getElementById("attention-items-container");
        try {
            const res = await fetch("/api/alerts");
            const items = await res.json();

            if (!items || items.length === 0) {
                container.innerHTML = '<div class="att-desc">No priority actions required today. All stock levels healthy!</div>';
                return;
            }

            container.innerHTML = "";
            items.slice(0, 4).forEach(item => {
                const card = document.createElement("div");
                card.className = `attention-card ${item.severity}`;
                card.innerHTML = `
                    <div>
                        <div class="att-title">${item.summary}</div>
                        <div class="att-desc"><strong>Action:</strong> ${item.recommended_action}</div>
                    </div>
                    <div>
                        <span class="severity-pill ${item.severity}">${item.severity}</span>
                    </div>
                `;
                container.appendChild(card);
            });
        } catch (err) {
            container.innerHTML = '<div class="att-desc">Failed to load priority actions.</div>';
        }
    }

    // Render Inventory Health Breakdown
    function renderInventoryHealthBreakdown(data) {
        const container = document.getElementById("inventory-health-container");
        const total = (data.total_inventory_units) || 1;

        const healthyCount = total - (data.critical_low_stock_count + data.warning_low_stock_count + data.slow_moving_count + data.overstock_count);

        const items = [
            { label: "Healthy", count: Math.max(0, healthyCount), color: "#15803D" },
            { label: "Warning (<= 7 Days)", count: data.warning_low_stock_count, color: "#B45309" },
            { label: "Critical (<= 2 Days)", count: data.critical_low_stock_count, color: "#B91C1C" },
            { label: "Overstocked", count: data.overstock_count, color: "#2563EB" },
            { label: "Slow Moving", count: data.slow_moving_count, color: "#64748B" }
        ];

        container.innerHTML = items.map(it => {
            const pct = Math.round((it.count / total) * 100);
            return `
                <div class="health-item">
                    <div class="health-info">
                        <span><strong>${it.label}</strong></span>
                        <span>${it.count} items (${pct}%)</span>
                    </div>
                    <div class="health-bar-bg">
                        <div class="health-bar-fill" style="width: ${pct}%; background-color: ${it.color};"></div>
                    </div>
                </div>
            `;
        }).join("");
    }

    // Render Top Products Table
    function renderTopProductsTable(products) {
        const tbody = document.getElementById("top-products-tbody");
        if (!products) return;

        tbody.innerHTML = products.map((p, idx) => `
            <tr>
                <td><strong>#${idx + 1}</strong></td>
                <td><strong>${p.product_name}</strong></td>
                <td><span class="badge badge-primary">${p.category}</span></td>
                <td class="text-right">${p.units_sold} units</td>
                <td class="text-right"><strong>$${p.revenue.toLocaleString('en-US', {minimumFractionDigits: 2})}</strong></td>
                <td><span class="badge badge-success">Growth</span></td>
            </tr>
        `).join("");
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

            document.getElementById("inv-kpi-total").textContent = total;
            document.getElementById("inv-kpi-critical").textContent = critical;
            document.getElementById("inv-kpi-warning").textContent = warning;
            document.getElementById("inv-kpi-overstock").textContent = overstock;
            document.getElementById("inv-kpi-slow").textContent = slow;

            const categories = [...new Set(state.inventoryData.map(i => i.category))];
            const catSelect = document.getElementById("inv-filter-category");
            catSelect.innerHTML = '<option value="all">All Categories</option>';
            categories.forEach(cat => {
                const opt = document.createElement("option");
                opt.value = cat;
                opt.textContent = cat;
                catSelect.appendChild(opt);
            });

            renderInventoryTable();
        } catch (err) {
            console.error("Failed to load inventory:", err);
        }
    }

    // Render Inventory Data Table
    function renderInventoryTable() {
        const tbody = document.getElementById("inventory-tbody");
        const search = document.getElementById("inv-search-input").value.toLowerCase();
        const selectedCat = document.getElementById("inv-filter-category").value;
        const selectedStatus = document.getElementById("inv-filter-status").value;

        let filtered = state.inventoryData.filter(item => {
            if (state.selectedStore !== "all" && item.store_id !== state.selectedStore) return false;
            if (search && !item.product_name.toLowerCase().includes(search) && !item.category.toLowerCase().includes(search)) return false;
            if (selectedCat !== "all" && item.category !== selectedCat) return false;
            if (selectedStatus !== "all" && item.status !== selectedStatus) return false;
            return true;
        });

        if (filtered.length === 0) {
            tbody.innerHTML = '<tr><td colspan="8" style="text-align: center; color: var(--text-muted);">No matching inventory records found.</td></tr>';
            return;
        }

        tbody.innerHTML = filtered.map(i => {
            let statusBadge = `<span class="badge badge-healthy">Healthy</span>`;
            if (i.status === "CRITICAL" || i.status === "OUT_OF_STOCK") {
                statusBadge = `<span class="badge badge-critical">CRITICAL</span>`;
            } else if (i.status === "WARNING") {
                statusBadge = `<span class="badge badge-warning">WARNING</span>`;
            } else if (i.status === "SLOW_MOVING") {
                statusBadge = `<span class="badge badge-slow">SLOW MOVING</span>`;
            } else if (i.status === "OVERSTOCK") {
                statusBadge = `<span class="badge badge-overstock">OVERSTOCK</span>`;
            }

            const reorderText = i.recommended_reorder > 0 ? 
                `<strong style="color: var(--brand-emerald);">+${i.recommended_reorder} units</strong>` : 
                `<span style="color: var(--text-dim);">0</span>`;

            return `
                <tr data-product-id="${i.product_id}" data-store-id="${i.store_id}">
                    <td><strong>${i.product_name}</strong></td>
                    <td><span class="badge badge-primary">${i.category}</span></td>
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
        modal.classList.remove("hidden");
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
                    <div style="font-weight: 700; color: var(--brand-emerald); font-size: 14px; margin-bottom: 4px;">
                        Reorder Recommendation: +${reorderQty} Units
                    </div>
                    <div>Current stock of <strong>${data.metrics.current_stock}</strong> covers only <strong>${data.metrics.days_remaining} days</strong> of average demand. Reorder ${reorderQty} units to maintain 7-day target coverage.</div>
                `;
            } else {
                document.getElementById("modal-reorder-summary").innerHTML = `
                    <div style="font-weight: 700; color: var(--status-success); font-size: 14px; margin-bottom: 4px;">
                        Stock Level Healthy
                    </div>
                    <div>Current stock of <strong>${data.metrics.current_stock}</strong> units fully covers demand for <strong>${data.metrics.days_remaining} days</strong> (exceeding 7-day safety threshold).</div>
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
                datasets: [{ label: "Daily Revenue ($)", data: revs, color: "#0F766E" }]
            };
            renderSVGChart("modal-sales-chart", chartSpec);

        } catch (err) {
            console.error("Modal load error:", err);
        }
    }

    // Load Sales Analytics Workspace Data (6 Charts)
    async function loadSalesWorkspace() {
        try {
            const res = await fetch(`/api/analytics/charts?days=${state.salesTimeframe}&store_id=${state.selectedStore}`);
            const data = await res.json();

            const revSum = data.revenue_trend.datasets[0].data.reduce((a, b) => a + b, 0);
            const unitSum = data.units_trend.datasets[0].data.reduce((a, b) => a + b, 0);
            const dailyAvg = revSum / Math.max(1, data.revenue_trend.labels.length);

            document.getElementById("sales-kpi-revenue").textContent = `$${revSum.toLocaleString('en-US', {minimumFractionDigits: 2})}`;
            document.getElementById("sales-kpi-units").textContent = unitSum.toLocaleString();
            document.getElementById("sales-kpi-daily-rev").textContent = `$${dailyAvg.toLocaleString('en-US', {minimumFractionDigits: 2})}`;
            
            const topCatName = data.category_chart.labels[0] || "Electronics";
            document.getElementById("sales-kpi-top-cat").textContent = topCatName;

            renderSVGChart("chart-sales-revenue", data.revenue_trend);
            renderSVGChart("chart-sales-units", data.units_trend);
            renderSVGChart("chart-sales-category", data.category_chart);
            renderSVGChart("chart-sales-top-products", data.top_products_chart);
            renderSVGChart("chart-sales-store", data.store_chart);

            const spikesContainer = document.getElementById("spikes-drops-container");
            let highlightsHTML = "";
            if (data.spikes && data.spikes.length > 0) {
                highlightsHTML += data.spikes.slice(0, 3).map(s => `
                    <div class="trend-card">
                        <div>
                            <strong>SPIKE: ${s.product_name}</strong>
                            <div style="font-size: 11px; color: var(--text-muted);">${s.prev_units_30d} → ${s.curr_units_30d} units</div>
                        </div>
                        <span class="badge badge-success">+${s.pct_change_units}%</span>
                    </div>
                `).join("");
            }
            if (data.drops && data.drops.length > 0) {
                highlightsHTML += data.drops.slice(0, 3).map(d => `
                    <div class="trend-card">
                        <div>
                            <strong>DROP: ${d.product_name}</strong>
                            <div style="font-size: 11px; color: var(--text-muted);">${d.prev_units_30d} → ${d.curr_units_30d} units</div>
                        </div>
                        <span class="badge badge-critical">${d.pct_change_units}%</span>
                    </div>
                `).join("");
            }

            spikesContainer.innerHTML = highlightsHTML || '<div style="font-size:12px; color:var(--text-muted);">No major sales spikes/drops detected.</div>';

            const insightsContainer = document.getElementById("sales-insights-container");
            insightsContainer.innerHTML = data.insights.map(ins => `
                <div class="insight-chip-item">${ins}</div>
            `).join("");

        } catch (err) {
            console.error("Failed to load sales workspace:", err);
        }
    }

    // PURE SVG CHART RENDER ENGINE (Light Theme Optimized)
    function renderSVGChart(containerId, chartSpec) {
        const container = document.getElementById(containerId);
        if (!container || !chartSpec || !chartSpec.labels || chartSpec.labels.length === 0) {
            if (container) container.innerHTML = '<div style="color:var(--text-muted); font-size:12px; padding:20px;">No chart data available.</div>';
            return;
        }

        const width = 500;
        const height = 200;
        const padding = 35;

        const type = chartSpec.type || "line";
        const labels = chartSpec.labels;
        const dataset = chartSpec.datasets[0];
        const dataVals = dataset.data;
        const mainColor = "#0F766E";

        if (type === "line" || type === "area") {
            const maxVal = Math.max(...dataVals) || 100;
            const points = dataVals.map((v, i) => {
                const x = padding + (i / Math.max(1, dataVals.length - 1)) * (width - 2 * padding);
                const y = height - padding - (v / maxVal) * (height - 2 * padding);
                return `${x},${y}`;
            }).join(" ");

            const fillHTML = type === "area" ? `
                <defs>
                    <linearGradient id="areaGrad_${containerId}" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0%" stop-color="${mainColor}" stop-opacity="0.25"/>
                        <stop offset="100%" stop-color="${mainColor}" stop-opacity="0.0"/>
                    </linearGradient>
                </defs>
                <polygon points="${padding},${height - padding} ${points} ${width - padding},${height - padding}" fill="url(#areaGrad_${containerId})" />
            ` : "";

            const svgHTML = `
                <svg viewBox="0 0 ${width} ${height}" style="width: 100%; height: 100%; overflow: visible;">
                    <line x1="${padding}" y1="${height - padding}" x2="${width - padding}" y2="${height - padding}" stroke="#E2E8F0" stroke-width="1" />
                    <line x1="${padding}" y1="${padding}" x2="${width - padding}" y2="${padding}" stroke="#E2E8F0" stroke-dasharray="4" stroke-width="1" />
                    ${fillHTML}
                    <polyline fill="none" stroke="${mainColor}" stroke-width="2" points="${points}" />
                    <text x="${padding}" y="${padding - 8}" fill="#64748B" font-size="10">$${Math.round(maxVal).toLocaleString()}</text>
                    <text x="${padding}" y="${height - 8}" fill="#64748B" font-size="10">${labels[0]}</text>
                    <text x="${width - padding - 45}" y="${height - 8}" fill="#64748B" font-size="10">${labels[labels.length - 1]}</text>
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
                    <text x="${x + w/2}" y="${height - 10}" fill="#64748B" font-size="9" text-anchor="middle">${labels[i] ? labels[i].substring(0, 8) : ''}</text>
                `;
            }).join("");

            container.innerHTML = `
                <svg viewBox="0 0 ${width} ${height}" style="width: 100%; height: 100%;">
                    <line x1="${padding}" y1="${height - padding}" x2="${width - padding}" y2="${height - padding}" stroke="#E2E8F0" stroke-width="1" />
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
                    <text x="10" y="${y + h/1.4}" fill="#475569" font-size="10">${displayLabel}</text>
                    <rect x="150" y="${y}" width="${barWidth}" height="${h}" fill="${mainColor}" rx="3" />
                    <text x="${156 + barWidth}" y="${y + h/1.4}" fill="#0F172A" font-size="10" font-weight="600">${typeof v === 'number' ? '$' + Math.round(v).toLocaleString() : v}</text>
                `;
            }).join("");

            container.innerHTML = `
                <svg viewBox="0 0 ${width} ${height}" style="width: 100%; height: 100%;">
                    ${barsHTML}
                </svg>
            `;
        } else if (type === "donut") {
            container.innerHTML = `
                <div style="display:flex; align-items:center; gap:16px; height:100%; justify-content:center;">
                    <svg viewBox="0 0 100 100" style="width:110px; height:110px;">
                        <circle cx="50" cy="50" r="38" fill="none" stroke="#E2E8F0" stroke-width="12"/>
                        <circle cx="50" cy="50" r="38" fill="none" stroke="${mainColor}" stroke-width="12" stroke-dasharray="180 240" transform="rotate(-90 50 50)"/>
                    </svg>
                    <div style="font-size:11px; color:var(--text-secondary);">
                        ${labels.map((l, i) => `<div><span style="color:${mainColor}">●</span> ${l}: <strong>${dataVals[i]}</strong></div>`).join("")}
                    </div>
                </div>
            `;
        }
    }

    // AI COPILOT SETUP & EXECUTIVE REPORT RENDERER
    function setupCopilot() {
        const form = document.getElementById("chat-form");
        const input = document.getElementById("chat-input");
        const pills = document.querySelectorAll(".prompt-pill");
        const suggCards = document.querySelectorAll(".suggestion-card");

        const handlePromptClick = (promptText) => {
            input.value = promptText;
            sendChatQuery(promptText);
        };

        pills.forEach(pill => {
            pill.addEventListener("click", () => handlePromptClick(pill.getAttribute("data-prompt")));
        });

        suggCards.forEach(card => {
            card.addEventListener("click", () => handlePromptClick(card.getAttribute("data-prompt")));
        });

        form.addEventListener("submit", (e) => {
            e.preventDefault();
            const text = input.value.trim();
            if (!text) return;
            input.value = "";
            sendChatQuery(text);
        });
    }

    async function sendChatQuery(userQuery) {
        const messagesContainer = document.getElementById("chat-messages-container");
        const welcomeCard = document.getElementById("copilot-welcome-card");
        const loadingCard = document.getElementById("ai-loading-indicator");

        // Hide landing card if present
        if (welcomeCard) welcomeCard.style.display = "none";

        // User Message
        const userMsgDiv = document.createElement("div");
        userMsgDiv.className = "chat-message user-message";
        userMsgDiv.innerHTML = `<div>${userQuery}</div>`;
        messagesContainer.appendChild(userMsgDiv);

        // Show Multi-step thinking indicator
        loadingCard.classList.remove("hidden");
        messagesContainer.scrollTop = messagesContainer.scrollHeight;

        // Assistant Placeholder Message
        const assistantMsgDiv = document.createElement("div");
        assistantMsgDiv.className = "chat-message assistant-message";
        assistantMsgDiv.innerHTML = `
            <div class="message-header">
                <span class="assistant-avatar">🤖</span>
                <span class="assistant-name">RetailIQ Evidence Copilot</span>
            </div>
            <div class="message-content">
                <div class="loading-spinner">Evaluating database & generating grounded response...</div>
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
            loadingCard.classList.add("hidden");
            renderCopilotResponse(assistantMsgDiv, data);

        } catch (err) {
            loadingCard.classList.add("hidden");
            assistantMsgDiv.querySelector(".message-content").innerHTML = `
                <div style="color: var(--status-critical);">Error executing query. Please check server logs.</div>
            `;
        }
        messagesContainer.scrollTop = messagesContainer.scrollHeight;
    }

    // Render Executive BI Report Card in Chat
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
                        <div style="background:var(--bg-light); border:1px solid var(--border-color); padding:6px 12px; border-radius:6px; font-size:11px;">
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
                <div style="background:var(--brand-emerald-bg); border-left:3px solid var(--brand-emerald); padding:10px 14px; border-radius:6px; font-size:12px; margin:10px 0; color:var(--text-secondary);">
                    <div style="color:var(--brand-emerald); font-weight:700; font-size:11px; text-transform:uppercase;">💡 Action Plan:</div>
                    <ul style="padding-left:16px; margin-top:4px;">
                        ${data.recommendations.map(r => `<li>${r}</li>`).join("")}
                    </ul>
                </div>
            `;
        }

        let chartContainerId = `chat-chart-${Date.now()}`;
        let chartHTML = data.chart ? `
            <div style="background:var(--bg-light); border:1px solid var(--border-color); padding:14px; border-radius:8px; margin:12px 0;">
                <div style="font-size:12px; font-weight:700; color:var(--text-primary); margin-bottom:8px;">${data.chart.title}</div>
                <div id="${chartContainerId}" class="svg-chart-container" style="height:160px;"></div>
            </div>
        ` : "";

        let evidenceHTML = "";
        if (data.evidence && data.evidence.length > 0) {
            evidenceHTML = `
                <details style="margin-top:10px; font-size:11px; color:var(--text-muted);">
                    <summary style="cursor:pointer; font-weight:600; color:var(--text-secondary);">▸ Supporting Evidence Details (${data.evidence.length} items)</summary>
                    <div style="margin-top:8px; display:flex; flex-direction:column; gap:4px;">
                        ${data.evidence.map(e => `
                            <div style="background:var(--bg-light); border:1px solid var(--border-color); padding:6px 10px; border-radius:4px; display:grid; grid-template-columns:repeat(auto-fit, minmax(120px, 1fr)); gap:4px;">
                                <div><strong>Product:</strong> ${e.product_name}</div>
                                <div><strong>Store:</strong> ${e.store_name}</div>
                                <div><strong>Stock:</strong> ${e.current_stock}</div>
                                <div><strong>Avg Sales:</strong> ${e.avg_daily_sales}</div>
                                <div><strong>Days Left:</strong> ${e.days_remaining}</div>
                            </div>
                        `).join("")}
                    </div>
                </details>
            `;
        }

        let assumptionsHTML = "";
        if (data.assumptions && data.assumptions.length > 0) {
            assumptionsHTML = `
                <div style="font-size:10px; color:var(--text-dim); margin-top:6px;">
                    <strong>Assumptions Used:</strong> ${data.assumptions.join(" | ")}
                </div>
            `;
        }

        msgElement.querySelector(".message-content").innerHTML = `
            ${sufficiencyBadge}
            <div style="font-size: 13px; line-height: 1.6; color: var(--text-primary); margin-top:8px;">
                ${data.answer}
            </div>
            ${metricsHTML}
            ${recsHTML}
            ${chartHTML}
            ${evidenceHTML}
            ${assumptionsHTML}
        `;

        if (data.chart) {
            setTimeout(() => {
                renderSVGChart(chartContainerId, data.chart);
            }, 50);
        }
    }
});
