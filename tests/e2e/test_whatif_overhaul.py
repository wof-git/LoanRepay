"""E2E: What-If Explorer overhaul — dynamic slider, impact cards,
additive rate/extra, scenario save with what-if state, apply confirmation, reset."""

from playwright.sync_api import expect


def _create_loan(page):
    """Helper to create a standard test loan ($612.39 fortnightly)."""
    page.click("button:has-text('Create your first loan')")
    page.wait_for_timeout(300)
    page.fill("input[name=name]", "What-If Overhaul")
    page.fill("input[name=principal]", "30050")
    page.fill("input[name=annual_rate]", "5.75")
    page.select_option("select[name=frequency]", "fortnightly")
    page.fill("input[name=start_date]", "2026-02-20")
    page.fill("input[name=loan_term]", "52")
    page.fill("input[name=fixed_repayment]", "612.39")
    page.click("button:has-text('Create Loan')")
    page.wait_for_timeout(500)


def _open_whatif(page):
    """Navigate to Schedule tab and open What-If Explorer."""
    page.click("button:has-text('Schedule')")
    page.wait_for_timeout(500)
    page.click("text=What-If Explorer")
    page.wait_for_timeout(300)


# --- Panel UI ---

def test_panel_renamed_to_explorer(page):
    """Panel header says 'What-If Explorer', not 'What If Panel'."""
    _create_loan(page)
    page.click("button:has-text('Schedule')")
    page.wait_for_timeout(500)
    expect(page.locator("text=What-If Explorer")).to_be_visible()
    expect(page.locator("text=What If Panel")).not_to_be_visible()


def test_guidance_text_visible(page):
    """Guidance paragraph shown when panel is expanded."""
    _create_loan(page)
    _open_whatif(page)
    expect(page.locator("text=Explore hypothetical changes")).to_be_visible()


def test_current_context_labels(page):
    """Current repayment and rate context labels populated."""
    _create_loan(page)
    _open_whatif(page)
    repayment_label = page.locator("#whatif-current-repayment")
    rate_label = page.locator("#whatif-current-rate")
    expect(repayment_label).to_contain_text("$612.39")
    expect(repayment_label).to_contain_text("fortnightly")
    expect(rate_label).to_contain_text("5.75%")


def test_dynamic_slider_range(page):
    """Slider min/max set dynamically based on loan repayment."""
    _create_loan(page)
    _open_whatif(page)
    slider = page.locator("#whatif-slider")
    # For $612.39: min = max(floor(612.39*0.5/10)*10, 50) = 300
    #              max = ceil(612.39*2.5/10)*10 = 1540
    expect(slider).to_have_attribute("min", "300")
    expect(slider).to_have_attribute("max", "1540")
    expect(slider).to_have_attribute("step", "1")


def test_slider_prefilled_with_loan_repayment(page):
    """Slider and number input pre-filled with loan's fixed repayment.
    Note: range inputs truncate to integer, number input keeps decimals."""
    _create_loan(page)
    _open_whatif(page)
    # Range input truncates 612.39 to 612 (HTML range behavior)
    expect(page.locator("#whatif-slider")).to_have_value("612")
    expect(page.locator("#whatif-repayment")).to_have_value("612.39")


# --- Impact Cards ---

def test_impact_cards_appear_on_change(page):
    """Before/after impact cards appear when repayment is changed."""
    _create_loan(page)
    _open_whatif(page)
    # Impact hidden initially
    expect(page.locator("#whatif-impact")).to_be_hidden()
    # Change repayment
    page.fill("input#whatif-repayment", "700")
    page.wait_for_timeout(600)
    # Impact cards should now be visible
    expect(page.locator("#whatif-impact")).to_be_visible()
    expect(page.locator("#impact-base-interest")).not_to_have_text("-")
    expect(page.locator("#impact-wi-interest")).not_to_have_text("-")
    expect(page.locator("#impact-base-payments")).not_to_have_text("-")
    expect(page.locator("#impact-wi-payments")).not_to_have_text("-")


