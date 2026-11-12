from __future__ import annotations

from concurrent.futures import Future, ThreadPoolExecutor
from threading import Lock
from typing import Any

from fpg_lab.flows.p01 import P01FlowRunner


class P01JobManager:
    def __init__(self, runner: P01FlowRunner, *, max_workers: int = 1) -> None:
        self.runner = runner
        self._executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="p01")
        self._futures: dict[int, Future[None]] = {}
        self._lock = Lock()
        self._closed = False

    def submit(self, experiment_id: int, flow_type: str) -> None:
        with self._lock:
            if self._closed:
                raise RuntimeError("The P01 job manager is closed")
            existing = self._futures.get(experiment_id)
            if existing is not None and not existing.done():
                return
            future = self._executor.submit(self.runner.run, experiment_id, flow_type)
            self._futures[experiment_id] = future

            def remove_completed(completed: Future[None], item_id: int = experiment_id) -> None:
                self._remove(item_id, completed)

        # Completed futures invoke callbacks immediately; never hold the callback's lock.
        future.add_done_callback(remove_completed)

    def shutdown(self, *, wait: bool = True) -> None:
        with self._lock:
            self._closed = True
        self._executor.shutdown(wait=wait, cancel_futures=False)

    def submit_task(self, function, *args):
        with self._lock:
            if self._closed:
                raise RuntimeError("The P01 job manager is closed")
            return self._executor.submit(function, *args)

    def active_ids(self) -> tuple[int, ...]:
        with self._lock:
            return tuple(key for key, future in self._futures.items() if not future.done())

    def _remove(self, experiment_id: int, _future: Future[Any]) -> None:
        with self._lock:
            if self._futures.get(experiment_id) is _future:
                self._futures.pop(experiment_id, None)
