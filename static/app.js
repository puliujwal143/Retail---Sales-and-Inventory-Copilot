// RetailIQ - Single Page Application JS Engine
document.addEventListener("DOMContentLoaded", () => {
    // State management
    const state = {
        currentTab: "dashboard",
        selectedStore: "all",
        inventoryData: [],
        dashboardData: null,
        salesData: null,
        storesData: [],
        categoriesData: []
    };

    // DOM Elements
    const navItems = document.querySelectorAll(".nav-item");
    const tabViews = document.querySelectorAll(".tab-view");
    const storeSelect = document.getElementById("global-store-select");
    const tabTitle = document.getElementById("current-tab-title");
    const tabSubtitle = document.getElementById("current-tab-subtitle");

    // Initialize App
    init();

    async function init() {
        setupNavigation();
        setupFilters();
        setupCopilot();

        await loadStores();
        await loadDashboard();
        await loadInventory();
        await loadSalesAnalytics();
    }

    // Navigation setup
    function setupNavigation() {
        navItems.forEach(btn => {
            btn.addEventListener("click", () => {
                const targetTab = btn.getAttribute("data-tab");
                if (targetTab === state.currentTab) return;

                navItems.forEach(b => b.classList.remove("active"));
                tabViews.forEach(v => v.classList.remove("active"));

                btn.classList.add("active");
                document.getElementById(`tab-${targetTab}`).classList.add("active");
                state.currentTab = targetTab;

                // Update headers
                switch (targetTab) {
                    case "dashboard":
                        tabTitle.textContent = "Executive Dashboard";
                        tabSubtitle.textContent = "Real-time inventory intelligence and operational metrics";
                        break;
                    case "inventory":
                        tabTitle.textContent = "Inventory Management";
                        tabSubtitle.textContent = "Stock levels, average daily sales, and automated reorder recommendations";
                        break;
                    case "sales":
                        tabTitle.textContent = "Sales Analytics";
                        tabSubtitle.textContent = "Period-over-period sales trends, spikes, drops, and category performance";
                        break;
                    case "copilot":
                        tabTitle.textContent = "AI Evidence Copilot";
                        tabSubtitle.textContent = "Ask natural language questions grounded strictly by deterministic python analytics";
                        break;
                }
            });
        });
    }

    function setupFilters() {
        storeSelect.addEventListener("change", (e) => {
            state.selectedStore = e.target.value;
            loadDashboard();
            renderInventoryTable();
        });

        // Inventory search & category filters
        document.getElementById("inv-search-input").addEventListener("input", renderInventoryTable);
        document.getElementById("inv-filter-category").addEventListener("change", renderInventoryTable);
        document.getElementById("inv-filter-status").addEventListener("change", renderInventoryTable);
    }

    // Load Stores dropdown
    async function loadStores() {
        try {
            const res = await fetch("/api/stores");
            const data = await res.json();
            state.storesData = data;
            
            storeSelect.innerHTML = '<option value="all">All Stores (5)</option>';
            data.forEach(s => {
                const opt = document.createElement("option");
                opt.value = s.store_id;
                opt.textContent = `${s.store_name} (${s.location})`;
                storeSelect.appendChild(opt);
            });
        } catch (err) {
            console.error("Failed to load stores:", err);
        }
    }

    // Load Dashboard Data
    async function loadDashboard() {
        try {
            const url = `/api/dashboard?store_id=${state.selectedStore}`;
            const res = await fetch(url);
            const data = await res.json();
            state.dashboardData = data;

            // Render KPIs
            document.getElementById("kpi-revenue").textContent = `$${data.total_revenue.toLocaleString('en-US', {minimumFractionDigits: 2})}`;
            document.getElementById("kpi-transactions").textContent = `${data.total_transactions.toLocaleString()} Transactions`;
            document.getElementById("kpi-units").textContent = data.total_units_sold.toLocaleString();
            document.getElementById("kpi-valuation").textContent = `$${data.total_inventory_valuation.toLocaleString('en-US', {minimumFractionDigits: 2})}`;
            document.getElementById("kpi-inv-units").textContent = `${data.total_inventory_units.toLocaleString()} Units in Stock`;

            const totalAlerts = data.critical_low_stock_count + data.warning_low_stock_count;
            document.getElementById("kpi-alerts-count").textContent = totalAlerts;
            document.getElementById("kpi-alerts-breakdown").textContent = `Critical: ${data.critical_low_stock_count} | Warning: ${data.warning_low_stock_count}`;

            // Load Attention items
            loadAttentionItems();

            // Render SVG Trend Chart
            renderSalesSVGChart(data.daily_trend);

            // Render Store Performance
            renderStorePerformanceList(data.store_performance);

            // Render Top Products
            renderTopProductsTable(data.top_products);

        } catch (err) {
            console.error("Failed to load dashboard:", err);
        }
    }

    // Load Attention Items
    async function loadAttentionItems() {
        const container = document.getElementById("attention-items-container");
        try {
            const res = await fetch("/api/alerts");
            const items = await res.json();

            if (!items || items.length === 0) {
                container.innerHTML = '<div class="att-desc">No high-priority attention items detected today. All stock levels healthy!</div>';
                return;
            }

            container.innerHTML = "";
            items.slice(0, 6).forEach(item => {
                const card = document.createElement("div");
                card.className = `attention-card ${item.severity}`;
                card.innerHTML = `
                    <div class="att-left">
                        <div class="att-title">${item.summary}</div>
                        <div class="att-desc"><strong>Action:</strong> ${item.recommended_action}</div>
                    </div>
                    <div class="att-right">
                        <span class="severity-pill ${item.severity}">${item.severity}</span>
                    </div>
                `;
                container.appendChild(card);
            });
        } catch (err) {
            container.innerHTML = '<div class="att-desc">Failed to load attention items.</div>';
        }
    }

    // Render SVG Sales Trend Chart
    function renderSalesSVGChart(trendData) {
        const container = document.getElementById("sales-chart-container");
        if (!trendData || trendData.length === 0) {
            container.innerHTML = "No trend data available.";
            return;
        }

        const width = 600;
        const height = 220;
        const padding = 30;

        const maxRev = Math.max(...trendData.map(d => d.total_revenue)) || 1000;
        const points = trendData.map((d, i) => {
            const x = padding + (i / (trendData.length - 1)) * (width - 2 * padding);
            const y = height - padding - (d.total_revenue / maxRev) * (height - 2 * padding);
            return `${x},${y}`;
        }).join(" ");

        const svgHTML = `
            <svg viewBox="0 0 ${width} ${height}" style="width: 100%; height: 100%; overflow: visible;">
                <!-- Grid Lines -->
                <line x1="${padding}" y1="${height - padding}" x2="${width - padding}" y2="${height - padding}" stroke="#374151" stroke-width="1" />
                <line x1="${padding}" y1="${padding}" x2="${width - padding}" y2="${padding}" stroke="#374151" stroke-dasharray="4" stroke-width="1" />

                <!-- Gradient Fill -->
                <defs>
                    <linearGradient id="chartGrad" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0%" stop-color="#3b82f6" stop-opacity="0.4"/>
                        <stop offset="100%" stop-color="#3b82f6" stop-opacity="0.0"/>
                    </linearGradient>
                </defs>
                <polygon points="${padding},${height - padding} ${points} ${width - padding},${height - padding}" fill="url(#chartGrad)" />

                <!-- Line -->
                <polyline fill="none" stroke="#3b82f6" stroke-width="3" points="${points}" />

                <!-- Text Labels -->
                <text x="${padding}" y="${padding - 8}" fill="#9ca3af" font-size="10">$${Math.round(maxRev).toLocaleString()}</text>
                <text x="${padding}" y="${height - 8}" fill="#9ca3af" font-size="10">${trendData[0].date}</text>
                <text x="${width - padding - 40}" y="${height - 8}" fill="#9ca3af" font-size="10">${trendData[trendData.length - 1].date}</text>
            </svg>
        `;

        container.innerHTML = svgHTML;
    }

    // Render Store Performance
    function renderStorePerformanceList(stores) {
        const container = document.getElementById("store-performance-container");
        if (!stores) return;

        const maxRev = stores[0]?.total_revenue || 1;
        container.innerHTML = stores.map(s => {
            const pct = Math.round((s.total_revenue / maxRev) * 100);
            return `
                <div class="store-item">
                    <div class="store-info">
                        <span><strong>${s.store_name}</strong> (${s.location})</span>
                        <span>$${s.total_revenue.toLocaleString('en-US', {minimumFractionDigits: 2})}</span>
                    </div>
                    <div class="progress-bar-bg">
                        <div class="progress-bar-fill" style="width: ${pct}%;"></div>
                    </div>
                </div>
            `;
        }).join("");
    }

    // Render Top Products Table
    function renderTopProductsTable(products) {
        const tbody = document.getElementById("top-products-tbody");
        if (!products) return;

        tbody.innerHTML = products.map(p => `
            <tr>
                <td><strong>${p.product_name}</strong></td>
                <td><span class="badge badge-primary">${p.category}</span></td>
                <td>${p.units_sold} units</td>
                <td><strong>$${p.revenue.toLocaleString('en-US', {minimumFractionDigits: 2})}</strong></td>
            </tr>
        `).join("");
    }

    // Load Inventory Data
    async function loadInventory() {
        try {
            const res = await fetch("/api/inventory");
            state.inventoryData = await res.json();

            // Populate category filter dropdown
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

    // Render Inventory Table with Filters
    function renderInventoryTable() {
        const tbody = document.getElementById("inventory-tbody");
        const search = document.getElementById("inv-search-input").value.toLowerCase();
        const selectedCat = document.getElementById("inv-filter-category").value;
        const selectedStatus = document.getElementById("inv-filter-status").value;

        let filtered = state.inventoryData.filter(item => {
            // Global store filter
            if (state.selectedStore !== "all" && item.store_id !== state.selectedStore) return false;
            // Search filter
            if (search && !item.product_name.toLowerCase().includes(search) && !item.category.toLowerCase().includes(search)) return false;
            // Category filter
            if (selectedCat !== "all" && item.category !== selectedCat) return false;
            // Status filter
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
                `<strong style="color: var(--accent-cyan);">+${i.recommended_reorder} units</strong>` : 
                `<span style="color: var(--text-dim);">0</span>`;

            return `
                <tr>
                    <td><strong>${i.product_name}</strong></td>
                    <td><span class="badge badge-primary">${i.category}</span></td>
                    <td>${i.store_name}</td>
                    <td><strong>${i.current_stock}</strong></td>
                    <td>${i.average_daily_sales.toFixed(1)} / day</td>
                    <td>${i.days_remaining > 900 ? '999+' : i.days_remaining} days</td>
                    <td>${statusBadge}</td>
                    <td>${reorderText}</td>
                </tr>
            `;
        }).join("");
    }

    // Load Sales Analytics Tab Data
    async function loadSalesAnalytics() {
        try {
            const res = await fetch("/api/sales");
            const data = await res.json();
            state.salesData = data;

            // Render Spikes
            const spikesContainer = document.getElementById("spikes-list-container");
            if (data.spikes && data.spikes.length > 0) {
                spikesContainer.innerHTML = data.spikes.map(s => `
                    <div class="trend-card">
                        <div>
                            <strong>${s.product_name}</strong> (${s.category})
                            <div style="font-size: 12px; color: var(--text-muted);">${s.prev_units_30d} → ${s.curr_units_30d} units</div>
                        </div>
                        <span class="badge badge-healthy">+${s.pct_change_units}%</span>
                    </div>
                `).join("");
            } else {
                spikesContainer.innerHTML = '<div style="color: var(--text-muted); font-size: 13px;">No sales spikes detected in this period.</div>';
            }

            // Render Drops
            const dropsContainer = document.getElementById("drops-list-container");
            if (data.drops && data.drops.length > 0) {
                dropsContainer.innerHTML = data.drops.map(d => `
                    <div class="trend-card">
                        <div>
                            <strong>${d.product_name}</strong> (${d.category})
                            <div style="font-size: 12px; color: var(--text-muted);">${d.prev_units_30d} → ${d.curr_units_30d} units</div>
                        </div>
                        <span class="badge badge-critical">${d.pct_change_units}%</span>
                    </div>
                `).join("");
            } else {
                dropsContainer.innerHTML = '<div style="color: var(--text-muted); font-size: 13px;">No significant sales drops detected.</div>';
            }

            // Category Cards
            const categoryGrid = document.getElementById("category-grid");
            if (data.category_performance) {
                categoryGrid.innerHTML = data.category_performance.map(c => `
                    <div class="category-card">
                        <div style="font-size: 12px; color: var(--text-muted);">${c.product_count} Products</div>
                        <div style="font-weight: 700; font-size: 15px; margin: 4px 0;">${c.category}</div>
                        <div style="color: var(--accent-blue); font-weight: 600;">$${c.total_revenue.toLocaleString('en-US', {minimumFractionDigits: 2})}</div>
                        <div style="font-size: 12px; color: var(--text-muted);">${c.total_units_sold} units sold</div>
                    </div>
                `).join("");
            }

        } catch (err) {
            console.error("Failed to load sales analytics:", err);
        }
    }

    // AI Copilot setup
    function setupCopilot() {
        const form = document.getElementById("chat-form");
        const input = document.getElementById("chat-input");
        const pills = document.querySelectorAll(".prompt-pill");

        pills.forEach(pill => {
            pill.addEventListener("click", () => {
                const prompt = pill.getAttribute("data-prompt");
                input.value = prompt;
                sendChatQuery(prompt);
            });
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

        // Append User Message
        const userMsgDiv = document.createElement("div");
        userMsgDiv.className = "chat-message user-message";
        userMsgDiv.innerHTML = `<div>${userQuery}</div>`;
        messagesContainer.appendChild(userMsgDiv);

        // Append Typing/Thinking Placeholder
        const assistantMsgDiv = document.createElement("div");
        assistantMsgDiv.className = "chat-message assistant-message";
        assistantMsgDiv.innerHTML = `
            <div class="message-header">
                <span class="assistant-avatar">🤖</span>
                <span class="assistant-name">RetailIQ Evidence Copilot</span>
            </div>
            <div class="message-content">
                <div class="loading-spinner">Evaluating query against SQLite database engine & generating grounded evidence...</div>
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
            renderCopilotResponse(assistantMsgDiv, data);

        } catch (err) {
            assistantMsgDiv.querySelector(".message-content").innerHTML = `
                <div style="color: var(--status-critical);">Error processing query. Please ensure server is running.</div>
            `;
        }
        messagesContainer.scrollTop = messagesContainer.scrollHeight;
    }

    // Render Grounded JSON Response
    function renderCopilotResponse(msgElement, data) {
        const isSufficient = data.data_sufficiency === "sufficient";
        const sufficiencyBadge = isSufficient ? 
            `<span class="sufficiency-tag sufficiency-sufficient">✔ Data Grounded & Sufficient</span>` : 
            `<span class="sufficiency-tag sufficiency-insufficient">⚠️ Data Insufficient - Cause Unverified</span>`;

        let metricsHTML = "";
        if (data.key_metrics && data.key_metrics.length > 0) {
            metricsHTML = `
                <div class="copilot-metrics-row">
                    ${data.key_metrics.map(m => `
                        <div class="copilot-metric-chip">
                            <div class="copilot-metric-label">${m.label}</div>
                            <div class="copilot-metric-val">${m.value}</div>
                        </div>
                    `).join("")}
                </div>
            `;
        }

        let recsHTML = "";
        if (data.recommendations && data.recommendations.length > 0) {
            recsHTML = `
                <div class="copilot-recommendations">
                    <h5>💡 Recommended Action Plan:</h5>
                    <ul style="padding-left: 18px;">
                        ${data.recommendations.map(r => `<li>${r}</li>`).join("")}
                    </ul>
                </div>
            `;
        }

        let evidenceHTML = "";
        if (data.evidence && data.evidence.length > 0) {
            evidenceHTML = `
                <div class="evidence-block">
                    <h5>🔍 Supporting Evidence Figures:</h5>
                    ${data.evidence.map(e => `
                        <div class="evidence-card">
                            <div><strong>Product:</strong> ${e.product_name}</div>
                            <div><strong>Store:</strong> ${e.store_name}</div>
                            <div><strong>Stock:</strong> ${e.current_stock}</div>
                            <div><strong>Avg Sales:</strong> ${e.avg_daily_sales}/day</div>
                            <div><strong>Days Left:</strong> ${e.days_remaining}</div>
                            <div><strong>Source:</strong> ${e.source}</div>
                        </div>
                    `).join("")}
                </div>
            `;
        }

        let assumptionsHTML = "";
        if (data.assumptions && data.assumptions.length > 0) {
            assumptionsHTML = `
                <div class="assumptions-pill-box">
                    <span style="font-weight:600; font-size:11px;">Assumptions Used:</span>
                    ${data.assumptions.map(a => `<span class="assumption-chip">${a}</span>`).join("")}
                </div>
            `;
        }

        msgElement.querySelector(".message-content").innerHTML = `
            ${sufficiencyBadge}
            <div style="font-size: 15px; line-height: 1.6; color: var(--text-main); font-weight: 500;">
                ${data.answer}
            </div>
            ${metricsHTML}
            ${recsHTML}
            ${evidenceHTML}
            ${assumptionsHTML}
        `;
    }
});
