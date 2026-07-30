from __future__ import annotations

from collections.abc import Iterable

from .contracts import FloorPlanProcessor
from .exceptions import ConfigurationError


class ProcessorRegistry:
    def __init__(self, processors: Iterable[FloorPlanProcessor] = ()) -> None:
        self._processors: dict[str, FloorPlanProcessor] = {}
        for processor in processors:
            self.register(processor)

    def register(self, processor: FloorPlanProcessor) -> None:
        if processor.processor_id in self._processors:
            raise ConfigurationError(
                f"duplicate processor ID: {processor.processor_id}"
            )
        self._processors[processor.processor_id] = processor

    def resolve(self, processor_id: str) -> FloorPlanProcessor:
        try:
            return self._processors[processor_id]
        except KeyError as exc:
            raise ConfigurationError(f"unknown processor ID: {processor_id}") from exc

    @property
    def processor_ids(self) -> tuple[str, ...]:
        return tuple(self._processors)
