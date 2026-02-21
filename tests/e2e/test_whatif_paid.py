"""E2E: what-if preserves already-paid periods."""

from playwright.sync_api import expect


def _create_loan(page):
    """Helper to create a test loan."""
    page.click("button:has-text('Create your first loan')")
    page.wait_for_timeout(300)
    page.fill("input[name=name]", "Paid WhatIf Test")
    page.fill("input[name=principal]", "30050")
    page.fill("input[name=annual_rate]", "5.75")
    page.select_option("select[name=frequency]", "fortnightly")
    page.fill("input[name=start_date]", "2026-02-20")
    page.fill("input[name=loan_term]", "52")
    page.fill("input[name=fixed_repayment]", "612.39")
    page.click("button:has-text('Create Loan')")
    page.wait_for_timeout(500)


def _get_closing_balances(page, count):
    """Read the first `count` closing balance values from the schedule table.

    Closing balance is the last <td> in each <tr> within <tbody>.
    """
    return page.evaluate(f"""() => {{
        const rows = document.querySelectorAll('#schedule-table tbody tr');
        return Array.from(rows).slice(0, {count}).map(tr => {{
            const cells = tr.querySelectorAll('td');
            return cells[cells.length - 1].textContent.trim();
        }});
    }}""")


def test_whatif_does_not_alter_paid_periods(page):
    """Ticking payments as paid, then using what-if should not change those rows."""
    _create_loan(page)
    page.click("button:has-text('Schedule')")
    page.wait_for_timeout(500)

    # Tick first 3 payments as paid
    checkboxes = page.locator(".paid-checkbox")
    for i in range(3):
        checkboxes.nth(i).check()
        page.wait_for_timeout(300)

    # Record closing balances of paid rows + first unpaid row
    base_balances = _get_closing_balances(page, 4)
    assert len(base_balances) == 4

    # Open what-if and change repayment
    page.click("text=What-If Explorer")
    page.wait_for_timeout(300)
    page.fill("input#whatif-repayment", "800")
    page.wait_for_timeout(800)

    # Read closing balances again from the what-if schedule
    whatif_balances = _get_closing_balances(page, 4)

    # First 3 (paid) rows should be identical
    for i in range(3):
        assert base_balances[i] == whatif_balances[i], (
            f"Paid row {i+1} changed: {base_balances[i]} -> {whatif_balances[i]}"
        )

    # 4th row (first unpaid) should differ — higher repayment = lower closing balance
    assert whatif_balances[3] != base_balances[3], (
        "First unpaid row should change with what-if repayment"
    )


def test_whatif_checkboxes_disabled_during_whatif(page):
    """Paid checkboxes should be disabled when what-if is active."""
    _create_loan(page)
    page.click("button:has-text('Schedule')")
    page.wait_for_timeout(500)

    # Tick first payment as paid
    page.locator(".paid-checkbox").first.check()
    page.wait_for_timeout(300)

    # Open what-if and change repayment to trigger re-render
    page.click("text=What-If Explorer")
    page.wait_for_timeout(300)
    page.fill("input#whatif-repayment", "700")
    page.wait_for_timeout(800)

    # All checkboxes in what-if view should be disabled
    first_checkbox = page.locator(".paid-checkbox").first
    expect(first_checkbox).to_be_disabled()


def test_whatif_no_paid_still_works(page):
    """What-if with no paid periods should still change all rows normally."""
    _create_loan(page)
    page.click("button:has-text('Schedule')")
    page.wait_for_timeout(500)

    base_balances = _get_closing_balances(page, 2)

    page.click("text=What-If Explorer")
    page.wait_for_timeout(300)
    page.fill("input#whatif-repayment", "800")
    page.wait_for_timeout(800)

    whatif_balances = _get_closing_balances(page, 2)

    # Both rows should differ with higher repayment
    assert whatif_balances[0] != base_balances[0], "Row 1 should change"
    assert whatif_balances[1] != base_balances[1], "Row 2 should change"
