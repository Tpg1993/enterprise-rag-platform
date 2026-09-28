"""Unit tests for Production Containerization, Docker Compose Profiles, and CI/CD (Phase 30)."""

from pathlib import Path

import yaml


def get_repo_root() -> Path:
    """Finds repository root directory."""
    current = Path(__file__).resolve().parent
    while current != current.parent:
        if (current / "pyproject.toml").exists():
            return current
        current = current.parent
    raise FileNotFoundError("Could not find repository root containing pyproject.toml")


def test_dockerfile_compliance() -> None:
    """Verifies that Dockerfile strictly adheres to multi-stage, non-root,

    and healthcheck requirements from AGENTS.md Section 8.
    """
    root = get_repo_root()
    dockerfile_path = root / "Dockerfile"
    assert dockerfile_path.exists(), "Dockerfile must exist at repository root"

    content = dockerfile_path.read_text(encoding="utf-8")

    assert "AS builder" in content, "Must use multi-stage build with builder stage"
    assert "AS runner" in content, "Must use multi-stage build with runner stage"
    assert "uv sync --frozen --no-dev" in content, (
        "Must use uv sync with frozen lockfile and no-dev"
    )
    assert "uid 10001" in content or "UID 10001" in content or "10001" in content, (
        "Must configure unprivileged user with UID 10001"
    )
    assert "USER appuser" in content, "Must switch to non-root appuser"
    assert "EXPOSE 8000" in content, "Must expose port 8000"
    assert "HEALTHCHECK" in content, "Must define container HEALTHCHECK instruction"
    assert "/api/v1/health" in content, "HEALTHCHECK must target /api/v1/health"


def test_docker_compose_profiles() -> None:
    """Verifies that docker-compose.yml defines all 5 mandatory enterprise profiles:

    core, search, graph, observability, security.
    """
    root = get_repo_root()
    compose_path = root / "docker-compose.yml"
    assert compose_path.exists(), "docker-compose.yml must exist at repository root"

    with open(compose_path, encoding="utf-8") as f:
        compose_data = yaml.safe_load(f)

    services = compose_data.get("services", {})
    assert "api" in services, "Must define api service"
    assert "qdrant" in services, "Must define qdrant vector store"
    assert "redis" in services, "Must define redis cache"
    assert "postgres" in services, "Must define postgres relational store"
    assert "neo4j" in services, "Must define neo4j graph database"
    assert "opensearch" in services, "Must define opensearch lexical search"
    assert "prometheus" in services, "Must define prometheus metrics collector"
    assert "grafana" in services, "Must define grafana telemetry dashboard"
    assert "opa" in services, "Must define opa security policy agent"

    # Verify profile assignments
    all_profiles = set()
    for s_name, s_conf in services.items():
        profiles = s_conf.get("profiles", [])
        all_profiles.update(profiles)

    expected_profiles = {"core", "graph", "search", "observability", "security"}
    diff = expected_profiles - all_profiles
    assert expected_profiles.issubset(all_profiles), f"Missing profiles: {diff}"


def test_github_actions_ci_workflow() -> None:
    """Verifies that GitHub Actions CI workflow is configured and valid YAML."""
    root = get_repo_root()
    ci_path = root / ".github" / "workflows" / "ci.yml"
    assert ci_path.exists(), "ci.yml must exist at .github/workflows/"

    with open(ci_path, encoding="utf-8") as f:
        ci_data = yaml.safe_load(f)

    assert "jobs" in ci_data, "CI workflow must define jobs"
    jobs = ci_data["jobs"]

    assert "lint-and-typecheck" in jobs, "Must have lint-and-typecheck job"
    assert "test-suite" in jobs, "Must have test-suite job"
    assert "docker-build" in jobs, "Must have docker-build job"
