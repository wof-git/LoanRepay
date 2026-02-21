import { renderDashboard } from './dashboard.js';
import { renderSchedule } from './schedule.js';
import { renderScenarios } from './scenarios.js';

const API = '/api';

const state = {
    loans: [],
    currentLoanId: null,
    currentTab: 'dashboard',
    schedule: null,
    whatIfActive: false,
    whatIfAbort: null,
    selectedScenarios: new Set(),
};

// --- API Helpers ---

async function api(path, options = {}) {
    const url = `${API}${path}`;
    const res = await fetch(url, {
        headers: { 'Content-Type': 'application/json', ...options.headers },
        ...options,
    });
    if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: res.statusText }));
        throw new Error(err.detail || 'API error');
    }
    if (res.status === 204 || res.headers.get('content-length') === '0') return null;
    const ct = res.headers.get('content-type') || '';
    if (ct.includes('json')) return res.json();
    return null;
}

async function apiJson(path, method, body) {
    return api(path, { method, body: JSON.stringify(body) });
}

// --- Toast ---

function toast(message, type = 'info') {
    const colors = { info: 'bg-blue-500', success: 'bg-green-500', error: 'bg-red-500' };
    const el = document.createElement('div');
    el.className = `toast text-white px-4 py-2 rounded-lg shadow-lg text-sm ${colors[type] || colors.info}`;
    el.textContent = message;
    document.getElementById('toast-container').appendChild(el);
    setTimeout(() => el.remove(), 3000);
}

// --- Modal ---

function showModal(html) {
    document.getElementById('modal-content').innerHTML = html;
    document.getElementById('modal-overlay').classList.remove('hidden');
}

function closeModal() {
    document.getElementById('modal-overlay').classList.add('hidden');
}

document.getElementById('modal-overlay').addEventListener('click', (e) => {
    if (e.target === e.currentTarget) closeModal();
});

// --- Formatting ---

