/**
 * Trading Platform - Frontend Application Logic
 * Includes settings panel for runtime broker/LLM configuration.
 */

const API = '';
let currentState = null;
let selectedLLMProvider = 'openai';

// ── Data Fetching ────────────────────────────────────────────
async function fetchJSON(url, opts = {}) {
    try {
        const resp = await fetch(API + url, opts);
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        return await resp.json();
    } catch (e) {
        console.error(`Fetch error ${url}:`, e);
        return null;
    }
}

async function refreshDashboard() {
    const refreshBtn = document.querySelector('.btn-outline');
    if (refreshBtn) refreshBtn.style.opacity = '0.5';

    const [state, risk] = await Promise.all([
        fetchJSON('/api/dashboard/state'),
        fetchJSON('/api/trading/risk-status'),
    ]);

    if (state) {
        currentState = state;
        renderStats(state);
        renderBrokerStatus(state.broker_status);
        renderMode(state.trading_mode, state.active_market);
        renderPositions(state.positions);
        renderRegime(state.market_regime);
        renderStrategies(state.active_strategies);
        renderCandidates(state.candidate_strategies);
        renderOrders(state.recent_orders);
        fetchWatchlist(state.active_market);
    }

    if (risk) renderRiskControls(risk);

    // Check config and show alert if needed
    checkConfigStatus();

    const lastRefreshEl = document.getElementById('last-refresh');
    if (lastRefreshEl) {
        lastRefreshEl.textContent = `Last updated: ${new Date().toLocaleTimeString()}`;
    }
    if (refreshBtn) refreshBtn.style.opacity = '1';
}

// ── Renderers ────────────────────────────────────────────────
function renderStats(s) {
    const pnlEl = document.getElementById('stat-pnl');
    const pnl = s.todays_pnl || 0;
    if (pnlEl) {
        pnlEl.textContent = `₹${pnl.toLocaleString('en-IN', {minimumFractionDigits:2})}`;
        pnlEl.className = `stat-value ${pnl >= 0 ? 'pnl-positive' : 'pnl-negative'}`;
    }
    const pnlSubEl = document.getElementById('stat-pnl-sub');
    if (pnlSubEl) pnlSubEl.textContent = `${s.trading_mode} mode active`;

    const posEl = document.getElementById('stat-positions');
    if (posEl) posEl.textContent = (s.positions || []).length;

    const stratEl = document.getElementById('stat-strategies');
    if (stratEl) stratEl.textContent = (s.active_strategies || []).length;

    const fundsEl = document.getElementById('stat-funds');
    if (fundsEl) {
        const bal = s.funds?.available_balance || 0;
        fundsEl.textContent = `₹${bal.toLocaleString('en-IN', {minimumFractionDigits:2})}`;
    }
}

function renderBrokerStatus(bs) {
    const dot = document.getElementById('broker-dot');
    const label = document.getElementById('broker-label');
    if (!dot || !label) return;
    if (bs?.connected) {
        dot.className = 'status-dot connected';
        label.textContent = `Dhan Connected (${bs.client_id || '—'})`;
    } else {
        dot.className = 'status-dot disconnected';
        label.textContent = 'Dhan Disconnected';
    }
}

function renderMode(mode, market) {
    const paper = document.getElementById('mode-paper');
    const live = document.getElementById('mode-live');
    const badge = document.getElementById('pos-mode-badge');
    if (!paper || !live || !badge) return;
    paper.className = mode === 'paper' ? 'mode-btn active-paper' : 'mode-btn';
    live.className = mode === 'live' ? 'mode-btn active-live' : 'mode-btn';
    
    let badgeText = mode.toUpperCase();
    if (market) {
        if (market === 'CRYPTO') badgeText += ' (CRYPTO)';
        else if (market === 'US_EQ') badgeText += ' (US)';
        else if (market === 'GLOBAL_EQ') badgeText += ' (GLOBAL)';
        else badgeText += ' (IN)';
        
        const wlBadge = document.getElementById('watchlist-market-badge');
        if (wlBadge) wlBadge.textContent = market;
        
        const marketSelector = document.getElementById('market-selector');
        if (marketSelector) {
            marketSelector.value = market;
            // Disable market selector in live mode for now (only paper supports everything easily without broker change)
            marketSelector.disabled = mode === 'live';
        }
    }
    
    badge.textContent = badgeText;
    badge.className = `card-badge ${mode === 'paper' ? 'badge-green' : 'badge-red'}`;
}

