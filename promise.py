import asyncio
import logging
import threading
from enum import Enum
from typing import Callable, Any, Coroutine, Optional
from contextlib import suppress

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setLevel(logging.INFO)
    formatter = logging.Formatter('%(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)

class PromiseState(Enum):
    PENDING = "pending"
    FULFILLED = "fulfilled"
    REJECTED = "rejected"

class Promise:
    def __init__(self, coro: Optional[Coroutine] = None, executor: Optional[Callable] = None, loop=None):
        if coro is None and executor is None:
            raise ValueError("Either coro or executor must be provided")
        
        self.coro = coro
        self.executor = executor
        self.state = PromiseState.PENDING
        self.value: Any = None
        self.reason: Optional[Exception] = None
        self.callback: Optional[Callable[[Any], None]] = None
        self.error_callback: Optional[Callable[[Exception], None]] = None
        self.loop = loop
        self.task = None
        self.thread = None
        self._started = False
        
        if executor:
            self._execute_executor()
        elif coro:
            pass
    
    def then(self, callback: Optional[Callable] = None, error_callback: Optional[Callable] = None):
        if callback:
            self.callback = callback
        if error_callback:
            self.error_callback = error_callback
        
        if not self._started and self.coro:
            self._start()
        elif self.state == PromiseState.FULFILLED and self.callback is not None:
            try:
                self.callback(self.value)
            except Exception as e:
                logger.error(f"❌ Callback error in then: {e}", exc_info=True)
        elif self.state == PromiseState.REJECTED and self.error_callback is not None and self.reason is not None:
            try:
                self.error_callback(self.reason)
            except Exception as e:
                logger.error(f"❌ Error callback error in then: {e}", exc_info=True)
        
        return self
    
    def catch(self, error_callback: Callable):
        self.error_callback = error_callback
        
        if not self._started and self.coro:
            self._start()
        elif self.state == PromiseState.REJECTED and self.reason is not None:
            if self.error_callback is not None:
                try:
                    self.error_callback(self.reason)
                except Exception as e:
                    logger.error(f"❌ Error callback error in catch: {e}", exc_info=True)
        
        return self
    
    def _execute_executor(self):
        if self.executor:
            def resolve(value):
                if self.state == PromiseState.PENDING:
                    self.state = PromiseState.FULFILLED
                    self.value = value
                    if self.callback is not None:
                        try:
                            self.callback(value)
                        except Exception as e:
                            logger.error(f"❌ Callback error: {e}", exc_info=True)
            
            def reject(reason):
                if self.state == PromiseState.PENDING:
                    self.state = PromiseState.REJECTED
                    self.reason = reason
                    if self.error_callback is not None:
                        try:
                            self.error_callback(reason)
                        except Exception as e:
                            logger.error(f"❌ Error callback error: {e}", exc_info=True)
            
            try:
                self.executor(resolve, reject)
            except Exception as e:
                reject(e)
    
    @staticmethod
    def from_coroutine(coro: Coroutine) -> 'Promise':
        """Create a Promise from a coroutine"""
        def executor(resolve, reject):
            loop = None
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                
                async def run_coro():
                    try:
                        result = await coro
                        resolve(result)
                    except Exception as e:
                        reject(e)
                
                loop.run_until_complete(run_coro())
            finally:
                if loop is not None:
                    try:
                        if not loop.is_closed():
                            try:
                                loop.run_until_complete(loop.shutdown_asyncgens())
                            except:
                                pass
                            try:
                                loop.close()
                            except:
                                pass
                    except:
                        pass
                try:
                    asyncio.set_event_loop(None)
                except:
                    pass
        
        promise = Promise(executor=executor)
        return promise
    
    @staticmethod
    def resolve(value: Any) -> 'Promise':
        """Create a resolved Promise"""
        promise = Promise(executor=lambda resolve, reject: resolve(value))
        return promise
    
    @staticmethod
    def reject(reason: Exception) -> 'Promise':
        """Create a rejected Promise"""
        promise = Promise(executor=lambda resolve, reject: reject(reason))
        return promise
    
    def _start(self):
        if self._started:
            logger.warning("⚠️ Promise already started, ignoring duplicate start")
            return
        
        self._started = True
        logger.info(f"🚀 Starting Promise execution in new thread...")
        
        def run_in_thread():
            loop = None
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                
                logger.info(f"🔄 Promise thread started, executing coroutine...")
                
                result = None
                try:
                    result = loop.run_until_complete(
                        asyncio.wait_for(self.coro, timeout=30.0)
                    )
                    result_type = type(result).__name__
                    result_repr = "None" if result is None else f"{result_type}({bool(result)})"
                    logger.info(f"✅ Coroutine completed successfully, result type: {result_repr}")
                    
                    self.state = PromiseState.FULFILLED
                    self.value = result
                    
                    if self.callback is not None:
                        try:
                            logger.info(f"📞 Executing success callback with result (type: {result_type})...")
                            self.callback(result)
                            logger.info(f"✅ Success callback completed")
                        except Exception as callback_error:
                            logger.error(f"❌ Callback error: {callback_error}", exc_info=True)
                            if self.error_callback is not None:
                                try:
                                    self.error_callback(callback_error)
                                except:
                                    pass
                    else:
                        logger.warning(f"⚠️ Coroutine returned result but no success callback registered")
                except asyncio.TimeoutError:
                    error_msg = "Promise coroutine timed out after 30 seconds"
                    logger.error(f"⏱️ {error_msg}")
                    timeout_error = Exception(error_msg)
                    self.state = PromiseState.REJECTED
                    self.reason = timeout_error
                    if self.error_callback is not None:
                        try:
                            self.error_callback(timeout_error)
                        except Exception as e:
                            logger.error(f"❌ Error callback error: {e}", exc_info=True)
                    else:
                        logger.warning(f"⚠️ Timeout occurred but no error callback registered")
                except Exception as e:
                    logger.error(f"❌ Promise execution error: {e}", exc_info=True)
                    self.state = PromiseState.REJECTED
                    self.reason = e
                    if self.error_callback is not None:
                        try:
                            self.error_callback(e)
                        except Exception as callback_error:
                            logger.error(f"❌ Error callback error: {callback_error}", exc_info=True)
                    else:
                        logger.warning(f"⚠️ Exception occurred but no error callback registered: {e}")
            except Exception as e:
                logger.error(f"❌ Fatal error in Promise thread: {e}", exc_info=True)
                if self.error_callback is not None:
                    try:
                        self.error_callback(e)
                    except:
                        pass
            finally:
                if loop is not None:
                    try:
                        if not loop.is_closed():
                            try:
                                pending = asyncio.all_tasks(loop)
                                if pending:
                                    for task in pending:
                                        task.cancel()
                                    try:
                                        loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
                                    except Exception:
                                        pass
                            except (RuntimeError, ValueError):
                                pass
                            
                            try:
                                loop.run_until_complete(loop.shutdown_asyncgens())
                            except (RuntimeError, ValueError, Exception):
                                pass
                            
                            try:
                                loop.run_until_complete(loop.shutdown_default_executor())
                            except (RuntimeError, ValueError, Exception):
                                pass
                            
                            try:
                                loop.close()
                            except Exception:
                                pass
                    except Exception as cleanup_error:
                        logger.debug(f"Cleanup error (ignored): {cleanup_error}")
                
                try:
                    asyncio.set_event_loop(None)
                except:
                    pass
                
                try:
                    import gc
                    gc.collect()
                except:
                    pass
                
                logger.info(f"🔄 Promise thread finished")
        
        self.thread = threading.Thread(target=run_in_thread, daemon=True, name=f"Promise-{id(self)}")
        self.thread.start()
        logger.info(f"✅ Promise thread started: {self.thread.name}")
