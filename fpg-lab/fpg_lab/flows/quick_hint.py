"""Temporary P01 candidate search for a portable hint-map preset."""

from fpg_lab.core.serialization import to_jsonable
from fpg_lab.flows.p01 import score_candidate
from fpg_lab.integrations.fpg_core.adapter import FpgCoreCandidateRejected
from fpg_lab.integrations.fpg_core.p01b_input import validate_export


def search_hint_map(adapter, request, configuration, count, threshold, state, cancel):
    try:
        if cancel.is_set():
            state.update(status="cancelled", result=None)
            return
        prepared = adapter.preprocess(request, debug=False).result
        if cancel.is_set():
            state.update(status="cancelled", result=None)
            return
        search = adapter.create_candidate_search(prepared, trial_count=count)
        best = None
        while state["completed"] < count and search.has_remaining_trials:
            if cancel.is_set():
                state.update(status="cancelled", result=None)
                return
            trial = search.ask()
            try:
                circulation = adapter.run_circulation(trial.candidate, debug=False)
            except FpgCoreCandidateRejected:
                search.record_score(trial, 0.0)
                state["completed"] += 1
                continue
            if cancel.is_set():
                search.fail_pending()
                state.update(status="cancelled", result=None)
                return
            _, score = score_candidate(adapter, prepared.generation_spec, circulation, debug=False)
            if cancel.is_set():
                search.fail_pending()
                state.update(status="cancelled", result=None)
                return
            search.record_score(trial, score)
            state["completed"] += 1
            if best is None or score > best:
                candidate = circulation.result.candidate
                document = {
                    "version": 1,
                    "candidate": to_jsonable(candidate),
                    "specification": to_jsonable(
                        adapter.generation_specification_for_candidate(prepared, candidate)
                    ),
                    "request": request,
                    "project_units_per_meter": configuration["project_units_per_meter"],
                }
                validate_export(document)
                best = score
                state.update(best_score=score, result=document)
            if score >= threshold:
                state.update(status="completed", stop_reason="Required score reached")
                return
        if cancel.is_set():
            state.update(status="cancelled", result=None)
        elif best is None:
            state.update(status="failed", error="No usable hint map was generated.")
        else:
            state.update(
                status="completed",
                stop_reason="Trial limit reached"
                if state["completed"] >= count
                else "Candidate search exhausted",
            )
    except Exception as exc:
        state.update(status="failed", error=str(exc), result=None)
