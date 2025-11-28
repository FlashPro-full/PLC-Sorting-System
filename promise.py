import asyncio
import logging
import threading
from typing import Callable, Any

logger = logging.getLogger(__name__)
# Set to INFO level - change to DEBUG for troubleshooting
logger.setLevel(logging.INFO)

# Add console handler if not present
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setLevel(logging.INFO)
    formatter = logging.Formatter('%(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)

class Promise:
    """
    Simple Promise implementation that runs each coroutine in its own thread.
    This ensures all Promises execute independently and concurrently.
    """
    def __init__(self, coro, loop=None):
        self.coro = coro
        self.callback = None
        self.error_callback = None
        self.loop = loop
        self.task = None
        self.thread = None
        self._started = False
    
    def then(self, callback):
        self.callback = callback
        if not self._started:
            self._start()
        return self
    
    def catch(self, error_callback):
        self.error_callback = error_callback
        if not self._started:
            self._start()
        return self
    
    def _start(self):
        """Start executing the coroutine in a separate thread."""
        if self._started:
            logger.warning("⚠️ Promise already started, ignoring duplicate start")
            return
        
        self._started = True
        logger.info(f"🚀 Starting Promise execution in new thread...")
        
        def run_in_thread():
            """Run the coroutine in this thread's event loop."""
            try:
                # Create a new event loop for this thread
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                
                logger.info(f"🔄 Promise thread started, executing coroutine...")
                
                # Run the coroutine with timeout
                try:
                    result = loop.run_until_complete(
                        asyncio.wait_for(self.coro, timeout=30.0)
                    )
                    logger.info(f"✅ Coroutine completed successfully, result: {result is not None}")
                    
                    # Execute callback in this thread (it will handle thread-safety if needed)
                    if self.callback:
                        try:
                            logger.info(f"📞 Executing success callback...")
                            self.callback(result)
                            logger.info(f"✅ Success callback completed")
                        except Exception as callback_error:
                            logger.error(f"❌ Callback error: {callback_error}", exc_info=True)
                            if self.error_callback:
                                try:
                                    self.error_callback(callback_error)
                                except:
                                    pass
                except asyncio.TimeoutError:
                    error_msg = "Promise coroutine timed out after 30 seconds"
                    logger.error(f"⏱️ {error_msg}")
                    if self.error_callback:
                        try:
                            self.error_callback(Exception(error_msg))
                        except Exception as e:
                            logger.error(f"❌ Error callback error: {e}", exc_info=True)
                    elif self.callback:
                        try:
                            self.callback(None)
                        except Exception as e:
                            logger.error(f"❌ Callback error: {e}", exc_info=True)
                except Exception as e:
                    logger.error(f"❌ Promise execution error: {e}", exc_info=True)
                    if self.error_callback:
                        try:
                            self.error_callback(e)
                        except Exception as callback_error:
                            logger.error(f"❌ Error callback error: {callback_error}", exc_info=True)
                    elif self.callback:
                        try:
                            self.callback(None)
                        except Exception as callback_error:
                            logger.error(f"❌ Callback error: {callback_error}", exc_info=True)
                finally:
                    loop.close()
                    logger.info(f"🔄 Promise thread finished")
            except Exception as e:
                logger.error(f"❌ Fatal error in Promise thread: {e}", exc_info=True)
                if self.error_callback:
                    try:
                        self.error_callback(e)
                    except:
                        pass
        
        # Start the thread
        self.thread = threading.Thread(target=run_in_thread, daemon=True, name=f"Promise-{id(self)}")
        self.thread.start()
        logger.info(f"✅ Promise thread started: {self.thread.name}")