function renderPositions(positions) {
    const body = document.getElementById('positions-body');
    if (!body) return;
    if (!positions || positions.length === 0) {
        body.innerHTML = '<div class="empty-state"><div class="icon">📭</div>No open positions</div>';
        return;
    }
    let html = `<div class="data-table-container"><table class="data-table">
        <thead><tr><th>Symbol</th><th>Qty</th><th>Avg Price</th><th>LTP</th><th>P&L</th></tr></thead><tbody>`;
    for (const p of positions) {
        const pnl = p.pnl || 0;
        const pnlClass = pnl >= 0 ? 'pnl-positive' : 'pnl-negative';
        html += `<tr>
            <td style="color:var(--text-primary);font-weight:700">${p.trading_symbol}</td>
            <td>${p.quantity}</td><td>₹${(p.avg_price||0).toFixed(2)}</td>
            <td>₹${(p.ltp||0).toFixed(2)}</td>
            <td class="${pnlClass}" style="font-weight:700">₹${pnl.toFixed(2)}</td></tr>`;
    }
    html += '</tbody></table></div>';
    body.innerHTML = html;
}

const REGIME_MAP = {
    trending_up: { icon: '📈', cls: 'up', desc: 'Market showing sustained upward momentum' },
    trending_down: { icon: '📉', cls: 'down', desc: 'Market showing sustained downward pressure' },
    range_bound: { icon: '📊', cls: 'range', desc: 'Market trading within a defined range' },
    high_volatility: { icon: '🌪️', cls: 'volatile', desc: 'Elevated volatility — increased risk' },
    event_risk: { icon: '⚡', cls: 'event', desc: 'Event-driven risk — RBI, Budget, Elections, etc.' },
};

function renderRegime(regime) {
    const r = REGIME_MAP[regime] || REGIME_MAP.range_bound;
    const iconEl = document.querySelector('.regime-icon');
    const nameEl = document.getElementById('regime-name');
    const descEl = document.getElementById('regime-desc');
    if (iconEl) { iconEl.textContent = r.icon; iconEl.className = `regime-icon ${r.cls}`; }
    if (nameEl) nameEl.textContent = regime.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
    if (descEl) descEl.textContent = r.desc;
}

function renderStrategies(strategies) {
    const body = document.getElementById('strategies-body');
    if (!body) return;
    if (!strategies || strategies.length === 0) {
        body.innerHTML = '<div class="empty-state"><div class="icon">🔌</div>No strategies loaded. Add plugins to /plugins directory.</div>';
        return;
    }
    let html = '<div class="strategy-list">';
    for (const s of strategies) {
        const statusCls = s.status === 'active' ? 'badge-green' : s.status === 'approved' ? 'badge-accent' : 'badge-amber';
        html += `<div class="strategy-item"><div class="strategy-info">
            <div class="strategy-name">${s.name}</div>
            <div class="strategy-tags">
                ${(s.tags||[]).map(t => `<span class="tag">${t}</span>`).join('')}
                <span class="tag">${s.timeframe || '1d'}</span>
            </div>
            <div style="margin-top: 8px; display: flex; gap: 6px; align-items: center;">
                <button class="btn btn-outline" style="padding: 3px 8px; font-size: 0.65rem;" onclick="updateStrategyStocks('${s.name}', 'gainers')">📈 Top Gainers</button>
                <button class="btn btn-outline" style="padding: 3px 8px; font-size: 0.65rem;" onclick="updateStrategyStocks('${s.name}', 'losers')">📉 Top Losers</button>
                <button class="btn btn-outline" style="padding: 3px 8px; font-size: 0.65rem;" onclick="updateStrategyStocks('${s.name}', 'custom')">✏️ Custom</button>
            </div>
            </div><span class="card-badge ${statusCls}">${s.status}</span></div>`;
    }
    html += '</div>';
    body.innerHTML = html;
}

