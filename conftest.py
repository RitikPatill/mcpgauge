"""Root conftest — register anyio pytest plugin for async test support."""

pytest_plugins = ("anyio",)


def pytest_configure(config):
    config.addinivalue_line("markers", "integration: requires subprocess (slow)")
