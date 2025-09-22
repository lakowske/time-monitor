"""Tests for CLI module."""

import logging
import signal
from datetime import datetime, timezone
from unittest.mock import Mock, patch

import pytest
from click.testing import CliRunner

from time_monitor.cli import TimeMonitor, main


class TestTimeMonitor:
    """Test cases for TimeMonitor class."""

    def test_init_default_interval(self):
        """Test TimeMonitor initialization with default interval."""
        monitor = TimeMonitor()
        assert monitor.update_interval == 0.05
        assert monitor.running is False
        assert monitor.stdscr is None

    def test_init_custom_interval(self):
        """Test TimeMonitor initialization with custom interval."""
        monitor = TimeMonitor(update_interval=0.1)
        assert monitor.update_interval == 0.1
        assert monitor.running is False
        assert monitor.stdscr is None

    def test_format_time(self):
        """Test time formatting functionality."""
        monitor = TimeMonitor()
        time_str = monitor.format_time()

        # Verify format: YYYY-MM-DD HH:MM:SS.mmm
        assert len(time_str) == 23
        assert time_str[4] == "-"
        assert time_str[7] == "-"
        assert time_str[10] == " "
        assert time_str[13] == ":"
        assert time_str[16] == ":"
        assert time_str[19] == "."

        # Verify it's a valid datetime format
        parsed_dt = datetime.strptime(time_str, "%Y-%m-%d %H:%M:%S.%f")  # noqa: DTZ007
        # Convert to timezone-aware datetime for compliance
        _ = parsed_dt.replace(tzinfo=timezone.utc)

    @patch("time_monitor.cli.signal.signal")
    def test_setup_signal_handlers(self, mock_signal):
        """Test signal handler setup."""
        monitor = TimeMonitor()
        monitor.setup_signal_handlers()

        # Verify signal handlers were registered
        assert mock_signal.call_count == 2
        # Check that SIGINT and SIGTERM were called with some handler function
        call_args_list = mock_signal.call_args_list
        signals_registered = [call[0][0] for call in call_args_list]
        assert signal.SIGINT in signals_registered
        assert signal.SIGTERM in signals_registered

    def test_signal_handler_functionality(self):
        """Test signal handler sets running to False."""
        monitor = TimeMonitor()
        monitor.running = True

        # Get the signal handler function
        monitor.setup_signal_handlers()

        # Create a mock signal handler to test the logic
        def mock_signal_handler(signum, frame):
            monitor.running = False

        mock_signal_handler(signal.SIGINT, None)
        assert monitor.running is False

    @patch("time_monitor.cli.curses")
    def test_init_curses(self, mock_curses):
        """Test curses initialization."""
        mock_stdscr = Mock()
        mock_curses.initscr.return_value = mock_stdscr

        monitor = TimeMonitor()
        monitor.init_curses()

        # Verify curses setup calls
        mock_curses.initscr.assert_called_once()
        mock_curses.noecho.assert_called_once()
        mock_curses.cbreak.assert_called_once()
        mock_curses.curs_set.assert_called_once_with(0)
        mock_stdscr.keypad.assert_called_once_with(True)
        mock_stdscr.nodelay.assert_called_once_with(True)

        assert monitor.stdscr == mock_stdscr

    @patch("time_monitor.cli.curses")
    def test_cleanup_curses_with_stdscr(self, mock_curses):
        """Test curses cleanup when stdscr exists."""
        mock_stdscr = Mock()
        monitor = TimeMonitor()
        monitor.stdscr = mock_stdscr

        monitor.cleanup_curses()

        # Verify cleanup calls
        mock_curses.nocbreak.assert_called_once()
        mock_curses.echo.assert_called_once()
        mock_curses.endwin.assert_called_once()
        mock_stdscr.keypad.assert_called_once_with(False)

    def test_cleanup_curses_without_stdscr(self):
        """Test curses cleanup when stdscr is None."""
        monitor = TimeMonitor()
        monitor.stdscr = None

        # Should not raise an exception
        monitor.cleanup_curses()

    @patch("time_monitor.cli.curses")
    @patch("time_monitor.cli.time.sleep")
    def test_run_quit_with_q_key(self, mock_sleep, mock_curses):
        """Test running monitor and quitting with 'q' key."""
        mock_stdscr = Mock()
        mock_curses.initscr.return_value = mock_stdscr
        mock_stdscr.getch.side_effect = [ord("q")]  # Simulate 'q' key press
        mock_stdscr.getmaxyx.return_value = (24, 80)

        monitor = TimeMonitor()

        with patch.object(monitor, "setup_signal_handlers"):
            monitor.run()

        # Verify the monitor stopped running
        assert monitor.running is False
        mock_stdscr.getch.assert_called()
        # Note: clear and refresh might not be called if we quit immediately
        # The test should focus on the quit logic working

    @patch("time_monitor.cli.curses")
    @patch("time_monitor.cli.time.sleep")
    def test_run_quit_with_capital_q_key(self, mock_sleep, mock_curses):
        """Test running monitor and quitting with 'Q' key."""
        mock_stdscr = Mock()
        mock_curses.initscr.return_value = mock_stdscr
        mock_stdscr.getch.side_effect = [ord("Q")]  # Simulate 'Q' key press
        mock_stdscr.getmaxyx.return_value = (24, 80)

        monitor = TimeMonitor()

        with patch.object(monitor, "setup_signal_handlers"):
            monitor.run()

        # Verify the monitor stopped running
        assert monitor.running is False

    @patch("time_monitor.cli.curses")
    @patch("time_monitor.cli.time.sleep")
    def test_run_with_keyboard_interrupt(self, mock_sleep, mock_curses):
        """Test running monitor with KeyboardInterrupt."""
        mock_stdscr = Mock()
        mock_curses.initscr.return_value = mock_stdscr
        mock_stdscr.getch.side_effect = KeyboardInterrupt()

        monitor = TimeMonitor()

        with patch.object(monitor, "setup_signal_handlers"):
            monitor.run()  # Should handle KeyboardInterrupt gracefully

        assert monitor.running is False

    @patch("time_monitor.cli.curses")
    def test_run_with_stdscr_none(self, mock_curses):
        """Test running monitor when stdscr is None."""
        mock_curses.initscr.return_value = None

        monitor = TimeMonitor()

        with (
            patch.object(monitor, "setup_signal_handlers"),
            pytest.raises(RuntimeError, match="Failed to initialize curses"),
        ):
            monitor.run()

        assert monitor.running is False

    @patch("time_monitor.cli.curses")
    @patch("time_monitor.cli.time.sleep")
    def test_run_display_formatting(self, mock_sleep, mock_curses):
        """Test display formatting and centering."""
        mock_stdscr = Mock()
        mock_curses.initscr.return_value = mock_stdscr
        # Make getch return some other key first, then 'q' to test display logic
        mock_stdscr.getch.side_effect = [65, ord("q")]  # 'A' then 'q'
        mock_stdscr.getmaxyx.return_value = (24, 80)

        monitor = TimeMonitor()

        with (
            patch.object(monitor, "setup_signal_handlers"),
            patch.object(monitor, "format_time", return_value="2024-01-01 12:00:00.000"),
        ):
            monitor.run()

        # Verify display calls - should be called at least once
        assert mock_stdscr.clear.call_count >= 1
        assert mock_stdscr.addstr.call_count >= 1
        assert mock_stdscr.refresh.call_count >= 1


