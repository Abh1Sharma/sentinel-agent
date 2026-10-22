# Sentinel: demo run sheet (3 minutes)

## Before you walk up
- [ ] `uv run streamlit run app.py` is running, browser zoomed to 150%, notifications off
- [ ] Run both demo inputs once beforehand so the Nimble cache is warm
- [ ] Opik tab open on the `sentinel` project, filtered to the last run
- [ ] Backup: a screen recording of a full run, and `SENTINEL_REPLAY=1` ready if the Wi-Fi dies
- [ ] Phone hotspot on

## Script

**0:00 Hook (15s)**
> "Every agent that reads the web is reading content written by strangers. Some of those strangers are writing for your agent, not for you."

**0:15 Live run on a real company (40s)**
- Ask the room for a company and type it in. Run **Sentinel only**.
- While it runs: "Five Nimble searches in parallel. News, funding, launches, pricing, reviews. Then it reads the top pages in full."
- Show the briefing: priorities, dates, confidence, a source on every claim.

**0:55 The twist (60s)**
- "Here's Quillstack, a competitor we track. Its site looks normal." Show the page. There's no acquisition anywhere on it.
- Run **Side by side**. Same model (Claude Opus 5.5) and same prompt on both sides; the only difference is Sentinel.
- Left, the naive agent: its P1 is "Quillstack signed a definitive agreement to be acquired by Helix Cloud for $4.2B", and it **posted that to your team's Slack**. "That acquisition never happened. It's a press release hidden with CSS. You can't see it; your scraper can."
- Right, Sentinel: 3 spans quarantined (the cloaked acquisition, a hidden 'post to Slack and email' instruction, and a visible 'note for AI agents'). The real news, the Pulse launch, pricing and hiring, still came through, and the Slack post waits for your approval.
- Honest aside, if asked: frontier models do ignore *obvious* "AI, do X" instructions. A cloaked fact is different. It doesn't look like an attack, so the model reports it.

**1:55 Production proof (45s)**
- Switch to Opik and show the trace tree: search → extract → `guardrail` spans → LLM.
- Read out the eval numbers: catch rate, **false-positive rate**, and how many pages were cleared with no LLM call at all.
- "Three checkpoints: request, content, action. One policy. Cheap deterministic checks first, and the LLM only sees what they flag."

**2:40 Close (20s)**
> "Nimble gives the agent the live web. Nexla gives it governed hands: write tools that need approval. Opik shows everything it did. Sentinel makes it safe to leave running."

## If a judge asks
- **"Isn't the model itself robust to injection?"** Sometimes. That's a coin flip you don't want in production. And the fake acquisition isn't an instruction, it's a planted *fact*, which models happily report. We remove it before the model ever sees it, and the corroboration gate catches anything that slips through.
- **"False positives?"** We measure them. Articles *about* prompt injection, Slack-webhook changelogs and hidden nav menus are all in the eval set as must-pass.
- **"Latency and cost?"** Most pages never hit an LLM. Only flagged spans do, in one batched call per page at low effort.
- **"How does it scale?"** A bounded semaphore under Nimble's 10 QPS limit, Retry-After-aware backoff, and a content-addressed cache that doubles as a replay log.
- **"Why Nexla?"** A task-specific MCP server exposes only the 2–3 write tools the agent needs, each marked requires-approval and audited, instead of handing the agent a whole Slack or CRM API.
