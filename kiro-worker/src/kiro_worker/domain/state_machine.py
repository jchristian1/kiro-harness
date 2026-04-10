from kiro_worker.domain.enums import TaskStatus

# All allowed transitions: (from_state, to_state) -> True
# Keyed by (from_state, to_state) for direct lookup
ALLOWED_TRANSITIONS: dict[tuple[TaskStatus, TaskStatus], bool] = {
    # T1: created → opening
    (TaskStatus.created, TaskStatus.opening): True,
    # T2: opening → analyzing
    (TaskStatus.opening, TaskStatus.analyzing): True,
    # T2-variant: opening → implementing (implement_now — no analysis step)
    (TaskStatus.opening, TaskStatus.implementing): True,
    # T3: opening → failed
    (TaskStatus.opening, TaskStatus.failed): True,
    # T4: analyzing → awaiting_approval (analyze_then_approve / implement_and_prepare_pr)
    (TaskStatus.analyzing, TaskStatus.awaiting_approval): True,
    # T4-variant: analyzing → implementing (implement_now)
    (TaskStatus.analyzing, TaskStatus.implementing): True,
    # T4-variant: analyzing → done (plan_only or no_action_needed)
    (TaskStatus.analyzing, TaskStatus.done): True,
    # T4-variant: analyzing → awaiting_revision (request_clarification — Kiro needs more input)
    (TaskStatus.analyzing, TaskStatus.awaiting_revision): True,
    # T5: analyzing → failed
    (TaskStatus.analyzing, TaskStatus.failed): True,
    # T6: awaiting_approval → implementing (APPROVAL GATE)
    (TaskStatus.awaiting_approval, TaskStatus.implementing): True,
    # T8: implementing → validating
    (TaskStatus.implementing, TaskStatus.validating): True,
    # T8-variant: implementing → awaiting_revision (request_review or needs_follow_up)
    (TaskStatus.implementing, TaskStatus.awaiting_revision): True,
    # T8-variant: implementing → done (if validation is skipped)
    (TaskStatus.implementing, TaskStatus.done): True,
    # T9: implementing → failed
    (TaskStatus.implementing, TaskStatus.failed): True,
    # T10: validating → done
    (TaskStatus.validating, TaskStatus.done): True,
    # T11: validating → awaiting_revision
    (TaskStatus.validating, TaskStatus.awaiting_revision): True,
    # T12: validating → failed
    (TaskStatus.validating, TaskStatus.failed): True,
    # T13: awaiting_revision → implementing
    (TaskStatus.awaiting_revision, TaskStatus.implementing): True,
    # T14: awaiting_revision → failed
    (TaskStatus.awaiting_revision, TaskStatus.failed): True,
    # T15: validating → done (Project Lead closes without running validation)
    # T16: awaiting_revision → done (Project Lead closes)
    # T17: failed → done (Project Lead closes after reviewing)
    (TaskStatus.validating, TaskStatus.done): True,
    (TaskStatus.awaiting_revision, TaskStatus.done): True,
    (TaskStatus.failed, TaskStatus.done): True,
    # Retry from failed: re-enter appropriate in-progress states
    (TaskStatus.failed, TaskStatus.opening): True,
    (TaskStatus.failed, TaskStatus.analyzing): True,
    (TaskStatus.failed, TaskStatus.implementing): True,
    (TaskStatus.failed, TaskStatus.validating): True,
    # Cancellation: any active in-progress state → awaiting_revision
    # The Project Manager cancelled the run; task is not complete but not failed
    (TaskStatus.opening, TaskStatus.awaiting_revision): True,
    (TaskStatus.analyzing, TaskStatus.awaiting_revision): True,
    (TaskStatus.implementing, TaskStatus.awaiting_revision): True,
    (TaskStatus.validating, TaskStatus.awaiting_revision): True,
}

TERMINAL_STATES: frozenset[TaskStatus] = frozenset({TaskStatus.done, TaskStatus.failed})
RESUMABLE_STATES: frozenset[TaskStatus] = frozenset({TaskStatus.awaiting_approval, TaskStatus.awaiting_revision})


def validate_transition(current: TaskStatus, target: TaskStatus) -> bool:
    """Return True if the transition from current to target is allowed."""
    return (current, target) in ALLOWED_TRANSITIONS


def get_allowed_transitions(current: TaskStatus) -> list[TaskStatus]:
    """Return all states reachable from the current state."""
    return [to for (frm, to) in ALLOWED_TRANSITIONS if frm == current]
