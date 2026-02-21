"""E2E: create loan, view schedule, mark paid, rate changes."""

import re
from playwright.sync_api import expect


def test_create_loan_and_view_schedule(page):
    """Full lifecycle: create loan -> see schedule -> verify data."""
    # Verify empty state
    expect(page.locator("button:has-text('Create your first loan')")).to_be_visible()

    # Create loan
    page.click("button:has-text('Create your first loan')")
    page.wait_for_timeout(300)
    page.fill("input[name=name]", "DCarlile Home Loan")
    page.fill("input[name=principal]", "30050")
    page.fill("input[name=annual_rate]", "5.75")
    page.select_option("select[name=frequency]", "fortnightly")
    page.fill("input[name=start_date]", "2026-02-20")
    page.fill("input[name=loan_term]", "52")
    page.fill("input[name=fixed_repayment]", "612.39")
    page.click("button:has-text('Create Loan')")

    # Verify dashboard shows
    page.wait_for_timeout(500)
    expect(page.locator("#dash-balance")).not_to_have_text("-")

    # Switch to schedule tab
    page.click("button:has-text('Schedule')")
    page.wait_for_timeout(500)

    # Verify schedule table exists with rows
    rows = page.locator("table tbody tr")
    expect(rows.first).to_be_visible()


def test_mark_repayment_paid(page):
    """Tick checkbox, verify persists after reload."""
    # Create loan first
    page.click("button:has-text('Create your first loan')")
    page.wait_for_timeout(300)
    page.fill("input[name=name]", "Test Loan")
    page.fill("input[name=principal]", "10000")
    page.fill("input[name=annual_rate]", "5")
    page.select_option("select[name=frequency]", "monthly")
    page.fill("input[name=start_date]", "2026-01-01")
    page.fill("input[name=loan_term]", "12")
    page.click("button:has-text('Create Loan')")
    page.wait_for_timeout(500)

    # Go to schedule
    page.click("button:has-text('Schedule')")
    page.wait_for_timeout(500)

    # Check first checkbox
    checkbox = page.locator("input.paid-checkbox").first
    checkbox.check()
    page.wait_for_timeout(500)

    # Reload and verify persistence
    page.reload()
    page.wait_for_timeout(500)
    page.click("button:has-text('Schedule')")
    page.wait_for_timeout(500)
    expect(page.locator("input.paid-checkbox").first).to_be_checked()


def test_add_rate_change(page):
    """Add rate change, verify schedule recalculates."""
    # Create loan
    page.click("button:has-text('Create your first loan')")
    page.wait_for_timeout(300)
    page.fill("input[name=name]", "Rate Test")
    page.fill("input[name=principal]", "30050")
    page.fill("input[name=annual_rate]", "5.75")
    page.select_option("select[name=frequency]", "fortnightly")
    page.fill("input[name=start_date]", "2026-02-20")
    page.fill("input[name=loan_term]", "52")
    page.fill("input[name=fixed_repayment]", "612.39")
    page.click("button:has-text('Create Loan')")
    page.wait_for_timeout(500)

    # Go to schedule
    page.click("button:has-text('Schedule')")
    page.wait_for_timeout(500)

    # Note initial total interest
    initial = page.locator(".total-interest").text_content()

    # Add rate change (click the "+ Add" button in the Rate Changes section)
    page.locator(".bg-violet-50 button:has-text('+ Add')").click()
    page.wait_for_timeout(300)
    page.fill("input[name=rate_date]", "2026-09-01")
    page.fill("input[name=new_rate]", "6.0")
    page.click("button:has-text('Preview Impact')")
    page.wait_for_timeout(500)
    page.click("button:has-text('Confirm & Save')")
    page.wait_for_timeout(500)

    # Verify interest changed
    new_interest = page.locator(".total-interest").text_content()
    assert new_interest != initial


def test_delete_loan(page):
    """Delete loan, verify return to empty state."""
    # Create loan
    page.click("button:has-text('Create your first loan')")
    page.wait_for_timeout(300)
    page.fill("input[name=name]", "To Delete")
    page.fill("input[name=principal]", "5000")
    page.fill("input[name=annual_rate]", "5")
    page.select_option("select[name=frequency]", "monthly")
    page.fill("input[name=start_date]", "2026-01-01")
    page.fill("input[name=loan_term]", "12")
    page.click("button:has-text('Create Loan')")
    page.wait_for_timeout(500)

    # Delete loan from dashboard
    page.click("text=Delete Loan")
    page.click("text=Confirm Delete")
    page.wait_for_timeout(500)

    # Verify empty state
    expect(page.locator("button:has-text('Create your first loan')")).to_be_visible()