function renderCandidates(candidates) {
    const body = document.getElementById('candidates-body');
    if (!body) return;
    if (!candidates || candidates.length === 0) {
        body.innerHTML = '<div class="empty-state"><div class="icon">🌐</div>Click "Search GitHub" to discover trading strategies</div>';
        return;
    }
    let html = '';
    for (const c of candidates) {
        const pct = Math.round((c.relevance_score || 0) * 100);
        html += `<div class="candidate-item">
            <div class="candidate-header">
                <div class="candidate-name"><a href="${c.repo_url}" target="_blank" rel="noopener">${c.repo_name}</a></div>
                <span class="stars">⭐ ${c.stars}</span>
            </div>
            <div class="candidate-desc">${c.description || 'No description available'}</div>
            <div class="relevance-bar"><div class="relevance-fill" style="width:${pct}%"></div></div>
            <div style="display:flex;justify-content:space-between;align-items:center;margin-top:8px;">
                <span style="font-size:0.75rem;color:var(--text-muted)">Match: ${pct}% ${c.indian_market_compatible ? '🇮🇳' : ''}</span>
                <span class="card-badge badge-amber">${c.status}</span>
            </div></div>`;
    }
    body.innerHTML = html;
}

function renderOrders(orders) {
    const body = document.getElementById('orders-body');
    if (!body) return;
    if (!orders || orders.length === 0) {
        body.innerHTML = '<div class="empty-state"><div class="icon">📃</div>No orders yet</div>';
        return;
    }
    let html = `<div class="data-table-container"><table class="data-table">
        <thead><tr><th>Order ID</th><th>Symbol</th><th>Side</th><th>Qty</th><th>Price</th><th>Status</th><th>Time</th></tr></thead><tbody>`;
    for (const o of orders) {
        const sideColor = o.order_side === 'BUY' ? 'var(--green)' : 'var(--red)';
        html += `<tr>
            <td style="font-size:0.75rem;opacity:0.6">${(o.order_id||'').substring(0,12)}</td>
            <td style="color:var(--text-primary);font-weight:700">${o.trading_symbol}</td>
            <td style="color:${sideColor};font-weight:800">${o.order_side}</td>
            <td>${o.quantity}</td><td>₹${(o.price||0).toFixed(2)}</td>
            <td><span class="card-badge ${o.status==='FILLED'?'badge-green':o.status==='REJECTED'?'badge-red':'badge-amber'}">${o.status}</span></td>
            <td style="font-size:0.75rem">${o.timestamp ? new Date(o.timestamp).toLocaleTimeString() : '—'}</td></tr>`;
    }
    html += '</tbody></table></div>';
    body.innerHTML = html;
}

function renderRiskControls(r) {
    document.getElementById('risk-maxloss').textContent = `₹${(r.max_loss_per_day||0).toLocaleString('en-IN')}`;
    document.getElementById('risk-maxorder').textContent = `₹${(r.max_order_size||0).toLocaleString('en-IN')}`;
    document.getElementById('risk-maxpos').textContent = r.max_open_positions || '—';
    document.getElementById('risk-hours').textContent = r.trading_hours || '—';
    document.getElementById('risk-cooldown').textContent = `${r.cooldown_seconds || 0}s`;
    document.getElementById('risk-sl').textContent = `${r.mandatory_sl_pct || 0}%`;
}

