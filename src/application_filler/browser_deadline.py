"""Bound browser protocol waits, including reads without a public Playwright timeout."""

import asyncio
from contextlib import contextmanager


class BrowserUnresponsive(RuntimeError):
    """Fatal transport failure, separate from recoverable field/validation errors."""


@contextmanager
def browser_deadline(playwright, seconds=60):
    # The sync API has no outer deadline for evaluate/title and similar protocol reads.
    # Keep this compatibility adapter in one place, tested against the locked Playwright.
    # All Playwright work remains on its owning thread and asyncio event loop.
    connection = playwright._impl_obj._connection
    original = connection.wrap_api_call

    async def bounded(callback, *args, **kwargs):
        async def request():
            task = asyncio.ensure_future(callback())
            try:
                done, _ = await asyncio.wait({task}, timeout=seconds)
            except BaseException:
                task.cancel()
                task.add_done_callback(consume)
                raise
            if done:
                return task.result()
            # Cancellation itself can wait for a reply from a frozen browser. Do not
            # await that acknowledgement, and consume any eventual task exception.
            task.cancel()
            task.add_done_callback(consume)
            raise BrowserUnresponsive(
                f"Browser did not respond within {seconds:g} seconds. "
                "Stopped this batch without retrying the unacknowledged action."
            )

        return await original(request, *args, **kwargs)

    def consume(task):
        if not task.cancelled():
            task.exception()

    connection.wrap_api_call = bounded
    try:
        yield
    finally:
        connection.wrap_api_call = original
