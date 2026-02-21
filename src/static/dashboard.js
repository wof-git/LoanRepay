let balanceChart = null;
let breakdownChart = null;

export function renderDashboard(state, { fmtMoney, fmtDate, fmtPct, api }) {
    const s = state.schedule;
    if (!s) return;

    const loan = state.loans.find(l => l.id === state.currentLoanId);
    const summary = s.summary;

    // Summary cards
    document.getElementById('dash-balance').textContent = fmtMoney(summary.remaining_balance);
    document.getElementById('dash-interest').textContent = fmtMoney(summary.total_interest);
    document.getElementById('dash-payoff').textContent = fmtDate(summary.payoff_date);

    // Loan name
    if (loan) {
        document.getElementById('loan-name-display').textContent = loan.name;
    }

    // Loan details
    if (loan) {
        document.getElementById('loan-details').innerHTML = `
            <div><span class="text-gray-500">Principal:</span> <span class="font-medium">${fmtMoney(loan.principal)}</span></div>
            <div><span class="text-gray-500">Rate:</span> <span class="font-medium">${fmtPct(loan.annual_rate)}</span></div>
            <div><span class="text-gray-500">Frequency:</span> <span class="font-medium capitalize">${loan.frequency}</span></div>
            <div><span class="text-gray-500">Term:</span> <span class="font-medium">${loan.loan_term} periods</span></div>
            <div><span class="text-gray-500">Fixed Payment:</span> <span class="font-medium">${loan.fixed_repayment ? fmtMoney(loan.fixed_repayment) : 'Calculated'}</span></div>
            <div><span class="text-gray-500">Start:</span> <span class="font-medium">${fmtDate(loan.start_date)}</span></div>
            <div><span class="text-gray-500">Total Paid:</span> <span class="font-medium">${fmtMoney(summary.total_paid)}</span></div>
            <div><span class="text-gray-500">Payments:</span> <span class="font-medium">${summary.payments_made}/${summary.total_repayments}</span></div>
        `;
    }

    // Balance timeline chart
    const labels = s.rows.map(r => r.date);
    const balances = s.rows.map(r => r.closing_balance);

    const balCtx = document.getElementById('chart-balance');
    if (balanceChart) balanceChart.destroy();
    balanceChart = new Chart(balCtx, {
        type: 'line',
        data: {
            labels,
            datasets: [{
                label: 'Balance',
                data: balances,
                borderColor: '#3b82f6',
                backgroundColor: 'rgba(59,130,246,0.1)',
                fill: true,
                tension: 0.1,
                pointRadius: 0,
            }],
        },
        options: {
            responsive: true,
            plugins: { legend: { display: false } },
            scales: {
                x: {
                    ticks: { maxTicksLimit: 10, callback: (_, i) => fmtDate(labels[i]) },
                },
                y: { ticks: { callback: v => '$' + v.toLocaleString() } },
            },
        },
    });

    // Principal vs Interest breakdown chart
    const principals = s.rows.map(r => r.principal);
    const interests = s.rows.map(r => r.interest);

    const brkCtx = document.getElementById('chart-breakdown');
    if (breakdownChart) breakdownChart.destroy();
    breakdownChart = new Chart(brkCtx, {
        type: 'bar',
        data: {
            labels: s.rows.map(r => '#' + r.number),
            datasets: [
                {
                    label: 'Principal',
                    data: principals,
                    backgroundColor: '#22c55e',
                },
                {
                    label: 'Interest',
                    data: interests,
                    backgroundColor: '#f97316',
                },
            ],
        },
        options: {
            responsive: true,
            plugins: { legend: { position: 'top' } },
            scales: {
                x: { stacked: true, ticks: { maxTicksLimit: 15 } },
                y: { stacked: true, ticks: { callback: v => '$' + v } },
            },
        },
    });
}
