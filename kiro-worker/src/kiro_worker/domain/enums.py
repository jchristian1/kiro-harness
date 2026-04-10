from enum import Enum


class Intent(str, Enum):
    new_project = "new_project"
    add_feature = "add_feature"
    refactor = "refactor"
    fix_bug = "fix_bug"
    analyze_codebase = "analyze_codebase"
    upgrade_dependencies = "upgrade_dependencies"
    prepare_pr = "prepare_pr"


class Source(str, Enum):
    new_project = "new_project"
    github_repo = "github_repo"
    local_repo = "local_repo"
    local_folder = "local_folder"


class Operation(str, Enum):
    plan_only = "plan_only"
    analyze_then_approve = "analyze_then_approve"
    implement_now = "implement_now"
    implement_and_prepare_pr = "implement_and_prepare_pr"


class TaskStatus(str, Enum):
    created = "created"
    opening = "opening"
    analyzing = "analyzing"
    awaiting_approval = "awaiting_approval"
    implementing = "implementing"
    validating = "validating"
    awaiting_revision = "awaiting_revision"
    done = "done"
    failed = "failed"


class RunMode(str, Enum):
    analyze = "analyze"
    implement = "implement"
    validate = "validate"


class RunStatus(str, Enum):
    running = "running"
    completed = "completed"
    parse_failed = "parse_failed"
    error = "error"
    cancelled = "cancelled"


class ArtifactType(str, Enum):
    analysis = "analysis"
    implementation = "implementation"
    validation = "validation"


class ParseStatus(str, Enum):
    ok = "ok"
    parse_failed = "parse_failed"
    schema_invalid = "schema_invalid"
