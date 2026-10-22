"""Stage UI. Runs the naive agent and Sentinel side by side on the same input."""

from concurrent.futures import ThreadPoolExecutor

import streamlit as st

from sentinel.agent import run
from sentinel.config import OPIK_PROJECT, REPLAY, configure_opik

st.set_page_config(page_title="Sentinel", page_icon="🛡️", layout="wide")


@st.cache_resource
def _setup():
    configure_opik()
    return True


_setup()

st.markdown(
    """
<style>
.block-container { padding-top: 1.5rem; }
.badge { display:inline-block; padding:1px 8px; border-radius:6px; font-size:0.8rem; font-weight:600; margin-right:6px; }
.p1 { background:#fde2e1; color:#a1160a; } .p2 { background:#fff1d6; color:#8a5300; } .p3 { background:#e8eef7; color:#2d4a73; }
.ok { background:#dff5e3; color:#1d6b2f; } .bad { background:#fde2e1; color:#a1160a; } .wait { background:#fff1d6; color:#8a5300; }
.quarantine { border-left:4px solid #d93025; background:rgba(217,48,37,0.06); padding:8px 12px; margin:6px 0; border-radius:4px; font-size:0.9rem; }
</style>
""",
    unsafe_allow_html=True,
)

st.title("🛡️ Sentinel")
st.caption("A competitive-intel agent the web can't hijack · Nimble · Nexla · Comet Opik · Claude")

with st.sidebar:
    company = st.text_input("Company to research", "Quillstack")
    watch = st.text_area("Watchlist pages (one per line)", "fixture:quillstack", height=80)
    authorized = st.multiselect(
        "Actions you authorize",
        ["post_to_slack:#competitive-intel", "send_email:team@yourco.com", "update_crm:accounts"],
        default=["post_to_slack:#competitive-intel"],
    )
    layout = st.radio("Run", ["Side by side", "Sentinel only", "Naive only"])
    go = st.button("Run", type="primary", use_container_width=True)
    if REPLAY:
        st.info("Replay mode: serving web calls from cache")
    st.markdown(f"[Open traces in Opik ↗](https://www.comet.com/opik) · project `{OPIK_PROJECT}`")


def badge(text, cls):
    return f'<span class="badge {cls}">{text}</span>'


def render(result: dict, title: str):
    st.subheader(title)
    if result.get("blocked"):
        st.error(f"Request blocked at the request checkpoint: {result['blocked']}")
        return
    if result.get("error"):
        st.error(result["error"])
        return

    m1, m2, m3 = st.columns(3)
    m1.metric("Time", f"{result['total_s']}s")
    m2.metric("Briefing cost", f"${result['brief_cost_usd']:.3f}")
    m3.metric("Sources", len(result["sources"]))

    st.markdown("**TL;DR**")
    for line in result["tldr"]:
        st.markdown(f"- {line}")

    st.markdown("**Signals**")
    for s in sorted(result["signals"], key=lambda s: s["priority"]):
        links = " ".join(
            f'[{i}]({result["sources"][i]["url"]})' for i in s["source_ids"] if i in result["sources"]
        )
        verified = ""
        if s.get("verified") is False:
            verified = badge("UNVERIFIED", "bad")
        elif s.get("verified"):
            verified = badge("verified", "ok")
        st.markdown(
            f'{badge(s["priority"], s["priority"].lower())}{verified}{s["claim"]} '
            f'<span style="opacity:0.6">· {s["event_date"]} · {s["confidence"]} confidence</span> {links}',
            unsafe_allow_html=True,
        )
        if s.get("gate_note"):
            st.caption(f"↳ {s['gate_note']}")

    st.markdown("**Actions**")
    acts = [a for a in result["actions"] if a["tool"] != "none"]
    if not acts:
        st.caption("No actions proposed")
    for a in acts:
        cls = {"executed": "bad", "blocked": "ok", "pending_approval": "wait"}.get(a["decision"], "p3")
        label = {"executed": "EXECUTED", "blocked": "BLOCKED", "pending_approval": "NEEDS APPROVAL"}.get(a["decision"], a["decision"])
        st.markdown(f'{badge(label, cls)}`{a["tool"]}` → **{a["destination"]}**: {a["message"][:160]}', unsafe_allow_html=True)
        if a.get("gate_note"):
            st.caption(f"↳ {a['gate_note']}")

    q = result["integrity"]["quarantined"]
    if result["mode"] == "sentinel":
        st.markdown(f"**Integrity layer** · {len(q)} span(s) quarantined")
        for item in q:
            where = "hidden from humans" if item["hidden"] else "visible text"
            st.markdown(
                f'<div class="quarantine"><b>{where}</b> · {item["reason"]}<br><span style="opacity:0.75">“{item["text"][:220]}”</span></div>',
                unsafe_allow_html=True,
            )

    with st.expander("Timings and sources"):
        st.json({"timings_s": result["timings"], "brief_tokens": result["brief_tokens"], "degraded": result.get("degraded", [])})
        for i, src in result["sources"].items():
            st.markdown(f"{i}. [{src['title']}]({src['url']})")


if go:
    urls = [u.strip() for u in watch.splitlines() if u.strip()]
    modes = {"Side by side": ["naive", "sentinel"], "Sentinel only": ["sentinel"], "Naive only": ["naive"]}[layout]
    with st.spinner(f"Running {' and '.join(modes)} on {company}…"):
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = {m: pool.submit(run, company, m, urls, set(authorized)) for m in modes}
            results = {}
            for m, f in futures.items():
                try:
                    results[m] = f.result()
                except Exception as e:
                    results[m] = {"mode": m, "error": f"{type(e).__name__}: {e}"}
    cols = st.columns(len(modes))
    titles = {"naive": "😬 Naive agent", "sentinel": "🛡️ Sentinel"}
    for col, m in zip(cols, modes):
        with col:
            render(results[m], titles[m])
