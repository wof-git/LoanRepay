"""API integration tests — all endpoints."""

import pytest


# --- Loan CRUD ---

def test_create_loan(client, sample_loan_data):
    res = client.post("/api/loans", json=sample_loan_data)
    assert res.status_code == 201
    data = res.json()
    assert data["name"] == "Test Loan"
    assert data["principal"] == 30050.00
    assert data["annual_rate"] == 0.0575
    assert data["frequency"] == "fortnightly"
    assert data["id"] is not None


def test_list_loans(client, created_loan):
    res = client.get("/api/loans")
    assert res.status_code == 200
    data = res.json()
    assert len(data) >= 1
    assert data[0]["name"] == "Test Loan"


def test_get_loan(client, created_loan):
    res = client.get(f"/api/loans/{created_loan['id']}")
    assert res.status_code == 200
    data = res.json()
    assert data["name"] == "Test Loan"
    assert "rate_changes" in data
    assert "extra_repayments" in data


def test_update_loan(client, created_loan):
    res = client.put(f"/api/loans/{created_loan['id']}", json={"name": "Updated Loan"})
    assert res.status_code == 200
    assert res.json()["name"] == "Updated Loan"


def test_delete_loan(client, created_loan):
    res = client.delete(f"/api/loans/{created_loan['id']}")
    assert res.status_code == 200
    # Verify gone
    res = client.get(f"/api/loans/{created_loan['id']}")
    assert res.status_code == 404


def test_create_loan_invalid(client):
    res = client.post("/api/loans", json={"name": "Bad"})
    assert res.status_code == 422


def test_loan_not_found(client):
    assert client.get("/api/loans/999").status_code == 404
    assert client.put("/api/loans/999", json={"name": "x"}).status_code == 404
    assert client.delete("/api/loans/999").status_code == 404


# --- Rate Changes ---

def test_add_rate_change(client, created_loan):
    lid = created_loan["id"]
    res = client.post(f"/api/loans/{lid}/rates", json={
        "effective_date": "2026-09-01",
        "annual_rate": 0.06,
        "note": "RBA hike",
    })
    assert res.status_code == 201
    assert res.json()["annual_rate"] == 0.06


def test_rate_change_before_start_date(client, created_loan):
    lid = created_loan["id"]
    res = client.post(f"/api/loans/{lid}/rates", json={
        "effective_date": "2025-01-01",
        "annual_rate": 0.06,
    })
    assert res.status_code == 422


def test_delete_rate_change(client, created_loan):
    lid = created_loan["id"]
    rc = client.post(f"/api/loans/{lid}/rates", json={
        "effective_date": "2026-09-01",
        "annual_rate": 0.06,
    }).json()
    res = client.delete(f"/api/loans/{lid}/rates/{rc['id']}")
    assert res.status_code == 200


# --- Extra Repayments ---

def test_add_extra_repayment(client, created_loan):
    lid = created_loan["id"]
    res = client.post(f"/api/loans/{lid}/extras", json={
        "payment_date": "2026-06-01",
        "amount": 5000.0,
        "note": "Tax refund",
    })
    assert res.status_code == 201
    assert res.json()["amount"] == 5000.0


def test_delete_extra(client, created_loan):
    lid = created_loan["id"]
    er = client.post(f"/api/loans/{lid}/extras", json={
        "payment_date": "2026-06-01",
        "amount": 1000.0,
    }).json()
    res = client.delete(f"/api/loans/{lid}/extras/{er['id']}")
    assert res.status_code == 200


# --- Schedule ---

def test_schedule(client, created_loan):
    lid = created_loan["id"]
    res = client.get(f"/api/loans/{lid}/schedule")
    assert res.status_code == 200
    data = res.json()
    assert "summary" in data
    assert "rows" in data
    assert data["summary"]["total_repayments"] == 52
    assert len(data["rows"]) == 52


def test_schedule_response_shape(client, created_loan):
    lid = created_loan["id"]
    data = client.get(f"/api/loans/{lid}/schedule").json()
    s = data["summary"]
    assert "total_interest" in s
    assert "total_paid" in s
    assert "payoff_date" in s
    assert "remaining_balance" in s
    assert "payments_made" in s
    assert "progress_pct" in s
    assert "next_payment" in s

    row = data["rows"][0]
    for field in ["number", "date", "opening_balance", "principal", "interest",
                  "rate", "calculated_pmt", "additional", "extra", "closing_balance", "is_paid"]:
        assert field in row


