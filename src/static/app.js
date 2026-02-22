import { renderDashboard } from './dashboard.js';
import { renderSchedule } from './schedule.js';
import { renderScenarios } from './scenarios.js';

const API = '/api';

const state = {
    loans: [],
    currentLoanId: null,
    currentLoan: null,
    currentTab: 'dashboard',
    schedule: null,
    whatIfActive: false,
    whatIfAbort: null,
    scheduleAbort: null,
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

document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') closeModal();
});

// --- Formatting ---

function fmtMoney(n) {
    if (n == null || isNaN(n)) return '$0.00';
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

function escapeHtml(str) {
    if (str == null) return '';
    return String(str)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
}

// --- PMT Calculation ---

function calcPMT(principal, annualRatePct, frequency, loanTerm) {
    const ppy = frequency === 'weekly' ? 52 : frequency === 'fortnightly' ? 26 : 12;
    const r = (annualRatePct / 100) / ppy;
    const n = loanTerm;
    if (n <= 0 || principal <= 0) return null;
    if (Math.abs(r) < 1e-12) return Math.round(principal / n * 100) / 100;
    const payment = principal * r * Math.pow(1 + r, n) / (Math.pow(1 + r, n) - 1);
    return Math.round(payment * 100) / 100;
}

function _calcAndFillRepayment(formId) {
    const form = document.getElementById(formId);
    const principal = parseFloat(form.querySelector('[name="principal"]').value);
    const rate = parseFloat(form.querySelector('[name="annual_rate"]').value);
    const frequency = form.querySelector('[name="frequency"]').value;
    const term = parseInt(form.querySelector('[name="loan_term"]').value, 10);
    if (!principal || !rate || !frequency || !term) {
        toast('Fill in principal, rate, frequency, and term first', 'error');
        return;
    }
    const pmt = calcPMT(principal, rate, frequency, term);
    if (pmt) {
        form.querySelector('[name="fixed_repayment"]').value = pmt.toFixed(2);
    }
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
    if (e.target.value) selectLoan(parseInt(e.target.value, 10));
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
    // Abort any in-flight what-if and clear debounce
    if (state.whatIfAbort) state.whatIfAbort.abort();
    clearTimeout(whatIfDebounce);
    // Abort previous schedule load
    if (state.scheduleAbort) state.scheduleAbort.abort();
    await loadSchedule();
    switchTab(state.currentTab);
}

async function loadSchedule() {
    if (!state.currentLoanId) return;
    if (state.scheduleAbort) state.scheduleAbort.abort();
    state.scheduleAbort = new AbortController();
    try {
        const opts = { signal: state.scheduleAbort.signal };
        const [schedule, loan] = await Promise.all([
            api(`/loans/${state.currentLoanId}/schedule`, opts),
            api(`/loans/${state.currentLoanId}`, opts),
        ]);
        state.schedule = schedule;
        state.currentLoan = loan;
        updateSummaryBar();
    } catch (e) {
        if (e.name === 'AbortError') return;
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
    // Clean up what-if state on tab switch
    if (state.whatIfAbort) state.whatIfAbort.abort();
    clearTimeout(whatIfDebounce);
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
    if (tab === 'dashboard') renderDashboard(state, { fmtMoney, fmtDate, fmtPct, escapeHtml });
    if (tab === 'schedule') renderSchedule(state, { fmtMoney, fmtDate, fmtPct, escapeHtml, api, apiJson, toast, loadSchedule, showModal, closeModal });
    if (tab === 'scenarios') renderScenarios(state, { fmtMoney, fmtDate, escapeHtml, api, apiJson, toast, showModal, closeModal });
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
                <div><label class="block text-sm text-gray-600">Fixed Repayment ($)</label>
                    <div class="flex gap-1">
                        <input name="fixed_repayment" type="number" step="0.01" class="w-full border rounded px-3 py-1.5 text-sm" placeholder="Auto-calc">
                        <button type="button" onclick="app._calcAndFillRepayment('create-loan-form')" class="bg-gray-200 hover:bg-gray-300 px-2 py-1.5 rounded text-xs font-medium whitespace-nowrap" title="Calculate PMT from principal, rate, frequency and term">Calc</button>
                    </div></div>
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
            loan_term: parseInt(fd.get('loan_term'), 10),
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
                <input name="name" value="${escapeHtml(loan.name)}" required class="w-full border rounded px-3 py-1.5 text-sm"></div>
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
                    <div class="flex gap-1">
                        <input name="fixed_repayment" type="number" step="0.01" value="${loan.fixed_repayment || ''}" class="w-full border rounded px-3 py-1.5 text-sm">
                        <button type="button" onclick="app._calcAndFillRepayment('edit-loan-form')" class="bg-gray-200 hover:bg-gray-300 px-2 py-1.5 rounded text-xs font-medium whitespace-nowrap" title="Calculate PMT from principal, rate, frequency and term">Calc</button>
                    </div></div>
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
            loan_term: parseInt(fd.get('loan_term'), 10),
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

        // Dynamic slider range
        const slider = document.getElementById('whatif-slider');
        slider.min = Math.max(Math.floor(repayment * 0.5 / 10) * 10, 50);
        slider.max = Math.ceil(repayment * 2.5 / 10) * 10;
        slider.step = 1;
        slider.value = repayment;
        document.getElementById('whatif-repayment').value = repayment;

        // Context labels
        const freq = loan?.frequency || 'fortnightly';
        document.getElementById('whatif-current-repayment').textContent = `Current: ${fmtMoney(repayment)}/${freq}`;
        document.getElementById('whatif-current-rate').textContent = `Current rate: ${((loan?.annual_rate || 0) * 100).toFixed(2)}%`;

        // Hide impact section on fresh open
        document.getElementById('whatif-impact').classList.add('hidden');
    }
}

function onWhatIfChange(source) {
    if (source === 'slider') {
        document.getElementById('whatif-repayment').value = document.getElementById('whatif-slider').value;
    } else if (source === 'repayment') {
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
        body.additional_rate_changes = [{ effective_date: rateDate, annual_rate: rateVal / 100 }];
    }

    const extraDate = document.getElementById('whatif-extra-date').value;
    const extraAmt = parseFloat(document.getElementById('whatif-extra-amount').value);
    if (extraDate && extraAmt > 0) {
        body.additional_extra_repayments = [{ payment_date: extraDate, amount: extraAmt }];
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
            { fmtMoney, fmtDate, fmtPct, escapeHtml, api, apiJson, toast, loadSchedule, showModal, closeModal },
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
        document.getElementById('whatif-impact').classList.add('hidden');
        return;
    }

    // Delta banner
    const parts = [];
    if (interestSaved > 0) parts.push(`Saves ${fmtMoney(interestSaved)} interest`);
    if (interestSaved < 0) parts.push(`Costs ${fmtMoney(Math.abs(interestSaved))} more interest`);
    if (repDiff > 0) parts.push(`Pays off ${repDiff} payments earlier`);
    if (repDiff < 0) parts.push(`Takes ${Math.abs(repDiff)} more payments`);

    banner.textContent = parts.join(' | ');
    banner.classList.remove('hidden');
    banner.className = `delta-banner rounded px-3 py-2 text-sm ${interestSaved >= 0 ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'}`;

    // Impact comparison cards
    const impact = document.getElementById('whatif-impact');
    impact.classList.remove('hidden');

    document.getElementById('impact-base-interest').textContent = fmtMoney(base.total_interest);
    document.getElementById('impact-base-payments').textContent = base.total_repayments;
    document.getElementById('impact-base-payoff').textContent = fmtDate(base.payoff_date);
    document.getElementById('impact-base-total').textContent = fmtMoney(base.total_paid);

    const wiInterestEl = document.getElementById('impact-wi-interest');
    const wiPaymentsEl = document.getElementById('impact-wi-payments');
    const wiPayoffEl = document.getElementById('impact-wi-payoff');
    const wiTotalEl = document.getElementById('impact-wi-total');

    wiInterestEl.textContent = fmtMoney(wi.total_interest);
    wiPaymentsEl.textContent = wi.total_repayments;
    wiPayoffEl.textContent = fmtDate(wi.payoff_date);
    wiTotalEl.textContent = fmtMoney(wi.total_paid);

    // Color code improvements vs regressions
    wiInterestEl.className = `font-medium ${interestSaved > 0 ? 'text-green-600' : interestSaved < 0 ? 'text-red-600' : ''}`;
    wiPaymentsEl.className = `font-medium ${repDiff > 0 ? 'text-green-600' : repDiff < 0 ? 'text-red-600' : ''}`;
}

function applyWhatIf() {
    const rep = parseFloat(document.getElementById('whatif-repayment').value);
    if (!rep || !state.currentLoanId) return;
    const loan = state.loans.find(l => l.id === state.currentLoanId);
    const currentRep = loan?.fixed_repayment || state.schedule?.rows[0]?.calculated_pmt || 0;
    showModal(`
        <h2 class="text-lg font-bold mb-4 text-amber-600">Apply Repayment to Loan</h2>
        <p class="text-sm text-gray-600 mb-2">This will permanently change the loan's fixed repayment amount:</p>
        <p class="text-sm mb-1"><span class="text-gray-500">Current:</span> <strong>${fmtMoney(currentRep)}</strong></p>
        <p class="text-sm mb-3"><span class="text-gray-500">New:</span> <strong>${fmtMoney(rep)}</strong></p>
        <p class="text-xs text-amber-600 mb-4">Only the repayment amount is applied. Rate changes and lump sums from the what-if panel are not saved to the loan.</p>
        <div class="flex gap-2">
            <button onclick="app._confirmApplyWhatIf(${rep})" class="bg-amber-500 text-white px-4 py-1.5 rounded text-sm hover:bg-amber-600">Confirm</button>
            <button onclick="app.closeModal()" class="text-gray-500 px-4 py-1.5 text-sm">Cancel</button>
        </div>
    `);
}

async function _confirmApplyWhatIf(rep) {
    try {
        await apiJson(`/loans/${state.currentLoanId}`, 'PUT', { fixed_repayment: rep });
        closeModal();
        toast('Repayment amount updated!', 'success');
        await loadLoans();
        await loadSchedule();
        switchTab('schedule');
    } catch (e) {
        toast('Failed: ' + e.message, 'error');
    }
}

async function saveWhatIfScenario() {
    const loan = state.loans.find(l => l.id === state.currentLoanId);
    const loanRepayment = loan?.fixed_repayment;
    const calcPmt = state.schedule?.rows[0]?.calculated_pmt;
    const currentRep = loanRepayment || calcPmt || 0;

    // Gather what-if params
    const whatIfParams = {};
    const includes = [];

    const sliderRep = parseFloat(document.getElementById('whatif-repayment').value);
    if (sliderRep > 0 && Math.abs(sliderRep - currentRep) > 0.5) {
        whatIfParams.whatif_fixed_repayment = sliderRep;
        includes.push(`Repayment ${fmtMoney(sliderRep)}`);
    } else if (sliderRep > 0 && loanRepayment === null) {
        // No fixed repayment on loan — any slider value counts
        whatIfParams.whatif_fixed_repayment = sliderRep;
        includes.push(`Repayment ${fmtMoney(sliderRep)}`);
    }

    const rateDate = document.getElementById('whatif-rate-date').value;
    const rateVal = parseFloat(document.getElementById('whatif-rate-value').value);
    if (rateDate && rateVal > 0) {
        whatIfParams.whatif_additional_rate_changes = [{ effective_date: rateDate, annual_rate: rateVal / 100 }];
        includes.push(`Rate ${rateVal}% from ${fmtDate(rateDate)}`);
    }

    const extraDate = document.getElementById('whatif-extra-date').value;
    const extraAmt = parseFloat(document.getElementById('whatif-extra-amount').value);
    if (extraDate && extraAmt > 0) {
        whatIfParams.whatif_additional_extra_repayments = [{ payment_date: extraDate, amount: extraAmt }];
        includes.push(`Lump sum ${fmtMoney(extraAmt)} on ${fmtDate(extraDate)}`);
    }

    const includesHtml = includes.length > 0
        ? `<div class="bg-indigo-50 border border-indigo-200 rounded p-2 mb-3"><p class="text-xs font-medium text-indigo-700 mb-1">Includes:</p><ul class="text-xs text-indigo-600 list-disc list-inside">${includes.map(i => `<li>${escapeHtml(i)}</li>`).join('')}</ul></div>`
        : '<p class="text-xs text-gray-400 mb-3">No what-if adjustments — base state will be saved.</p>';

    const autoDesc = includes.length > 0 ? includes.join('; ') : '';

    showModal(`
        <h2 class="text-lg font-bold mb-4">Save as Scenario</h2>
        ${includesHtml}
        <form id="save-scenario-form" class="space-y-3">
            <div><label class="block text-sm text-gray-600">Scenario Name</label>
                <input name="scenario_name" required class="w-full border rounded px-3 py-1.5 text-sm" placeholder="Pay $700/fortnight"></div>
            <div><label class="block text-sm text-gray-600">Description (optional)</label>
                <textarea name="description" class="w-full border rounded px-3 py-1.5 text-sm" rows="2">${autoDesc}</textarea></div>
            <div class="flex gap-2 pt-2">
                <button type="submit" class="bg-indigo-600 text-white px-4 py-1.5 rounded text-sm hover:bg-indigo-700">Save</button>
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
                ...whatIfParams,
            });
            closeModal();
            toast('Scenario saved!', 'success');
        } catch (e) {
            toast('Failed: ' + e.message, 'error');
        }
    });
}

function resetWhatIf() {
    const loan = state.loans.find(l => l.id === state.currentLoanId);
    const repayment = loan?.fixed_repayment || state.schedule?.rows[0]?.calculated_pmt || 500;
    document.getElementById('whatif-repayment').value = repayment;
    document.getElementById('whatif-slider').value = repayment;
    document.getElementById('whatif-rate-date').value = '';
    document.getElementById('whatif-rate-value').value = '';
    document.getElementById('whatif-extra-date').value = '';
    document.getElementById('whatif-extra-amount').value = '';
    document.getElementById('whatif-target-date').value = '';
    document.getElementById('payoff-result').textContent = '';
    document.getElementById('delta-banner').classList.add('hidden');
    document.getElementById('whatif-impact').classList.add('hidden');
    if (state.schedule) {
        renderSchedule(state, { fmtMoney, fmtDate, fmtPct, escapeHtml, api, apiJson, toast, loadSchedule, showModal, closeModal });
    }
}

async function calcPayoffTarget() {
    const targetDate = document.getElementById('whatif-target-date').value;
    if (!targetDate || !state.currentLoanId) return;
    try {
        const result = await api(`/loans/${state.currentLoanId}/payoff-target?date=${encodeURIComponent(targetDate)}`);
        const loan = state.loans.find(l => l.id === state.currentLoanId);
        const freqLabel = loan?.frequency === 'weekly' ? 'per week' : loan?.frequency === 'monthly' ? 'per month' : 'per fortnight';
        document.getElementById('payoff-result').textContent =
            `Need ${fmtMoney(result.required_repayment)} ${freqLabel} (${result.num_repayments} payments, ${fmtMoney(result.total_interest)} interest)`;
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
            <div id="rate-preview-area"></div>
            <div id="rate-form-buttons" class="flex gap-2 pt-2">
                <button type="button" id="rate-preview-btn" class="bg-blue-600 text-white px-4 py-1.5 rounded text-sm hover:bg-blue-700">Preview Impact</button>
                <button type="button" onclick="app.closeModal()" class="text-gray-500 px-4 py-1.5 text-sm">Cancel</button>
            </div>
        </form>
    `);

    document.getElementById('rate-preview-btn').addEventListener('click', async () => {
        const form = document.getElementById('add-rate-form');
        if (!form.reportValidity()) return;

        const fd = new FormData(form);
        const rateDate = fd.get('rate_date');
        const newRate = parseFloat(fd.get('new_rate')) / 100;
        const note = fd.get('note') || null;

        try {
            const preview = await apiJson(
                `/loans/${state.currentLoanId}/rates/preview`, 'POST',
                { effective_date: rateDate, annual_rate: newRate, note }
            );
            _showRatePreviewStep(preview, rateDate, newRate, note);
        } catch (e) {
            toast('Preview failed: ' + e.message, 'error');
        }
    });
}

function _showRatePreviewStep(preview, rateDate, newRate, note) {
    const area = document.getElementById('rate-preview-area');
    const buttons = document.getElementById('rate-form-buttons');

    // Disable inputs (step 1 is done)
    document.querySelectorAll('#add-rate-form input').forEach(el => el.disabled = true);
    document.getElementById('rate-preview-btn').classList.add('hidden');

    if (!preview.has_fixed_repayment || preview.options.length === 1) {
        // No choice needed — single option confirmation
        const opt = preview.options[0];
        area.innerHTML = `
            <div class="bg-gray-50 border rounded p-3 mt-2">
                <p class="text-sm font-medium mb-1">${escapeHtml(opt.label)}</p>
                <p class="text-xs text-gray-600">Payoff: ${fmtDate(opt.payoff_date)} | Interest: ${fmtMoney(opt.total_interest)} | Payments: ${opt.num_repayments}</p>
                ${opt.interest_delta !== 0 ? `<p class="text-xs mt-1 ${opt.interest_delta > 0 ? 'text-red-600' : 'text-green-600'}">${opt.interest_delta > 0 ? '+' : ''}${fmtMoney(opt.interest_delta)} interest</p>` : ''}
            </div>
        `;
        buttons.innerHTML = `
            <button type="button" id="rate-confirm-btn" class="bg-blue-600 text-white px-4 py-1.5 rounded text-sm hover:bg-blue-700">Confirm & Save</button>
            <button type="button" onclick="app.closeModal()" class="text-gray-500 px-4 py-1.5 text-sm">Cancel</button>
        `;
        document.getElementById('rate-confirm-btn').addEventListener('click', () =>
            _saveRateChange(rateDate, newRate, note, null)
        );
        return;
    }

    // Two options — show radio cards
    let cardsHtml = '<div class="space-y-2 mt-2">';
    preview.options.forEach((opt, i) => {
        const deltaClass = opt.interest_delta > 0 ? 'text-red-600' : opt.interest_delta < 0 ? 'text-green-600' : 'text-gray-600';
        const deltaText = opt.interest_delta !== 0
            ? `${opt.interest_delta > 0 ? '+' : ''}${fmtMoney(opt.interest_delta)} interest`
            : 'No change in interest';
        const repDeltaText = opt.repayment_delta !== 0
            ? ` | ${opt.repayment_delta > 0 ? '+' : ''}${opt.repayment_delta} payments`
            : '';
        cardsHtml += `
            <label class="block border rounded p-3 cursor-pointer hover:bg-blue-50 ${i === 0 ? 'border-blue-500 bg-blue-50' : ''}">
                <input type="radio" name="rate_option" value="${i}" ${i === 0 ? 'checked' : ''} class="mr-2">
                <span class="text-sm font-medium">${escapeHtml(opt.label)}</span>
                <p class="text-xs text-gray-600 ml-5">Payoff: ${fmtDate(opt.payoff_date)} | Interest: ${fmtMoney(opt.total_interest)} | Payments: ${opt.num_repayments}</p>
                <p class="text-xs ml-5 ${deltaClass}">${deltaText}${repDeltaText}</p>
            </label>
        `;
    });
    cardsHtml += '</div>';
    area.innerHTML = cardsHtml;

    // Highlight selected card
    area.querySelectorAll('input[name="rate_option"]').forEach(radio => {
        radio.addEventListener('change', () => {
            area.querySelectorAll('label').forEach(l => {
                l.classList.remove('border-blue-500', 'bg-blue-50');
            });
            radio.closest('label').classList.add('border-blue-500', 'bg-blue-50');
        });
    });

    buttons.innerHTML = `
        <button type="button" id="rate-confirm-btn" class="bg-blue-600 text-white px-4 py-1.5 rounded text-sm hover:bg-blue-700">Confirm & Save</button>
        <button type="button" onclick="app.closeModal()" class="text-gray-500 px-4 py-1.5 text-sm">Cancel</button>
    `;

    document.getElementById('rate-confirm-btn').addEventListener('click', () => {
        const selected = parseInt(document.querySelector('input[name="rate_option"]:checked').value, 10);
        const chosenOpt = preview.options[selected];
        // If user chose option B (adjust repayment), store it on the rate change
        const adjustedRepayment = (selected > 0 && chosenOpt.fixed_repayment !== preview.current_repayment)
            ? chosenOpt.fixed_repayment : null;
        _saveRateChange(rateDate, newRate, note, adjustedRepayment);
    });
}

async function _saveRateChange(rateDate, newRate, note, adjustedRepayment) {
    try {
        const body = {
            effective_date: rateDate,
            annual_rate: newRate,
            note: note,
        };
        if (adjustedRepayment != null) body.adjusted_repayment = adjustedRepayment;
        await apiJson(`/loans/${state.currentLoanId}/rates`, 'POST', body);
        closeModal();
        toast('Rate change added!', 'success');
        await loadLoans();
        await loadSchedule();
        switchTab('schedule');
    } catch (e) {
        toast('Failed: ' + e.message, 'error');
    }
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

// --- Repayment Changes ---

function showAddRepaymentChange() {
    showModal(`
        <h2 class="text-lg font-bold mb-4">Add Repayment Change</h2>
        <p class="text-xs text-gray-500 mb-3">Set a new fixed repayment amount from a specific date. The "additional" column in the schedule will show the difference from the minimum calculated payment.</p>
        <form id="add-repayment-change-form" class="space-y-3">
            <div><label class="block text-sm text-gray-600">Effective Date</label>
                <input name="effective_date" type="date" required class="w-full border rounded px-3 py-1.5 text-sm"></div>
            <div><label class="block text-sm text-gray-600">New Repayment Amount ($)</label>
                <input name="amount" type="number" step="0.01" required class="w-full border rounded px-3 py-1.5 text-sm" placeholder="700.00"></div>
            <div><label class="block text-sm text-gray-600">Note (optional)</label>
                <input name="note" class="w-full border rounded px-3 py-1.5 text-sm" placeholder="Increased repayment"></div>
            <div id="repayment-preview-area"></div>
            <div id="repayment-form-buttons" class="flex gap-2 pt-2">
                <button type="button" id="repayment-preview-btn" class="bg-blue-600 text-white px-4 py-1.5 rounded text-sm hover:bg-blue-700">Preview Impact</button>
                <button type="button" onclick="app.closeModal()" class="text-gray-500 px-4 py-1.5 text-sm">Cancel</button>
            </div>
        </form>
    `);

    document.getElementById('repayment-preview-btn').addEventListener('click', async () => {
        const form = document.getElementById('add-repayment-change-form');
        if (!form.reportValidity()) return;

        const fd = new FormData(form);
        const effectiveDate = fd.get('effective_date');
        const amount = parseFloat(fd.get('amount'));
        const note = fd.get('note') || null;

        try {
            const preview = await apiJson(
                `/loans/${state.currentLoanId}/repayment-changes/preview`, 'POST',
                { effective_date: effectiveDate, amount, note }
            );
            _showRepaymentPreviewStep(preview, effectiveDate, amount, note);
        } catch (e) {
            toast('Preview failed: ' + e.message, 'error');
        }
    });
}

function _showRepaymentPreviewStep(preview, effectiveDate, amount, note) {
    const area = document.getElementById('repayment-preview-area');
    const buttons = document.getElementById('repayment-form-buttons');

    // Disable inputs (step 1 is done)
    document.querySelectorAll('#add-repayment-change-form input').forEach(el => el.disabled = true);
    document.getElementById('repayment-preview-btn').classList.add('hidden');

    const interestDelta = preview.interest_delta;
    const repDelta = preview.repayment_delta;

    const parts = [];
    if (interestDelta < 0) parts.push(`<span class="text-green-600 font-medium">Save ${fmtMoney(Math.abs(interestDelta))} interest</span>`);
    if (interestDelta > 0) parts.push(`<span class="text-red-600 font-medium">+${fmtMoney(interestDelta)} more interest</span>`);
    if (repDelta < 0) parts.push(`<span class="text-green-600 font-medium">${Math.abs(repDelta)} fewer payments</span>`);
    if (repDelta > 0) parts.push(`<span class="text-red-600 font-medium">${repDelta} more payments</span>`);
    if (parts.length === 0) parts.push('<span class="text-gray-500">No significant change</span>');

    area.innerHTML = `
        <div class="bg-gray-50 border rounded p-3 mt-2 space-y-1">
            <p class="text-sm font-medium">Impact Preview</p>
            <p class="text-xs text-gray-600">Payoff: ${fmtDate(preview.current_payoff_date)} → ${fmtDate(preview.new_payoff_date)}</p>
            <p class="text-xs text-gray-600">Interest: ${fmtMoney(preview.current_total_interest)} → ${fmtMoney(preview.new_total_interest)}</p>
            <p class="text-xs text-gray-600">Payments: ${preview.current_num_repayments} → ${preview.new_num_repayments}</p>
            <p class="text-sm mt-1">${parts.join(' | ')}</p>
        </div>
    `;

    buttons.innerHTML = `
        <button type="button" id="repayment-confirm-btn" class="bg-blue-600 text-white px-4 py-1.5 rounded text-sm hover:bg-blue-700">Confirm & Save</button>
        <button type="button" onclick="app.closeModal()" class="text-gray-500 px-4 py-1.5 text-sm">Cancel</button>
    `;

    document.getElementById('repayment-confirm-btn').addEventListener('click', () =>
        _saveRepaymentChange(effectiveDate, amount, note)
    );
}

async function _saveRepaymentChange(effectiveDate, amount, note) {
    try {
        await apiJson(`/loans/${state.currentLoanId}/repayment-changes`, 'POST', {
            effective_date: effectiveDate,
            amount,
            note,
        });
        closeModal();
        toast('Repayment change added!', 'success');
        await loadSchedule();
        switchTab('schedule');
    } catch (e) {
        toast('Failed: ' + e.message, 'error');
    }
}

async function deleteRepaymentChange(id) {
    try {
        await api(`/loans/${state.currentLoanId}/repayment-changes/${id}`, { method: 'DELETE' });
        toast('Repayment change removed', 'success');
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
        const data = await api(`/loans/${state.currentLoanId}/scenarios/compare?ids=${encodeURIComponent(ids)}`);
        renderScenarios(state, { fmtMoney, fmtDate, escapeHtml, api, apiJson, toast, showModal, closeModal }, data);
    } catch (e) {
        toast('Failed: ' + e.message, 'error');
    }
}

// --- Toggle Paid ---

async function _togglePaid(num, checked) {
    if (!state.currentLoanId) return;
    try {
        await api(`/loans/${state.currentLoanId}/paid/${num}`, { method: checked ? 'POST' : 'DELETE' });
        await loadSchedule();
        switchTab('schedule');
    } catch (e) {
        toast('Failed to update: ' + e.message, 'error');
    }
}

// --- Export ---

function exportSchedule(format) {
    if (!state.currentLoanId) return;
    window.open(`${API}/loans/${state.currentLoanId}/export?format=${encodeURIComponent(format)}`, '_blank');
}

// --- Scenario Helpers ---

function _toggleScenario(id, checked) {
    if (checked) {
        state.selectedScenarios.add(id);
    } else {
        state.selectedScenarios.delete(id);
    }
    document.getElementById('btn-compare').classList.toggle('hidden', state.selectedScenarios.size < 2);
}

async function _deleteScenario(id) {
    try {
        await api(`/loans/${state.currentLoanId}/scenarios/${id}`, { method: 'DELETE' });
        state.selectedScenarios.delete(id);
        toast('Scenario deleted', 'success');
        switchTab('scenarios');
    } catch (e) {
        toast('Failed: ' + e.message, 'error');
    }
}

// --- Global Exports ---

window.app = {
    switchTab, showCreateLoan, showEditLoan, confirmDeleteLoan, deleteLoan,
    closeModal, startRenameLoan, cancelRenameLoan,
    toggleWhatIf, applyWhatIf, _confirmApplyWhatIf,
    saveWhatIfScenario, resetWhatIf, calcPayoffTarget,
    showAddRateChange, deleteRateChange,
    showAddRepaymentChange, deleteRepaymentChange,
    showAddExtra, deleteExtra,
    compareSelected, exportSchedule, _togglePaid, _calcAndFillRepayment,
    _toggleScenario, _deleteScenario,
};

// --- Init ---

// Bind what-if inputs via addEventListener (Safari ignores inline oninput on range inputs with custom CSS)
document.getElementById('whatif-slider').addEventListener('input', () => onWhatIfChange('slider'));
document.getElementById('whatif-slider').addEventListener('change', () => onWhatIfChange('slider'));
document.getElementById('whatif-repayment').addEventListener('input', () => onWhatIfChange('repayment'));
document.getElementById('whatif-rate-date').addEventListener('change', () => onWhatIfChange());
document.getElementById('whatif-rate-value').addEventListener('input', () => onWhatIfChange());
document.getElementById('whatif-extra-date').addEventListener('change', () => onWhatIfChange());
document.getElementById('whatif-extra-amount').addEventListener('input', () => onWhatIfChange());

loadLoans();
