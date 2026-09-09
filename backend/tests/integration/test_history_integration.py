"""Integration tests for Persistent Chat and Evaluation History REST APIs."""

import pytest
from httpx import ASGITransport, AsyncClient
from src.api.main import app


@pytest.mark.asyncio
async def test_chat_session_and_history_api():
    """Tests automatic chat history persistence and retrieval via REST API."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        session_id = "sess_api_test_01"
        tenant_id = "tenant_history_test"

        # 1. Send chat message with session_id
        chat_payload = {
            "query": "How is multi-tenancy enforced across vector stores?",
            "rag_strategy": "Basic",
            "session_id": session_id,
            "tenant_id": tenant_id,
            "user_id": "usr_history_tester",
        }
        chat_res = await client.post("/api/v1/chat", json=chat_payload)
        assert chat_res.status_code == 200

        # 2. Query chat history
        hist_res = await client.get(
            f"/api/v1/chat/history?session_id={session_id}&tenant_id={tenant_id}"
        )
        assert hist_res.status_code == 200
        hist_data = hist_res.json()
        assert hist_data["total_messages"] >= 2
        assert hist_data["messages"][0]["role"] == "user"
        assert hist_data["messages"][1]["role"] == "assistant"
        assert hist_data["messages"][1]["rag_strategy"] == "Basic"

        # 3. Query sessions list
        sess_res = await client.get(f"/api/v1/chat/sessions?tenant_id={tenant_id}")
        assert sess_res.status_code == 200
        sess_data = sess_res.json()
        assert sess_data["total_sessions"] >= 1


@pytest.mark.asyncio
async def test_evaluation_history_api():
    """Tests evaluation execution and historical tracking endpoint."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        tenant_id = "tenant_eval_hist_test"

        # 1. Run evaluation
        eval_payload = {
            "query": "What are the core components of RAG?",
            "rag_strategy": "Hybrid",
            "tenant_id": tenant_id,
        }
        eval_run_res = await client.post("/api/v1/evaluations/run", json=eval_payload)
        assert eval_run_res.status_code == 200

        # 2. Query evaluation history
        eval_hist_res = await client.get(f"/api/v1/evaluations/history?tenant_id={tenant_id}")
        assert eval_hist_res.status_code == 200
        eval_hist_data = eval_hist_res.json()
        assert eval_hist_data["total_runs"] >= 1
        run = eval_hist_data["history"][0]
        assert run["strategy"] == "Hybrid"
        assert "overall_score" in run
        assert "faithfulness" in run
