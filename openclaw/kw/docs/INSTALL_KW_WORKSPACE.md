# Installing the KW Integration Layer

## Prerequisites

- OpenClaw 2026.4+ installed and running
- kiro-worker running on `http://localhost:4000` (or set `KIRO_WORKER_URL`)
- kiro-cli installed: `curl -fsSL https://cli.kiro.dev/install | bash`
- Python 3.11+ on PATH
- Node 22+ on PATH

## Step 1 — Start the worker

```bash
cd /path/to/kiro-harness
./kiro-worker/start.sh
```

Verify:
```bash
curl http://localhost:4000/health
# {"status":"ok","version":"1.0.0"}
```

## Step 2 — Install the plugin

```bash
cd openclaw/kw/plugin
npm install
openclaw plugins install -l .
```

Verify:
```bash
openclaw plugins inspect kw-worker-tools
# Status: loaded
# Tools: kw_local_folder_analyze, kw_github_analyze, ...
```

## Step 3 — Sync skills to your workspace

```bash
WORKSPACE=~/.openclaw/workspace-henry

for skill in kw_local_folder_analyze kw_github_analyze kw_new_project_analyze kw_implement kw_approve_implement kw_task_status kw_complete_task kw_watch_task; do
  mkdir -p $WORKSPACE/skills/$skill
  cp openclaw/kw/skills/$skill/SKILL.md $WORKSPACE/skills/$skill/SKILL.md
  echo "synced $skill"
done
```

## Step 4 — Restart the gateway

```bash
openclaw gateway restart
```

## Step 5 — Verify skills loaded

```bash
openclaw skills list | grep kw
```

## Step 6 — Test from Telegram

```
/kw_local_folder_analyze {"name":"test","path":"/tmp/test","description":"Describe the structure"}
```

Expected immediate response:
```json
{
  "ok": true,
  "task_id": "task_01...",
  "run_id": "run_01...",
  "task_status": "analyzing",
  "run_status": "running"
}
```

Then poll:
```
/kw_task_status {"task_id":"task_01..."}
```

## Configuration

Set worker URL if not on localhost:4000:

```bash
openclaw config set plugins.entries.kw-worker-tools.config.workerUrl=http://your-worker:4000
```

## Updating skills

After changing SKILL.md files in the repo:

```bash
for skill in kw_local_folder_analyze kw_github_analyze kw_new_project_analyze kw_implement kw_approve_implement kw_task_status kw_complete_task kw_watch_task; do
  cp openclaw/kw/skills/$skill/SKILL.md ~/.openclaw/workspace-henry/skills/$skill/SKILL.md
done
openclaw gateway restart
```

## Updating the plugin

After changing plugin source code:

```bash
cd openclaw/kw/plugin
openclaw plugins install -l .
openclaw gateway restart
```

## Troubleshooting

**Worker not loading correct source:**
```bash
cat kiro-worker/.venv/lib/python3.12/site-packages/__editable__.kiro_worker-1.0.0.pth
# Should show: /path/to/kiro-harness/kiro-worker/src
# If wrong, run: ./kiro-worker/start.sh (fixes it automatically)
```

**Plugin not found:**
```bash
python3 -c "
import json
c = json.load(open('/home/christian/.openclaw/openclaw.json'))
print(c.get('plugins',{}).get('load',{}).get('paths'))
"
# Should show the path to openclaw/kw/plugin
```

**Skills not appearing in Telegram:**
```bash
openclaw config get channels.telegram.commands.nativeSkills
# Should be: true
```
