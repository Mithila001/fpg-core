from __future__ import annotations

from fpg_core.domain import ExecutionMetadata, ExecutionMode, FeatureExecution


def test_shared_execution_contract_is_stable() -> None:
    assert ExecutionMode.PRODUCTION.value == "production"
    assert ExecutionMode.DEBUG.value == "debug"

    metadata = ExecutionMetadata(mode=ExecutionMode.DEBUG, duration_seconds=0.0)
    execution = FeatureExecution(result="ok", details={"trace": True}, metadata=metadata)

    assert execution.result == "ok"
    assert execution.details == {"trace": True}
    assert execution.metadata is metadata