def test_whatif_endpoint(client, created_loan):
    lid = created_loan["id"]
    # Base schedule
    base = client.get(f"/api/loans/{lid}/schedule").json()
    # What-if with higher repayment
    whatif = client.post(f"/api/loans/{lid}/schedule/whatif", json={
        "fixed_repayment": 800.0,
    }).json()
    assert whatif["summary"]["total_repayments"] < base["summary"]["total_repayments"]
    assert whatif["summary"]["total_interest"] < base["summary"]["total_interest"]


def test_schedule_with_rate_change(client, created_loan):
    lid = created_loan["id"]
    base = client.get(f"/api/loans/{lid}/schedule").json()
    # Add rate change
    client.post(f"/api/loans/{lid}/rates", json={
        "effective_date": "2026-09-01",
        "annual_rate": 0.06,
    })
    changed = client.get(f"/api/loans/{lid}/schedule").json()
    assert changed["summary"]["total_interest"] != base["summary"]["total_interest"]


def test_schedule_with_extra(client, created_loan):
    lid = created_loan["id"]
    base = client.get(f"/api/loans/{lid}/schedule").json()
    client.post(f"/api/loans/{lid}/extras", json={
        "payment_date": "2026-06-01",
        "amount": 5000.0,
    })
    with_extra = client.get(f"/api/loans/{lid}/schedule").json()
    assert with_extra["summary"]["total_repayments"] < base["summary"]["total_repayments"]


# --- Paid Repayments ---

def test_mark_paid(client, created_loan):
    lid = created_loan["id"]
    res = client.post(f"/api/loans/{lid}/paid/1")
    assert res.status_code == 200
    # Verify in schedule
    sched = client.get(f"/api/loans/{lid}/schedule").json()
    assert sched["rows"][0]["is_paid"] is True
    assert sched["summary"]["payments_made"] == 1


def test_unmark_paid(client, created_loan):
    lid = created_loan["id"]
    client.post(f"/api/loans/{lid}/paid/1")
    client.delete(f"/api/loans/{lid}/paid/1")
    sched = client.get(f"/api/loans/{lid}/schedule").json()
    assert sched["rows"][0]["is_paid"] is False


def test_mark_paid_idempotent(client, created_loan):
    lid = created_loan["id"]
    client.post(f"/api/loans/{lid}/paid/1")
    res = client.post(f"/api/loans/{lid}/paid/1")
    assert res.status_code == 200  # Should not error


# --- Cascade Delete ---

def test_delete_loan_cascades(client, created_loan):
    lid = created_loan["id"]
    # Add related data
    client.post(f"/api/loans/{lid}/rates", json={"effective_date": "2026-09-01", "annual_rate": 0.06})
    client.post(f"/api/loans/{lid}/extras", json={"payment_date": "2026-06-01", "amount": 1000.0})
    client.post(f"/api/loans/{lid}/paid/1")
    client.post(f"/api/loans/{lid}/scenarios", json={"name": "Test Scenario"})
    # Delete loan
    client.delete(f"/api/loans/{lid}")
    # Verify all gone (loan returns 404)
    assert client.get(f"/api/loans/{lid}").status_code == 404


# --- Scenarios ---

def test_save_scenario(client, created_loan):
    lid = created_loan["id"]
    res = client.post(f"/api/loans/{lid}/scenarios", json={
        "name": "Base Case",
        "description": "Default settings",
    })
    assert res.status_code == 201
    data = res.json()
    assert data["name"] == "Base Case"
    assert data["total_interest"] > 0


def test_list_scenarios(client, created_loan):
    lid = created_loan["id"]
    client.post(f"/api/loans/{lid}/scenarios", json={"name": "S1"})
    client.post(f"/api/loans/{lid}/scenarios", json={"name": "S2"})
    res = client.get(f"/api/loans/{lid}/scenarios")
    assert res.status_code == 200
    assert len(res.json()) == 2


def test_compare_scenarios(client, created_loan):
    lid = created_loan["id"]
    s1 = client.post(f"/api/loans/{lid}/scenarios", json={"name": "S1"}).json()
    s2 = client.post(f"/api/loans/{lid}/scenarios", json={"name": "S2"}).json()
    res = client.get(f"/api/loans/{lid}/scenarios/compare?ids={s1['id']},{s2['id']}")
    assert res.status_code == 200
    data = res.json()
    assert len(data) == 2


def test_delete_scenario(client, created_loan):
    lid = created_loan["id"]
    s = client.post(f"/api/loans/{lid}/scenarios", json={"name": "To Delete"}).json()
    res = client.delete(f"/api/loans/{lid}/scenarios/{s['id']}")
    assert res.status_code == 200
    # Verify gone
    scenarios = client.get(f"/api/loans/{lid}/scenarios").json()
    assert len(scenarios) == 0


