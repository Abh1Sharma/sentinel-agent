# Sentinel: demo run sheet (3 minutes)

**Story:** Nimble's own framework ends with *"check a source, take it with you. Every agent, every time."* Sentinel automates that step, and it matters most for GTM agents that read strangers' pages and then write to prospects.

## Before you walk up (by 6:50)
- [ ] Terminal font at 18pt+, dark theme, window full screen, notifications off
- [ ] `uv run python -m sentinel leads --cached --top 2` runs clean (the agent result is cached)
- [ ] Nimble web UI open on **Sentinel Lead Radar** (Web Search Agents), showing its Sources, Skill and Output config
- [ ] Opik open on project `sentinel`
- [ ] Backup: screen recording of `scan fixture:quillstack`; phone hotspot on

## Script

**0:00 Hook (15s)**
> "AI SDRs read strangers' web pages and then write to your prospects. I'll show you one getting hijacked by a single hidden sentence, and the fix."

**0:15 The agent, built with Nimble's 5 steps (35s)**: show the Nimble UI
- Brief: "companies that shipped web-reading AI agents in the last 30 days: what counts, what doesn't."
- Sources: first-party pages are prioritized, and listicles are avoided as evidence. *"The default lead template cited 'top 10' roundups. I told it which pages to trust."*
- Skill: one job, an agent-launch signal analyst. Output: a table with plain column names. Effort: medium, about 3 minutes.
- "Those leads are exactly the companies that need Sentinel. It's finding its own customers."

**0:50 Check a source, automated (50s)**: terminal, `leads --cached --top 2`
- For each lead, Sentinel opens the evidence page with Nimble Extract, scans it, confirms the **quoted sentence is really on the page** and the **date is in the window**, then drafts outreach and holds the CRM write for approval (the Nexla requires-approval tool).

**1:40 The hijack (50s)**: `scan fixture:quillstack`
- Live logs: 2 hidden spans and 1 visible "note for AI agents" flagged, then the Claude classifier gives an ATTACK verdict on each.
- The naive SDR's email: *"Congrats on the pending Helix Cloud acquisition"*. That's a fake fact from a CSS-hidden press release, now in front of a prospect.
- Sentinel's email: clean, and built from real signals only.

**2:30 Proof and close (30s)**
- Evals: 6/6 attacks caught, 0/6 false positives, and a real LinkedIn page (229 paragraphs) cleared with **zero LLM calls**.
> "Nimble finds the leads, Sentinel checks every source, Nexla gates every write, and Opik shows all of it. Every agent, every time."

## If a judge asks
- **"Isn't the model robust to injection?"** To obvious "AI, do X" text, mostly yes. Today it ignored the hidden "post to Slack" order. But a cloaked *fact* doesn't look like an attack, so the model put it straight into an outbound email.
- **"False positives?"** Measured: an article *about* prompt injection, a Slack-webhook changelog, and hidden menus and tabs all pass.
- **"Cost and latency?"** Pattern rules first; Claude only sees flagged spans. Most real pages need zero LLM calls.
- **"Why Nimble agents rather than plain search?"** Search finds candidates. The agent applies the brief, sources and skill and returns a table with evidence, and Sentinel verifies that evidence.
- **"Scale?"** A bounded semaphore under Nimble's 10 QPS limit, Retry-After-aware backoff, and a content-addressed cache that doubles as a replay log.
