from importlib import import_module


def test_asgi_entry_point_imports() -> None:
    module = import_module("orkafin.main")

    assert module.app.title == "OrkaFin Local V1"