// ── Dashboard Actions ────────────────────────────────────────
async function switchMode(mode) {
    await fetchJSON(`/api/trading/mode/${mode}`, { method: 'POST' });
    await refreshDashboard();
}

async function switchMarket(market) {
    const resp = await fetchJSON(`/api/trading/market/${market}`, { method: 'POST' });
    if (resp && resp.market) {
        showToast(`Switched market to ${resp.market}`, 'success');
    }
    await refreshDashboard();
}

async function loadStrategies() {
    await fetchJSON('/api/strategies/load', { method: 'POST' });
    await refreshDashboard();
}

async function searchStrategies() {
    const body = document.getElementById('candidates-body');
    if (body) body.innerHTML = '<div class="empty-state"><div class="icon">⏳</div>Searching GitHub repositories…</div>';
    await fetchJSON('/api/discovery/search', {
        method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify({})
    });
    await refreshDashboard();
}


async function updateStrategyStocks(pluginName, type) {
    let payload = {};
    if (type === 'gainers' || type === 'losers') {
        payload.scan_market = type;
        payload.scan_count = 5;
        showToast(`Fetching Top ${type} from NSE...`);
    } else if (type === 'custom') {
        const symbols = prompt("Enter stock symbols separated by commas (e.g. RELIANCE, TCS, INFY):");
        if (!symbols) return;
        payload.symbols = symbols.split(',').map(s => s.trim().toUpperCase());
    }
    
    const resp = await fetchJSON(`/api/strategies/${pluginName}/symbols`, {
        method: 'POST', 
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(payload)
    });
    
    if (resp && resp.status === 'success') {
        showToast(resp.message, 'success');
        refreshDashboard();
    } else {
        showToast(resp?.message || 'Failed to update stocks', 'error');
    }
}


// ══════════════════════════════════════════════════════════════
// SETTINGS PANEL
// ══════════════════════════════════════════════════════════════

function toggleSettingsPanel() {
    const panel = document.getElementById('settings-panel');
    const overlay = document.getElementById('settings-overlay');
    const isOpen = panel.classList.contains('open');
    if (isOpen) {
        panel.classList.remove('open');
        overlay.classList.remove('open');
    } else {
        panel.classList.add('open');
        overlay.classList.add('open');
        loadSettingsData();
    }
}

function switchSettingsTab(btn, tabId) {
    document.querySelectorAll('.settings-tab').forEach(t => t.classList.remove('active'));
    document.querySelectorAll('.settings-tab-content').forEach(t => t.classList.remove('active'));
    btn.classList.add('active');
    document.getElementById(tabId).classList.add('active');
}

function togglePasswordVisibility(inputId, btn) {
    const input = document.getElementById(inputId);
    if (input.type === 'password') {
        input.type = 'text';
        btn.textContent = '🔒';
    } else {
        input.type = 'password';
        btn.textContent = '👁️';
    }
}

function showFeedback(elementId, type, message) {
    const el = document.getElementById(elementId);
    if (!el) return;
    el.className = `form-feedback ${type}`;
    el.textContent = message;
    if (type !== 'loading') {
        setTimeout(() => { el.className = 'form-feedback'; el.textContent = ''; }, 6000);
    }
}

function showToast(message, type = 'info') {
    const container = document.getElementById('toast-container');
    if (!container) return;
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.textContent = message;
    container.appendChild(toast);
    setTimeout(() => {
        toast.classList.add('fade-out');
        setTimeout(() => toast.remove(), 300);
    }, 3500);
}

