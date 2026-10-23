"""Terminal front end with live, color-coded logs.

    uv run python -m sentinel scan <url>               # any page: LinkedIn, a blog, a pricing page
    uv run python -m sentinel scan fixture:quillstack  # the built-in trap page
    uv run python -m sentinel brief <company> [--watch URL] [--mode side|sentinel|naive]
    uv run python -m sentinel leads [--effort medium] [--top 3] [--cached]
"""

import argparse
import sys
import textwrap
import threading
import time
from concurrent.futures import ThreadPoolExecutor

import opik

from .agent import run, scan_url

COLORS = {
    "step": "\033[36m",  # cyan
    "search": "\033[34m",  # blue
    "fetch": "\033[34m",
    "guard": "\033[35m",  # magenta
    "flag": "\033[33m",  # yellow
    "quarantine": "\033[1;31m",  # bold red
    "clear": "\033[32m",  # green
    "error": "\033[1;35m",
}
ICONS = {"step": "▸", "search": "🔎", "fetch": "🌐", "guard": "🛡 ", "flag": "⚠️ ", "quarantine": "⛔", "clear": "✅", "error": "‼️ "}
DIM, BOLD, RESET = "\033[2m", "\033[1m", "\033[0m"

_t0 = time.perf_counter()
_lock = threading.Lock()


def emit(kind: str, msg: str = "", excerpt: str = "", hidden: bool = False, **_):
    with _lock:
        stamp = f"{DIM}{time.perf_counter() - _t0:6.1f}s{RESET}"
        print(f"{stamp} {COLORS.get(kind, '')}{ICONS.get(kind, '·')} {msg}{RESET}", flush=True)
        if excerpt:
            tag = "hidden from humans" if hidden else "visible"
            wrapped = textwrap.fill(excerpt.replace("\n", " "), 100, initial_indent="          │ ", subsequent_indent="          │ ")
            print(f"{DIM}          │ [{tag}]\n{wrapped}{RESET}", flush=True)


def _print_reading(title: str, r: dict):
    print(f"\n{BOLD}{title}{RESET}")
    if r.get("error"):
        print(f"  error: {r['error']}")
        return
    for b in r["summary"]:
        print(textwrap.fill(b, 96, initial_indent="  • ", subsequent_indent="    "))
    print(textwrap.fill(r["outreach_draft"], 96, initial_indent="  ✉  ", subsequent_indent="     "))
    for a in r["actions_i_would_take"]:
        print(textwrap.fill(a, 96, initial_indent="  → ", subsequent_indent="    "))


def cmd_scan(args):
    res = scan_url(args.url, emit=emit, compare=not args.no_compare)
    if res.get("error"):
        return 1
    q = res["quarantined"]
    print(f"\n{BOLD}Integrity report{RESET}: {len(q)} span(s) quarantined · {res['hidden_spans']} hidden span(s) on page · {res['llm_checked']} sent to the classifier")
    if "naive" in res:
        _print_reading("😬 Naive agent (read the raw page)", res["naive"])
        _print_reading("🛡  Sentinel (read the cleaned page)", res["sentinel"])
    return 0


def cmd_brief(args):
    modes = {"side": ["naive", "sentinel"], "sentinel": ["sentinel"], "naive": ["naive"]}[args.mode]
    authorized = {"post_to_slack:#competitive-intel"}
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = {m: pool.submit(run, args.company, m, args.watch, authorized, emit=emit) for m in modes}
        results = {m: f.result() for m, f in futures.items()}
    for m, r in results.items():
        print(f"\n{BOLD}{'🛡  SENTINEL' if m == 'sentinel' else '😬 NAIVE'}{RESET}  {r.get('total_s', '?')}s · ${r.get('brief_cost_usd', 0):.3f}")
        if r.get("error") or r.get("blocked"):
            print("  ", r.get("error") or r.get("blocked"))
            continue
        for s in sorted(r["signals"], key=lambda s: s["priority"]):
            flag = " UNVERIFIED" if s.get("verified") is False else ""
            print(textwrap.fill(f"[{s['priority']}{flag}] {s['claim']}", 100, initial_indent="  ", subsequent_indent="      "))
        for a in r["actions"]:
            if a["tool"] != "none":
                print(f"  action {a['decision'].upper()}: {a['tool']} -> {a['destination']}")
    return 0


def _norm(text: str) -> str:
    return " ".join("".join(c.lower() if c.isalnum() else " " for c in text).split())


