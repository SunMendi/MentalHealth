from concurrent.futures import ThreadPoolExecutor

from asgiref.sync import sync_to_async
from django.db import connections


async def async_stream(sync_iterator):
    """Yield synchronous chat events one at a time without blocking ASGI.

    Passing a sync generator directly to Django under ASGI buffers it into a
    list. Keep the database and provider calls on one worker thread, and deliver
    each result before requesting the next. This also avoids reading ahead when
    the client is slow or disconnects.
    """
    finished = object()
    worker = ThreadPoolExecutor(max_workers=1, thread_name_prefix="chat-stream")

    def next_item():
        # StopIteration cannot cross an asyncio Future boundary.
        return next(sync_iterator, finished)

    def close():
        try:
            closer = getattr(sync_iterator, "close", None)
            if closer is not None:
                closer()
        finally:
            # This worker owns its database connections; request cleanup runs
            # on another thread and cannot close them for us.
            connections.close_all()

    try:
        while True:
            item = await sync_to_async(next_item, thread_sensitive=False, executor=worker)()
            if item is finished:
                return
            yield item
    finally:
        try:
            # Queue cleanup on the same worker, after any in-flight provider
            # call has returned, including when the client disconnects.
            await sync_to_async(close, thread_sensitive=False, executor=worker)()
        finally:
            worker.shutdown(wait=False)
