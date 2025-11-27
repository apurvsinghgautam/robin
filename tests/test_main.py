"""Tests for the main module (CLI)."""

import pytest
from click.testing import CliRunner


class TestValidateQuery:
    """Tests for query validation."""

    def test_validate_query_valid(self):
        """Test validation of valid query."""
        from main import validate_query

        result = validate_query(None, None, "test query")
        assert result == "test query"

    def test_validate_query_strips_whitespace(self):
        """Test that whitespace is stripped from query."""
        from main import validate_query

        result = validate_query(None, None, "  test query  ")
        assert result == "test query"

    def test_validate_query_empty_raises(self):
        """Test that empty query raises BadParameter."""
        from main import validate_query
        import click

        with pytest.raises(click.BadParameter):
            validate_query(None, None, "")

    def test_validate_query_whitespace_only_raises(self):
        """Test that whitespace-only query raises BadParameter."""
        from main import validate_query
        import click

        with pytest.raises(click.BadParameter):
            validate_query(None, None, "   ")

    def test_validate_query_too_long_raises(self):
        """Test that overly long query raises BadParameter."""
        from main import validate_query
        from constants import MAX_QUERY_LENGTH
        import click

        long_query = "x" * (MAX_QUERY_LENGTH + 1)
        with pytest.raises(click.BadParameter):
            validate_query(None, None, long_query)


class TestValidateOutputPath:
    """Tests for output path validation."""

    def test_validate_output_path_valid(self):
        """Test validation of valid output path."""
        from main import validate_output_path

        result = validate_output_path(None, None, "output_file")
        assert result == "output_file"

    def test_validate_output_path_none(self):
        """Test that None path is allowed."""
        from main import validate_output_path

        result = validate_output_path(None, None, None)
        assert result is None

    def test_validate_output_path_traversal_raises(self):
        """Test that path traversal is rejected."""
        from main import validate_output_path
        import click

        with pytest.raises(click.BadParameter):
            validate_output_path(None, None, "../../../etc/passwd")

    def test_validate_output_path_absolute_unix_raises(self):
        """Test that absolute Unix paths are rejected."""
        from main import validate_output_path
        import click

        with pytest.raises(click.BadParameter):
            validate_output_path(None, None, "/etc/passwd")

    def test_validate_output_path_absolute_windows_raises(self):
        """Test that absolute Windows paths are rejected."""
        from main import validate_output_path
        import click

        with pytest.raises(click.BadParameter):
            validate_output_path(None, None, "C:\\Windows\\System32")


class TestValidateThreads:
    """Tests for thread count validation."""

    def test_validate_threads_valid(self):
        """Test validation of valid thread count."""
        from main import validate_threads

        result = validate_threads(None, None, 10)
        assert result == 10

    def test_validate_threads_minimum(self):
        """Test that minimum thread count is 1."""
        from main import validate_threads

        result = validate_threads(None, None, 1)
        assert result == 1

    def test_validate_threads_maximum(self):
        """Test that maximum thread count is 50."""
        from main import validate_threads

        result = validate_threads(None, None, 50)
        assert result == 50

    def test_validate_threads_zero_raises(self):
        """Test that zero threads raises BadParameter."""
        from main import validate_threads
        import click

        with pytest.raises(click.BadParameter):
            validate_threads(None, None, 0)

    def test_validate_threads_negative_raises(self):
        """Test that negative threads raises BadParameter."""
        from main import validate_threads
        import click

        with pytest.raises(click.BadParameter):
            validate_threads(None, None, -1)

    def test_validate_threads_too_high_raises(self):
        """Test that too many threads raises BadParameter."""
        from main import validate_threads
        import click

        with pytest.raises(click.BadParameter):
            validate_threads(None, None, 100)


class TestCLI:
    """Integration tests for the CLI."""

    def test_cli_help(self):
        """Test that CLI help works."""
        from main import robin

        runner = CliRunner()
        result = runner.invoke(robin, ['--help'])

        assert result.exit_code == 0
        assert "Robin" in result.output

    def test_cli_version(self):
        """Test that CLI version works."""
        from main import robin

        runner = CliRunner()
        result = runner.invoke(robin, ['--version'])

        assert result.exit_code == 0

    def test_cli_subcommand_help(self):
        """Test that CLI subcommand help works."""
        from main import robin

        runner = CliRunner()
        result = runner.invoke(robin, ['cli', '--help'])

        assert result.exit_code == 0
        assert "--query" in result.output
        assert "--model" in result.output
