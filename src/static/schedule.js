export function renderSchedule(state, helpers, isWhatIf = false) {
    const { fmtMoney, fmtDate, fmtPct } = helpers;
    const s = state.schedule;
    if (!s) return;

    const today = new Date().toISOString().split('T')[0];

    // Use loan from state (loaded by app.js) instead of fetching via API
    const loan = state.currentLoan;
    if (loan) {
        renderRateChanges(loan, state, helpers);
        renderRepaymentChanges(loan, state, helpers);
        renderExtras(loan, state, helpers);
    }

    // Group rows by year
    const yearGroups = {};
    let nextPaymentNum = null;

    s.rows.forEach(row => {
        const year = row.date.substring(0, 4);
        if (!yearGroups[year]) yearGroups[year] = [];
        yearGroups[year].push(row);
        if (!row.is_paid && nextPaymentNum === null) {
            nextPaymentNum = row.number;
        }
    });

    const currentYear = new Date().getFullYear().toString();
    const container = document.getElementById('schedule-table');

    // Only show Extra column when there are actual extra repayments
    const hasExtras = s.rows.some(r => r.extra > 0);

    // Export buttons
    let html = `<div class="flex gap-2 mb-3 no-print">
        <button onclick="app.exportSchedule('csv')" class="text-xs bg-gray-100 text-gray-700 px-3 py-1 rounded hover:bg-gray-200">Export CSV</button>
        <button onclick="app.exportSchedule('xlsx')" class="text-xs bg-gray-100 text-gray-700 px-3 py-1 rounded hover:bg-gray-200">Export XLSX</button>
        <span class="text-xs text-gray-400 ml-2">Total Interest: ${fmtMoney(s.summary.total_interest)}</span>
    </div>`;

    const years = Object.keys(yearGroups).sort();
    years.forEach(year => {
        const rows = yearGroups[year];
        const isCurrentOrFuture = year >= currentYear;
        const hasNextPayment = rows.some(r => r.number === nextPaymentNum);
        const expanded = isCurrentOrFuture || hasNextPayment;

        html += `<div class="year-group bg-white rounded-xl shadow mb-2">
            <div class="flex justify-between items-center px-4 py-2 cursor-pointer hover:bg-gray-50 rounded-t-xl"
                 onclick="this.nextElementSibling.classList.toggle('collapsed'); this.querySelector('.chevron').classList.toggle('rotate-90')">
                <span class="font-medium text-gray-700">
                    <span class="chevron inline-block transition-transform ${expanded ? 'rotate-90' : ''}">&#9654;</span>
                    ${year} <span class="text-gray-400 text-sm">(${rows.length} payments)</span>
                </span>
            </div>
            <div class="year-group-content ${expanded ? '' : 'collapsed'}">
                <div class="overflow-x-auto">
                    <table class="w-full text-sm">
                        <thead>
                            <tr class="text-left text-xs text-gray-500 border-b">
                                <th class="px-3 py-1 w-8"></th>
                                <th class="px-2 py-1">#</th>
                                <th class="px-2 py-1">Date</th>
                                <th class="px-2 py-1">Rate</th>
                                <th class="px-2 py-1 text-right hidden sm:table-cell">Balance</th>
                                <th class="px-2 py-1 text-right">Repayment</th>
                                <th class="px-2 py-1 text-right">Interest</th>
                                <th class="px-2 py-1 text-right">Principal</th>${hasExtras ? '<th class="px-2 py-1 text-right">Extra</th>' : ''}
                                <th class="px-2 py-1 text-right">Closing</th>
                            </tr>
                        </thead>
                        <tbody>`;

        rows.forEach(row => {
            const isNext = row.number === nextPaymentNum;
            const isOverdue = !row.is_paid && row.date < today;
            let rowClass = '';
            if (row.is_paid) rowClass = 'paid';
            else if (isNext) rowClass = 'next-due';
            else if (isOverdue) rowClass = 'overdue';

            html += `<tr class="${rowClass}" ${isNext ? 'id="next-payment-row"' : ''}>
                <td class="px-3 py-1">
                    <input type="checkbox" class="paid-checkbox"
                        ${row.is_paid ? 'checked' : ''}
                        ${isWhatIf ? 'disabled' : ''}
                        onchange="app._togglePaid(${row.number}, this.checked)">
                </td>
                <td class="px-2 py-1 text-gray-500">${row.number}</td>
                <td class="px-2 py-1">${fmtDate(row.date)}</td>
                <td class="px-2 py-1 text-xs ${row.rate_start !== row.rate ? 'text-violet-600 font-medium' : 'text-gray-400'}">${row.rate_start !== row.rate ? `${fmtPct(row.rate_start)}/${fmtPct(row.rate)}` : fmtPct(row.rate)}</td>
                <td class="px-2 py-1 text-right hidden sm:table-cell">${fmtMoney(row.opening_balance)}</td>
                <td class="px-2 py-1 text-right font-medium">${fmtMoney(row.principal + row.interest)}</td>
                <td class="px-2 py-1 text-right text-orange-600">${fmtMoney(row.interest)}</td>
                <td class="px-2 py-1 text-right text-green-700">${fmtMoney(row.principal)}</td>${hasExtras ? `<td class="px-2 py-1 text-right text-blue-600">${row.extra > 0 ? fmtMoney(row.extra) : '-'}</td>` : ''}
                <td class="px-2 py-1 text-right font-medium">${fmtMoney(row.closing_balance)}</td>
            </tr>`;
        });

        html += `</tbody></table></div></div></div>`;
    });

    container.innerHTML = html;

    // Auto-scroll to next payment (skip during what-if debounce)
    if (!isWhatIf) {
        setTimeout(() => {
            const nextRow = document.getElementById('next-payment-row');
            if (nextRow) nextRow.scrollIntoView({ behavior: 'smooth', block: 'center' });
        }, 100);
    }
}

