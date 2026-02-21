let comparisonChart = null;

export async function renderScenarios(state, helpers, comparisonData = null) {
    const { fmtMoney, fmtDate, escapeHtml, api } = helpers;
    const container = document.getElementById('scenarios-list');
    const compareBtn = document.getElementById('btn-compare');
    const compView = document.getElementById('comparison-view');

    if (!state.currentLoanId) return;

    try {
        const scenarios = await api(`/loans/${state.currentLoanId}/scenarios`);

        if (scenarios.length === 0) {
            container.innerHTML = '<p class="text-gray-400 text-sm">No saved scenarios yet. Use the What-If panel to explore and save scenarios.</p>';
            compareBtn.classList.add('hidden');
            compView.classList.add('hidden');
            return;
        }

        container.innerHTML = scenarios.map(s => `
            <div class="bg-white rounded-xl shadow p-4">
                <div class="flex items-start justify-between mb-2">
                    <div class="flex items-center gap-2">
                        <input type="checkbox" value="${s.id}"
                            ${state.selectedScenarios.has(s.id) ? 'checked' : ''}
                            onchange="app._toggleScenario(${s.id}, this.checked)">
                        <h4 class="font-medium text-gray-800">${escapeHtml(s.name)}</h4>
                    </div>
                    <button onclick="app._deleteScenario(${s.id})" class="text-red-400 hover:text-red-600 text-xs">Delete</button>
                </div>
                ${s.description ? `<p class="text-xs text-gray-500 mb-2">${escapeHtml(s.description)}</p>` : ''}
                <div class="grid grid-cols-2 gap-2 text-sm">
                    <div><span class="text-gray-500">Interest:</span> <span class="font-medium">${fmtMoney(s.total_interest)}</span></div>
                    <div><span class="text-gray-500">Total Paid:</span> <span class="font-medium">${fmtMoney(s.total_paid)}</span></div>
                    <div><span class="text-gray-500">Payoff:</span> <span class="font-medium">${fmtDate(s.payoff_date)}</span></div>
                    <div><span class="text-gray-500">Payments:</span> <span class="font-medium">${s.actual_num_repayments}</span></div>
                </div>
            </div>
        `).join('');

        // Show compare button if 2+ selected
        compareBtn.classList.toggle('hidden', state.selectedScenarios.size < 2);

        // Show comparison if data provided
        if (comparisonData) {
            renderComparison(comparisonData, helpers);
        } else {
            compView.classList.add('hidden');
        }

    } catch (e) {
        container.innerHTML = '<p class="text-red-400 text-sm">Failed to load scenarios</p>';
    }
}

function renderComparison(data, { fmtMoney, fmtDate, escapeHtml }) {
    const compView = document.getElementById('comparison-view');
    const cardsContainer = document.getElementById('comparison-cards');
    compView.classList.remove('hidden');

    // Comparison cards
    cardsContainer.innerHTML = data.map(s => `
        <div class="bg-white rounded-xl shadow p-4">
            <h4 class="font-medium text-gray-800 mb-2">${escapeHtml(s.name)}</h4>
            <div class="space-y-1 text-sm">
                <div class="flex justify-between"><span class="text-gray-500">Total Interest:</span> <span class="font-medium">${fmtMoney(s.total_interest)}</span></div>
                <div class="flex justify-between"><span class="text-gray-500">Total Paid:</span> <span class="font-medium">${fmtMoney(s.total_paid)}</span></div>
                <div class="flex justify-between"><span class="text-gray-500">Payoff Date:</span> <span class="font-medium">${fmtDate(s.payoff_date)}</span></div>
                <div class="flex justify-between"><span class="text-gray-500">Payments:</span> <span class="font-medium">${s.actual_num_repayments}</span></div>
            </div>
        </div>
    `).join('');

    // Comparison chart — overlaid balance timelines
    const colors = ['#3b82f6', '#ef4444', '#22c55e', '#f59e0b'];
    const datasets = data.map((s, i) => ({
        label: s.name,
        data: s.schedule.map(r => ({ x: r.date, y: r.closing_balance })),
        borderColor: colors[i % colors.length],
        backgroundColor: 'transparent',
        tension: 0.1,
        pointRadius: 0,
    }));

    const ctx = document.getElementById('chart-comparison');
    if (comparisonChart) comparisonChart.destroy();
    comparisonChart = new Chart(ctx, {
        type: 'line',
        data: { datasets },
        options: {
            responsive: true,
            plugins: { legend: { position: 'top' } },
            scales: {
                x: { type: 'category', labels: data[0]?.schedule.map(r => r.date) || [], ticks: { maxTicksLimit: 12 } },
                y: { ticks: { callback: v => '$' + v.toLocaleString() } },
            },
        },
    });
}

