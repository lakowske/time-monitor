"""CLI module for time-monitor application with ncurses support."""

import curses
import logging
import signal
import sys
import time
from datetime import datetime, timezone
from typing import Any, Optional

import click

logger = logging.getLogger(__name__)


class TimeMonitor:
    """Time monitor with configurable update interval and ncurses display."""

    def __init__(self, update_interval: float = 0.05) -> None:
        """Initialize the time monitor.

        Args:
            update_interval: Update interval in seconds (default: 0.05 = 50ms)
        """
        self.update_interval = update_interval
        self.running = False
        self.stdscr: Optional[curses.window] = None
        logger.info(f"TimeMonitor initialized - update_interval: {update_interval}s")

    def setup_signal_handlers(self) -> None:
        """Set up signal handlers for graceful shutdown."""

        def signal_handler(signum: int, frame: Any) -> None:
            logger.info(f"Received signal {signum}, shutting down gracefully")
            self.running = False

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

    def init_curses(self) -> None:
        """Initialize curses display."""
        logger.debug("Initializing curses display")
        self.stdscr = curses.initscr()
        if self.stdscr is None:
            msg = "Failed to initialize curses"
            logger.error(msg)
            raise RuntimeError(msg)
        curses.noecho()
        curses.cbreak()
        self.stdscr.keypad(True)
        self.stdscr.nodelay(True)
        curses.curs_set(0)  # Hide cursor

    def cleanup_curses(self) -> None:
        """Clean up curses display."""
        logger.debug("Cleaning up curses display")
        if self.stdscr:
            curses.nocbreak()
            self.stdscr.keypad(False)
            curses.echo()
            curses.endwin()

    def format_time(self) -> str:
        """Format current time for display.

        Returns:
            Formatted time string with milliseconds
        """
        now = datetime.now(timezone.utc)
        return now.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]

    def run(self) -> None:
        """Run the time monitor main loop."""
        logger.info("Starting time monitor main loop")
        self.running = True
        self.setup_signal_handlers()

        try:
            self.init_curses()

            while self.running:
                # Check for 'q' key press to quit
                if self.stdscr is not None:
                    key = self.stdscr.getch()
                    if key == ord("q") or key == ord("Q"):
                        logger.info("User requested quit via 'q' key")
                        break

                    # Clear screen and display time
                    self.stdscr.clear()
                    time_str = self.format_time()

                    # Get screen dimensions for centering
                    height, width = self.stdscr.getmaxyx()
                    y = height // 2
                    x = max(0, (width - len(time_str)) // 2)

                    # Display time and instructions
                    self.stdscr.addstr(y, x, time_str)
                    self.stdscr.addstr(height - 2, 0, "Press 'q' to quit")

                    # Refresh display
                    self.stdscr.refresh()
                else:
                    # If stdscr is None, we can't continue
                    logger.error("stdscr is None, cannot continue")
                    break

                # Sleep for the specified interval
                time.sleep(self.update_interval)

        except KeyboardInterrupt:
            logger.info("Received KeyboardInterrupt, shutting down")
        except Exception as e:
            logger.error(f"Unexpected error in main loop: {str(e)}", exc_info=True)
            raise
        finally:
            self.running = False
            self.cleanup_curses()
            logger.info("Time monitor shutdown complete")


@click.command()  # type: ignore[misc]
@click.option("--interval", "-i", type=float, default=0.05, help="Update interval in seconds (default: 0.05 = 50ms)")  # type: ignore[misc]
@click.option("--verbose", "-v", is_flag=True, help="Enable verbose logging")  # type: ignore[misc]
def main(interval: float, verbose: bool) -> None:
    """Time monitor CLI that displays current time with configurable update interval.

    The display updates on the same line using ncurses and can be configured
    to update as frequently as every 50ms.

    Controls:
    - Press 'q' to quit
    - Ctrl+C to force quit
    """
    # Configure logging
    log_level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s",
        handlers=[
            logging.FileHandler("time-monitor.log"),
            logging.StreamHandler(sys.stderr) if verbose else logging.NullHandler(),
        ],
    )

    logger.info(f"Starting time monitor CLI - interval: {interval}s, verbose: {verbose}")

    if interval <= 0:
        click.echo("Error: Interval must be greater than 0", err=True)
        logger.error(f"Invalid interval provided: {interval}")
        sys.exit(1)

    if interval < 0.001:
        click.echo("Warning: Very small intervals may cause high CPU usage", err=True)
        logger.warning(f"Small interval detected: {interval}s - may cause high CPU usage")

    try:
        monitor = TimeMonitor(update_interval=interval)
        monitor.run()
    except Exception as e:
        logger.error(f"Failed to run time monitor: {str(e)}", exc_info=True)
        click.echo(f"Error: {str(e)}", err=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
