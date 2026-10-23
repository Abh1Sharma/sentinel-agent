"""Sentinel Lead Radar: a Nimble Web Search Agent built with Nimble's 5-step
framework (brief, sources, skill, output, effort), followed by the step the
framework says to never skip: check a source. Sentinel automates that step.

The agent lives in your Nimble account under AGENT_NAME, so it can also be run
from the Nimble web UI."""

import datetime
import time

from opik import track

from . import guard
from .config import nimble_client

AGENT_NAME = "sentinel-lead-radar"

_today = datetime.date.today()
_start = _today - datetime.timedelta(days=30)

# Step 1: brief it like an analyst. Name the companies, the dates and what counts.
BRIEF = (
    f"Find US B2B software companies that, between {_start:%B %d} and {_today:%B %d, %Y}, shipped or announced "
    "a product feature where an AI agent reads the open web or customer-supplied content on users' behalf: "
    "web-browsing agents, AI SDR or research agents, or AI support agents that read external pages. "
    "Counts: a dated launch post, changelog entry, press release or news article inside that window. "
    "Does not count: companies whose main product is AI security, frontier model labs (OpenAI, Anthropic, "
    "Google, Meta, Microsoft), or announcements outside the window. Return up to 8 companies, one row each."
)

# Step 2: tell it which pages to trust.
SOURCES = {
    "allow": [
        {"title": "Company blogs, changelogs and newsrooms", "domains": [], "order": 0},
        {"title": "Launch platforms", "domains": ["producthunt.com", "news.ycombinator.com", "ycombinator.com"], "order": 1},
        {"title": "Tech and business news", "domains": ["techcrunch.com", "venturebeat.com", "siliconangle.com", "businesswire.com", "prnewswire.com"], "order": 2},
        {"title": "LinkedIn company pages (discovery only)", "domains": ["linkedin.com"], "order": 3},
    ],
    "prioritize": "First-party pages (company blog, changelog, newsroom, docs) dated inside the window.",
    "avoid": "Listicles, 'top AI agents' roundups, SEO comparison pages and vendor marketplaces as evidence. Use them only to discover candidates, then confirm on a first-party page.",
}

# Step 3: make it an expert at one job.
SKILL = """# Agent-Launch Signal Analyst

You find B2B companies that just shipped AI agents which read the web, and you prove it.

## Evidence standard
- Every row needs an evidence_url that is first-party (company blog, changelog, newsroom, docs) or reputable news, dated inside the window. A listicle or roundup is never evidence.
- signal_date is the announcement date on that page, as YYYY-MM-DD. If the page has no clear date inside the window, drop the company.
- evidence_quote is one sentence copied from the evidence page that describes the agent reading web or customer content.
- One row per company: its single strongest, most recent signal.

## Judgment
- The agent must act for users and read external content (web pages, inboxes, docs, profiles). A chatbot over the company's own help center does not count.
- buyer_title is the role most likely to own agent safety at that company (Head of AI, VP Engineering, CTO, CISO). Never name a person.
- Never invent a company, URL, date or quote. Return fewer rows rather than guess."""

GOALS = [
    "Every row has a first-party or reputable-news evidence_url dated inside the window",
    "evidence_quote is copied from the evidence page, not paraphrased",
    "Never invent companies, URLs, dates or quotes; return fewer rows rather than guess",
]

# Step 4: choose what comes back. A table, one row each, plain column names.
OUTPUT_SCHEMA = {
    "type": "array",
    "items": {
        "type": "object",
        "additionalProperties": False,
        "required": ["company", "website", "signal_date", "what_they_shipped", "evidence_url", "evidence_quote", "buyer_title"],
        "properties": {
            "company": {"type": "string"},
            "website": {"type": "string", "description": "Bare hostname, e.g. acme.ai"},
            "signal_date": {"type": "string", "description": "YYYY-MM-DD"},
            "what_they_shipped": {"type": "string", "description": "One sentence"},
            "evidence_url": {"type": "string"},
            "evidence_quote": {"type": "string"},
            "buyer_title": {"type": "string"},
        },
    },
}

# Step 5: match the effort to the job. medium is about 3 minutes, which works live on stage.
DEFAULT_EFFORT = "medium"


def ensure_agent() -> str:
    """Create the agent in the Nimble account, or update it to match this file."""
    n = nimble_client()
    config = dict(
        display_name="Sentinel Lead Radar",
        description="Finds B2B companies that just shipped web-reading AI agents, with first-party evidence. Built with the 5-step framework; Sentinel checks every source.",
        effort=DEFAULT_EFFORT,
        goals=GOALS,
        output_schema=OUTPUT_SCHEMA,
        skill=SKILL,
        sources=SOURCES,
        suggested_questions=[BRIEF],
        use_case="dataset_building",
    )
    existing = next(
        (a for a in n.agents.list().model_dump(warnings=False).get("items", []) if a.get("name") == AGENT_NAME),
        None,
    )
    if existing:
        n.agents.update(existing["id"], body=config)
        return existing["id"]
    return n.agents.create(agent_name=AGENT_NAME, **config).model_dump(warnings=False).get("id", AGENT_NAME)


@track(name="radar.run", type="tool")
def run_radar(effort: str = DEFAULT_EFFORT, brief: str = BRIEF, emit=guard._noop) -> dict:
    n = nimble_client()
    emit("step", msg=f"Running Nimble agent '{AGENT_NAME}' at effort={effort}")
    t0 = time.perf_counter()
    run = n.agents.run(agent_name=AGENT_NAME, input=brief, effort=effort)
    agent_id = run.web_search_agent_id
    while run.is_active:
        time.sleep(8)
        run = n.agents.runs.get(run.id, agent_id=agent_id)
        emit("search", msg=f"Nimble agent {getattr(run, 'status', 'running')} ({time.perf_counter() - t0:.0f}s)")
    res = n.agents.runs.result(run.id, agent_id=agent_id).model_dump(warnings=False)
    output = res.get("output") or {}
    rows = output.get("data") or output.get("content")
    emit("step", msg=f"Nimble agent finished in {time.perf_counter() - t0:.0f}s")
    return {"rows": rows, "trust": output.get("trust"), "raw": res, "seconds": round(time.perf_counter() - t0)}
