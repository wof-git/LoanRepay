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


# --- Health ---

def test_health(client):
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json()["status"] == "ok"