function fmtMoney(n) {
    return '$' + Number(n).toLocaleString('en-AU', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function fmtDate(iso) {
    if (!iso) return '-';
    const d = new Date(iso + 'T00:00:00');
    return d.toLocaleDateString('en-AU', { day: '2-digit', month: '2-digit', year: '2-digit' });
}

function fmtPct(n) {
    return (n * 100).toFixed(2) + '%';
}

// --- Loan Loading ---

async function loadLoans() {
    try {
        state.loans = await api('/loans');
        renderLoanSelector();
        if (state.loans.length === 0) {
            showEmptyState();
        } else if (!state.currentLoanId) {
            selectLoan(state.loans[0].id);
        }
    } catch (e) {
        toast('Failed to load loans: ' + e.message, 'error');
    }
}

function renderLoanSelector() {
    const sel = document.getElementById('loan-selector');
    sel.innerHTML = '<option value="">Select a loan...</option>';
    state.loans.forEach(l => {
        const opt = document.createElement('option');
        opt.value = l.id;
        opt.textContent = l.name;
        if (l.id === state.currentLoanId) opt.selected = true;
        sel.appendChild(opt);
    });
}

document.getElementById('loan-selector').addEventListener('change', (e) => {
    if (e.target.value) selectLoan(parseInt(e.target.value));
});

function showEmptyState() {
    document.getElementById('empty-state').classList.remove('hidden');
    document.getElementById('tab-nav').classList.add('hidden');
    document.getElementById('summary-bar').classList.add('hidden');
    ['tab-dashboard', 'tab-schedule', 'tab-scenarios'].forEach(id =>
        document.getElementById(id).classList.add('hidden')
    );
}

function hideEmptyState() {
    document.getElementById('empty-state').classList.add('hidden');
    document.getElementById('tab-nav').classList.remove('hidden');
}

async function selectLoan(id) {
    state.currentLoanId = id;
    renderLoanSelector();
    hideEmptyState();
    await loadSchedule();
    switchTab(state.currentTab);
}

async function loadSchedule() {
    if (!state.currentLoanId) return;
    try {
        state.schedule = await api(`/loans/${state.currentLoanId}/schedule`);
        updateSummaryBar();
    } catch (e) {
        toast('Failed to load schedule: ' + e.message, 'error');
    }
}

function updateSummaryBar() {
    const s = state.schedule?.summary;
    if (!s) return;
    document.getElementById('summary-bar').classList.remove('hidden');
    document.getElementById('sum-balance').textContent = fmtMoney(s.remaining_balance);
    document.getElementById('sum-next').textContent = s.next_payment
        ? `${fmtMoney(s.next_payment.amount)} on ${fmtDate(s.next_payment.date)}`
        : 'All paid!';
    document.getElementById('sum-paid').textContent = `${s.payments_made}/${s.total_repayments} (${s.progress_pct}%)`;
    document.getElementById('sum-payoff').textContent = fmtDate(s.payoff_date);
    document.getElementById('sum-progress').style.width = `${s.progress_pct}%`;
}

// --- Tab Switching ---

function switchTab(tab) {
    state.currentTab = tab;
    document.querySelectorAll('.tab-btn').forEach(btn => {
        const isActive = btn.dataset.tab === tab;
        btn.classList.toggle('bg-white', isActive);
        btn.classList.toggle('text-blue-600', isActive);
        btn.classList.toggle('border-b-2', isActive);
        btn.classList.toggle('border-blue-600', isActive);
        btn.classList.toggle('text-gray-500', !isActive);
    });
    ['dashboard', 'schedule', 'scenarios'].forEach(t => {
        document.getElementById(`tab-${t}`).classList.toggle('hidden', t !== tab);
    });
    if (tab === 'dashboard') renderDashboard(state, { fmtMoney, fmtDate, fmtPct, api });
    if (tab === 'schedule') renderSchedule(state, { fmtMoney, fmtDate, fmtPct, api, apiJson, toast, loadSchedule, showModal, closeModal });
    if (tab === 'scenarios') renderScenarios(state, { fmtMoney, fmtDate, api, apiJson, toast, showModal, closeModal });
}

// --- Loan CRUD ---

function showCreateLoan() {
    showModal(`
        <h2 class="text-lg font-bold mb-4">Create New Loan</h2>
        <form id="create-loan-form" class="space-y-3">
            <div><label class="block text-sm text-gray-600">Name</label>
                <input name="name" required class="w-full border rounded px-3 py-1.5 text-sm" placeholder="My Home Loan"></div>
            <div class="grid grid-cols-2 gap-3">
                <div><label class="block text-sm text-gray-600">Principal ($)</label>
                    <input name="principal" type="number" step="0.01" required class="w-full border rounded px-3 py-1.5 text-sm" placeholder="30050"></div>
                <div><label class="block text-sm text-gray-600">Annual Rate (%)</label>
                    <input name="annual_rate" type="number" step="0.01" required class="w-full border rounded px-3 py-1.5 text-sm" placeholder="5.75"></div>
            </div>
            <div class="grid grid-cols-2 gap-3">
                <div><label class="block text-sm text-gray-600">Frequency</label>
                    <select name="frequency" class="w-full border rounded px-3 py-1.5 text-sm">
                        <option value="fortnightly">Fortnightly</option>
                        <option value="weekly">Weekly</option>
                        <option value="monthly">Monthly</option>
                    </select></div>
                <div><label class="block text-sm text-gray-600">Start Date</label>
                    <input name="start_date" type="date" required class="w-full border rounded px-3 py-1.5 text-sm"></div>
            </div>
            <div class="grid grid-cols-2 gap-3">
                <div><label class="block text-sm text-gray-600">Loan Term (periods)</label>
                    <input name="loan_term" type="number" required class="w-full border rounded px-3 py-1.5 text-sm" placeholder="52"></div>
                <div><label class="block text-sm text-gray-600">Fixed Repayment ($, optional)</label>
                    <input name="fixed_repayment" type="number" step="0.01" class="w-full border rounded px-3 py-1.5 text-sm" placeholder="612.39"></div>
            </div>
            <div class="flex gap-2 pt-2">
                <button type="submit" class="bg-blue-600 text-white px-4 py-1.5 rounded text-sm hover:bg-blue-700">Create Loan</button>
                <button type="button" onclick="app.closeModal()" class="text-gray-500 px-4 py-1.5 text-sm">Cancel</button>
            </div>
        </form>
    `);
    document.getElementById('create-loan-form').addEventListener('submit', async (e) => {
        e.preventDefault();
        const fd = new FormData(e.target);
        const data = {
            name: fd.get('name'),
            principal: parseFloat(fd.get('principal')),
            annual_rate: parseFloat(fd.get('annual_rate')) / 100,
            frequency: fd.get('frequency'),
            start_date: fd.get('start_date'),
            loan_term: parseInt(fd.get('loan_term')),
        };
        const fr = fd.get('fixed_repayment');
        if (fr) data.fixed_repayment = parseFloat(fr);
        try {
            const loan = await apiJson('/loans', 'POST', data);
            closeModal();
            toast('Loan created!', 'success');
            state.currentLoanId = loan.id;
            await loadLoans();
            await selectLoan(loan.id);
        } catch (e) {
            toast('Failed: ' + e.message, 'error');
        }
    });
}

function showEditLoan() {
    const loan = state.loans.find(l => l.id === state.currentLoanId);
    if (!loan) return;
    showModal(`
        <h2 class="text-lg font-bold mb-4">Edit Loan</h2>
        <form id="edit-loan-form" class="space-y-3">
            <div><label class="block text-sm text-gray-600">Name</label>
                <input name="name" value="${loan.name}" required class="w-full border rounded px-3 py-1.5 text-sm"></div>
            <div class="grid grid-cols-2 gap-3">
                <div><label class="block text-sm text-gray-600">Principal ($)</label>
                    <input name="principal" type="number" step="0.01" value="${loan.principal}" required class="w-full border rounded px-3 py-1.5 text-sm"></div>
                <div><label class="block text-sm text-gray-600">Annual Rate (%)</label>
                    <input name="annual_rate" type="number" step="0.01" value="${(loan.annual_rate * 100).toFixed(2)}" required class="w-full border rounded px-3 py-1.5 text-sm"></div>
            </div>
            <div class="grid grid-cols-2 gap-3">
                <div><label class="block text-sm text-gray-600">Frequency</label>
                    <select name="frequency" class="w-full border rounded px-3 py-1.5 text-sm">
                        <option value="weekly" ${loan.frequency === 'weekly' ? 'selected' : ''}>Weekly</option>
                        <option value="fortnightly" ${loan.frequency === 'fortnightly' ? 'selected' : ''}>Fortnightly</option>
                        <option value="monthly" ${loan.frequency === 'monthly' ? 'selected' : ''}>Monthly</option>
                    </select></div>
                <div><label class="block text-sm text-gray-600">Start Date</label>
                    <input name="start_date" type="date" value="${loan.start_date}" required class="w-full border rounded px-3 py-1.5 text-sm"></div>
            </div>
            <div class="grid grid-cols-2 gap-3">
                <div><label class="block text-sm text-gray-600">Loan Term</label>
                    <input name="loan_term" type="number" value="${loan.loan_term}" required class="w-full border rounded px-3 py-1.5 text-sm"></div>
                <div><label class="block text-sm text-gray-600">Fixed Repayment ($)</label>
                    <input name="fixed_repayment" type="number" step="0.01" value="${loan.fixed_repayment || ''}" class="w-full border rounded px-3 py-1.5 text-sm"></div>
            </div>
            <div class="flex gap-2 pt-2">
                <button type="submit" class="bg-blue-600 text-white px-4 py-1.5 rounded text-sm hover:bg-blue-700">Save</button>
                <button type="button" onclick="app.closeModal()" class="text-gray-500 px-4 py-1.5 text-sm">Cancel</button>
            </div>
        </form>
    `);
    document.getElementById('edit-loan-form').addEventListener('submit', async (e) => {
        e.preventDefault();
        const fd = new FormData(e.target);
        const data = {
            name: fd.get('name'),
            principal: parseFloat(fd.get('principal')),
            annual_rate: parseFloat(fd.get('annual_rate')) / 100,
            frequency: fd.get('frequency'),
            start_date: fd.get('start_date'),
            loan_term: parseInt(fd.get('loan_term')),
        };
        const fr = fd.get('fixed_repayment');
        data.fixed_repayment = fr ? parseFloat(fr) : null;
        try {
            await apiJson(`/loans/${state.currentLoanId}`, 'PUT', data);
            closeModal();
            toast('Loan updated!', 'success');
            await loadLoans();
            await loadSchedule();
            switchTab(state.currentTab);
        } catch (e) {
            toast('Failed: ' + e.message, 'error');
        }
    });
}

function confirmDeleteLoan() {
    showModal(`
        <h2 class="text-lg font-bold mb-4 text-red-600">Delete Loan</h2>
        <p class="text-sm text-gray-600 mb-4">This will permanently delete this loan and all its rate changes, extra repayments, paid repayments, and scenarios. This cannot be undone.</p>
        <div class="flex gap-2">
            <button onclick="app.deleteLoan()" class="bg-red-600 text-white px-4 py-1.5 rounded text-sm hover:bg-red-700">Confirm Delete</button>
            <button onclick="app.closeModal()" class="text-gray-500 px-4 py-1.5 text-sm">Cancel</button>
        </div>
    `);
}

async function deleteLoan() {
    try {
        await api(`/loans/${state.currentLoanId}`, { method: 'DELETE' });
        closeModal();
        toast('Loan deleted', 'success');
        state.currentLoanId = null;
        state.schedule = null;
        await loadLoans();
    } catch (e) {
        toast('Failed: ' + e.message, 'error');
    }
}

// --- Import ---

function showImport() {
    showModal(`
        <h2 class="text-lg font-bold mb-4">Import from Spreadsheet</h2>
        <form id="import-form" class="space-y-3">
            <div>
                <label class="block text-sm text-gray-600 mb-1">Select .xlsx file</label>
                <input type="file" name="file" accept=".xlsx" required class="w-full text-sm">
            </div>
            <div class="flex gap-2 pt-2">
                <button type="submit" class="bg-blue-600 text-white px-4 py-1.5 rounded text-sm hover:bg-blue-700">Import</button>
                <button type="button" onclick="app.closeModal()" class="text-gray-500 px-4 py-1.5 text-sm">Cancel</button>
            </div>
        </form>
    `);
    document.getElementById('import-form').addEventListener('submit', async (e) => {
        e.preventDefault();
        const fd = new FormData(e.target);
        try {
            const res = await fetch(`${API}/loans/import`, { method: 'POST', body: fd });
            if (!res.ok) {
                const err = await res.json().catch(() => ({}));
                throw new Error(err.detail || 'Import failed');
            }
            const loan = await res.json();
            closeModal();
            toast('Spreadsheet imported!', 'success');
            state.currentLoanId = loan.id;
            await loadLoans();
            await selectLoan(loan.id);
        } catch (e) {
            toast('Import failed: ' + e.message, 'error');
        }
    });
}

// --- Rename Loan ---

function startRenameLoan() {
    const loan = state.loans.find(l => l.id === state.currentLoanId);
    if (!loan) return;
    document.getElementById('loan-name-display').classList.add('hidden');
    document.querySelector('[onclick="app.startRenameLoan()"]').classList.add('hidden');
    const form = document.getElementById('loan-rename-form');
    const input = document.getElementById('loan-rename-input');
    form.classList.remove('hidden');
    input.value = loan.name;
    input.focus();
    input.select();
}

function cancelRenameLoan() {
    document.getElementById('loan-name-display').classList.remove('hidden');
    document.querySelector('[onclick="app.startRenameLoan()"]').classList.remove('hidden');
    document.getElementById('loan-rename-form').classList.add('hidden');
}

document.getElementById('loan-rename-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    const newName = document.getElementById('loan-rename-input').value.trim();
    if (!newName || !state.currentLoanId) return;
    try {
        await apiJson(`/loans/${state.currentLoanId}`, 'PUT', { name: newName });
        toast('Loan renamed!', 'success');
        cancelRenameLoan();
        await loadLoans();
        await loadSchedule();
        switchTab(state.currentTab);
    } catch (e) {
        toast('Failed: ' + e.message, 'error');
    }
});

// --- What-If ---

let whatIfDebounce = null;

function toggleWhatIf() {
    const panel = document.getElementById('whatif-panel');
    const toggle = document.getElementById('whatif-toggle');
    state.whatIfActive = panel.classList.toggle('hidden') === false;
    toggle.innerHTML = state.whatIfActive ? '&#9660; Collapse' : '&#9654; Expand';
    if (state.whatIfActive && state.schedule) {
        const loan = state.loans.find(l => l.id === state.currentLoanId);
        const repayment = loan?.fixed_repayment || state.schedule.rows[0]?.calculated_pmt || 500;
        document.getElementById('whatif-slider').value = repayment;
        document.getElementById('whatif-repayment').value = repayment;
    }
}

function onWhatIfChange() {
    const src = document.activeElement?.id;
    if (src === 'whatif-slider') {
        document.getElementById('whatif-repayment').value = document.getElementById('whatif-slider').value;
    } else if (src === 'whatif-repayment') {
        document.getElementById('whatif-slider').value = document.getElementById('whatif-repayment').value;
    }
    clearTimeout(whatIfDebounce);
    whatIfDebounce = setTimeout(() => runWhatIf(), 300);
}

async function runWhatIf() {
    if (!state.currentLoanId) return;
    if (state.whatIfAbort) state.whatIfAbort.abort();
    state.whatIfAbort = new AbortController();

    const body = {};
    const rep = parseFloat(document.getElementById('whatif-repayment').value);
    if (rep > 0) body.fixed_repayment = rep;

    const rateDate = document.getElementById('whatif-rate-date').value;
    const rateVal = parseFloat(document.getElementById('whatif-rate-value').value);
    if (rateDate && rateVal > 0) {
        body.rate_changes = [{ effective_date: rateDate, annual_rate: rateVal / 100 }];
    }

    const extraDate = document.getElementById('whatif-extra-date').value;
    const extraAmt = parseFloat(document.getElementById('whatif-extra-amount').value);
    if (extraDate && extraAmt > 0) {
        body.extra_repayments = [{ payment_date: extraDate, amount: extraAmt }];
    }

    try {
        const res = await fetch(`${API}/loans/${state.currentLoanId}/schedule/whatif`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body),
            signal: state.whatIfAbort.signal,
        });
        if (!res.ok) throw new Error('What-if failed');
        const whatIfSchedule = await res.json();
        showWhatIfDelta(whatIfSchedule);
        renderSchedule(
            { ...state, schedule: whatIfSchedule },
            { fmtMoney, fmtDate, fmtPct, api, apiJson, toast, loadSchedule, showModal, closeModal },
            true
        );
    } catch (e) {
        if (e.name !== 'AbortError') toast('What-if error: ' + e.message, 'error');
    }
}

