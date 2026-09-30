"""Jev adapter boundary and adapter for TypeSafe's official Python SDK."""

from __future__ import annotations

from dataclasses import dataclass, field
from math import isfinite
from time import perf_counter
from typing import Any, Mapping, Protocol

from .domain import DecisionRequest, DecisionView, JevResult, Primitive


class JevAdapter(Protocol):
    def evaluate(self, request: DecisionRequest) -> tuple[JevResult, ...]: ...


@dataclass
class TypeSafeJevAdapter:
    """Batch views through the official TypeSafe ``system_one`` SDK method."""

    client: Any | None = None
    noul_yes_threshold: float = 0.5
    model: str | None = None
    _owns_client: bool = field(default=False, init=False, repr=False)

    def __post_init__(self) -> None:
        if not 0 <= self.noul_yes_threshold <= 1:
            raise ValueError("noul_yes_threshold must be between 0 and 1")

    def evaluate(self, request: DecisionRequest) -> tuple[JevResult, ...]:
        client = self.client
        owned = client is None
        if owned:
            client = self._new_client()
        questions = {view.view_id: self._question(view) for view in request.views}
        started = perf_counter()
        try:
            response = client.system_one(
                state=request.to_jev_state(),
                questions=questions,
                **({"model": self.model} if self.model else {}),
            )
        finally:
            elapsed_ms = (perf_counter() - started) * 1000
            if owned:
                client.close()
        return tuple(
            self._normalize(view, response, elapsed_ms)
            for view in request.views
        )

    def prepare(self) -> None:
        """Validate SDK credentials locally before the runner writes a run record.

        TypeSafeClient construction validates configuration without sending a
        request. Reusing the prepared client avoids reconstructing it per case.
        """
        if self.client is not None:
            return
        self.client = self._new_client()
        self._owns_client = True

    def close(self) -> None:
        """Close only a client this adapter prepared itself."""
        if self._owns_client and self.client is not None:
            self.client.close()
        if self._owns_client:
            self.client = None
            self._owns_client = False

    @staticmethod
    def _new_client() -> Any:
        try:
            from typesafe_sdk import TypeSafeClient
        except ImportError as exc:
            raise RuntimeError("Install the official SDK with `python -m pip install -e .` to use Jev") from exc
        try:
            return TypeSafeClient()
        except Exception as exc:
            raise RuntimeError(
                "Could not initialize TypeSafe Jev. Configure a valid TYPESAFE_API_KEY before a live run."
            ) from exc

    @staticmethod
    def _question(view: DecisionView) -> Any:
        try:
            from typesafe_sdk import Choice, Noul, Score
        except ImportError as exc:
            raise RuntimeError("Install the official TypeSafe SDK to build Jev questions") from exc
        if view.primitive is Primitive.NOUL:
            return Noul(instructions=view.instructions)
        if view.primitive is Primitive.CHOICE:
            return Choice(instructions=view.instructions, criteria=dict(view.criteria or {}))
        return Score(instructions=view.instructions, criteria=list(view.criteria or ()))

    def _normalize(self, view: DecisionView, response: Any, elapsed_ms: float) -> JevResult:
        groups = {
            Primitive.NOUL: response.nouls,
            Primitive.CHOICE: response.choices,
            Primitive.SCORE: response.scores,
        }
        answer_obj = groups[view.primitive][view.view_id]
        raw = self._as_mapping(answer_obj)
        if view.primitive is Primitive.NOUL:
            probability = float(answer_obj.noul)
            if not isfinite(probability) or not 0 <= probability <= 1:
                raise ValueError(f"Jev Noul probability out of range for {view.view_id}")
            answer: bool | str | float = probability >= self.noul_yes_threshold
            probabilities: Mapping[str, float] | None = {"true": probability, "false": 1 - probability}
            # This binary distribution is derived from Noul's one reported
            # probability, not an additional API output.
        elif view.primitive is Primitive.CHOICE:
            answer = str(answer_obj.choice)
            allowed = set((view.criteria or {}).keys())
            if answer not in allowed:
                raise ValueError(f"Jev Choice answer is not in criteria for {view.view_id}")
            probabilities = self._validate_probabilities(answer_obj.probabilities, view.view_id)
        else:
            answer = float(answer_obj.score)
            criteria = view.criteria or ()
            if not isfinite(answer) or not 0 <= answer <= len(criteria) - 1:
                raise ValueError(f"Jev Score answer is out of rubric range for {view.view_id}")
            probabilities = self._validate_probabilities(answer_obj.probabilities, view.view_id)
        confidence = getattr(answer_obj, "confidence", None)
        if confidence is not None and (not isfinite(float(confidence)) or not 0 <= confidence <= 1):
            raise ValueError(f"Jev confidence out of range for {view.view_id}")
        usage = self._as_mapping(getattr(response, "usage", None)) or None
        # The SDK's request_id is a property backed by a response header and
        # can raise when that optional header is absent.
        try:
            request_id = response.request_id
        except Exception:  # noqa: BLE001 - this optional SDK property may raise if absent
            request_id = None
        return JevResult(
            view_id=view.view_id,
            primitive=view.primitive,
            answer=answer,
            probabilities=probabilities,
            confidence=confidence,
            model=getattr(response, "model", None),
            latency_ms=elapsed_ms,
            raw_answer=raw,
            request_id=request_id,
            usage=usage,
        )

    @staticmethod
    def _validate_probabilities(values: Mapping[str | int, Any], view_id: str) -> Mapping[str | int, float]:
        probabilities = {key: float(value) for key, value in values.items()}
        if not probabilities or any(not isfinite(value) or not 0 <= value <= 1 for value in probabilities.values()):
            raise ValueError(f"Jev probabilities are invalid for {view_id}")
        return probabilities

    @staticmethod
    def _as_mapping(value: Any) -> dict[str, Any]:
        if value is None:
            return {}
        if hasattr(value, "model_dump"):
            return value.model_dump(mode="json")
        if isinstance(value, Mapping):
            return dict(value)
        return {"value": value}