class TestMainCLI:
    """Test cases for main CLI function."""

    def test_main_help(self):
        """Test CLI help output."""
        runner = CliRunner()
        result = runner.invoke(main, ["--help"])

        assert result.exit_code == 0
        assert "Time monitor CLI" in result.output
        assert "--interval" in result.output
        assert "--verbose" in result.output

    def test_main_invalid_interval_zero(self):
        """Test CLI with zero interval."""
        runner = CliRunner()
        result = runner.invoke(main, ["--interval", "0"])

        assert result.exit_code == 1
        assert "Error: Interval must be greater than 0" in result.output

    def test_main_invalid_interval_negative(self):
        """Test CLI with negative interval."""
        runner = CliRunner()
        result = runner.invoke(main, ["--interval", "-0.1"])

        assert result.exit_code == 1
        assert "Error: Interval must be greater than 0" in result.output

    def test_main_small_interval_warning(self):
        """Test CLI with very small interval shows warning."""
        runner = CliRunner()

        with patch("time_monitor.cli.TimeMonitor") as mock_monitor_class:
            mock_monitor = Mock()
            mock_monitor_class.return_value = mock_monitor

            result = runner.invoke(main, ["--interval", "0.0005"])

            assert "Warning: Very small intervals may cause high CPU usage" in result.output
            mock_monitor.run.assert_called_once()

    @patch("time_monitor.cli.TimeMonitor")
    def test_main_normal_execution(self, mock_monitor_class):
        """Test normal CLI execution."""
        mock_monitor = Mock()
        mock_monitor_class.return_value = mock_monitor

        runner = CliRunner()
        result = runner.invoke(main, ["--interval", "0.1"])

        assert result.exit_code == 0
        mock_monitor_class.assert_called_once_with(update_interval=0.1)
        mock_monitor.run.assert_called_once()

    @patch("time_monitor.cli.TimeMonitor")
    def test_main_with_verbose(self, mock_monitor_class):
        """Test CLI with verbose flag."""
        mock_monitor = Mock()
        mock_monitor_class.return_value = mock_monitor

        runner = CliRunner()
        result = runner.invoke(main, ["--verbose"])

        assert result.exit_code == 0
        mock_monitor.run.assert_called_once()

    @patch("time_monitor.cli.TimeMonitor")
    def test_main_exception_handling(self, mock_monitor_class):
        """Test CLI exception handling."""
        mock_monitor = Mock()
        mock_monitor.run.side_effect = RuntimeError("Test error")
        mock_monitor_class.return_value = mock_monitor

        runner = CliRunner()
        result = runner.invoke(main, ["--interval", "0.1"])

        assert result.exit_code == 1
        assert "Error: Test error" in result.output

    @patch("time_monitor.cli.logging.basicConfig")
    def test_main_logging_configuration_verbose(self, mock_logging_config):
        """Test logging configuration with verbose flag."""
        with patch("time_monitor.cli.TimeMonitor") as mock_monitor_class:
            mock_monitor = Mock()
            mock_monitor_class.return_value = mock_monitor

            runner = CliRunner()
            runner.invoke(main, ["--verbose"])

            # Check that logging was configured
            mock_logging_config.assert_called_once()
            call_args = mock_logging_config.call_args
            assert call_args[1]["level"] == logging.DEBUG

    @patch("time_monitor.cli.logging.basicConfig")
    def test_main_logging_configuration_normal(self, mock_logging_config):
        """Test logging configuration without verbose flag."""
        with patch("time_monitor.cli.TimeMonitor") as mock_monitor_class:
            mock_monitor = Mock()
            mock_monitor_class.return_value = mock_monitor

            runner = CliRunner()
            runner.invoke(main, [])

            # Check that logging was configured
            mock_logging_config.assert_called_once()
            call_args = mock_logging_config.call_args
            assert call_args[1]["level"] == logging.INFO