function showWhatIfDelta(whatIfSchedule) {
    const base = state.schedule?.summary;
    const wi = whatIfSchedule.summary;
    if (!base || !wi) return;

    const interestSaved = base.total_interest - wi.total_interest;
    const repDiff = base.total_repayments - wi.total_repayments;
    const banner = document.getElementById('delta-banner');

    if (Math.abs(interestSaved) < 0.01 && repDiff === 0) {
        banner.classList.add('hidden');
        return;
    }

    const parts = [];
    if (interestSaved > 0) parts.push(`Saves ${fmtMoney(interestSaved)} interest`);
    if (interestSaved < 0) parts.push(`Costs ${fmtMoney(Math.abs(interestSaved))} more interest`);
    if (repDiff > 0) parts.push(`Pays off ${repDiff} payments earlier`);
    if (repDiff < 0) parts.push(`Takes ${Math.abs(repDiff)} more payments`);

    banner.textContent = parts.join(' | ');
    banner.classList.remove('hidden');
    banner.className = `delta-banner rounded px-3 py-2 text-sm ${interestSaved >= 0 ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'}`;
}

async function applyWhatIf() {
    const rep = parseFloat(document.getElementById('whatif-repayment').value);
    if (!rep || !state.currentLoanId) return;
    try {
        await apiJson(`/loans/${state.currentLoanId}`, 'PUT', { fixed_repayment: rep });
        toast('Repayment amount updated!', 'success');
        await loadLoans();
        await loadSchedule();
        switchTab('schedule');
    } catch (e) {
        toast('Failed: ' + e.message, 'error');
    }
}

