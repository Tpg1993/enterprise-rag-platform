"""Pytest global configuration and fixtures."""

import os
import pytest

# Ensure MOCK_LLM=true during all unit, integration, and E2E test runs
os.environ["MOCK_LLM"] = "true"
os.environ["MOCK_EMBEDDINGS"] = "true"
