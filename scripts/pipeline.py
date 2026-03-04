#!/usr/bin/env python3
"""
Clara Pipeline — Pipeline A: Demo Transcript → Account Memo + Agent Spec (v1)
Pipeline B: Onboarding Input → Updated Memo + Agent Spec (v2)

Zero-cost. Uses local Ollama LLM or falls back to rule-based extraction.
"""

import json
import os
import sys
import re
import argparse
import hashlib
import datetime
from pathlib import Path

OUTPUTS_DIR = Path(__file__).parent.parent / "outputs" / "accounts"
OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)

# ── helpers ──────────────────────────────────────────────────────────────────

def timestamp():
    return datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")

def make_account_id(company_name: str) -> str:
    """Deterministic short ID from company name."""
    slug = re.sub(r"[^a-z0-9]", "", company_name.lower())[:6].upper()
    h = hashlib.md5(company_name.encode()).hexdigest()[:3].upper()
    return f"{slug}{h}"

def load_json(path: Path) -> dict:
    with open(path) as f:
        return json.load(f)

def save_json(data: dict, path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f, indent=2)
    print(f"  ✓ Saved: {path}")

# ── LLM call (Ollama local, zero-cost) ────────────────────────────────────────

def call_ollama(prompt: str, model: str = "llama3") -> str:
    """Call local Ollama. Falls back gracefully if not running."""
    try:
        import urllib.request
        payload = json.dumps({"model": model, "prompt": prompt, "stream": False}).encode()
        req = urllib.request.Request(
            "http://localhost:11434/api/generate",
            data=payload,
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=120) as resp:
            result = json.loads(resp.read())
            return result.get("response", "")
    except Exception as e:
        print(f"  ⚠ Ollama not available ({e}). Using rule-based extraction.")
        return ""

# ── extraction prompts ────────────────────────────────────────────────────────

EXTRACTION_PROMPT = """You are a configuration specialist for Clara AI, an AI voice agent for trade businesses.

Read the following demo call transcript and extract ONLY information that is explicitly stated. Do NOT invent or assume details.

Return a JSON object with these exact fields (use null if not found):
{{
  "company_name": string or null,
  "contact_name": string or null,
  "email": string or null,
  "phone": string or null,
  "office_address": string or null,
  "city": string or null,
  "timezone": string or null,
  "business_hours_start": string (HH:MM) or null,
  "business_hours_end": string (HH:MM) or null,
  "business_days": string or null,
  "crm_system": string or null,
  "services_supported": [list of strings],
  "services_not_supported": [list of strings],
  "emergency_definition": [list of strings],
  "emergency_routing_primary": string or null,
  "after_hours_on_call": string or null,
  "call_volume_estimate": string or null,
  "questions_or_unknowns": [list of strings],
  "notes": string or null
}}

TRANSCRIPT:
{transcript}

Return ONLY the JSON object, no preamble or explanation.
"""

# ── rule-based fallback extractor ────────────────────────────────────────────

