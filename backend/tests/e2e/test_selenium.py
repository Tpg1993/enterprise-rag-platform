"""Selenium E2E Web UI Automation Test Suite."""

import socket
import threading
import time
import pytest
import uvicorn
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select
from src.api.main import app


def get_free_port() -> int:
    """Finds a free dynamic port on localhost."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


TEST_PORT = get_free_port()


def run_server(port: int):
    """Runs FastAPI uvicorn server in a daemon thread for Selenium testing."""
    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="error")
    srv = uvicorn.Server(config)
    srv.run()


@pytest.fixture(scope="module", autouse=True)
def server():
    """Fixture to start uvicorn server on dynamic port for Selenium tests."""
    t = threading.Thread(target=run_server, args=(TEST_PORT,), daemon=True)
    t.start()
    for _ in range(30):
        try:
            with socket.create_connection(("127.0.0.1", TEST_PORT), timeout=0.2):
                break
        except Exception:
            time.sleep(0.2)
    yield


def test_selenium_ui_navigation_and_elements():
    """Selenium WebDriver E2E test verifying Web UI rendering, navigation, and DOM elements."""
    driver = None
    # 1. Prefer native Edge driver on Windows
    try:
        from selenium.webdriver.edge.options import Options as EdgeOptions

        edge_options = EdgeOptions()
        edge_options.add_argument("--headless=new")
        edge_options.add_argument("--no-sandbox")
        edge_options.add_argument("--disable-gpu")
        driver = webdriver.Edge(options=edge_options)
    except Exception:
        # Fallback to Chrome driver
        try:
            from selenium.webdriver.chrome.options import Options as ChromeOptions

            chrome_options = ChromeOptions()
            chrome_options.add_argument("--headless=new")
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-gpu")
            driver = webdriver.Chrome(options=chrome_options)
        except Exception as err:
            pytest.skip(f"No headless browser driver available on local machine: {err}")

    try:
        driver.implicitly_wait(5)
        driver.get(f"http://127.0.0.1:{TEST_PORT}/ui/")

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
        assert any("Governance" in t or "RBAC" in t for t in tabs_text)

        # 4. Assert Strategy Selection Dropdown Options (All 15 strategies)
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
        assert "GraphRAG" in option_values
        assert "SQL-RAG" in option_values
        assert "Multimodal" in option_values
        assert "Hybrid-Graph-Agentic" in option_values

        # 5. Assert Governance & Security Inspector Elements (Phase 26)
        gov_btn = next((btn for btn in nav_items if "Governance" in btn.text or "RBAC" in btn.text), None)
        if gov_btn:
            gov_btn.click()
            time.sleep(0.3)
            sec_input = driver.find_element(By.ID, "sec-inspect-input")
            assert sec_input is not None
            sec_btn = driver.find_element(By.ID, "btn-sec-inspect")
            assert sec_btn is not None

        # 6. Test Chat query execution and DOM response
        chat_btn = next((btn for btn in nav_items if "Chat" in btn.text), None)
        if chat_btn:
            chat_btn.click()
            time.sleep(0.3)

        select_elem = Select(strategy_dropdown)
        select_elem.select_by_value("Basic")

        query_input = driver.find_element(By.ID, "query-input")
        send_btn = driver.find_element(By.ID, "send-btn")

        driver.execute_script("arguments[0].scrollIntoView(true);", query_input)
        query_input.clear()
        query_input.send_keys("What is the platform objective?")
        driver.execute_script("arguments[0].click();", send_btn)

        # Wait for assistant response bubble
        time.sleep(2.5)
        messages = driver.find_elements(By.CLASS_NAME, "message")
        assert len(messages) >= 2

    finally:
        if driver:
            driver.quit()
