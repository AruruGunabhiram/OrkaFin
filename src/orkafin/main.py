"""ASGI entry point for local development."""

from orkafin.api.app import create_app

app = create_app()