async function saveWhatIfScenario() {
    showModal(`
        <h2 class="text-lg font-bold mb-4">Save Scenario</h2>
        <form id="save-scenario-form" class="space-y-3">
            <div><label class="block text-sm text-gray-600">Scenario Name</label>
                <input name="scenario_name" required class="w-full border rounded px-3 py-1.5 text-sm" placeholder="Pay $700/fortnight"></div>
            <div><label class="block text-sm text-gray-600">Description (optional)</label>
                <textarea name="description" class="w-full border rounded px-3 py-1.5 text-sm" rows="2"></textarea></div>
            <div class="flex gap-2 pt-2">
                <button type="submit" class="bg-blue-600 text-white px-4 py-1.5 rounded text-sm hover:bg-blue-700">Save</button>
                <button type="button" onclick="app.closeModal()" class="text-gray-500 px-4 py-1.5 text-sm">Cancel</button>
            </div>
        </form>
    `);
    document.getElementById('save-scenario-form').addEventListener('submit', async (e) => {
        e.preventDefault();
        const fd = new FormData(e.target);
        try {
            await apiJson(`/loans/${state.currentLoanId}/scenarios`, 'POST', {
                name: fd.get('scenario_name'),
                description: fd.get('description') || null,
            });
            closeModal();
            toast('Scenario saved!', 'success');
        } catch (e) {
            toast('Failed: ' + e.message, 'error');
        }
    });
}

