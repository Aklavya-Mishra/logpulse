"""
LogPulse - Ingestion Pipeline
Orchestrates log sources, writes to DB, and feeds the anomaly detector.
"""

import asyncio
from typing import Awaitable, Callable

from config import settings
from ingestion.parser import parse_log_line
from ingestion.simulator import simulate_logs


async def tail_log_file(path: str):
    """Yield parsed log entries from a file, including lines appended later."""
    while True:
        try:
            with open(path, "r", encoding="utf-8") as file:
                while True:
                    line = file.readline()
                    if line:
                        yield parse_log_line(line)
                    else:
                        await asyncio.sleep(0.5)
        except FileNotFoundError:
            await asyncio.sleep(1.0)


async def run_ingestion(on_log: Callable[[dict], Awaitable[None]]):
    """
    Main ingestion loop. Pulls from the configured log source
    and calls `on_log` for each normalized entry.
    """
    if settings.log_source == "simulator":
        async for log in simulate_logs():
            await on_log(log)
    elif settings.log_source == "file":
        async for log in tail_log_file(settings.log_file_path):
            await on_log(log)
    else:
        raise ValueError(
            f"Unsupported LOG_SOURCE '{settings.log_source}'. "
            "Use 'simulator' or 'file'."
        )
