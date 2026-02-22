"""E2E: what-if panel, live recalculation."""

from playwright.sync_api import expect


def _create_loan(page):
    """Helper to create a test loan."""
    page.click("button:has-text('Create your first loan')")
    page.wait_for_timeout(300)
    page.fill("input[name=name]", "What-If Test")
    page.fill("input[name=principal]", "30050")
    page.fill("input[name=annual_rate]", "5.75")
    page.select_option("select[name=frequency]", "fortnightly")
    page.fill("input[name=start_date]", "2026-02-20")
    page.fill("input[name=loan_term]", "52")
    page.fill("input[name=fixed_repayment]", "612.39")
    page.click("button:has-text('Create Loan')")
    page.wait_for_timeout(500)


def test_whatif_repayment_change(page):
    """Adjust repayment, verify schedule updates live."""
    _create_loan(page)
    page.click("button:has-text('Schedule')")
    page.wait_for_timeout(500)

    # Open what-if panel
    page.click("text=What-If Explorer")
    page.wait_for_timeout(300)

    # Change repayment amount
    page.fill("input#whatif-repayment", "700")
    page.wait_for_timeout(500)

    # Verify delta banner shows
    expect(page.locator("#delta-banner")).to_be_visible()
    expect(page.locator("#delta-banner")).to_contain_text("Saves")


def test_early_payoff_target(page):
    """Enter target date, verify required repayment shown."""
    _create_loan(page)
    page.click("button:has-text('Schedule')")
    page.wait_for_timeout(500)

    page.click("text=What-If Explorer")
    page.wait_for_timeout(300)

    page.fill("input#whatif-target-date", "2027-06-01")
    page.click("button:has-text('Calculate')")
    page.wait_for_timeout(500)

    expect(page.locator("#payoff-result")).not_to_be_empty()


def test_whatif_save_as_scenario(page):
    """Tweak what-if, save as scenario, verify in scenarios tab."""
    _create_loan(page)
    page.click("button:has-text('Schedule')")
    page.wait_for_timeout(500)

    page.click("text=What-If Explorer")
    page.wait_for_timeout(300)

    page.fill("input#whatif-repayment", "700")
    page.wait_for_timeout(500)

    page.click("text=Save as New Scenario")
    page.fill("input[name=scenario_name]", "Pay $700")
    page.click("#modal-content button:has-text('Save')")
    page.wait_for_timeout(500)

    # Check scenarios tab
    page.click("button:has-text('Scenarios')")
    page.wait_for_timeout(500)
    expect(page.locator("#scenarios-list >> text=Pay $700")).to_be_visible()
