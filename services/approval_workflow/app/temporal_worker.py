import asyncio
import logging

from temporalio.client import Client
from temporalio.worker import Worker

from app.config import settings
from app.temporal_workflows import (
    ApprovalWorkflow,
    escalate_step,
    finalize_request,
    mark_step_pending,
    record_decision,
)

logger = logging.getLogger("approval_workflow.temporal_worker")

_worker_task: asyncio.Task | None = None


async def _run_worker() -> None:
    client = await Client.connect(settings.temporal_host, namespace=settings.temporal_namespace)
    worker = Worker(
        client,
        task_queue=settings.temporal_task_queue,
        workflows=[ApprovalWorkflow],
        activities=[mark_step_pending, record_decision, escalate_step, finalize_request],
    )
    logger.info("Temporal worker starting on task queue %s", settings.temporal_task_queue)
    await worker.run()


def start_worker_task() -> None:
    """Runs the Temporal worker inside the FastAPI process's own event loop as a
    background task, so the API and the workflow worker share one container/process
    without needing a second deployable."""
    global _worker_task
    loop = asyncio.get_event_loop()
    _worker_task = loop.create_task(_run_worker())