// ── Load Settings Data ────────────────────────────────────────
async function loadSettingsData() {
    const summary = await fetchJSON('/api/settings/summary');
    if (!summary) return;

    // Broker
    const clientIdInput = document.getElementById('input-dhan-client-id');
    if (clientIdInput && summary.broker.dhan_client_id) {
        clientIdInput.placeholder = summary.broker.dhan_client_id || 'Enter Client ID';
    }
    const hintToken = document.getElementById('hint-dhan-token');
    if (hintToken && summary.broker.dhan_access_token_masked) {
        hintToken.textContent = `Current: ${summary.broker.dhan_access_token_masked}`;
    }
    const brokerStatus = document.getElementById('broker-config-status');
    if (brokerStatus) {
        if (summary.broker.dhan_access_token_set) {
            brokerStatus.textContent = 'Configured';
            brokerStatus.className = 'config-status configured';
        } else {
            brokerStatus.textContent = 'Not configured';
            brokerStatus.className = 'config-status';
        }
    }

    // LLM
    selectedLLMProvider = summary.llm.active_llm || 'openai';
    highlightSelectedProvider(selectedLLMProvider);
    showProviderConfig(selectedLLMProvider);

    // Set hints for existing keys
    const hintOpenai = document.getElementById('hint-openai-key');
    if (hintOpenai && summary.llm.openai.key_masked) hintOpenai.textContent = `Current: ${summary.llm.openai.key_masked}`;
    const hintAnthropic = document.getElementById('hint-anthropic-key');
    if (hintAnthropic && summary.llm.anthropic.key_masked) hintAnthropic.textContent = `Current: ${summary.llm.anthropic.key_masked}`;
    const hintGemini = document.getElementById('hint-gemini-key');
    if (hintGemini && summary.llm.gemini.key_masked) hintGemini.textContent = `Current: ${summary.llm.gemini.key_masked}`;

    // Set model selects
    setSelectValue('input-openai-model', summary.llm.openai.model);
    setSelectValue('input-anthropic-model', summary.llm.anthropic.model);
    setSelectValue('input-gemini-model', summary.llm.gemini.model);
    setInputValue('input-ollama-host', summary.llm.ollama.host);
    setInputValue('input-ollama-model', summary.llm.ollama.model);

    const llmStatus = document.getElementById('llm-config-status');
    if (llmStatus) {
        const providerInfo = summary.llm[selectedLLMProvider];
        const isConfigured = selectedLLMProvider === 'ollama' || (providerInfo && providerInfo.key_set);
        llmStatus.textContent = isConfigured ? `${selectedLLMProvider} active` : 'Not configured';
        llmStatus.className = isConfigured ? 'config-status configured' : 'config-status';
    }

    // GitHub
    const hintGithub = document.getElementById('hint-github-token');
    if (hintGithub && summary.github_token_masked) hintGithub.textContent = `Current: ${summary.github_token_masked}`;

    // Risk — load current values
    const risk = await fetchJSON('/api/trading/risk-status');
    if (risk) {
        setInputValue('input-max-loss', risk.max_loss_per_day);
        setInputValue('input-max-order', risk.max_order_size);
        setInputValue('input-max-positions', risk.max_open_positions);
        setInputValue('input-cooldown', risk.cooldown_seconds);
        setInputValue('input-stop-loss', risk.mandatory_sl_pct);
        if (risk.trading_hours) {
            const parts = risk.trading_hours.split(' - ');
            if (parts.length === 2) {
                setInputValue('input-trading-start', parts[0].trim());
                setInputValue('input-trading-end', parts[1].trim());
            }
        }
    }
}

function setSelectValue(id, val) {
    const el = document.getElementById(id);
    if (el && val) {
        // If value exists in options, select it; otherwise add it
        const exists = Array.from(el.options).some(o => o.value === val);
        if (exists) { el.value = val; }
        else { const opt = new Option(val, val, true, true); el.add(opt); }
    }
}

function setInputValue(id, val) {
    const el = document.getElementById(id);
    if (el && val !== undefined && val !== null) el.value = val;
}

// ── LLM Provider Selection ───────────────────────────────────
function selectLLMProvider(provider) {
    selectedLLMProvider = provider;
    highlightSelectedProvider(provider);
    showProviderConfig(provider);
}