# --- Payoff Target ---

def test_payoff_target(client, created_loan):
    lid = created_loan["id"]
    res = client.get(f"/api/loans/{lid}/payoff-target?date=2027-06-01")
    assert res.status_code == 200
    data = res.json()
    assert data["required_repayment"] > 0
    assert data["target_date"] == "2027-06-01"


def test_payoff_target_impossible(client, created_loan):
    lid = created_loan["id"]
    # Target before first payment — impossible
    res = client.get(f"/api/loans/{lid}/payoff-target?date=2026-02-21")
    assert res.status_code == 422


# --- Export ---

def test_export_csv(client, created_loan):
    lid = created_loan["id"]
    res = client.get(f"/api/loans/{lid}/export?format=csv")
    assert res.status_code == 200
    assert "text/csv" in res.headers["content-type"]
    lines = res.text.strip().split("\n")
    assert len(lines) == 53  # header + 52 rows


def test_export_xlsx(client, created_loan):
    lid = created_loan["id"]
    res = client.get(f"/api/loans/{lid}/export?format=xlsx")
    assert res.status_code == 200
    assert "spreadsheetml" in res.headers["content-type"]


# --- Rate Change Preview ---

def test_rate_change_preview_with_fixed_repayment(client, created_loan):
    lid = created_loan["id"]
    res = client.post(f"/api/loans/{lid}/rates/preview", json={
        "effective_date": "2026-09-01",
        "annual_rate": 0.06,
    })
    assert res.status_code == 200
    data = res.json()
    assert data["has_fixed_repayment"] is True
    assert data["current_repayment"] == 612.39
    assert len(data["options"]) == 2
    # Option A: keep repayment
    assert "Keep repayment" in data["options"][0]["label"]
    assert data["options"][0]["fixed_repayment"] == 612.39
    # Option B: adjust repayment
    assert "Adjust repayment" in data["options"][1]["label"]
    assert data["options"][1]["fixed_repayment"] != 612.39


def test_rate_change_preview_without_fixed_repayment(client, sample_loan_data):
    # Create loan without fixed_repayment
    loan_data = {**sample_loan_data, "fixed_repayment": None}
    del loan_data["fixed_repayment"]
    loan = client.post("/api/loans", json=loan_data).json()
    lid = loan["id"]
    res = client.post(f"/api/loans/{lid}/rates/preview", json={
        "effective_date": "2026-09-01",
        "annual_rate": 0.06,
    })
    assert res.status_code == 200
    data = res.json()
    assert data["has_fixed_repayment"] is False
    assert len(data["options"]) == 1


def test_rate_change_with_adjusted_repayment(client, created_loan):
    """Rate change with adjusted_repayment stored on the rate change record."""
    lid = created_loan["id"]
    res = client.post(f"/api/loans/{lid}/rates", json={
        "effective_date": "2026-09-01",
        "annual_rate": 0.06,
        "adjusted_repayment": 620.00,
    })
    assert res.status_code == 201
    data = res.json()
    assert data["adjusted_repayment"] == 620.00
    # Loan's fixed_repayment should NOT change
    loan = client.get(f"/api/loans/{lid}").json()
    assert loan["fixed_repayment"] == 612.39


def test_rate_change_without_adjusted_repayment(client, created_loan):
    lid = created_loan["id"]
    res = client.post(f"/api/loans/{lid}/rates", json={
        "effective_date": "2026-09-01",
        "annual_rate": 0.06,
    })
    assert res.status_code == 201
    assert res.json()["adjusted_repayment"] is None
    loan = client.get(f"/api/loans/{lid}").json()
    assert loan["fixed_repayment"] == 612.39


def test_delete_rate_change_reverts_schedule(client, created_loan):
    """Deleting a rate change with adjusted_repayment reverts the schedule."""
    lid = created_loan["id"]
    # Get base schedule
    base = client.get(f"/api/loans/{lid}/schedule").json()

    # Add rate change with adjusted_repayment
    rc = client.post(f"/api/loans/{lid}/rates", json={
        "effective_date": "2026-09-01",
        "annual_rate": 0.06,
        "adjusted_repayment": 620.00,
    }).json()
    changed = client.get(f"/api/loans/{lid}/schedule").json()
    assert changed["summary"]["total_interest"] != base["summary"]["total_interest"]

    # Delete the rate change — schedule should revert
    client.delete(f"/api/loans/{lid}/rates/{rc['id']}")
    reverted = client.get(f"/api/loans/{lid}/schedule").json()
    assert reverted["summary"]["total_interest"] == base["summary"]["total_interest"]
    assert reverted["summary"]["total_repayments"] == base["summary"]["total_repayments"]


