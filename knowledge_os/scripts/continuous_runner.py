#!/usr/bin/env python3
"""Continuous workflow runner for autonomous trading team"""

from __future__ import annotations

import asyncio
import json
import logging
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)
LOGGER = logging.getLogger("continuous_runner")

CONFIG_PATH = Path(".cursor/continuous_config.json")
CURSOR_CLI = "cursor"


class ContinuousWorkflowRunner:
    """Runner orchestrating Cursor-agent workflows in continuous mode."""

    def __init__(self) -> None:
        self.config: Dict[str, Any] = self._load_config()
        self.workflows: Dict[str, Dict[str, Any]] = self.config.get("workflows", {})
        self.is_running: bool = False

    @staticmethod
    def _load_config() -> Dict[str, Any]:
        if not CONFIG_PATH.exists():
            raise FileNotFoundError(
                "continuous_config.json not found. Ensure .cursor/continuous_config.json exists."
            )
        with CONFIG_PATH.open("r", encoding="utf-8") as config_file:
            return json.load(config_file)

    async def run_workflow(self, name: str) -> None:
        workflow = self.workflows.get(name)
        if not workflow:
            LOGGER.error("Workflow %s not configured", name)
            return

        LOGGER.info("Starting workflow: %s", name)
        for step in workflow.get("steps", []):
            try:
                await self._execute_step(step)
                await asyncio.sleep(1)
            except Exception as exc:  # pylint: disable=broad-except
                LOGGER.exception("Error during step %s: %s", step, exc)
                await self._handle_error(step, exc)

    async def _execute_step(self, step: str) -> None:
        handlers: Dict[str, asyncio.coroutine] = {
            "analyze_performance": self._cmd_quant("analyze_current_performance"),
            "generate_improvements": self._sequence([
                self._cmd_quant("suggest_strategy_improvements"),
                self._cmd_trader("validate_improvements"),
            ]),
            "implement_changes": self._cmd_quant("implement_optimizations"),
            "run_backtests": self._cmd_quant("run_backtest_suite"),
            "deploy_to_staging": self._cmd_devops("deploy_strategy_updates"),
            "scan_market_conditions": self._cmd_trader("analyze_market_regime"),
            "adjust_strategy_parameters": self._cmd_quant("optimize_parameters_current_market"),
            "update_risk_limits": self._cmd_risk("update_risk_parameters"),
            "generate_alerts": self._noop,
        }

        handler = handlers.get(step, self._noop)
        await handler()

    async def _handle_error(self, step: str, error: Exception) -> None:
        LOGGER.error("Handling error for step %s: %s", step, error)
        if "risk" in step.lower():
            await self._cmd_risk("handle_system_error")()
        elif "performance" in step.lower():
            await self._cmd_quant("investigate_performance_issue")()
        else:
            await self._cmd_architect("handle_general_error")()

    async def _noop(self) -> None:
        LOGGER.debug("No-op handler executed")

    def _cmd_quant(self, command: str) -> asyncio.coroutine:
        return self._cursor_cmd(f"@quant {command} --auto")

    def _cmd_trader(self, command: str) -> asyncio.coroutine:
        return self._cursor_cmd(f"@trader {command} --auto")

    def _cmd_devops(self, command: str) -> asyncio.coroutine:
        return self._cursor_cmd(f"@devops {command} --auto")

    def _cmd_risk(self, command: str) -> asyncio.coroutine:
        return self._cursor_cmd(f"@risk_manager {command} --auto")

    def _cmd_architect(self, command: str) -> asyncio.coroutine:
        return self._cursor_cmd(f"@system_architect {command} --auto")

    def _sequence(self, tasks: List[asyncio.coroutine]) -> asyncio.coroutine:
        async def _runner() -> None:
            for task in tasks:
                await task()
        return _runner

    def _cursor_cmd(self, command: str) -> asyncio.coroutine:
        async def _runner() -> None:
            LOGGER.info("Triggering Cursor command: %s", command)
            try:
                subprocess.run(
                    [CURSOR_CLI, "cmd", command],
                    check=False,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    encoding="utf-8",
                )
            except FileNotFoundError:
                LOGGER.warning("Cursor CLI not available. Skipping command %s", command)
        return _runner

    async def run_continuous_loop(self) -> None:
        self.is_running = True
        LOGGER.info("Starting continuous operation loop")

        while self.is_running:
            try:
                utc_now = datetime.utcnow()

                # hourly workflow at start of hour
                if utc_now.minute == 0:
                    await self.run_workflow("market_monitoring")

                # morning workflow at 08:00 UTC
                if utc_now.hour == 8 and utc_now.minute == 0:
                    await self.run_workflow("continuous_development")

                await self._check_event_triggers()
                await asyncio.sleep(60)
            except Exception as exc:  # pylint: disable=broad-except
                LOGGER.exception("Error in continuous loop: %s", exc)
                await asyncio.sleep(300)

    async def _check_event_triggers(self) -> None:
        await asyncio.gather(
            self._cmd_devops("run_health_checks")(),
            self._cmd_quant("monitor_live_performance")(),
        )


async def main() -> None:
    runner = ContinuousWorkflowRunner()
    try:
        await runner.run_continuous_loop()
    except KeyboardInterrupt:
        LOGGER.info("Continuous runner interrupted. Shutting down...")
        runner.is_running = False


if __name__ == "__main__":
    asyncio.run(main())