function highlightSelectedProvider(provider) {
    document.querySelectorAll('.llm-provider-card').forEach(card => {
        card.classList.toggle('selected', card.dataset.provider === provider);
    });
}

function showProviderConfig(provider) {
    ['openai', 'anthropic', 'gemini', 'ollama'].forEach(p => {
        const panel = document.getElementById(`config-${p}`);
        if (panel) panel.style.display = (p === provider) ? 'block' : 'none';
    });
}

// ── Save Handlers ────────────────────────────────────────────
async function saveBrokerConfig() {
    const clientId = document.getElementById('input-dhan-client-id').value.trim();
    const token = document.getElementById('input-dhan-access-token').value.trim();
    if (!clientId && !token) {
        showFeedback('broker-feedback', 'error', 'Please enter at least one field to update.');
        return;
    }
    showFeedback('broker-feedback', 'loading', 'Saving broker config…');
    const payload = {};
    if (clientId) payload.dhan_client_id = clientId;
    if (token) payload.dhan_access_token = token;
    const resp = await fetchJSON('/api/settings/broker', {
        method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify(payload)
    });
    if (resp) {
        showFeedback('broker-feedback', 'success', `✅ Broker config saved! Client ID: ${resp.dhan_client_id}`);
        showToast('Broker credentials updated', 'success');
        document.getElementById('input-dhan-client-id').value = '';
        document.getElementById('input-dhan-access-token').value = '';
        refreshDashboard();
    } else {
        showFeedback('broker-feedback', 'error', '❌ Failed to save. Check console for details.');
    }
}

async function testBrokerConnection() {
    showFeedback('broker-feedback', 'loading', '🔌 Testing broker connection…');
    const resp = await fetchJSON('/api/settings/broker/test', { method: 'POST' });
    if (resp?.success) {
        showFeedback('broker-feedback', 'success', `✅ ${resp.message}`);
        showToast('Broker connected!', 'success');
    } else {
        showFeedback('broker-feedback', 'error', `❌ ${resp?.message || 'Connection test failed'}`);
        showToast('Broker connection failed', 'error');
    }
    refreshDashboard();
}

async function saveLLMConfig() {
    showFeedback('llm-feedback', 'loading', 'Saving LLM config…');
    const payload = { active_llm: selectedLLMProvider };

    // Gather provider-specific fields
    const openaiKey = document.getElementById('input-openai-key').value.trim();
    if (openaiKey) payload.openai_api_key = openaiKey;
    payload.openai_model = document.getElementById('input-openai-model').value;

    const anthropicKey = document.getElementById('input-anthropic-key').value.trim();
    if (anthropicKey) payload.anthropic_api_key = anthropicKey;
    payload.anthropic_model = document.getElementById('input-anthropic-model').value;

    const geminiKey = document.getElementById('input-gemini-key').value.trim();
    if (geminiKey) payload.gemini_api_key = geminiKey;
    payload.gemini_model = document.getElementById('input-gemini-model').value;

    payload.ollama_host = document.getElementById('input-ollama-host').value.trim() || undefined;
    payload.ollama_model = document.getElementById('input-ollama-model').value.trim() || undefined;

    const resp = await fetchJSON('/api/settings/llm', {
        method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify(payload)
    });
    if (resp) {
        showFeedback('llm-feedback', 'success', `✅ LLM switched to ${resp.active_llm}. Config saved!`);
        showToast(`LLM provider: ${resp.active_llm}`, 'success');
        // Clear key inputs after save
        ['input-openai-key','input-anthropic-key','input-gemini-key'].forEach(id => {
            document.getElementById(id).value = '';
        });
        loadSettingsData();
    } else {
        showFeedback('llm-feedback', 'error', '❌ Failed to save LLM config.');
    }
}

