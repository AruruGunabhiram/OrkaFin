from orkafin.api.app import create_app
from orkafin.core.settings import Settings


def test_application_factory_constructs_an_isolated_app() -> None:
    application = create_app(settings=Settings(application_name="Test OrkaFin"))

    assert application.title == "Test OrkaFin"
    assert application.version == "v1"
