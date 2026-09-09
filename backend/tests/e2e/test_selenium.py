"""Selenium E2E Web UI Automation Test Suite."""

import multiprocessing
import time
import pytest
import uvicorn
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from src.api.main import app


import socket


def run_server():
    """Runs FastAPI uvicorn server in a separate process for Selenium testing."""
    uvicorn.run(app, host="127.0.0.1", port=8888, log_level="error")


@pytest.fixture(scope="module", autouse=True)
def server():
    """Fixture to start uvicorn server on port 8888 for Selenium tests."""
    p = multiprocessing.Process(target=run_server, daemon=True)
    p.start()
    for _ in range(30):
        try:
            with socket.create_connection(("127.0.0.1", 8888), timeout=0.2):
                break
        except Exception:
            time.sleep(0.2)
    yield
    p.terminate()


def test_selenium_ui_navigation_and_elements():
    """Selenium WebDriver E2E test verifying Web UI rendering and DOM elements."""
    chrome_options = Options()
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")

    driver = None
    try:
        driver = webdriver.Chrome(options=chrome_options)
    except Exception:
        try:
            # Fallback to Edge headless driver if Chrome driver binary is not pre-installed
            from selenium.webdriver.edge.options import Options as EdgeOptions

            edge_options = EdgeOptions()
            edge_options.add_argument("--headless=new")
            driver = webdriver.Edge(options=edge_options)
        except Exception as err:
            pytest.skip(f"No headless browser driver available on local machine: {err}")

    try:
        driver.implicitly_wait(5)
        driver.get("http://127.0.0.1:8888/ui/")

        # 1. Assert Web UI Title
        assert "RAG & Agentic AI Platform" in driver.title

        # 2. Assert Header DOM elements
        header_text = driver.find_element(By.TAG_NAME, "h1").text
        assert "Enterprise RAG & Agentic AI Platform" in header_text

        # 3. Assert Navigation Tab Buttons
        nav_items = driver.find_elements(By.CLASS_NAME, "nav-item")
        assert len(nav_items) >= 5

        tabs_text = [item.text for item in nav_items]
        assert any("Chat" in t for t in tabs_text)
        assert any("Documents" in t for t in tabs_text)
        assert any("Strategies" in t for t in tabs_text)
        assert any("Comparison" in t for t in tabs_text)
        assert any("Traces" in t for t in tabs_text)

        # 4. Assert Strategy Selection Dropdown Options
        strategy_dropdown = driver.find_element(By.ID, "strategy-select")
        options = strategy_dropdown.find_elements(By.TAG_NAME, "option")
        option_values = [opt.get_attribute("value") for opt in options]

        assert "Basic" in option_values
        assert "Hybrid" in option_values
        assert "MMR" in option_values
        assert "Reranked" in option_values
        assert "Parent-Child" in option_values
        assert "Multi-Query" in option_values
        assert "HyDE" in option_values
        assert "Adaptive" in option_values
        assert "Corrective" in option_values
        assert "Self-RAG" in option_values
        assert "ReAct" in option_values

    finally:
        if driver:
            driver.quit()
