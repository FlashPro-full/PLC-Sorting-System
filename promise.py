import asyncio
import logging

logger = logging.getLogger(__name__)

class Promise:
    def __init__(self, coro, loop=None):
        self.coro = coro
        self.callback = None
        self.error_callback = None
        self.loop = loop
        self.task = None
    
    def then(self, callback):
        self.callback = callback
        if self.task is None:
            self._start()
        return self
    
    def catch(self, error_callback):
        self.error_callback = error_callback
        if self.task is None:
            self._start()
        return self
    
    def _start(self):
        try:
            current_loop = asyncio.get_running_loop()
            self.loop = current_loop
        except RuntimeError:
            try:
                self.loop = asyncio.get_event_loop()
            except RuntimeError:
                self.loop = asyncio.new_event_loop()
        
        if self.loop.is_running():
            self.task = asyncio.create_task(self._run())
        else:
            self.task = asyncio.run_coroutine_threadsafe(self._run(), self.loop)
    
    async def _run(self):
        try:
            result = await self.coro
            if self.callback:
                self.callback(result)
        except Exception as e:
            logger.error(f"❌ Promise error: {e}", exc_info=True)
            if self.error_callback:
                self.error_callback(e)
            elif self.callback:
                self.callback(None)

