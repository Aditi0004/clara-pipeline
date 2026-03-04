# Clara AI Pipeline

**Zero-cost, fully local automation pipeline.**  
Converts demo call transcripts → structured account memos → Retell agent configurations, then updates them with onboarding data.

---

## Architecture

```
Demo Transcript (.txt)
        │
        ▼
[ Pipeline A: scripts/pipeline.py demo ]
        │
        ├── outputs/accounts/<ID>/v1/account_memo.json
        └── outputs/accounts/<ID>/v1/retell_agent_spec.json

Onboarding Transcript (.txt)
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

### Prerequisites (all free, all local)

```bash
# Python 3.9+
python --version

# Git
git --version

# Optional: Ollama for smarter LLM-based extraction
# Install from https://ollama.ai
ollama pull llama3
```

No paid APIs. No cloud services. No subscriptions. No Docker required.

### Run Pipeline A (Demo → v1)

```bash
python scripts/pipeline.py demo demo_BEN001.txt --company "Ben's Electric Solutions"
```

### Run Pipeline B (Onboarding → v2)

```bash
python scripts/pipeline.py onboard BEN001 onboarding_BEN001.txt
```

### View what changed (diff)

```bash
python scripts/diff_viewer.py BEN001
```

### Run all 10 files at once (batch)

```bash
python scripts/pipeline.py batch dataset/
```

---

## Dataset File Naming (batch mode)

```
dataset/
  demo_1.txt
  demo_2.txt
  demo_3.txt
  demo_4.txt
  demo_5.txt
  onboarding_1.txt
  onboarding_2.txt
  onboarding_3.txt
  onboarding_4.txt
  onboarding_5.txt
```

The number suffix links each demo to its matching onboarding file.

---

## Automation — Make.com (free, no Docker)

Instead of Docker + n8n, this pipeline uses **Make.com free tier** + **ngrok** for webhook-triggered automation. No install required beyond Python.

### How it works

1. Run the local webhook server:
```bash
python webhook_server.py
```

2. Expose it to the internet (in a second terminal):
```bash
.\ngrok http 8080
```

3. In Make.com, a **Custom Webhook → HTTP** scenario triggers the pipeline automatically when a POST request is received.

### Make.com Webhook URLs

| Endpoint | Description |
|---|---|
| `/pipeline-a` | Trigger Pipeline A (demo transcript → v1) |
| `/pipeline-b` | Trigger Pipeline B (onboarding → v2) |

### Screenshot

See `workflows/make_screenshot.png` for the configured scenario.

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
| `emergency_routing_rules` | Who to call, in what order, VIP clients |
| `call_transfer_rules` | Timeout, fail message, transfer number |
| `pricing_policy` | Call-out fee, hourly rate, mention policy |
| `notification_settings` | Email and SMS for post-call alerts |
| `integration_constraints` | CRM/platform constraints |
| `questions_or_unknowns` | Gaps still needing confirmation |

---

## Retell Agent Spec Fields

| Field | Description |
|---|---|
| `agent_name` | Display name |
| `voice_style` | Gender, tone, speed, language |
| `system_prompt` | Full agent prompt (business hours + after-hours flows) |
| `key_variables` | Business hours, timezone, transfer numbers |
| `call_transfer_protocol` | How to transfer, what to say |
| `fallback_protocol` | What to do if transfer fails |
| `version` | v1 (demo) or v2 (onboarding) |

---

## Deploying to Retell

Since the free Retell tier does not allow programmatic agent creation:

1. Go to https://app.retellai.com and create a free account.
2. Create a new agent manually.
3. Copy the `system_prompt` from `retell_agent_spec.json` into the agent's system prompt field.
4. Set voice, language, and other settings from `voice_style` and `key_variables`.
5. Configure phone number forwarding to your Retell agent number.

---

## Sample Run — BEN001 (Ben's Electric Solutions)

This repo includes complete outputs for **BEN001** generated from the provided demo and onboarding transcripts.

```
outputs/accounts/BEN001/v1/account_memo.json        ← from demo call
outputs/accounts/BEN001/v1/retell_agent_spec.json
outputs/accounts/BEN001/v2/account_memo.json        ← updated after onboarding
outputs/accounts/BEN001/v2/retell_agent_spec.json
outputs/accounts/BEN001/changelog.json              ← 11 fields changed v1→v2
```

### Key changes confirmed at onboarding (v1 → v2)

| Field | v1 | v2 |
|---|---|---|
| Business hours end | TBD | 17:00 (5pm) |
| Pricing | Unknown | $115 call-out + $98/hr |
| Emergency client | Vague | GNM Pressure Washing / Shelley Manley |
| Notification email | Unknown | info@benselectricsolutionsteam.com |
| Call routing | Unknown | Android conditional forwarding |
| Questions remaining | 8 unknowns | 3 unknowns |

---

## LLM Usage

The pipeline tries **Ollama** first (http://localhost:11434). If not running, it falls back to rule-based regex extraction automatically. **No paid LLM APIs are ever called.**

---

## Known Limitations

- Rule-based extraction is less accurate than LLM for unusual phrasing
- Batch mode matches demo/onboarding by filename number suffix only
- Retell API integration is manual on free tier
- ngrok URL changes every time it restarts (update Make.com HTTP module URL accordingly)

---

## What to Improve with Production Access

- Retell API calls to auto-create/update agents programmatically
- Whisper transcription for raw M4A/MP3 audio inputs
- Supabase or Airtable backend for multi-user account storage
- Persistent ngrok URL (paid ngrok plan) or self-hosted webhook server
- Simple React dashboard for reviewing outputs and diffs
- Claude or GPT-4 API for higher-quality extraction (with cost controls)