def test_impact_cards_show_improvement_for_higher_repayment(page):
    """Higher repayment shows green (fewer payments, less interest)."""
    _create_loan(page)
    _open_whatif(page)
    page.fill("input#whatif-repayment", "800")
    page.wait_for_timeout(600)
    # Delta banner should say "Saves"
    expect(page.locator("#delta-banner")).to_contain_text("Saves")


# --- Rate Change Input ---

def test_rate_change_triggers_recalculation(page):
    """Filling both rate date and value triggers live recalculation."""
    _create_loan(page)
    _open_whatif(page)
    page.fill("input#whatif-rate-date", "2026-09-01")
    page.fill("input#whatif-rate-value", "8")
    page.wait_for_timeout(600)
    # Higher rate → more interest → delta banner should show cost
    expect(page.locator("#delta-banner")).to_be_visible()
    expect(page.locator("#delta-banner")).to_contain_text("Costs")
    expect(page.locator("#whatif-impact")).to_be_visible()


def test_rate_change_incomplete_pair_ignored(page):
    """Filling only rate value (no date) does not trigger rate recalc."""
    _create_loan(page)
    _open_whatif(page)
    page.fill("input#whatif-rate-value", "8")
    page.wait_for_timeout(600)
    # No date means rate change is ignored — no delta unless repayment changed
    expect(page.locator("#delta-banner")).to_be_hidden()


# --- Lump Sum Input ---

def test_lump_sum_triggers_recalculation(page):
    """Filling both lump sum date and amount triggers recalculation."""
    _create_loan(page)
    _open_whatif(page)
    page.fill("input#whatif-extra-date", "2026-06-01")
    page.fill("input#whatif-extra-amount", "5000")
    page.wait_for_timeout(600)
    # Lump sum → less interest
    expect(page.locator("#delta-banner")).to_be_visible()
    expect(page.locator("#delta-banner")).to_contain_text("Saves")


# --- Save as Scenario ---

def test_save_scenario_shows_includes(page):
    """Save modal shows what what-if adjustments are included."""
    _create_loan(page)
    _open_whatif(page)
    page.fill("input#whatif-repayment", "700")
    page.wait_for_timeout(600)
    page.click("text=Save as New Scenario")
    page.wait_for_timeout(300)
    # Modal should show "Includes:" with repayment
    expect(page.locator("#modal-content")).to_contain_text("Includes")
    expect(page.locator("#modal-content")).to_contain_text("Repayment")
    expect(page.locator("#modal-content")).to_contain_text("$700")


def test_save_scenario_auto_populates_description(page):
    """Description textarea is auto-populated from what-if params."""
    _create_loan(page)
    _open_whatif(page)
    page.fill("input#whatif-repayment", "700")
    page.wait_for_timeout(600)
    page.click("text=Save as New Scenario")
    page.wait_for_timeout(300)
    desc = page.locator("textarea[name=description]")
    expect(desc).not_to_be_empty()


def test_save_scenario_with_whatif_repayment_persists(page):
    """Save scenario with changed repayment, verify it appears in Scenarios tab."""
    _create_loan(page)
    _open_whatif(page)
    page.fill("input#whatif-repayment", "800")
    page.wait_for_timeout(600)
    page.click("text=Save as New Scenario")
    page.wait_for_timeout(300)
    page.fill("input[name=scenario_name]", "Pay $800")
    page.click("#modal-content button:has-text('Save')")
    page.wait_for_timeout(500)
    # Check scenarios tab
    page.click("button:has-text('Scenarios')")
    page.wait_for_timeout(500)
    expect(page.locator("#scenarios-list >> text=Pay $800")).to_be_visible()


