import asyncio
import logging
import threading
import time
from enum import Enum
from typing import Callable, Any, Coroutine, Optional
from concurrent.futures import ThreadPoolExecutor

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setLevel(logging.INFO)
    formatter = logging.Formatter('%(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)

_loop = None
_loop_thread = None
_loop_lock = threading.Lock()
_callback_executor = ThreadPoolExecutor(max_workers=8, thread_name_prefix="promise-cb")

def _get_loop():
    global _loop, _loop_thread
    with _loop_lock:
        if _loop is None:
            _loop = asyncio.new_event_loop()
            def _run_loop():
                asyncio.set_event_loop(_loop)
                _loop.run_forever()
            _loop_thread = threading.Thread(target=_run_loop, daemon=True)
            _loop_thread.start()
            while not _loop.is_running():
                time.sleep(0.01)
        return _loop

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
        self._started = False
        self._state_lock = threading.Lock()
        
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
            self._invoke_callback(self.callback, self.value, "then")
        elif self.state == PromiseState.REJECTED and self.error_callback is not None and self.reason is not None:
            self._invoke_callback(self.error_callback, self.reason, "then")
        
        return self
    
    def catch(self, error_callback: Callable):
        self.error_callback = error_callback
        
        if not self._started and self.coro:
            self._start()
        elif self.state == PromiseState.REJECTED and self.reason is not None:
            if self.error_callback is not None:
                self._invoke_callback(self.error_callback, self.reason, "catch")
        
        return self
    
    def _execute_executor(self):
        if self.executor:
            def resolve(value):
                with self._state_lock:
                    if self.state != PromiseState.PENDING:
                        return
                    self.state = PromiseState.FULFILLED
                    self.value = value
                    cb = self.callback
                if cb is not None:
                    self._invoke_callback(cb, value, "resolve")
            
            def reject(reason):
                with self._state_lock:
                    if self.state != PromiseState.PENDING:
                        return
                    self.state = PromiseState.REJECTED
                    self.reason = reason
                    ecb = self.error_callback
                if ecb is not None:
                    self._invoke_callback(ecb, reason, "reject")
            
            try:
                self.executor(resolve, reject)
            except Exception as e:
                reject(e)
    
    @staticmethod
    def from_coroutine(coro: Coroutine) -> 'Promise':
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
        promise = Promise(executor=lambda resolve, reject: resolve(value))
        return promise
    
    @staticmethod
    def reject(reason: Exception) -> 'Promise':
        promise = Promise(executor=lambda resolve, reject: reject(reason))
        return promise
    
    def _start(self):
        if self._started:
            return
        self._started = True
        loop = _get_loop()
        future = asyncio.run_coroutine_threadsafe(
            asyncio.wait_for(self.coro, timeout=30.0),
            loop
        )

        def _done(f):
            try:
                result = f.result()
                with self._state_lock:
                    self.state = PromiseState.FULFILLED
                    self.value = result
                    cb = self.callback
                if cb is not None:
                    self._invoke_callback(cb, result, "then")
            except asyncio.TimeoutError:
                timeout_error = Exception("Promise coroutine timed out after 30 seconds")
                with self._state_lock:
                    self.state = PromiseState.REJECTED
                    self.reason = timeout_error
                    ecb = self.error_callback
                if ecb is not None:
                    self._invoke_callback(ecb, timeout_error, "timeout")
            except Exception as e:
                with self._state_lock:
                    self.state = PromiseState.REJECTED
                    self.reason = e
                    ecb = self.error_callback
                if ecb is not None:
                    self._invoke_callback(ecb, e, "error")

        future.add_done_callback(_done)

    def _invoke_callback(self, cb: Callable, arg: Any, where: str):
        def _runner():
            try:
                cb(arg)
            except Exception as e:
                logger.error(f"❌ Callback error in {where}: {e}", exc_info=True)
        _callback_executor.submit(_runner)
