from threading import Event
from types import SimpleNamespace

import pytest
from pydantic import ValidationError
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from fpg_lab.database.models import P01BPreset
from fpg_lab.flows.quick_hint import search_hint_map
from fpg_lab.inputs import P01BInput
from fpg_lab.integrations.fpg_core.adapter import FpgCoreCandidateRejected
from fpg_lab.services.p01b import P01BService, next_preset_name, save_preset
from fpg_lab.services.p01c import P01CService


class Search:
    def __init__(self, scores):
        self.scores = iter(scores)
        self.pending = None
        self.recorded = []
        self.remaining = len(scores)

    @property
    def has_remaining_trials(self):
        return self.remaining > 0

    def ask(self):
        try:
            self.pending = next(self.scores)
        except StopIteration:
            raise AssertionError("Unexpected extra trial") from None
        self.remaining -= 1
        return SimpleNamespace(candidate=self.pending)

    def record_score(self, trial, score):
        self.recorded.append(score)

    def fail_pending(self):
        pass


class Adapter:
    def __init__(self, scores):
        self.search = Search(scores)

    def preprocess(self, request, *, debug):
        return SimpleNamespace(result=SimpleNamespace(generation_spec="spec"))

    def create_candidate_search(self, prepared, *, trial_count):
        return self.search

    def run_circulation(self, candidate, *, debug):
        if candidate is None:
            raise FpgCoreCandidateRejected("rejected", cause_type="test")
        return SimpleNamespace(result=SimpleNamespace(candidate=candidate))

    def score_candidate(self, specification, circulation, *, debug):
        return circulation.result.candidate

    def final_score(self, scoring):
        return scoring

    def generation_specification_for_candidate(self, prepared, candidate):
        return {"candidate": candidate}


@pytest.mark.parametrize(
    "scores,threshold,expected,completed",
    [
        ([20, 70, 90], 70, 70, 2),
        ([40, 30, 40], 90, 40, 3),
        ([None, 60], 90, 60, 2),
    ],
)
def test_quick_search_selects_best(monkeypatch, scores, threshold, expected, completed):
    monkeypatch.setattr("fpg_lab.flows.quick_hint.validate_export", lambda data: None)
    adapter = Adapter(scores)
    state = {"completed": 0}
    search_hint_map(
        adapter, {}, {"project_units_per_meter": 10}, len(scores), threshold, state, Event()
    )
    assert state["status"] == "completed"
    assert state["completed"] == completed
    assert state["best_score"] == expected
    assert state["result"]["candidate"] == expected
    assert state["result"]["specification"] == {"candidate": expected}


def test_no_candidate_and_cancel(monkeypatch):
    monkeypatch.setattr("fpg_lab.flows.quick_hint.validate_export", lambda data: None)
    state = {"completed": 0}
    search_hint_map(Adapter([None]), {}, {"project_units_per_meter": 10}, 1, 70, state, Event())
    assert state["status"] == "failed"
    cancel = Event()
    cancel.set()
    state = {"completed": 0}
    search_hint_map(Adapter([70]), {}, {"project_units_per_meter": 10}, 1, 70, state, cancel)
    assert state["status"] == "cancelled"
    assert state["result"] is None


def test_search_exhausted_returns_best(monkeypatch):
    monkeypatch.setattr("fpg_lab.flows.quick_hint.validate_export", lambda data: None)
    state = {"completed": 0}
    search_hint_map(Adapter([40, 60]), {}, {"project_units_per_meter": 10}, 5, 90, state, Event())
    assert state["best_score"] == 60
    assert state["stop_reason"] == "Candidate search exhausted"


def test_preset_input_requires_exactly_one():
    common = {"initial_time_limit": 5}
    assert P01BInput.model_validate({**common, "preset_id": 1}).preset_id == 1
    assert P01BInput.model_validate({**common, "preset_data": {}}).preset_data == {}
    for payload in (common, {**common, "preset_id": 1, "preset_data": {}}):
        with pytest.raises(ValidationError):
            P01BInput.model_validate(payload)


def test_preset_saving_and_inline_input(monkeypatch):
    monkeypatch.setattr(
        "fpg_lab.integrations.fpg_core.p01b_input.validate_export", lambda data: None
    )
    engine = create_engine("sqlite://")
    P01BPreset.__table__.create(engine)
    with Session(engine) as session:
        assert next_preset_name(session) == "hintMap_001"
        save_preset(session, "hintMap_999", {"request": {}})
        assert next_preset_name(session) == "hintMap_1000"
        saved_id = save_preset(session, "hintMap_1000", {"request": {}}, "hintMap_1000")
        assert session.get(P01BPreset, saved_id).name == "hintMap_1000"
        with pytest.raises(ValueError, match="already exists"):
            save_preset(session, "hintMap_999", {"request": {}})
        before = len(session.scalars(select(P01BPreset)).all())
        document = {"request": {"rooms": ["original"]}}
        for service_type in (P01BService, P01CService):
            service = service_type(session)
            monkeypatch.setattr(service, "_create_experiment", lambda **kwargs: kwargs)
            result = service.create_experiment(
                P01BInput(preset_data=document, initial_time_limit=5)
            )
            assert result["hint_points"]["preset"] == document
            assert result["hint_points"]["preset_name"] == "Unsaved hint map"
        assert len(session.scalars(select(P01BPreset)).all()) == before
