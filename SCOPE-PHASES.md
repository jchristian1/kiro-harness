Phase 0

Lock the contracts and explicitly decide what belongs to Kiro vs worker. This now includes the new kiro-native-capabilities.md document so you do not accidentally rebuild agent config, persistent standards, or code intelligence. Kiro’s docs make clear these are already first-class product features.

Phase 1

Build kiro-worker core, but only for the parts Kiro does not already own:

project/task/run/artifact registry
workspace lifecycle
approval state machine
audit storage
worker API
Kiro invocation adapter

Do not build custom repo indexing, custom long-term standards memory, or ad hoc role simulation. Kiro already gives you code intelligence, steering, and custom-agent config for those areas.

Phase 2

Create one real Kiro custom agent, repo-engineer, plus the repo-level context scaffolding:

.kiro/agents/repo-engineer.json
.kiro/steering/*.md
AGENTS.md
one or two small Kiro skills where reusable workflows make sense

This phase is earlier and more important than before, because Kiro custom agents and resources are the right place for execution-role behavior and persistent context. Also remember: if you want steering inside custom agents, you must include it in resources.

Phase 3

Connect worker → Kiro properly:

invoke the custom agent
pass structured prompts
parse structured JSON result blocks
preserve raw logs and normalized summaries
optionally add only minimal hooks if they clearly reduce glue code

Hooks can receive JSON via stdin and can block or warn on tool execution, so they may help later with validation or policy enforcement, but I would keep them light in the first pass.

Phase 4

Connect Henry to the worker:

classify request into Intent / Source / Operation Mode
ask only blocking clarifications
call worker cleanly
present result like a tech lead
request approval when required

Henry stays thin because the worker is still the source of truth, and Kiro remains the engineering layer.

Phase 5

Add continuity and resume maturity:

active-task lookup
project aliases
resume unfinished tasks
stable workspace reuse
last run summaries/artifacts

Kiro does have per-directory session persistence and resume, but that is not enough for your delivery system because it does not replace explicit project/task/run state in your worker.

Phase 6

Add reusable workflow packaging:

Henry skill for routing and policy
targeted Kiro skills for repeated engineering workflows

This is now later than “basic Henry integration” but earlier than advanced specialization, because Kiro skills are a cleaner reuse mechanism than giant prompts.

Phase 7

Add specialization:

extra Kiro custom agents
possibly Kiro subagents for delegated or parallel work

Since Kiro already supports subagents with separate context, parallel execution, and result aggregation, you should not hand-build elaborate multi-role orchestration before you’ve proven a single-role flow works.

Phase 8

Add extension points carefully:

MCP if external services/tools are truly needed
hooks where automation at lifecycle/tool boundaries is clearly valuable

MCP is the official way to connect specialized servers, APIs, and domain-specific tools, so prefer that over inventing your own side-channel integration pattern when external tools are needed.

Phase 9

Add professional delivery workflow:

branch/commit conventions
PR preparation
push/PR approvals
richer validation/reporting
stronger permissions and safety controls
Phase 10

Only evaluate experimental Kiro features after the core system is working
Kiro’s experimental knowledge management offers persistent semantic retrieval across sessions, but it is explicitly experimental, so I would not make it foundational to v1.

The practical difference in the roadmap

The old version was:

worker
Henry
skill
more roles

The new version is:

contracts
worker core
one real Kiro custom agent + steering/resources
worker/Kiro integration
Henry integration
continuity
skills
more agents/subagents
MCP/hooks where justified

That is safer and cheaper, because it uses Kiro for what Kiro is already built to do.