function renderRateChanges(loan, state, { fmtDate, fmtPct, escapeHtml }) {
    const container = document.getElementById('rate-changes-list');
    if (!state.currentLoanId) { container.innerHTML = ''; return; }

    if (!loan.rate_changes || loan.rate_changes.length === 0) {
        container.innerHTML = '<span class="text-gray-400">No rate changes</span>';
        return;
    }
    container.innerHTML = loan.rate_changes.map(rc => `
        <div class="flex justify-between items-center py-1 border-b last:border-0">
            <span>${fmtDate(rc.effective_date)} → ${fmtPct(rc.annual_rate)} ${rc.note ? `<span class="text-gray-400">(${escapeHtml(rc.note)})</span>` : ''}</span>
            <button onclick="app.deleteRateChange(${rc.id})" class="text-red-400 hover:text-red-600 text-xs">Remove</button>
        </div>
    `).join('');
}

function renderRepaymentChanges(loan, state, { fmtDate, fmtMoney, escapeHtml }) {
    const container = document.getElementById('repayment-changes-list');
    if (!state.currentLoanId) { container.innerHTML = ''; return; }

    if (!loan.repayment_changes || loan.repayment_changes.length === 0) {
        container.innerHTML = '<span class="text-gray-400">No repayment changes</span>';
        return;
    }
    container.innerHTML = loan.repayment_changes.map(rc => `
        <div class="flex justify-between items-center py-1 border-b last:border-0">
            <span>${fmtDate(rc.effective_date)} → ${fmtMoney(rc.amount)}/period ${rc.note ? `<span class="text-gray-400">(${escapeHtml(rc.note)})</span>` : ''}</span>
            <button onclick="app.deleteRepaymentChange(${rc.id})" class="text-red-400 hover:text-red-600 text-xs">Remove</button>
        </div>
    `).join('');
}

function renderExtras(loan, state, { fmtDate, fmtMoney, escapeHtml }) {
    const container = document.getElementById('extras-list');
    if (!state.currentLoanId) { container.innerHTML = ''; return; }

    if (!loan.extra_repayments || loan.extra_repayments.length === 0) {
        container.innerHTML = '<span class="text-gray-400">No extra repayments</span>';
        return;
    }
    container.innerHTML = loan.extra_repayments.map(er => `
        <div class="flex justify-between items-center py-1 border-b last:border-0">
            <span>${fmtDate(er.payment_date)} → ${fmtMoney(er.amount)} ${er.note ? `<span class="text-gray-400">(${escapeHtml(er.note)})</span>` : ''}</span>
            <button onclick="app.deleteExtra(${er.id})" class="text-red-400 hover:text-red-600 text-xs">Remove</button>
        </div>
    `).join('');
}

