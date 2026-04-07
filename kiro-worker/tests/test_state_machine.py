import pytest
from kiro_worker.domain.enums import TaskStatus
from kiro_worker.domain.state_machine import (
    validate_transition,
    get_allowed_transitions,
    TERMINAL_STATES,
    RESUMABLE_STATES,
    ALLOWED_TRANSITIONS,
)


class TestAllowedTransitions:
    def test_created_to_opening(self):
        assert validate_transition(TaskStatus.created, TaskStatus.opening) is True

    def test_opening_to_analyzing(self):
        assert validate_transition(TaskStatus.opening, TaskStatus.analyzing) is True

    def test_opening_to_failed(self):
        assert validate_transition(TaskStatus.opening, TaskStatus.failed) is True

    def test_analyzing_to_awaiting_approval(self):
        assert validate_transition(TaskStatus.analyzing, TaskStatus.awaiting_approval) is True

    def test_analyzing_to_implementing(self):
        assert validate_transition(TaskStatus.analyzing, TaskStatus.implementing) is True

    def test_analyzing_to_done(self):
        assert validate_transition(TaskStatus.analyzing, TaskStatus.done) is True

    def test_analyzing_to_failed(self):
        assert validate_transition(TaskStatus.analyzing, TaskStatus.failed) is True

    def test_awaiting_approval_to_implementing(self):
        assert validate_transition(TaskStatus.awaiting_approval, TaskStatus.implementing) is True

    def test_implementing_to_validating(self):
        assert validate_transition(TaskStatus.implementing, TaskStatus.validating) is True

    def test_implementing_to_failed(self):
        assert validate_transition(TaskStatus.implementing, TaskStatus.failed) is True

    def test_validating_to_done(self):
        assert validate_transition(TaskStatus.validating, TaskStatus.done) is True

    def test_validating_to_awaiting_revision(self):
        assert validate_transition(TaskStatus.validating, TaskStatus.awaiting_revision) is True

    def test_validating_to_failed(self):
        assert validate_transition(TaskStatus.validating, TaskStatus.failed) is True

    def test_awaiting_revision_to_implementing(self):
        assert validate_transition(TaskStatus.awaiting_revision, TaskStatus.implementing) is True

    def test_awaiting_revision_to_failed(self):
        assert validate_transition(TaskStatus.awaiting_revision, TaskStatus.failed) is True


class TestForbiddenTransitions:
    def test_created_to_analyzing(self):
        assert validate_transition(TaskStatus.created, TaskStatus.analyzing) is False

    def test_created_to_implementing(self):
        assert validate_transition(TaskStatus.created, TaskStatus.implementing) is False

    def test_created_to_done(self):
        assert validate_transition(TaskStatus.created, TaskStatus.done) is False

    def test_opening_to_done(self):
        assert validate_transition(TaskStatus.opening, TaskStatus.done) is False

    def test_opening_to_implementing(self):
        assert validate_transition(TaskStatus.opening, TaskStatus.implementing) is False

    def test_awaiting_approval_to_done(self):
        assert validate_transition(TaskStatus.awaiting_approval, TaskStatus.done) is False

    def test_awaiting_approval_to_analyzing(self):
        assert validate_transition(TaskStatus.awaiting_approval, TaskStatus.analyzing) is False

    def test_implementing_to_done(self):
        assert validate_transition(TaskStatus.implementing, TaskStatus.done) is False

    def test_implementing_to_awaiting_approval(self):
        assert validate_transition(TaskStatus.implementing, TaskStatus.awaiting_approval) is False

    def test_validating_to_implementing(self):
        assert validate_transition(TaskStatus.validating, TaskStatus.implementing) is False

    def test_awaiting_revision_to_done(self):
        assert validate_transition(TaskStatus.awaiting_revision, TaskStatus.done) is False


class TestTerminalStates:
    def test_done_is_terminal(self):
        assert TaskStatus.done in TERMINAL_STATES

    def test_failed_is_terminal(self):
        assert TaskStatus.failed in TERMINAL_STATES

    def test_done_cannot_transition_to_anything(self):
        for target in TaskStatus:
            if target != TaskStatus.done:
                assert validate_transition(TaskStatus.done, target) is False

    def test_failed_can_retry(self):
        # failed can re-enter in-progress states for retry
        assert validate_transition(TaskStatus.failed, TaskStatus.opening) is True
        assert validate_transition(TaskStatus.failed, TaskStatus.analyzing) is True
        assert validate_transition(TaskStatus.failed, TaskStatus.implementing) is True
        assert validate_transition(TaskStatus.failed, TaskStatus.validating) is True

    def test_failed_cannot_go_to_done(self):
        assert validate_transition(TaskStatus.failed, TaskStatus.done) is False

    def test_failed_cannot_go_to_awaiting_approval(self):
        assert validate_transition(TaskStatus.failed, TaskStatus.awaiting_approval) is False


class TestApprovalGate:
    def test_awaiting_approval_to_implementing_allowed(self):
        """The approval gate: awaiting_approval → implementing is allowed."""
        assert validate_transition(TaskStatus.awaiting_approval, TaskStatus.implementing) is True

    def test_awaiting_approval_cannot_skip_to_validating(self):
        assert validate_transition(TaskStatus.awaiting_approval, TaskStatus.validating) is False

    def test_awaiting_approval_cannot_skip_to_done(self):
        assert validate_transition(TaskStatus.awaiting_approval, TaskStatus.done) is False


class TestResumableStates:
    def test_awaiting_approval_is_resumable(self):
        assert TaskStatus.awaiting_approval in RESUMABLE_STATES

    def test_awaiting_revision_is_resumable(self):
        assert TaskStatus.awaiting_revision in RESUMABLE_STATES

    def test_created_not_resumable(self):
        assert TaskStatus.created not in RESUMABLE_STATES

    def test_done_not_resumable(self):
        assert TaskStatus.done not in RESUMABLE_STATES


class TestGetAllowedTransitions:
    def test_created_transitions(self):
        allowed = get_allowed_transitions(TaskStatus.created)
        assert TaskStatus.opening in allowed

    def test_done_has_no_transitions(self):
        allowed = get_allowed_transitions(TaskStatus.done)
        assert allowed == []

    def test_analyzing_has_multiple_transitions(self):
        allowed = get_allowed_transitions(TaskStatus.analyzing)
        assert TaskStatus.awaiting_approval in allowed
        assert TaskStatus.implementing in allowed
        assert TaskStatus.done in allowed
        assert TaskStatus.failed in allowed
