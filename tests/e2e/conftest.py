import os
import time
import shutil
import signal
import tempfile
import subprocess
import pytest


BASE_URL = os.environ.get("BASE_URL", "http://localhost:8099")
SERVER_PORT = 8099


@pytest.fixture(scope="session")
def server():
    """Start FastAPI server as subprocess for E2E tests."""
    tmpdir = tempfile.mkdtemp(prefix="loanrepay_e2e_")
    env = os.environ.copy()
    env["DATA_DIR"] = tmpdir

    proc = subprocess.Popen(
        ["python3", "-m", "uvicorn", "src.main:app", "--port", str(SERVER_PORT)],
        cwd=os.path.join(os.path.dirname(__file__), "..", ".."),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    # Wait for server to start
    import urllib.request
    for _ in range(30):
        try:
            urllib.request.urlopen(f"{BASE_URL}/health", timeout=1)
            break
        except Exception:
            time.sleep(0.5)

    yield proc

    proc.send_signal(signal.SIGTERM)
    proc.wait(timeout=5)
    shutil.rmtree(tmpdir, ignore_errors=True)


@pytest.fixture(scope="function")
def clean_db(server):
    """Reset DB by deleting all loans before each test."""
    import urllib.request
    import json
    # Get all loans and delete them
    try:
        req = urllib.request.Request(f"{BASE_URL}/api/loans")
        with urllib.request.urlopen(req) as resp:
            loans = json.loads(resp.read())
        for loan in loans:
            req = urllib.request.Request(f"{BASE_URL}/api/loans/{loan['id']}", method="DELETE")
            urllib.request.urlopen(req)
    except Exception:
        pass


@pytest.fixture
def page(browser, server, clean_db):
    """Provide a Playwright page pointed at the test server."""
    context = browser.new_context()
    page = context.new_page()
    page.goto(BASE_URL)
    yield page
    context.close()
