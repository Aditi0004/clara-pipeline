# Clara AI Pipeline

**Zero-cost, fully local automation pipeline.**
Converts demo call transcripts → structured account memos → Retell agent configurations, then updates them with onboarding data.

---

## Architecture

```
Demo Transcript (.txt/.md)
        │
        ▼
[ Pipeline A: scripts/pipeline.py demo ]
        │
        ├── outputs/accounts/<ID>/v1/account_memo.json
        └── outputs/accounts/<ID>/v1/retell_agent_spec.json

Onboarding Transcript or JSON
        │
        ▼
[ Pipeline B: scripts/pipeline.py onboard ]
        │
        ├── outputs/accounts/<ID>/v2/account_memo.json
        ├── outputs/accounts/<ID>/v2/retell_agent_spec.json
        └── outputs/accounts/<ID>/changelog.json
```

The pipeline uses **Ollama (local LLM)** for intelligent extraction if available, with a **rule-based fallback** that works with zero dependencies. Both paths are zero-cost.

---

## Setup

### 1. Prerequisites (all free, all local)

```bash
# Python 3.9+
python --version

# Optional but recommended: Ollama for smarter extraction
# Install from https://ollama.ai (free, runs locally)
ollama pull llama3
```

No paid APIs. No cloud services. No subscriptions.

### 2. Clone & run

```bash
git clone <your-repo-url>
cd clara-pipeline

# Run Pipeline A on a demo transcript
python scripts/pipeline.py demo path/to/demo_transcript.txt --company "Acme Electric"

# Run Pipeline B with onboarding data
python scripts/pipeline.py onboard <ACCOUNT_ID> path/to/onboarding.txt

# Run on full dataset (5 demo + 5 onboarding files)
python scripts/pipeline.py batch path/to/dataset/
```

### 3. View diffs

```bash
python scripts/diff_viewer.py <ACCOUNT_ID>
```

---

## Dataset File Naming (for batch mode)

Place files in a folder:
```
dataset/
  demo_1.txt
  demo_2.txt
  ...
  onboarding_1.txt
  onboarding_2.txt
  ...
```

The number suffix links each demo to its onboarding pair.

---

## n8n Automation (optional, for webhook-triggered runs)

### Setup

```bash
cd workflows
docker-compose up -d
```

Then open http://localhost:5678, go to **Workflows → Import**, and import `n8n_workflow.json`.

### Endpoints (after import & activation)

| Endpoint | Method | Body | Description |
|---|---|---|---|
| `/webhook/pipeline-a` | POST | `{"transcript_path": "...", "company_name": "..."}` | Run Pipeline A |
| `/webhook/pipeline-b` | POST | `{"account_id": "...", "onboarding_path": "..."}` | Run Pipeline B |
| `/webhook/pipeline-batch` | POST | `{"dataset_dir": "..."}` | Batch run |

---

## Output Structure

```
outputs/
  accounts/
    <ACCOUNT_ID>/
      v1/
        account_memo.json       ← Structured data from demo call
        retell_agent_spec.json  ← Agent prompt + config
      v2/
        account_memo.json       ← Updated after onboarding
        retell_agent_spec.json  ← Revised agent prompt + config
      changelog.json            ← What changed from v1 → v2
```

---

## Account Memo Fields

| Field | Description |
|---|---|
| `account_id` | Auto-generated deterministic ID |
| `company_name` | Client company name |
| `business_hours` | Days, start time, end time, timezone |
| `services_supported` | List of services offered |
| `emergency_definition` | What counts as an emergency |
| `emergency_routing_rules` | Who to call, in what order |
| `call_transfer_rules` | Timeout, retries, fail message |
| `integration_constraints` | CRM/platform constraints |
| `questions_or_unknowns` | Gaps needing onboarding clarification |

---

## Retell Agent Spec Fields

| Field | Description |
|---|---|
| `agent_name` | Display name |
| `voice_style` | Gender, tone, speed, language |
| `system_prompt` | Full agent prompt (business + after-hours flows) |
| `key_variables` | Business hours, timezone, transfer numbers |
| `call_transfer_protocol` | How to transfer, what to say |
| `fallback_protocol` | What to do if transfer fails |
| `version` | v1 (demo) or v2 (onboarding) |

---

## Deploying to Retell

Since the free Retell tier may not allow programmatic agent creation:

1. Go to https://app.retellai.com and create a free account.
2. Create a new agent manually.
3. Copy the `system_prompt` from `retell_agent_spec.json` into the agent's system prompt field.
4. Set the voice, language, and other settings from `voice_style` and `key_variables`.
5. Configure phone number forwarding to your Retell agent number.

---

## LLM Usage

The pipeline tries Ollama first (http://localhost:11434). If Ollama is not running, it automatically falls back to rule-based regex extraction. **No paid LLM APIs are ever called.**

To use a different local model:
```python
# In scripts/pipeline.py, line ~40:
call_ollama(prompt, model="mistral")  # or any model you've pulled
```

---

## Known Limitations

- Rule-based extraction is less accurate than LLM for unusual phrasing
- Batch mode matches demo/onboarding by filename number suffix only
- Retell API integration is stubbed (manual import required on free tier)
- No web UI (outputs are JSON files)

## What to Improve with Production Access

- Retell API calls to auto-create/update agents programmatically
- Whisper-based audio transcription for raw M4A/MP3 inputs
- Supabase or Airtable backend for multi-user account storage
- Slack/email notifications after each pipeline run
- Simple React dashboard for reviewing outputs and diffs
- GPT-4 or Claude API for higher-quality extraction (with cost control)

---

## Sample Run (BEN001)

This repo includes pre-generated outputs for `BEN001` (Ben's Electric Solutions) from the provided demo transcript.

```
outputs/accounts/BEN001/v1/account_memo.json
outputs/accounts/BEN001/v1/retell_agent_spec.json
```

The v2 outputs will be generated once the onboarding call or form is received.