def check_source(row: dict, clean_text: str, start: str, end: str) -> dict:
    """The framework's last step, automated: does the evidence page really say
    what the agent quoted, and is the date inside the window?"""
    quote = _norm(row.get("evidence_quote", ""))
    page = _norm(clean_text)
    probe = quote[:80]
    return {
        "quote_on_page": bool(probe) and probe in page,
        "date_in_window": start <= row.get("signal_date", "") <= end,
    }


def cmd_leads(args):
    import datetime
    import json
    from pathlib import Path

    from .agent import read_page
    from .config import CACHE_DIR
    from .radar import run_radar

    cache = Path(CACHE_DIR) / "radar_result.json"
    if args.cached and cache.exists():
        emit("step", msg=f"Using the last Nimble agent result from {cache.name}")
        res = json.loads(cache.read_text())
    else:
        res = run_radar(effort=args.effort, emit=emit)
        cache.parent.mkdir(exist_ok=True)
        cache.write_text(json.dumps(res, default=str))
    rows = res["rows"]
    if not isinstance(rows, list):
        print(rows)
        return 1

    print(f"\n{BOLD}Nimble agent: {len(rows)} lead(s){RESET}")
    for i, r in enumerate(rows, 1):
        print(f"  {i}. {BOLD}{r['company']}{RESET} ({r['website']}) · {r['signal_date']} · buyer: {r['buyer_title']}")
        print(textwrap.fill(r["what_they_shipped"], 96, initial_indent="     ", subsequent_indent="     "))

    today = datetime.date.today()
    start, end = (today - datetime.timedelta(days=30)).isoformat(), today.isoformat()
    emit("step", msg=f"Check a source, every agent, every time: Sentinel opens the evidence page for the top {args.top} lead(s)")
    for r in rows[: args.top]:
        print(f"\n{BOLD}── {r['company']} ──{RESET}")
        scan = scan_url(r["evidence_url"], emit=emit, compare=False)
        if scan.get("error"):
            continue
        check = check_source(r, scan["clean_text"], start, end)
        emit("clear" if check["quote_on_page"] else "quarantine", msg=f"Quoted sentence {'FOUND' if check['quote_on_page'] else 'NOT FOUND'} on the evidence page")
        emit("clear" if check["date_in_window"] else "quarantine", msg=f"Signal date {r['signal_date']} {'is inside' if check['date_in_window'] else 'is OUTSIDE'} {start}..{end}")
        if scan["quarantined"]:
            emit("quarantine", msg=f"{len(scan['quarantined'])} injected span(s) removed before drafting outreach")
        draft = read_page(f"Lead: {r['company']} ({r['website']}). Buyer: {r['buyer_title']}.\nSignal: {r['what_they_shipped']}\n\n{scan['clean_text']}", True)
        if draft.get("error"):
            continue
        print(textwrap.fill(draft["outreach_draft"], 96, initial_indent="  ✉  ", subsequent_indent="     "))
        verified = check["quote_on_page"] and check["date_in_window"]
        decision = "NEEDS APPROVAL" if verified else "HELD (source check failed)"
        print(f"  → update_crm: add {r['company']} with signal + draft · {decision}")
    return 0


def main(argv=None):
    p = argparse.ArgumentParser(prog="sentinel", description="A competitive-intel agent the web can't hijack")
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("scan", help="Scan any URL for prompt injection, with live logs")
    s.add_argument("url")
    s.add_argument("--no-compare", action="store_true", help="skip the naive-vs-Sentinel comparison")
    b = sub.add_parser("brief", help="Competitive briefing on a company, with live logs")
    b.add_argument("company")
    b.add_argument("--watch", action="append", default=[], help="extra page to read (repeatable)")
    b.add_argument("--mode", choices=["side", "sentinel", "naive"], default="sentinel")
    lead = sub.add_parser("leads", help="Run the Nimble Lead Radar agent, then have Sentinel check every source")
    lead.add_argument("--effort", default="medium", choices=["low", "medium", "high", "x-high"])
    lead.add_argument("--top", type=int, default=3, help="how many leads to verify and draft outreach for")
    lead.add_argument("--cached", action="store_true", help="reuse the last agent result instead of re-running")
    args = p.parse_args(argv)
    try:
        return {"scan": cmd_scan, "brief": cmd_brief, "leads": cmd_leads}[args.cmd](args)
    finally:
        opik.flush_tracker()


if __name__ == "__main__":
    sys.exit(main())