function resetWhatIf() {
    document.getElementById('whatif-repayment').value = '';
    document.getElementById('whatif-slider').value = 500;
    document.getElementById('whatif-rate-date').value = '';
    document.getElementById('whatif-rate-value').value = '';
    document.getElementById('whatif-extra-date').value = '';
    document.getElementById('whatif-extra-amount').value = '';
    document.getElementById('whatif-target-date').value = '';
    document.getElementById('payoff-result').textContent = '';
    document.getElementById('delta-banner').classList.add('hidden');
    if (state.schedule) {
        renderSchedule(state, { fmtMoney, fmtDate, fmtPct, api, apiJson, toast, loadSchedule, showModal, closeModal });
    }
}

async function calcPayoffTarget() {
    const targetDate = document.getElementById('whatif-target-date').value;
    if (!targetDate || !state.currentLoanId) return;
    try {
        const result = await api(`/loans/${state.currentLoanId}/payoff-target?date=${targetDate}`);
        document.getElementById('payoff-result').textContent =
            `Need ${fmtMoney(result.required_repayment)} per fortnight (${result.num_repayments} payments, ${fmtMoney(result.total_interest)} interest)`;
    } catch (e) {
        document.getElementById('payoff-result').textContent = e.message;
    }
}

// --- Rate Changes ---

