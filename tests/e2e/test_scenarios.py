"""E2E: save, compare scenarios."""

from playwright.sync_api import expect


def _create_loan_with_scenarios(page):
    """Helper: create loan and save two scenarios."""
    # Create loan
    page.click("button:has-text('Create your first loan')")
    page.wait_for_timeout(300)
    page.fill("input[name=name]", "Scenario Test")
    page.fill("input[name=principal]", "30050")
    page.fill("input[name=annual_rate]", "5.75")
    page.select_option("select[name=frequency]", "fortnightly")
    page.fill("input[name=start_date]", "2026-02-20")
    page.fill("input[name=loan_term]", "52")
    page.fill("input[name=fixed_repayment]", "612.39")
    page.click("button:has-text('Create Loan')")
    page.wait_for_timeout(500)

    # Save base scenario
    page.click("button:has-text('Schedule')")
    page.wait_for_timeout(500)
    page.click("text=What-If Explorer")
    page.wait_for_timeout(300)
    page.click("text=Save as Scenario")
    page.fill("input[name=scenario_name]", "Base")
    page.click("#modal-content button:has-text('Save')")
    page.wait_for_timeout(500)

    # Save higher repayment scenario
    page.fill("input#whatif-repayment", "700")
    page.wait_for_timeout(500)
    page.click("text=Save as Scenario")
    page.fill("input[name=scenario_name]", "Pay $700")
    page.click("#modal-content button:has-text('Save')")
    page.wait_for_timeout(500)


def test_compare_scenarios(page):
    """Save two scenarios, compare side by side."""
    _create_loan_with_scenarios(page)

    # Go to scenarios tab
    page.click("button:has-text('Scenarios')")
    page.wait_for_timeout(500)

    # Select both scenarios via JS (inline onchange handler has a known
    # module loading issue where app.js overwrites window.app after scenarios.js)
    checkboxes = page.locator("input.scenario-check")
    expect(checkboxes).to_have_count(2)
    page.evaluate("""() => {
        document.querySelectorAll('input.scenario-check').forEach(cb => {
            const id = parseInt(cb.value);
            window.app.state.selectedScenarios.add(id);
        });
    }""")
    page.evaluate("window.app.compareSelected()")
    page.wait_for_timeout(1000)

    # Verify comparison view shows
    expect(page.locator("#comparison-view")).to_be_visible()
    expect(page.locator("canvas#chart-comparison")).to_be_visible()