def rule_based_extract(transcript: str) -> dict:
    """
    Simple pattern-based extraction when Ollama is unavailable.
    Looks for common signals in transcripts.
    """
    extracted = {
        "company_name": None,
        "contact_name": None,
        "email": None,
        "phone": None,
        "office_address": None,
        "city": None,
        "timezone": None,
        "business_hours_start": None,
        "business_hours_end": None,
        "business_days": None,
        "crm_system": None,
        "services_supported": [],
        "services_not_supported": [],
        "emergency_definition": [],
        "emergency_routing_primary": None,
        "after_hours_on_call": None,
        "call_volume_estimate": None,
        "questions_or_unknowns": [],
        "notes": ""
    }

    t = transcript.lower()

    # Email
    emails = re.findall(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+", transcript)
    if emails:
        extracted["email"] = emails[0]

    # Phone numbers
    phones = re.findall(r"\b\d{3}[-.\s]\d{3}[-.\s]\d{4}\b", transcript)
    if phones:
        extracted["phone"] = phones[0]

    # Business hours hints
    if "8am" in t or "8:00" in t:
        extracted["business_hours_start"] = "08:00"
    if "6" in t and ("pm" in t or "o'clock" in t or "o\\'" in t):
        extracted["business_hours_end"] = "18:00"

    # CRM
    if "jobber" in t:
        extracted["crm_system"] = "Jobber"
    elif "servicetitan" in t or "service titan" in t:
        extracted["crm_system"] = "ServiceTitan"

    # City / timezone
    if "calgary" in t:
        extracted["city"] = "Calgary, AB, Canada"
        extracted["timezone"] = "America/Edmonton"

    # Emergency signals
    if "emergency" in t:
        extracted["emergency_definition"].append("Caller identifies situation as emergency")
    if "on call" in t or "on-call" in t:
        if "i'm the one on call" in t or "i am the one on call" in t:
            extracted["after_hours_on_call"] = "Owner / primary contact"

    # Call volume
    vol = re.search(r"(\d+)\s*to\s*(\d+)\s*calls?\s*(a\s*week|per\s*week)", t)
    if vol:
        extracted["call_volume_estimate"] = f"{vol.group(1)} to {vol.group(2)} calls per week"

    # Common services for electrical
    service_keywords = {
        "outlet replacement": "Outlet replacements",
        "panel change": "Panel changes",
        "ev charger": "EV charger installation",
        "hot tub": "Hot tub electrical hookup",
        "aluminum wiring": "Aluminum wiring mitigation",
        "led lighting": "LED lighting upgrades",
        "generator": "Generator integration",
        "renovation": "Renovations",
        "service call": "Service calls",
        "troubleshoot": "Troubleshooting",
        "tenant improvement": "Tenant improvement",
        "residential": "Residential electrical",
        "commercial": "Commercial electrical"
    }
    for keyword, label in service_keywords.items():
        if keyword in t:
            extracted["services_supported"].append(label)

    extracted["questions_or_unknowns"] = [
        "Exact business hours days and end time",
        "Office/billing address",
        "Emergency call transfer number and timeout",
        "Fallback if transfer fails after hours",
        "VIP/bypass number list"
    ]

    return extracted

# ── memo builder ─────────────────────────────────────────────────────────────

def build_memo(extracted: dict, account_id: str, version: str, source: str) -> dict:
    return {
        "account_id": account_id,
        "version": version,
        "source": source,
        "generated_at": timestamp(),
        "company_name": extracted.get("company_name"),
        "contact_name": extracted.get("contact_name"),
        "email": extracted.get("email"),
        "phone": extracted.get("phone"),
        "office_address": extracted.get("office_address"),
        "business_hours": {
            "days": extracted.get("business_days") or "TBD",
            "start": extracted.get("business_hours_start") or "TBD",
            "end": extracted.get("business_hours_end") or "TBD",
            "timezone": extracted.get("timezone") or "TBD"
        },
        "crm_system": extracted.get("crm_system"),
        "services_supported": extracted.get("services_supported", []),
        "services_not_supported": extracted.get("services_not_supported", []),
        "emergency_definition": extracted.get("emergency_definition", []),
        "emergency_routing_rules": {
            "primary": extracted.get("emergency_routing_primary") or "TBD",
            "after_hours_on_call": extracted.get("after_hours_on_call") or "TBD",
            "fallback": "TBD — confirm at onboarding"
        },
        "non_emergency_routing_rules": {
            "business_hours": "Collect name, number, job details, preferred date. Send notification.",
            "after_hours": "Collect details. Confirm follow-up next business day."
        },
        "call_transfer_rules": {
            "timeout": "TBD",
            "retries": "TBD",
            "transfer_fail_message": "TBD"
        },
        "integration_constraints": [],
        "call_volume_estimate": extracted.get("call_volume_estimate"),
        "after_hours_flow_summary": "Greet → ask purpose → confirm emergency → if emergency collect name/number/address and transfer → if non-emergency collect details and assure callback",
        "office_hours_flow_summary": "Greet → ask purpose → collect name/number/job details/preferred time → notify team",
        "questions_or_unknowns": extracted.get("questions_or_unknowns", []),
        "notes": extracted.get("notes") or ""
    }

# ── agent spec builder ────────────────────────────────────────────────────────

def build_agent_spec(memo: dict) -> dict:
    company = memo.get("company_name") or "the company"
    bh_start = memo["business_hours"].get("start") or "08:00"
    bh_end = memo["business_hours"].get("end") or "18:00"
    bh_days = memo["business_hours"].get("days") or "Monday to Friday"
    tz = memo["business_hours"].get("timezone") or "local time"
    services = ", ".join(memo.get("services_supported", [])[:8]) or "general services"

    prompt = f"""You are Clara, a friendly and professional AI receptionist for {company}.

You handle inbound calls. Your job is to greet callers, understand their needs, collect required information, and route or arrange callbacks. Be warm, calm, and professional. Do NOT mention AI, tools, functions, or internal systems.

## BUSINESS HOURS FLOW ({bh_days}, {bh_start} to {bh_end} {tz})

1. GREETING
   "Thank you for calling {company}. This is Clara. How can I help you today?"

2. ASK PURPOSE
   Listen carefully. If this is a sales or spam call, politely decline and end.

3. COLLECT NAME AND NUMBER
   "May I get your name and the best phone number to reach you?"
   Confirm the number back.

4. COLLECT JOB DETAILS
   Ask for a brief description of the work needed, location, and preferred date/time.

5. TRANSFER OR ROUTE
   If urgent, initiate warm transfer. Otherwise confirm details are noted and team will follow up.
   "I've got all your details. The team will be in touch to confirm. Is there anything else?"

6. FALLBACK IF TRANSFER FAILS
   "I wasn't able to connect you directly. Your details have been noted and someone will follow up as soon as possible."

7. CLOSE
   "Is there anything else I can help you with today?"
   If no: "Thank you for calling {company}. Have a great day!"

## AFTER-HOURS FLOW

1. GREETING
   "Thank you for calling {company}. You've reached us outside regular business hours. This is Clara. How can I help?"

2. ASK PURPOSE
   Determine if emergency or non-emergency.

3. CONFIRM EMERGENCY
   "Is this an emergency that needs to be addressed tonight?"

4. IF EMERGENCY
   "I understand — let me get your details right away."
   Collect: full name, phone number (confirm), address.
   Attempt transfer. If fails: "I wasn't able to reach anyone directly but your details have been sent and someone will follow up as soon as possible."

5. IF NON-EMERGENCY
   "Our team isn't available right now but I'll make sure they follow up with you first thing in the morning."
   Collect: name, phone number, description, preferred callback time.
   "Ben's team will follow up during business hours. Thank you for your patience."

6. CLOSE
   "Is there anything else?" → "Thank you for calling. Have a good evening."

## SERVICES
{company} offers: {services}.
Always direct questions about pricing or timelines to the team for a proper quote.

## RULES
- Never ask more questions than needed for routing.
- Never mention internal tools, functions, or systems.
- Always confirm phone numbers back to caller.
- Always ask "anything else" before ending.
- Be warm and human.
"""

    return {
        "agent_name": f"Clara — {company}",
        "version": memo.get("version", "v1"),
        "account_id": memo.get("account_id"),
        "generated_at": timestamp(),
        "voice_style": {
            "gender": "female",
            "tone": "friendly, professional, calm",
            "speed": "normal",
            "language": "en-CA"
        },
        "key_variables": {
            "company_name": company,
            "timezone": tz,
            "business_hours_start": bh_start,
            "business_hours_end": bh_end,
            "business_days": bh_days,
            "primary_contact_phone": memo["emergency_routing_rules"].get("primary") or "TBD",
            "emergency_transfer_number": "TBD"
        },
        "call_transfer_protocol": {
            "method": "warm_transfer",
            "primary_number": "{{emergency_transfer_number}}",
            "timeout_seconds": memo["call_transfer_rules"].get("timeout") or "TBD",
            "on_transfer_message": "Please hold for a moment while I connect you.",
            "on_transfer_fail": memo["call_transfer_rules"].get("transfer_fail_message") or "I wasn't able to reach anyone right now. Your details have been noted and someone will follow up as soon as possible."
        },
        "fallback_protocol": {
            "trigger": "Transfer fails or no answer",
            "action": "Apologize, confirm details collected, assure callback",
            "message": f"I'm sorry I wasn't able to connect you directly. I've noted your details and {company}'s team will follow up with you as soon as possible."
        },
        "system_prompt": prompt
    }

# ── changelog builder ─────────────────────────────────────────────────────────

def build_changelog(v1_memo: dict, v2_memo: dict) -> dict:
    changes = []
    skip_keys = {"version", "generated_at", "source"}

    def compare(key, old, new):
        if old != new:
            changes.append({"field": key, "from": old, "to": new})

    for key in v2_memo:
        if key in skip_keys:
            continue
        compare(key, v1_memo.get(key), v2_memo.get(key))

    return {
        "account_id": v2_memo.get("account_id"),
        "from_version": "v1",
        "to_version": "v2",
        "generated_at": timestamp(),
        "total_changes": len(changes),
        "changes": changes
    }

# ── pipeline A ────────────────────────────────────────────────────────────────

def pipeline_a(transcript_path: str, company_name_hint: str = None):
    print(f"\n=== Pipeline A: Demo Transcript → v1 Agent ===")
    print(f"Input: {transcript_path}")

    transcript = Path(transcript_path).read_text(encoding="utf-8", errors="ignore")

    # Try LLM extraction first, fall back to rule-based
    llm_response = call_ollama(EXTRACTION_PROMPT.format(transcript=transcript[:6000]))

    if llm_response:
        try:
            # Strip markdown fences if present
            cleaned = re.sub(r"```json|```", "", llm_response).strip()
            extracted = json.loads(cleaned)
            print("  ✓ LLM extraction successful")
        except Exception as e:
            print(f"  ⚠ LLM JSON parse failed ({e}), using rule-based")
            extracted = rule_based_extract(transcript)
    else:
        extracted = rule_based_extract(transcript)
        print("  ✓ Rule-based extraction complete")

    # Determine account ID
    company = extracted.get("company_name") or company_name_hint or "Unknown Company"
    account_id = make_account_id(company)
    print(f"  Account ID: {account_id}")

    # Build outputs
    memo = build_memo(extracted, account_id, "v1", "demo_call")
    agent_spec = build_agent_spec(memo)

    # Save
    out_dir = OUTPUTS_DIR / account_id / "v1"
    save_json(memo, out_dir / "account_memo.json")
    save_json(agent_spec, out_dir / "retell_agent_spec.json")

    print(f"\n✅ Pipeline A complete. Outputs in: {out_dir}")
    return account_id, memo, agent_spec

# ── pipeline B ────────────────────────────────────────────────────────────────

def pipeline_b(account_id: str, onboarding_input_path: str):
    print(f"\n=== Pipeline B: Onboarding → v2 Agent ===")
    print(f"Account: {account_id}")
    print(f"Onboarding input: {onboarding_input_path}")

    # Load v1
    v1_dir = OUTPUTS_DIR / account_id / "v1"
    if not (v1_dir / "account_memo.json").exists():
        print(f"  ✗ No v1 memo found for {account_id}. Run Pipeline A first.")
        sys.exit(1)

    v1_memo = load_json(v1_dir / "account_memo.json")

    # Load onboarding data
    onb_path = Path(onboarding_input_path)
    if onb_path.suffix == ".json":
        onboarding = load_json(onb_path)
    else:
        # Treat as transcript
        transcript = onb_path.read_text(encoding="utf-8", errors="ignore")
        llm_response = call_ollama(EXTRACTION_PROMPT.format(transcript=transcript[:6000]))
        if llm_response:
            try:
                cleaned = re.sub(r"```json|```", "", llm_response).strip()
                onboarding = json.loads(cleaned)
            except Exception:
                onboarding = rule_based_extract(transcript)
        else:
            onboarding = rule_based_extract(transcript)

    # Patch v1 with onboarding data
    import copy
    v2_memo = copy.deepcopy(v1_memo)
    v2_memo["version"] = "v2"
    v2_memo["source"] = "onboarding_call"
    v2_memo["generated_at"] = timestamp()

    # Apply patches — only overwrite if onboarding has a non-null value
    patch_fields = [
        "company_name", "contact_name", "email", "phone", "office_address",
        "crm_system", "call_volume_estimate", "notes"
    ]
    for field in patch_fields:
        if onboarding.get(field):
            v2_memo[field] = onboarding[field]

    # Patch business hours
    bh_updates = {
        "start": onboarding.get("business_hours_start"),
        "end": onboarding.get("business_hours_end"),
        "days": onboarding.get("business_days"),
        "timezone": onboarding.get("timezone")
    }
    for k, v in bh_updates.items():
        if v:
            v2_memo["business_hours"][k] = v

    # Merge lists (deduplicate)
    for list_field in ["services_supported", "services_not_supported", "emergency_definition"]:
        existing = set(v2_memo.get(list_field, []))
        new_items = set(onboarding.get(list_field, []))
        v2_memo[list_field] = list(existing | new_items)

    # Patch emergency routing
    if onboarding.get("emergency_routing_primary"):
        v2_memo["emergency_routing_rules"]["primary"] = onboarding["emergency_routing_primary"]
    if onboarding.get("after_hours_on_call"):
        v2_memo["emergency_routing_rules"]["after_hours_on_call"] = onboarding["after_hours_on_call"]

    # Clear questions that are now answered
    remaining_unknowns = []
    for q in v2_memo.get("questions_or_unknowns", []):
        # Simple heuristic: if a related field is now filled, drop the question
        q_lower = q.lower()
        if "business hours" in q_lower and v2_memo["business_hours"]["start"] != "TBD":
            continue
        if "address" in q_lower and v2_memo.get("office_address"):
            continue
        if "emergency" in q_lower and v2_memo["emergency_routing_rules"]["primary"] != "TBD":
            continue
        remaining_unknowns.append(q)
    v2_memo["questions_or_unknowns"] = remaining_unknowns

    # Build v2 agent spec
    v2_agent_spec = build_agent_spec(v2_memo)

    # Changelog
    changelog = build_changelog(v1_memo, v2_memo)

    # Save
    out_dir = OUTPUTS_DIR / account_id / "v2"
    save_json(v2_memo, out_dir / "account_memo.json")
    save_json(v2_agent_spec, out_dir / "retell_agent_spec.json")
    save_json(changelog, OUTPUTS_DIR / account_id / "changelog.json")

    print(f"\n✅ Pipeline B complete.")
    print(f"   v2 outputs in: {out_dir}")
    print(f"   Changelog:     {OUTPUTS_DIR / account_id / 'changelog.json'}")
    print(f"   Total changes: {changelog['total_changes']}")

    return v2_memo, v2_agent_spec, changelog

# ── batch runner ──────────────────────────────────────────────────────────────

def run_batch(dataset_dir: str):
    """
    Process all transcripts in dataset_dir.
    Expects files named: demo_<name>.txt and onboarding_<name>.txt
    or: demo_<name>.json and onboarding_<name>.json
    """
    dataset = Path(dataset_dir)
    demo_files = sorted(dataset.glob("demo_*.*"))
    onboarding_files = sorted(dataset.glob("onboarding_*.*"))

    print(f"\n=== Batch Run ===")
    print(f"Found {len(demo_files)} demo files, {len(onboarding_files)} onboarding files")

    account_map = {}

    for demo_file in demo_files:
        stem = demo_file.stem.replace("demo_", "")
        print(f"\n--- Processing: {stem} ---")
        account_id, memo, _ = pipeline_a(str(demo_file))
        account_map[stem] = account_id

    for onb_file in onboarding_files:
        stem = onb_file.stem.replace("onboarding_", "")
        account_id = account_map.get(stem)
        if not account_id:
            print(f"\n⚠ No matching demo account for onboarding: {stem}")
            continue
        pipeline_b(account_id, str(onb_file))

    print("\n=== Batch complete ===")
    print(f"Accounts processed: {list(account_map.values())}")

# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Clara Pipeline — zero-cost automation")
    sub = parser.add_subparsers(dest="command")

    pa = sub.add_parser("demo", help="Pipeline A: demo transcript → v1")
    pa.add_argument("transcript", help="Path to transcript file (.txt or .md)")
    pa.add_argument("--company", help="Company name hint if not in transcript")

    pb = sub.add_parser("onboard", help="Pipeline B: onboarding input → v2")
    pb.add_argument("account_id", help="Account ID from Pipeline A")
    pb.add_argument("onboarding", help="Path to onboarding transcript or JSON")

    pc = sub.add_parser("batch", help="Batch process a dataset directory")
    pc.add_argument("dataset_dir", help="Directory with demo_*.txt and onboarding_*.txt files")

    args = parser.parse_args()

    if args.command == "demo":
        pipeline_a(args.transcript, args.company)
    elif args.command == "onboard":
        pipeline_b(args.account_id, args.onboarding)
    elif args.command == "batch":
        run_batch(args.dataset_dir)
    else:
        parser.print_help()
