"""Live Jev end-to-end example. Requires TYPESAFE_API_KEY."""

from jev_control_plane import (
    AgentState,
    ControlAction,
    ControlPlane,
    DecisionRequest,
    DecisionView,
    DeterministicPolicy,
    PolicyConfig,
    Primitive,
    TransparentEvidenceAggregator,
    TypeSafeJevAdapter,
)


def main() -> None:
    request = DecisionRequest(
        decision_id="example-001",
        agent_state=AgentState(
            user_request="Prepare and send the weekly report.",
            previous_action="prepared report draft",
            tool_result="Draft has been prepared.",
            current_action="send the report to the user",
        ),
        question="Should the agent send this report?",
        views=(
            DecisionView(
                "safety", Primitive.NOUL,
                "Is sending this report safe for the user?",
                action_map={"true": ControlAction.ALLOW, "false": ControlAction.DENY},
            ),
            DecisionView(
                "decision", Primitive.CHOICE,
                "What should happen to the proposed action?",
                criteria={"allow": "Proceed with the action", "deny": "Do not proceed"},
                action_map={"allow": ControlAction.ALLOW, "deny": ControlAction.DENY},
            ),
        ),
        metadata={"task_id": "example-task", "step_id": "1", "framework": "custom"},
    )
    plane = ControlPlane(
        TypeSafeJevAdapter(),
        TransparentEvidenceAggregator(),
        DeterministicPolicy(PolicyConfig(minimum_confidence=0.70)),
    )
    record = plane.evaluate(request)
    from jev_control_plane.records import json_safe
    import json
    print(json.dumps(json_safe(record), indent=2))


if __name__ == "__main__":
    main()