function showAddRateChange() {
    showModal(`
        <h2 class="text-lg font-bold mb-4">Add Rate Change</h2>
        <form id="add-rate-form" class="space-y-3">
            <div><label class="block text-sm text-gray-600">Effective Date</label>
                <input name="rate_date" type="date" required class="w-full border rounded px-3 py-1.5 text-sm"></div>
            <div><label class="block text-sm text-gray-600">New Rate (%)</label>
                <input name="new_rate" type="number" step="0.01" required class="w-full border rounded px-3 py-1.5 text-sm" placeholder="6.0"></div>
            <div><label class="block text-sm text-gray-600">Note (optional)</label>
                <input name="note" class="w-full border rounded px-3 py-1.5 text-sm" placeholder="RBA rate change"></div>
            <div class="flex gap-2 pt-2">
                <button type="submit" class="bg-blue-600 text-white px-4 py-1.5 rounded text-sm hover:bg-blue-700">Save</button>
                <button type="button" onclick="app.closeModal()" class="text-gray-500 px-4 py-1.5 text-sm">Cancel</button>
            </div>
        </form>
    `);
    document.getElementById('add-rate-form').addEventListener('submit', async (e) => {
        e.preventDefault();
        const fd = new FormData(e.target);
        try {
            await apiJson(`/loans/${state.currentLoanId}/rates`, 'POST', {
                effective_date: fd.get('rate_date'),
                annual_rate: parseFloat(fd.get('new_rate')) / 100,
                note: fd.get('note') || null,
            });
            closeModal();
            toast('Rate change added!', 'success');
            await loadSchedule();
            switchTab('schedule');
        } catch (e) {
            toast('Failed: ' + e.message, 'error');
        }
    });
}