async function testLLMConnection() {
    showFeedback('llm-feedback', 'loading', `🔌 Testing ${selectedLLMProvider} connection…`);
    const resp = await fetchJSON('/api/settings/llm/test', { method: 'POST' });
    if (resp?.success) {
        showFeedback('llm-feedback', 'success', `✅ ${resp.message}`);
        showToast(`${resp.provider} is healthy!`, 'success');
    } else {
        showFeedback('llm-feedback', 'error', `❌ ${resp?.message || 'LLM test failed'}`);
        showToast('LLM connection failed', 'error');
    }
}

async function saveRiskConfig() {
    showFeedback('risk-feedback', 'loading', 'Saving risk controls…');
    const payload = {};
    const fields = [
        ['input-max-loss', 'max_loss_per_day', parseFloat],
        ['input-max-order', 'max_order_size', parseFloat],
        ['input-max-positions', 'max_open_positions', parseInt],
        ['input-cooldown', 'cooldown_between_trades_seconds', parseInt],
        ['input-stop-loss', 'mandatory_stop_loss_percent', parseFloat],
        ['input-trading-start', 'allowed_trading_start', String],
        ['input-trading-end', 'allowed_trading_end', String],
    ];
    for (const [id, key, parser] of fields) {
        const val = document.getElementById(id)?.value?.trim();
        if (val) payload[key] = parser(val);
    }
    const resp = await fetchJSON('/api/settings/risk', {
        method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify(payload)
    });
    if (resp) {
        showFeedback('risk-feedback', 'success', '✅ Risk controls updated!');
        showToast('Risk controls saved', 'success');
        refreshDashboard();
    } else {
        showFeedback('risk-feedback', 'error', '❌ Failed to save risk controls.');
    }
}

async function saveGithubConfig() {
    const token = document.getElementById('input-github-token').value.trim();
    if (!token) { showFeedback('github-feedback', 'error', 'Please enter a token.'); return; }
    showFeedback('github-feedback', 'loading', 'Saving…');
    const resp = await fetchJSON('/api/settings/github', {
        method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify({ github_token: token })
    });
    if (resp) {
        showFeedback('github-feedback', 'success', '✅ GitHub token saved!');
        showToast('GitHub token updated', 'success');
        document.getElementById('input-github-token').value = '';
        loadSettingsData();
    } else {
        showFeedback('github-feedback', 'error', '❌ Failed to save.');
    }
}

// ── Config Status Check ──────────────────────────────────────
async function checkConfigStatus() {
    const summary = await fetchJSON('/api/settings/summary');
    if (!summary) return;
    const brokerOk = summary.broker.dhan_access_token_set;
    const llmOk = (summary.llm.active_llm === 'ollama') ||
        (summary.llm[summary.llm.active_llm] && summary.llm[summary.llm.active_llm].key_set);

    const alert = document.getElementById('config-alert');
    const msg = document.getElementById('config-alert-message');
    if (!alert) return;

    const issues = [];
    if (!brokerOk) issues.push('Broker credentials');
    if (!llmOk) issues.push('LLM API key');
    if (issues.length > 0) {
        msg.textContent = `Configure your ${issues.join(' and ')} to start trading.`;
        alert.style.display = 'block';
    } else {
        alert.style.display = 'none';
    }
}

// ── Keyboard Shortcuts ───────────────────────────────────────
document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
        const panel = document.getElementById('settings-panel');
        if (panel && panel.classList.contains('open')) toggleSettingsPanel();
    }
});

