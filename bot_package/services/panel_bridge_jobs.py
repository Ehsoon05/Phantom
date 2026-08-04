from __future__ import annotations

import logging

from telegram.ext import Application, ContextTypes

from .panel_bridge_service import PanelBridgeService


logger = logging.getLogger(__name__)


async def panel_bridge_discovery_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        stats = await PanelBridgeService.discover_external_configs()
        if stats["imported"] or stats["failed"]:
            logger.info("Panel bridge discovery finished: %s", stats)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Panel bridge discovery failed: %s", exc, exc_info=True)


def register_panel_bridge_jobs(app: Application) -> None:
    if app.job_queue is None:
        logger.warning("JobQueue unavailable; panel bridge discovery was not registered.")
        return
    app.job_queue.run_repeating(
        panel_bridge_discovery_job,
        interval=300,
        first=45,
        name="panel_bridge_external_discovery",
        job_kwargs={"max_instances": 1, "coalesce": True},
    )
    logger.info("Registered panel bridge discovery job.")