async function deleteRateChange(id) {
    try {
        await api(`/loans/${state.currentLoanId}/rates/${id}`, { method: 'DELETE' });
        toast('Rate change removed', 'success');
        await loadSchedule();
        switchTab('schedule');
    } catch (e) {
        toast('Failed: ' + e.message, 'error');
    }
}

// --- Extra Repayments ---

function showAddExtra() {
    showModal(`
        <h2 class="text-lg font-bold mb-4">Add Extra Repayment</h2>
        <form id="add-extra-form" class="space-y-3">
            <div><label class="block text-sm text-gray-600">Payment Date</label>
                <input name="payment_date" type="date" required class="w-full border rounded px-3 py-1.5 text-sm"></div>
            <div><label class="block text-sm text-gray-600">Amount ($)</label>
                <input name="amount" type="number" step="0.01" required class="w-full border rounded px-3 py-1.5 text-sm" placeholder="5000"></div>
            <div><label class="block text-sm text-gray-600">Note (optional)</label>
                <input name="note" class="w-full border rounded px-3 py-1.5 text-sm" placeholder="Tax refund"></div>
            <div class="flex gap-2 pt-2">
                <button type="submit" class="bg-blue-600 text-white px-4 py-1.5 rounded text-sm hover:bg-blue-700">Save</button>
                <button type="button" onclick="app.closeModal()" class="text-gray-500 px-4 py-1.5 text-sm">Cancel</button>
            </div>
        </form>
    `);
    document.getElementById('add-extra-form').addEventListener('submit', async (e) => {
        e.preventDefault();
        const fd = new FormData(e.target);
        try {
            await apiJson(`/loans/${state.currentLoanId}/extras`, 'POST', {
                payment_date: fd.get('payment_date'),
                amount: parseFloat(fd.get('amount')),
                note: fd.get('note') || null,
            });
            closeModal();
            toast('Extra repayment added!', 'success');
            await loadSchedule();
            switchTab('schedule');
        } catch (e) {
            toast('Failed: ' + e.message, 'error');
        }
    });
}

async function deleteExtra(id) {
    try {
        await api(`/loans/${state.currentLoanId}/extras/${id}`, { method: 'DELETE' });
        toast('Extra repayment removed', 'success');
        await loadSchedule();
        switchTab('schedule');
    } catch (e) {
        toast('Failed: ' + e.message, 'error');
    }
}

// --- Scenarios ---

async function compareSelected() {
    if (state.selectedScenarios.size < 2) {
        toast('Select at least 2 scenarios to compare', 'error');
        return;
    }
    const ids = [...state.selectedScenarios].join(',');
    try {
        const data = await api(`/loans/${state.currentLoanId}/scenarios/compare?ids=${ids}`);
        renderScenarios(state, { fmtMoney, fmtDate, api, apiJson, toast, showModal, closeModal }, data);
    } catch (e) {
        toast('Failed: ' + e.message, 'error');
    }
}

// --- Toggle Paid ---

async function _togglePaid(num, checked) {
    if (!state.currentLoanId) return;
    try {
        if (checked) {
            await fetch(`${API}/loans/${state.currentLoanId}/paid/${num}`, { method: 'POST' });
        } else {
            await fetch(`${API}/loans/${state.currentLoanId}/paid/${num}`, { method: 'DELETE' });
        }
        await loadSchedule();
        switchTab('schedule');
    } catch (e) {
        toast('Failed to update: ' + e.message, 'error');
    }
}

// --- Export ---

function exportSchedule(format) {
    if (!state.currentLoanId) return;
    window.open(`${API}/loans/${state.currentLoanId}/export?format=${format}`, '_blank');
}

// --- Global Exports ---

window.app = {
    switchTab, showCreateLoan, showEditLoan, confirmDeleteLoan, deleteLoan,
    showImport, closeModal, startRenameLoan, cancelRenameLoan,
    toggleWhatIf, onWhatIfChange, applyWhatIf,
    saveWhatIfScenario, resetWhatIf, calcPayoffTarget,
    showAddRateChange, deleteRateChange, showAddExtra, deleteExtra,
    compareSelected, exportSchedule, _togglePaid,
    // State access for child modules
    get state() { return state; },
    fmtMoney, fmtDate, fmtPct, api, apiJson, toast, loadSchedule,
};

// --- Init ---
loadLoans();
