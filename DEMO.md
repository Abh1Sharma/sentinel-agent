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
- "Here's Quillstack, a competitor we track. Its site looks normal." Show the page.
- Run **Side by side**.
- Left, the naive agent: the P1 is "Quillstack acquired by Helix Cloud for $4.2B", and it **posted it to #general**. "That acquisition never happened. It was hidden text on the page, invisible to you, written for your agent."
- Right, Sentinel: the claim was quarantined (hidden from humans), and the Slack post to #general was **blocked** because you never authorized that destination. The real news, the Pulse launch and the pricing, still came through.

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