# --- Repayment Changes ---

def test_add_repayment_change(client, created_loan):
    lid = created_loan["id"]
    res = client.post(f"/api/loans/{lid}/repayment-changes", json={
        "effective_date": "2026-06-01",
        "amount": 700.0,
        "note": "Increased repayment",
    })
    assert res.status_code == 201
    data = res.json()
    assert data["amount"] == 700.0
    assert data["effective_date"] == "2026-06-01"


def test_repayment_change_before_start_date(client, created_loan):
    lid = created_loan["id"]
    res = client.post(f"/api/loans/{lid}/repayment-changes", json={
        "effective_date": "2025-01-01",
        "amount": 700.0,
    })
    assert res.status_code == 422


def test_delete_repayment_change(client, created_loan):
    lid = created_loan["id"]
    rc = client.post(f"/api/loans/{lid}/repayment-changes", json={
        "effective_date": "2026-06-01",
        "amount": 700.0,
    }).json()
    res = client.delete(f"/api/loans/{lid}/repayment-changes/{rc['id']}")
    assert res.status_code == 200


def test_repayment_change_in_loan_detail(client, created_loan):
    lid = created_loan["id"]
    client.post(f"/api/loans/{lid}/repayment-changes", json={
        "effective_date": "2026-06-01",
        "amount": 700.0,
    })
    loan = client.get(f"/api/loans/{lid}").json()
    assert "repayment_changes" in loan
    assert len(loan["repayment_changes"]) == 1
    assert loan["repayment_changes"][0]["amount"] == 700.0


def test_schedule_with_repayment_change(client, created_loan):
    lid = created_loan["id"]
    base = client.get(f"/api/loans/{lid}/schedule").json()
    client.post(f"/api/loans/{lid}/repayment-changes", json={
        "effective_date": "2026-06-01",
        "amount": 700.0,
    })
    changed = client.get(f"/api/loans/{lid}/schedule").json()
    # Higher repayment = less total interest and fewer payments
    assert changed["summary"]["total_interest"] < base["summary"]["total_interest"]
    assert changed["summary"]["total_repayments"] < base["summary"]["total_repayments"]


def test_delete_repayment_change_reverts_schedule(client, created_loan):
    lid = created_loan["id"]
    base = client.get(f"/api/loans/{lid}/schedule").json()
    rc = client.post(f"/api/loans/{lid}/repayment-changes", json={
        "effective_date": "2026-06-01",
        "amount": 700.0,
    }).json()
    client.delete(f"/api/loans/{lid}/repayment-changes/{rc['id']}")
    reverted = client.get(f"/api/loans/{lid}/schedule").json()
    assert reverted["summary"]["total_interest"] == base["summary"]["total_interest"]
    assert reverted["summary"]["total_repayments"] == base["summary"]["total_repayments"]


def test_delete_loan_cascades_repayment_changes(client, created_loan):
    """Repayment changes should be deleted when loan is deleted."""
    lid = created_loan["id"]
    client.post(f"/api/loans/{lid}/repayment-changes", json={
        "effective_date": "2026-06-01",
        "amount": 700.0,
    })
    client.delete(f"/api/loans/{lid}")
    assert client.get(f"/api/loans/{lid}").status_code == 404


def test_repayment_change_preview(client, created_loan):
    """Preview shows impact of a proposed repayment change."""
    lid = created_loan["id"]
    # Get base schedule for comparison
    base = client.get(f"/api/loans/{lid}/schedule").json()

    res = client.post(f"/api/loans/{lid}/repayment-changes/preview", json={
        "effective_date": "2026-06-01",
        "amount": 700.0,
    })
    assert res.status_code == 200
    data = res.json()

    # Current values should match the base schedule
    assert data["current_payoff_date"] == base["summary"]["payoff_date"]
    assert data["current_total_interest"] == base["summary"]["total_interest"]
    assert data["current_num_repayments"] == base["summary"]["total_repayments"]

    # Higher repayment -> less interest, fewer payments
    assert data["new_total_interest"] < data["current_total_interest"]
    assert data["new_num_repayments"] < data["current_num_repayments"]
    assert data["interest_delta"] < 0
    assert data["repayment_delta"] < 0


# --- Health ---

def test_health(client):
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json()["status"] == "ok"