// ── Watchlist & Quick Trade ──────────────────────────────────
async function fetchWatchlist(market) {
    const wlBody = document.getElementById('watchlist-body');
    if (!wlBody) return;
    
    const data = await fetchJSON(`/api/broker/watchlist?market=${market}`);
    if (!data || !data.watchlist || data.watchlist.length === 0) {
        wlBody.innerHTML = '<div class="empty-state"><div class="icon">📭</div>No watchlist items</div>';
        return;
    }
    
    let html = `<div class="data-table-container"><table class="data-table">
        <thead><tr><th>Symbol</th><th>Name</th><th style="text-align:right">LTP</th></tr></thead><tbody>`;
    for (const item of data.watchlist) {
        const symbolText = item.symbol;
        const priceText = item.ltp > 0 ? `₹${item.ltp.toLocaleString('en-IN', {minimumFractionDigits:2})}` : 'Loading...';
        html += `<tr style="cursor: pointer;" onclick="selectWatchlistSymbol('${item.symbol}')">
            <td style="color:var(--cyan);font-weight:700">${symbolText}</td>
            <td style="font-size:0.8rem;color:var(--text-secondary)">${item.name}</td>
            <td style="font-weight:700;text-align:right;color:var(--text-primary)">${priceText}</td>
        </tr>`;
    }
    html += '</tbody></table></div>';
    wlBody.innerHTML = html;
}

function selectWatchlistSymbol(symbol) {
    const tradeSymbolEl = document.getElementById('trade-symbol');
    if (tradeSymbolEl) {
        tradeSymbolEl.value = symbol;
        showToast(`Selected ${symbol} for trading`, 'info');
    }
}

async function placeQuickOrder(side) {
    const symbolEl = document.getElementById('trade-symbol');
    const qtyEl = document.getElementById('trade-qty');
    const priceEl = document.getElementById('trade-price');
    const feedbackEl = document.getElementById('quick-trade-feedback');
    
    if (!symbolEl || !qtyEl || !feedbackEl) return;
    
    const symbol = symbolEl.value.trim().toUpperCase();
    const qty = parseFloat(qtyEl.value);
    const price = priceEl && priceEl.value ? parseFloat(priceEl.value) : 0.0;
    
    if (!symbol) {
        showFeedbackQuickTrade('error', 'Please enter a valid symbol.');
        return;
    }
    if (isNaN(qty) || qty <= 0) {
        showFeedbackQuickTrade('error', 'Please enter a valid quantity.');
        return;
    }
    
    showFeedbackQuickTrade('loading', `Executing ${side} order for ${symbol}...`);
    
    // Determine active segment
    let segment = "NSE_EQ";
    if (currentState && currentState.active_market) {
        segment = currentState.active_market;
    }
    
    const orderRequest = {
        trading_symbol: symbol,
        exchange_segment: segment,
        security_id: symbol,
        order_side: side,
        order_type: price > 0 ? "LIMIT" : "MARKET",
        product_type: "DELIVERY",
        quantity: qty,
        price: price,
        trigger_price: 0.0,
        tag: "quick_trade"
    };
    
    const resp = await fetchJSON('/api/trading/order', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(orderRequest)
    });
    
    if (resp && resp.status === 'FILLED') {
        showFeedbackQuickTrade('success', `✅ Order FILLED! ID: ${resp.order_id}`);
        showToast(`${side} order for ${symbol} filled!`, 'success');
        refreshDashboard();
    } else if (resp && resp.status === 'REJECTED') {
        showFeedbackQuickTrade('error', `❌ Rejected: ${resp.message}`);
        showToast(`Order rejected: ${resp.message}`, 'error');
    } else if (resp) {
        showFeedbackQuickTrade('success', `✅ Order placed: ${resp.status}`);
        refreshDashboard();
    } else {
        showFeedbackQuickTrade('error', '❌ Failed to place order.');
    }
}

function showFeedbackQuickTrade(type, message) {
    const el = document.getElementById('quick-trade-feedback');
    if (!el) return;
    el.className = `form-feedback ${type}`;
    el.textContent = message;
    if (type !== 'loading') {
        setTimeout(() => { el.className = 'form-feedback'; el.textContent = ''; }, 6000);
    }
}

// ── Init ─────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
    refreshDashboard();
    setInterval(refreshDashboard, 15000);
});
