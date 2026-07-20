"""Prepare and run the synthetic, loopback-only OrkaFin Local V1 demo."""

from __future__ import annotations

import argparse
import os
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

import uvicorn
import yaml
from alembic import command
from alembic.config import Config

from orkafin.adapters.orka_ats.seed import reset_mock_state
from orkafin.core.config import AppEnvironment, Settings
from orkafin.knowledge import load_knowledge

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
SAFE_DATABASE_URL = "sqlite:///./var/orkafin.db"
LOOPBACK_HOSTS = frozenset({"127.0.0.1", "localhost", "::1"})


class DemoConfigurationError(RuntimeError):
    """Raised when a requested demo configuration would leave Local V1 boundaries."""


@dataclass(frozen=True, slots=True)
class LocalDemoPlan:
    """Validated inputs for the local fixture-only demo process."""

    subject: str
    host: str
    port: int
    reload: bool


def fixture_subjects(root: Path = REPOSITORY_ROOT) -> frozenset[str]:
    """Load only verified synthetic subjects eligible for the interactive demo."""
    fixture_path = root / "fixtures" / "orka_ats" / "users.yaml"
    try:
        payload = yaml.safe_load(fixture_path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as error:
        raise DemoConfigurationError("the synthetic user fixture is unavailable") from error
    users = payload.get("users") if isinstance(payload, dict) else None
    if not isinstance(users, list):
        raise DemoConfigurationError("the synthetic user fixture is invalid")
    return frozenset(
        user["fixture_id"]
        for user in users
        if isinstance(user, dict)
        and isinstance(user.get("fixture_id"), str)
        and isinstance(user.get("user_id"), str)
    )


def build_local_demo_plan(
    *,
    settings: Settings,
    subject: str,
    host: str,
    port: int,
    reload: bool,
    root: Path = REPOSITORY_ROOT,
) -> LocalDemoPlan:
    """Fail closed unless every enabled boundary is the documented local demo boundary."""
    if settings.environment is not AppEnvironment.LOCAL:
        raise DemoConfigurationError("the demo requires ORKAFIN_ENVIRONMENT=local")
    if not settings.fixture_mode:
        raise DemoConfigurationError("the demo requires ORKAFIN_FIXTURE_MODE=true")
    if settings.ai_provider != "deterministic":
        raise DemoConfigurationError("the demo requires ORKAFIN_AI_PROVIDER=deterministic")
    if settings.ai_provider_api_key and settings.ai_provider_api_key.get_secret_value().strip():
        raise DemoConfigurationError("the demo refuses a configured provider API key")
    if settings.database_url != SAFE_DATABASE_URL:
        raise DemoConfigurationError(
            "the demo requires ORKAFIN_DATABASE_URL=sqlite:///./var/orkafin.db"
        )
    if settings.cors_allow_credentials:
        raise DemoConfigurationError("the demo requires credential-free loopback CORS")
    if host not in LOOPBACK_HOSTS:
        raise DemoConfigurationError("the demo may bind only to a loopback host")
    if not 1 <= port <= 65_535:
        raise DemoConfigurationError("the demo port must be between 1 and 65535")
    if subject not in fixture_subjects(root):
        raise DemoConfigurationError("the demo subject must be a verified synthetic fixture")
    return LocalDemoPlan(subject=subject, host=host, port=port, reload=reload)


def prepare_local_demo(root: Path = REPOSITORY_ROOT) -> tuple[int, int, int, Path]:
    """Migrate Local V1 storage, validate knowledge, and reset adapter-only mock state."""
    alembic_config = Config(str(root / "alembic.ini"))
    alembic_config.set_main_option("script_location", str(root / "migrations"))
    command.upgrade(alembic_config, "head")
    knowledge = load_knowledge(root / "knowledge" / "orka_ats")
    state_path = reset_mock_state()
    return (
        len(knowledge.pages),
        len(knowledge.features),
        len(knowledge.help_articles),
        state_path,
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Prepare and run the synthetic, loopback-only OrkaFin Local V1 demo."
    )
    parser.add_argument("--subject", default="admin", help="Verified synthetic fixture subject.")
    parser.add_argument(
        "--host", default="127.0.0.1", help="Loopback bind host (default: 127.0.0.1)."
    )
    parser.add_argument("--port", type=int, default=8000, help="Loopback port (default: 8000).")
    parser.add_argument("--reload", action="store_true", help="Enable local Uvicorn reload mode.")
    parser.add_argument(
        "--check-only",
        action="store_true",
        help="Validate, migrate, load knowledge, and reset mock state without starting Uvicorn.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _parser()
    arguments = parser.parse_args(argv)
    os.environ["ORKAFIN_LOCAL_FIXTURE_SUBJECT"] = arguments.subject
    try:
        settings = Settings()
        plan = build_local_demo_plan(
            settings=settings,
            subject=arguments.subject,
            host=arguments.host,
            port=arguments.port,
            reload=arguments.reload,
        )
        pages, features, help_articles, state_path = prepare_local_demo()
    except (DemoConfigurationError, ValueError) as error:
        parser.exit(2, f"Refusing to run the local demo: {error}\n")

    print(
        "Local demo checks passed: "
        f"{pages} pages, {features} features, {help_articles} help articles; "
        f"mock state reset at {state_path.relative_to(REPOSITORY_ROOT)}."
    )
    if arguments.check_only:
        return 0
    print(f"Serving the synthetic demo at http://{plan.host}:{plan.port}/demo")
    uvicorn.run("orkafin.main:app", host=plan.host, port=plan.port, reload=plan.reload)
    return 0


if __name__ == "__main__":
    sys.exit(main())