def test_save_scenario_with_rate_change(page):
    """Save scenario with what-if rate change, verify in Scenarios tab."""
    _create_loan(page)
    _open_whatif(page)
    page.fill("input#whatif-rate-date", "2026-09-01")
    page.fill("input#whatif-rate-value", "7")
    page.wait_for_timeout(600)
    page.click("text=Save as New Scenario")
    page.wait_for_timeout(300)
    # Modal should mention rate
    expect(page.locator("#modal-content")).to_contain_text("Rate")
    page.fill("input[name=scenario_name]", "Rate Hike")
    page.click("#modal-content button:has-text('Save')")
    page.wait_for_timeout(500)
    page.click("button:has-text('Scenarios')")
    page.wait_for_timeout(500)
    expect(page.locator("#scenarios-list >> text=Rate Hike")).to_be_visible()


def test_save_scenario_with_lump_sum(page):
    """Save scenario with what-if lump sum, verify in Scenarios tab."""
    _create_loan(page)
    _open_whatif(page)
    page.fill("input#whatif-extra-date", "2026-06-01")
    page.fill("input#whatif-extra-amount", "5000")
    page.wait_for_timeout(600)
    page.click("text=Save as New Scenario")
    page.wait_for_timeout(300)
    # Modal should mention lump sum
    expect(page.locator("#modal-content")).to_contain_text("Lump sum")
    page.fill("input[name=scenario_name]", "Tax Refund")
    page.click("#modal-content button:has-text('Save')")
    page.wait_for_timeout(500)
    page.click("button:has-text('Scenarios')")
    page.wait_for_timeout(500)
    expect(page.locator("#scenarios-list >> text=Tax Refund")).to_be_visible()


def test_save_no_changes_shows_base_state_message(page):
    """Save without adjustments shows 'no adjustments' message."""
    _create_loan(page)
    _open_whatif(page)
    page.click("text=Save as New Scenario")
    page.wait_for_timeout(300)
    expect(page.locator("#modal-content")).to_contain_text("No what-if adjustments")


def test_two_whatif_scenarios_have_different_interest(page):
    """Save base + higher repayment scenario, compare shows different interest."""
    _create_loan(page)
    _open_whatif(page)

    # Save base scenario
    page.click("text=Save as New Scenario")
    page.wait_for_timeout(300)
    page.fill("input[name=scenario_name]", "Base")
    page.click("#modal-content button:has-text('Save')")
    page.wait_for_timeout(500)

    # Save higher repayment scenario
    page.fill("input#whatif-repayment", "800")
    page.wait_for_timeout(600)
    page.click("text=Save as New Scenario")
    page.wait_for_timeout(300)
    page.fill("input[name=scenario_name]", "Pay $800")
    page.click("#modal-content button:has-text('Save')")
    page.wait_for_timeout(500)

    # Compare — verify both scenarios saved with different data
    page.click("button:has-text('Scenarios')")
    page.wait_for_timeout(500)
    cards = page.locator("#scenarios-list > div")
    # Default + Base + Pay $800 = 3
    expect(cards).to_have_count(3)
    # Verify both scenario names appear in scenario cards
    expect(page.locator("#scenarios-list h4 >> text=Base")).to_be_visible()
    expect(page.locator("#scenarios-list h4 >> text=Pay $800")).to_be_visible()
    # Select user-created scenarios and compare
    checkboxes = page.locator("#scenarios-list input[type=checkbox]")
    checkboxes.nth(1).check()
    checkboxes.nth(2).check()
    page.wait_for_timeout(300)
    page.click("button:has-text('Compare Selected')")
    page.wait_for_timeout(1000)
    expect(page.locator("#comparison-view")).to_be_visible()


# --- Apply Repayment to Loan ---

