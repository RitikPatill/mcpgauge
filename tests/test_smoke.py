def test_package_importable():
    import mcpgauge  # noqa: F401


def test_cli_version():
    from typer.testing import CliRunner

    from mcpgauge.cli import app

    # NO_COLOR avoids rich unicode box-drawing chars that can cause encoding
    # errors on Windows. Invoke with no args: typer runs a single registered
    # command directly without requiring the subcommand name.
    result = CliRunner(env={"NO_COLOR": "1"}).invoke(app, [])
    assert result.exit_code == 0
    assert "0.1.0" in result.output