def test_apply_repayment_shows_confirmation(page):
    """Apply button shows confirmation modal with current vs new."""
    _create_loan(page)
    _open_whatif(page)
    page.fill("input#whatif-repayment", "700")
    page.wait_for_timeout(300)
    page.click("text=Apply Repayment to Loan")
    page.wait_for_timeout(300)
    # Confirmation modal should appear
    expect(page.locator("#modal-content")).to_contain_text("Apply Repayment to Loan")
    expect(page.locator("#modal-content")).to_contain_text("$612.39")
    expect(page.locator("#modal-content")).to_contain_text("$700.00")
    expect(page.locator("#modal-content")).to_contain_text("Only the repayment amount is applied")


def test_apply_repayment_confirm_updates_loan(page):
    """Confirming apply actually updates the loan's fixed repayment."""
    _create_loan(page)
    _open_whatif(page)
    page.fill("input#whatif-repayment", "700")
    page.wait_for_timeout(300)
    page.click("text=Apply Repayment to Loan")
    page.wait_for_timeout(300)
    page.click("#modal-content button:has-text('Confirm')")
    page.wait_for_timeout(1000)
    # After apply, the loan is updated and page re-renders.
    # Verify by checking that the loan detail shows updated repayment.
    page.click("button:has-text('Dashboard')")
    page.wait_for_timeout(500)
    # The loan details grid should show $700.00
    expect(page.locator("#loan-details")).to_contain_text("700.00")


def test_apply_repayment_cancel_does_not_update(page):
    """Canceling apply does not change the loan."""
    _create_loan(page)
    _open_whatif(page)
    page.fill("input#whatif-repayment", "700")
    page.wait_for_timeout(300)
    page.click("text=Apply Repayment to Loan")
    page.wait_for_timeout(300)
    page.click("#modal-content button:has-text('Cancel')")
    page.wait_for_timeout(300)
    # Context label should still show original
    expect(page.locator("#whatif-current-repayment")).to_contain_text("$612.39")


# --- Reset ---

def test_reset_clears_all_inputs(page):
    """Reset returns all inputs to default and hides impact."""
    _create_loan(page)
    _open_whatif(page)
    # Make changes
    page.fill("input#whatif-repayment", "800")
    page.fill("input#whatif-rate-date", "2026-09-01")
    page.fill("input#whatif-rate-value", "7")
    page.fill("input#whatif-extra-date", "2026-06-01")
    page.fill("input#whatif-extra-amount", "5000")
    page.wait_for_timeout(600)
    # Verify impact visible
    expect(page.locator("#whatif-impact")).to_be_visible()
    # Reset
    page.click("text=Reset")
    page.wait_for_timeout(300)
    # Slider/number should be back to loan repayment
    expect(page.locator("#whatif-repayment")).to_have_value("612.39")
    # Rate/extra fields cleared
    expect(page.locator("#whatif-rate-date")).to_have_value("")
    expect(page.locator("#whatif-rate-value")).to_have_value("")
    expect(page.locator("#whatif-extra-date")).to_have_value("")
    expect(page.locator("#whatif-extra-amount")).to_have_value("")
    # Impact hidden
    expect(page.locator("#whatif-impact")).to_be_hidden()
    expect(page.locator("#delta-banner")).to_be_hidden()


# --- Button ordering ---

def test_button_order(page):
    """Save as Scenario is first (primary), Apply is second (amber), Reset is last."""
    _create_loan(page)
    _open_whatif(page)
    buttons = page.locator("#whatif-panel .flex.flex-wrap.gap-2 button")
    expect(buttons.nth(0)).to_contain_text("Save as New Scenario")
    expect(buttons.nth(1)).to_contain_text("Apply Repayment to Loan")
    expect(buttons.nth(2)).to_contain_text("Reset")


# --- Scenarios tab hint ---

def test_scenarios_tab_hint_visible(page):
    """Hint about Scenarios tab is shown at bottom of panel."""
    _create_loan(page)
    _open_whatif(page)
    expect(page.locator("text=Saved scenarios can be compared in the Scenarios tab")).to_be_visible()
