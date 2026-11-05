import html as _html
import json
import re

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

from clinicc import compile_source, pretty, listing, rows, to_orders_json
from clinicc.samples import SAMPLES

st.set_page_config(page_title="ClinicFlow · Hospital Command Center", page_icon="🏥", layout="wide")

S = st.session_state
S.setdefault("src", SAMPLES["Cardiac triage (demo)"])
for k, v in {"scale": 100, "spacing": 1.6, "contrast": False, "dyslexic": False,
             "calm": False, "plain": False, "intro_done": False,
             "page": "🏥 Command Center"}.items():
    S.setdefault(k, v)

PAGES = ["🏥 Command Center", "🧑‍⚕️ Patient Workflow", "🧬 Protocol Studio", "🗺 Workflow Map"]
esc = _html.escape


def html(s: str):
    st.markdown("".join(line.strip() for line in s.splitlines()), unsafe_allow_html=True)


# ------------------------------------------------------------------ styling
CSS = """
@import url('https://fonts.googleapis.com/css2?family=Atkinson+Hyperlegible:wght@400;700&family=Inter:wght@400;600;700&family=JetBrains+Mono:wght@500;700&display=swap');
@property --n{syntax:'<integer>';initial-value:0;inherits:false}
:root{__VARS__}
.stApp{background:var(--bg);line-height:__LS__}
.stApp h1,.stApp h2,.stApp h3,.stApp h4,.stApp p,.stApp li,.stApp label,.stApp textarea,.stApp button,.stApp [data-testid="stCaptionContainer"]{font-family:var(--font)!important;color:var(--fg)}
.block-container p,.block-container li,.block-container label,.block-container textarea,.block-container code{font-size:__FS__rem!important}
*:focus-visible{outline:3px solid var(--ac)!important;outline-offset:2px!important}
section[data-testid="stSidebar"]{background:var(--side)}
section[data-testid="stSidebar"] :is(p,label,span,div,h1,h2,h3){color:var(--sf)}
section[data-testid="stSidebar"] div[role="radiogroup"] label{padding:.55rem .8rem;border-radius:10px;width:100%}
section[data-testid="stSidebar"] div[role="radiogroup"] label:has(input:checked){background:var(--ac)}
section[data-testid="stSidebar"] div[role="radiogroup"] label:has(input:checked) *{color:var(--ao)}
.logo{display:flex;gap:.6rem;align-items:center;font-size:1.4rem;font-weight:700}
.logo i{font-style:normal;background:var(--ac);color:var(--ao)!important;border-radius:10px;padding:.1rem .5rem}
.subt{font-family:'JetBrains Mono',monospace;letter-spacing:.2em;font-size:.62rem;opacity:.85;margin:.2rem 0 1rem}
.skip{position:absolute;left:-999px;background:var(--ac);color:var(--ao)!important;padding:.5rem 1rem;border-radius:8px;font-weight:700}
.skip:focus{left:8px;top:8px;z-index:9999}
.sr{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0);white-space:nowrap}
h2.pg{font-size:1.9rem;font-weight:700;margin:.1rem 0 .2rem;animation:rise .5s both}
.mut{color:var(--mut)}
.pill{display:inline-flex;gap:.4rem;align-items:center;border:2px solid var(--ac);border-radius:999px;padding:.2rem .8rem;font:700 .78rem 'JetBrains Mono',monospace;color:var(--fg)}
.dot{width:.6rem;height:.6rem;border-radius:50%;background:#1fa35c;animation:pulse 1.6s infinite}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:1rem;margin:1rem 0}
.card{background:var(--card);color:var(--fg);border:2px solid var(--ln);border-radius:16px;padding:1rem 1.2rem;animation:rise .5s both}
.card *{color:var(--fg)}
.card h3{margin:.1rem 0 .5rem}
.kpi{border-top:6px solid var(--ac);transition:transform .2s}.kpi:hover{transform:translateY(-3px)}
.kpi .l{font:600 .75rem 'JetBrains Mono',monospace;letter-spacing:.12em;text-transform:uppercase;color:var(--mut)!important}
.kpi .v{font:700 2.3rem 'JetBrains Mono',monospace;line-height:1.2}
.kpi .s{font-size:.82rem;color:var(--mut)!important}
.num{--n:0;animation:count 1.2s ease-out forwards;counter-reset:n var(--n)}
.num::after{content:counter(n)}
.badge{display:inline-block;font:700 .72rem 'JetBrains Mono',monospace;border-radius:8px;padding:.1rem .5rem;border:2px solid}
.card .b-c{color:#c62828;border-color:#c62828}.card .b-u{color:#b26a00;border-color:#b26a00}.card .b-s{color:#1b7f4b;border-color:#1b7f4b}
.bar{height:12px;background:var(--ln);border-radius:8px;overflow:hidden;margin:.2rem 0 .8rem}
.bar span{display:block;height:100%;background:var(--ac);width:0;animation:fill 1.2s ease forwards}
.feed{list-style:none;padding:0;margin:0}
.feed li{border-left:6px solid var(--ac);padding:.5rem .8rem;margin:.5rem 0;background:var(--bg);border-radius:8px;animation:slide .6s both}
.feed li:nth-child(2){animation-delay:.15s}.feed li:nth-child(3){animation-delay:.3s}.feed li:nth-child(4){animation-delay:.45s}
.feed li.c{border-left-color:#c62828}.feed li.u{border-left-color:#e29a00}
.vit{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:.7rem}
.vit div{background:var(--bg);border-radius:12px;padding:.7rem;border:2px solid var(--ln)}
.vit b{display:block;font:700 1.5rem 'JetBrains Mono',monospace}
.tl{list-style:none;padding:0;margin:.5rem 0 .5rem .6rem;border-left:4px solid var(--ac)}
.tl li{padding:.3rem 0 .6rem 1rem;position:relative;animation:slide .6s both}
.tl li::before{content:"✔";position:absolute;left:-1.05rem;top:.2rem;background:var(--ac);color:var(--ao);border-radius:50%;width:1.4rem;height:1.4rem;text-align:center;font-size:.8rem;line-height:1.4rem}
.tl li:nth-child(2){animation-delay:.15s}.tl li:nth-child(3){animation-delay:.3s}.tl li:nth-child(4){animation-delay:.45s}.tl li:nth-child(5){animation-delay:.6s}
.stages{display:flex;flex-wrap:wrap;gap:.5rem;margin:.6rem 0}
.st{border:2px solid var(--ln);border-radius:12px;padding:.4rem .8rem;font-weight:600;background:var(--card);color:var(--fg);animation:rise .5s both}
.st.ok{border-color:#1fa35c}.st.err{border-color:#c62828}.st.wait{border-style:dashed}
.det{border-left:8px solid var(--ac)}
.tag{display:inline-block;font:700 .7rem 'JetBrains Mono',monospace;background:var(--ac);color:var(--ao)!important;border-radius:6px;padding:.1rem .45rem;margin-right:.3rem}
.msg{border-radius:12px;padding:.6rem 1rem;margin:.4rem 0;background:var(--card);color:var(--fg);border:2px solid var(--ln);border-left-width:10px;animation:rise .4s both}
.msg *{color:var(--fg)}
.msg.ok{border-left-color:#1fa35c}.msg.err{border-left-color:#d93636}.msg.warn{border-left-color:#e29a00}.msg.info{border-left-color:#2f6fdb}
.stButton>button,.stDownloadButton>button{background:var(--side);border:2px solid var(--ac);border-radius:12px;font-weight:700;min-height:2.8rem}
.stButton>button p,.stDownloadButton>button p{color:var(--sf)!important}
.stButton>button:hover,.stDownloadButton>button:hover{background:var(--ac)}
.stButton>button:hover p,.stDownloadButton>button:hover p{color:var(--ao)!important}
div[data-baseweb="textarea"],div[data-baseweb="base-input"]{background:var(--card)!important}
.stApp textarea{font-family:'JetBrains Mono',monospace!important;color:var(--fg)!important;background:var(--card)!important;border:2px solid var(--ln)!important;border-radius:12px}
.intro{position:fixed;inset:0;z-index:999999;background:#0f2a43;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:1rem;text-align:center;pointer-events:none;animation:introOut .7s 4.2s forwards}
.intro .mark{font-size:3rem;font-weight:700;background:#0e9aa7;color:#fff;border-radius:18px;width:84px;height:84px;display:grid;place-items:center;animation:beat 1.2s ease-in-out infinite}
.intro h2{font-size:2.6rem;margin:0;color:#e8f1f7!important;animation:rise .8s .3s both}
.intro p{margin:0;color:#e8f1f7!important;animation:rise .8s .5s both}
.intro svg{width:min(560px,90vw);height:70px}
.intro svg path{fill:none;stroke:#2fd3df;stroke-width:3;vector-effect:non-scaling-stroke;stroke-dasharray:1400;stroke-dashoffset:1400;animation:trace 2.6s linear forwards;filter:drop-shadow(0 0 6px #2fd3df)}
.intro ul{list-style:none;padding:0;margin:0;text-align:left;font:600 .95rem 'JetBrains Mono',monospace}
.intro li{opacity:0;color:#e8f1f7!important;animation:rise .5s both}
.intro li::before{content:"✔ ";color:#2fd3df}
.intro li:nth-child(1){animation-delay:.8s}.intro li:nth-child(2){animation-delay:1.5s}.intro li:nth-child(3){animation-delay:2.2s}.intro li:nth-child(4){animation-delay:2.9s}
.intro .pbar{width:min(360px,80vw);height:8px;background:#ffffff33;border-radius:8px;overflow:hidden}
.intro .pbar span{display:block;height:100%;background:#2fd3df;width:0;animation:fillp 4.2s linear forwards}
@keyframes rise{from{opacity:0;transform:translateY(12px)}to{opacity:1;transform:none}}
@keyframes slide{from{opacity:0;transform:translateX(-18px)}to{opacity:1;transform:none}}
@keyframes pulse{50%{transform:scale(1.5);opacity:.5}}
@keyframes fill{to{width:var(--w)}}
@keyframes beat{0%,100%{transform:scale(1)}50%{transform:scale(1.12)}}
@keyframes trace{to{stroke-dashoffset:0}}
@keyframes fillp{to{width:100%}}
@keyframes count{from{--n:0}to{--n:var(--to)}}
@keyframes introOut{to{opacity:0;visibility:hidden}}
__CALM__
"""

CALM = """*,*::before,*::after{animation:none!important;transition:none!important}
.num{--n:var(--to)!important}.bar span{width:var(--w)!important}.intro{display:none!important}"""


def inject_css():
    if S["contrast"]:
        v = dict(bg="#000", fg="#fff", card="#000", ln="#fff", side="#000", sf="#fff",
                 ac="#ffe600", ao="#000", mut="#fff")
    else:
        v = dict(bg="#eef3f6", fg="#12263a", card="#ffffff", ln="#d5e0e8", side="#0f2a43",
                 sf="#e8f1f7", ac="#0e9aa7", ao="#ffffff", mut="#52687c")
    font = "'Atkinson Hyperlegible','Inter',sans-serif" if S["dyslexic"] else "'Inter',sans-serif"
    vars_ = "".join(f"--{k}:{x};" for k, x in v.items()) + f"--font:{font};"
    calm = CALM if S["calm"] else "@media (prefers-reduced-motion:reduce){" + CALM + "}"
    css = (CSS.replace("__VARS__", vars_).replace("__LS__", str(S["spacing"]))
           .replace("__FS__", str(S["scale"] / 100)).replace("__CALM__", calm))
    st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)


def intro():
    if S["intro_done"] or S["calm"]:
        return
    S["intro_done"] = True
    html("""<div class="intro" aria-hidden="true">
      <div class="mark">+</div><h2>ClinicFlow</h2>
      <p>Clinical workflow automation, powered by compiler technology</p>
      <svg viewBox="0 0 900 60" preserveAspectRatio="none"><path d="M0 40 L120 40 L140 40 L150 12 L162 56 L174 4 L186 40 L320 40 L340 40 L350 12 L362 56 L374 4 L386 40 L520 40 L540 40 L550 12 L562 56 L574 4 L586 40 L720 40 L740 40 L750 12 L762 56 L774 4 L786 40 L900 40"/></svg>
      <ul><li>Reading clinical protocol</li><li>Checking safety rules</li><li>Optimizing workflow</li><li>Generating orders</li></ul>
      <div class="pbar"><span></span></div></div>""")


# ------------------------------------------------------------------ helpers
def msg(kind, text):
    icon = {"ok": "✔ Success", "err": "✖ Error", "warn": "⚠ Warning", "info": "ℹ Tip"}[kind]
    role = "alert" if kind == "err" else "status"
    html(f'<div class="msg {kind}" role="{role}"><b>{icon}:</b> {esc(text)}</div>')


def kpis(items):
    """items: (label, integer value, sub text, suffix). Rendered as ONE html block so the grid works."""
    cells = "".join(
        f'<div class="card kpi" role="group" aria-label="{esc(l)}: {v}{suf}. {esc(sub)}">'
        f'<div class="l">{esc(l)}</div>'
        f'<div class="v"><span class="num" aria-hidden="true" style="--to:{int(v)}"></span>'
        f'<span aria-hidden="true">{suf}</span><span class="sr">{v}{suf}</span></div>'
        f'<div class="s">{esc(sub)}</div></div>' for l, v, sub, suf in items)
    html(f'<div class="grid">{cells}</div>')


def badge(text, lvl):
    return f'<span class="badge b-{lvl}">{esc(text)}</span>'


def hint(text):
    if S["plain"]:
        msg("info", text)


def head(title, lead):
    html(f'<h2 class="pg">{esc(title)}</h2><p class="mut">{esc(lead)}</p>')


def speak(text):
    safe = json.dumps(text).replace("</", "<\\/")
    components.html(f"""
    <style>button{{font:600 15px sans-serif;padding:8px 14px;border-radius:10px;border:2px solid #0f2a43;
    background:#fff;color:#0f2a43;cursor:pointer;margin-right:6px}}button:focus-visible{{outline:3px solid #0e9aa7}}</style>
    <button id="r" aria-label="Read this page summary aloud">🔊 Read summary aloud</button>
    <button id="s" aria-label="Stop reading">⏹ Stop</button>
    <script>
      const t = {safe};
      document.getElementById('r').onclick = () => {{
        speechSynthesis.cancel();
        const u = new SpeechSynthesisUtterance(t); u.rate = 0.95; speechSynthesis.speak(u);
      }};
      document.getElementById('s').onclick = () => speechSynthesis.cancel();
    </script>""", height=56)


def load_sample():
    text = SAMPLES[S["sample_pick"]]
    S["src"] = text
    S["editor"] = text


def get_res():
    return compile_source(S["src"])


NORMAL = {"bp_sys": ("Systolic BP", 90, 140, "mmHg"), "bp_dia": ("Diastolic BP", 60, 90, "mmHg"),
          "hr": ("Heart rate", 60, 100, "bpm"), "spo2": ("SpO₂", 94, 100, "%"),
          "temp": ("Temperature", 36.1, 37.8, "°C"), "glucose": ("Glucose", 70, 180, "mg/dL")}


def vitals_from(ast):
    out = {}
    for s in ast["body"]:
        if s["kind"] == "Let" and s["value"]["kind"] == "Num":
            out[s["name"]] = s["value"]["value"]
    return out


def route(kind, text):
    t = text.lower()
    if kind == "PRESCRIBE":
        return "Pharmacy"
    if kind == "ALERT":
        return "Doctor and nurse"
    if "ecg" in t or "echo" in t:
        return "Cardiology"
    if re.search(r"\b(ct|mri|x-ray|xray|scan|ultrasound)\b", t):
        return "Radiology"
    if re.search(r"(panel|test|blood|troponin|culture)", t):
        return "Laboratory"
    if "referral" in t:
        return "Referrals desk"
    return "Care team"


ICONS = {"ORDER": "📋 Order", "ALERT": "⚠ Alert", "PRESCRIBE": "💊 Prescription", "ERROR": "✖ Error"}

# ------------------------------------------------------------------ sidebar
with st.sidebar:
    html('<a class="skip" href="#main">Skip to main content</a>'
         '<div class="logo"><i>+</i>ClinicFlow</div><div class="subt">CITYCARE HOSPITAL · AUTOMATION</div>')
    st.radio("Navigate", PAGES, key="page")
    st.divider()
    st.markdown("**♿ Accessibility**")
    st.slider("Text size (%)", 80, 160, step=10, key="scale")
    st.slider("Line spacing", 1.2, 2.2, step=0.1, key="spacing")
    st.toggle("High contrast", key="contrast")
    st.toggle("Dyslexia-friendly font", key="dyslexic")
    st.toggle("Reduce motion", key="calm")
    st.toggle("Plain-language tips", key="plain")
    if st.button("▶ Replay intro"):
        S["intro_done"] = False
    st.caption("Tab and Shift+Tab move between controls. Enter or Space activates them.")

inject_css()
intro()
html('<div id="main" tabindex="-1"></div>')


# ------------------------------------------------------------------ pages
def page_cc():
    r = get_res()
    head("Command Center", "Live view of the emergency department, wards and automated workflows.")
    html('<span class="pill"><span class="dot" aria-hidden="true"></span>Workflow engine online</span>'
         ' <span class="mut">Demo data</span>')
    n_act = len(r["run_opt"]) if r["ok"] else 0
    kpis([("Patients in ED", 42, "8 waiting for triage", ""),
          ("Critical alerts", 5, "2 need review now", ""),
          ("Steps removed", r["stats"]["reduction"] if r["ok"] else 0, "by the optimizer on this protocol", "%"),
          ("Orders generated", n_act, "from the current protocol", "")])
    if not r["ok"]:
        msg("warn", "The current protocol has errors. Open Protocol Studio to fix them.")

    c1, c2 = st.columns(2)
    with c1:
        html('<div class="card"><h3>Triage queue</h3></div>')
        q = pd.DataFrame([
            ("P-1042", "R.K., 67", "Chest pain", "▲ CRITICAL", "2 min"),
            ("P-1043", "S.M., 54", "High glucose", "● URGENT", "9 min"),
            ("P-1044", "A.D., 31", "Fever", "■ STANDARD", "18 min"),
            ("P-1045", "L.T., 72", "Low oxygen", "▲ CRITICAL", "3 min"),
            ("P-1046", "N.P., 26", "Sprained ankle", "■ STANDARD", "34 min")],
            columns=["ID", "Patient", "Complaint", "Priority", "Wait"])
        st.dataframe(q, hide_index=True)
    with c2:
        items = ""
        if r["ok"]:
            for kind, text in r["run_opt"]:
                if kind == "ALERT":
                    items += f'<li class="c"><b>⚠ P-1042</b> {esc(text)}</li>'
        items += '<li><b>✔ Pharmacy</b> Duplicate order blocked automatically.</li>'
        html(f'<div class="card"><h3>Live alerts</h3><ul class="feed" aria-live="polite">{items}</ul></div>')

    beds = [("ICU", 18, 20), ("Emergency", 42, 50), ("Cardiology", 26, 40), ("General ward", 88, 120)]
    bars = "".join(f'<div>{n} · {a} of {b}</div><div class="bar" role="img" aria-label="{n} {round(100*a/b)} percent">'
                   f'<span style="--w:{round(100*a/b)}%"></span></div>' for n, a, b in beds)
    html(f'<div class="card"><h3>Bed occupancy</h3>{bars}</div>')
    speak(f"Command center. 42 patients in the emergency department, 5 critical alerts. "
          f"The current protocol generated {n_act} orders.")


def page_patient():
    r = get_res()
    head("Patient Workflow · P-1042", "R.K., 67 · Emergency · Chest pain · Protocol: Cardiac triage v3")
    hint("Vitals come from the protocol in Protocol Studio. Change a number there and this page updates.")
    vit = vitals_from(r["ast"])
    tiles = ""
    for key, (label, lo, hi, unit) in NORMAL.items():
        if key in vit:
            v = vit[key]
            b = badge("▲ HIGH", "c") if v > hi else badge("▼ LOW", "c") if v < lo else badge("✔ NORMAL", "s")
            tiles += f"<div>{esc(label)}<b>{v:g} <small>{unit}</small></b>{b}</div>"
    html(f'<div class="card"><h3>Vitals</h3><div class="vit">{tiles or "<p>No vitals defined in the protocol.</p>"}</div></div>')
    if not r["ok"]:
        msg("warn", "Fix the protocol errors in Protocol Studio to generate this patient's orders.")
        return
    s = r["stats"]
    c1, c2 = st.columns(2)
    with c1:
        html(f"""<div class="card"><h3>Automated workflow</h3><ol class="tl">
          <li><b>08:02</b> Registered, vitals captured by monitor</li>
          <li><b>08:03</b> Protocol compiled: {s['before']} steps simplified to {s['after']}</li>
          <li><b>08:03</b> Safety checks passed (ranges, dose limits)</li>
          <li><b>08:04</b> Orders sent to lab, radiology and pharmacy</li>
          <li><b>08:04</b> Nurse and doctor notified. Awaiting approval</li></ol></div>""")
    with c2:
        html('<div class="card"><h3>Generated orders</h3></div>')
        df = pd.DataFrame([(ICONS[k], t, route(k, t)) for k, t in r["run_opt"]],
                          columns=["Type", "Detail", "Routed to"])
        st.dataframe(df, hide_index=True)
        st.caption("Duplicate orders were removed by the optimizer. A clinician approves every order.")
    speak(f"Patient P-1042. The protocol produced {len(r['run_opt'])} orders. " +
          ". ".join(f"{k.lower()} {t}" for k, t in r["run_opt"]))


def page_studio():
    head("Protocol Studio", "Write clinical rules in structured text. The compiler checks, optimizes and turns them into orders.")
    hint("The three tabs are the three compiler modules: reading the rules, checking them, and optimizing them into orders.")
    st.selectbox("Load an example protocol", list(SAMPLES), key="sample_pick", on_change=load_sample)
    S["src"] = st.text_area("Protocol (Ctrl+Enter to apply)", value=S["src"], height=320, key="editor")
    r = get_res()

    syn = not r["syntax_errors"]
    sem = bool(r["sem"]) and not r["sem"]["errors"]
    opt_txt = f"Optimized: {r['stats']['before']} → {r['stats']['after']} steps" if r["ok"] else "Optimization"
    states = [("Syntax check", "ok" if syn else "err"),
              ("Safety check", "wait" if not syn else ("ok" if sem else "err")),
              (opt_txt, "ok" if r["ok"] else "wait"), ("Orders generated", "ok" if r["ok"] else "wait")]
    mark = {"ok": "✔", "err": "✖", "wait": "○"}
    html('<div class="stages" role="status" aria-label="Compilation stages">' + "".join(
        f'<span class="st {c}">{mark[c]} {esc(t)}</span>' for t, c in states) + "</div>")

    t1, t2, t3 = st.tabs(["① Syntax analysis", "② Logic & intermediate code", "③ Optimize & generate"])

    with t1:
        if r["syntax_errors"]:
            for e in r["syntax_errors"]:
                msg("err", e)
        else:
            msg("ok", f"No syntax errors. {len(r['tokens']) - 1} tokens and {len(r['ast']['body'])} top-level statements.")
        a, b = st.columns(2)
        with a:
            st.markdown("**Tokens**")
            st.dataframe(pd.DataFrame([{"Line": t.line, "Col": t.col, "Type": t.type, "Lexeme": t.value}
                                       for t in r["tokens"] if t.type != "EOF"]), hide_index=True)
        with b:
            st.markdown("**Parse tree**")
            st.code(pretty(r["ast"]), language="text")

    with t2:
        if r["syntax_errors"]:
            msg("warn", "Fix the syntax errors first.")
        else:
            for e in r["sem"]["errors"]:
                msg("err", e)
            for w in r["sem"]["warnings"]:
                msg("warn", w)
            if not r["sem"]["errors"]:
                msg("ok", "Semantic analysis passed. Types, vital ranges and dose limits are satisfied.")
                a, b = st.columns([2, 3])
                with a:
                    st.markdown("**Symbol table**")
                    st.dataframe(pd.DataFrame([{"Name": k, "Type": v} for k, v in r["sem"]["symbols"].items()]),
                                 hide_index=True)
                with b:
                    st.markdown("**Three-address code**")
                    st.code(listing(r["ir"]), language="text")

    with t3:
        if not r["ok"]:
            msg("warn", "Fix the errors in the first two tabs before optimizing.")
        else:
            s = r["stats"]
            kpis([("Before", s["before"], "IR instructions", ""), ("After", s["after"], "IR instructions", ""),
                  ("Reduction", s["reduction"], "less work", "%"), ("Passes", s["passes"], "until nothing changed", "")])
            if r["equivalent"]:
                msg("ok", "Verified: the optimized program produces the same clinical actions as the original (duplicate orders collapsed).")
            else:
                msg("err", "The optimized program differs from the original. This is a compiler bug.")
            st.markdown("**What the optimizer changed**")
            if r["log"]:
                st.dataframe(pd.DataFrame(r["log"], columns=["Optimization", "What changed"]), hide_index=True)
                st.bar_chart(pd.DataFrame({"Count": s["by_pass"]}))
                st.caption("Text alternative: " + ", ".join(f"{k}: {v}" for k, v in s["by_pass"].items()))
            a, b = st.columns(2)
            a.markdown("**Before**")
            a.code(listing(r["ir"]), language="text")
            b.markdown("**After**")
            b.code(listing(r["opt"]), language="text")
            a, b = st.columns(2)
            a.markdown("**ClinicalVM assembly**")
            a.code(r["asm"], language="nasm")
            b.markdown("**Generated Python**")
            b.code(r["py"], language="python")
            st.markdown("**Clinical actions produced**")
            st.dataframe(pd.DataFrame([(ICONS[k], t, route(k, t)) for k, t in r["run_opt"]],
                                      columns=["Type", "Detail", "Routed to"]), hide_index=True)
            orders = to_orders_json(r["run_opt"])
            with st.expander("FHIR-style orders (simplified, for teaching)"):
                st.code(orders, language="json")
            report = ("ClinicFlow report\n\n" + "\n".join(f"- {k}: {v}" for k, v in r["run_opt"]) +
                      f"\n\nInstructions: {s['before']} -> {s['after']} ({s['reduction']}% reduction)\n")
            d1, d2, d3, d4 = st.columns(4)
            d1.download_button("⬇ Assembly", r["asm"], "workflow.asm")
            d2.download_button("⬇ Python", r["py"], "workflow.py")
            d3.download_button("⬇ Orders JSON", orders, "orders.json")
            d4.download_button("⬇ Text report", report, "report.txt")
    summary = ("Protocol studio. " + (f"{len(r['syntax_errors'])} syntax errors. " + " ".join(r["syntax_errors"])
               if r["syntax_errors"] else "No syntax errors. ") +
               (f"The optimizer reduced {r['stats']['before']} steps to {r['stats']['after']}." if r["ok"] else ""))
    speak(summary)


STAGES = [
    ("Capture", "Source input", "Vitals from monitors, lab feeds, EHR fields and clinician-written protocols arrive as raw text and data.", "The compiler’s input: source text."),
    ("Understand", "Module 1 · Lexer + Parser", "“If BP is above 140 then order an ECG” is split into tokens and checked against a grammar. Malformed rules are caught early, all at once.", "Lexical and syntax analysis."),
    ("Verify", "Module 2 · Semantic analysis", "Units, plausible vital ranges, drug maximum doses and data types are checked. A 9000 mg Paracetamol dose is rejected before it reaches anyone.", "Semantic analysis and symbol table."),
    ("Represent", "Module 2 · Intermediate code", "The protocol becomes neutral three-address steps, independent of any one hospital system.", "Three-address code generation."),
    ("Optimize", "Module 3 · Optimizer", "Duplicate ECGs removed, impossible branches dropped, constants folded. Fewer tasks for staff.", "Folding, propagation, dead code removal."),
    ("Generate", "Module 3 · Code generation", "The same program is emitted as FHIR-style orders, nurse tasks, pharmacy queue items and dashboard alerts.", "Target code generation."),
    ("Run & learn", "Runtime + audit", "A clinician approves, actions execute and every step is logged. Protocol versions are tested before release.", "Execution and verification."),
]


def page_map():
    head("Workflow Map", "How a next-gen clinical workflow is automated. Each hospital step is powered by one compiler phase.")
    opts = [f"{i + 1}. {w[0]}" for i, w in enumerate(STAGES)]
    pick = st.radio("Select a stage", opts, horizontal=True, key="stage")
    i = opts.index(pick)
    w = STAGES[i]
    html(f'<div class="card det" aria-live="polite"><h3>Stage {i + 1}: {esc(w[0])}</h3>'
         f'<p><span class="tag">HOSPITAL</span>{esc(w[2])}</p>'
         f'<p><span class="tag">COMPILER</span>{esc(w[3])} ({esc(w[1])})</p></div>')
    html("""<div class="grid">
      <div class="card"><h3>Today</h3><ul><li>Guidelines live in PDFs and memory</li><li>Staff re-enter the same orders</li><li>Duplicate tests and missed alerts</li><li>Rules differ between wards</li></ul></div>
      <div class="card"><h3>Next-gen with a compiler</h3><ul><li>Guidelines become checked, versioned code</li><li>Unsafe doses are rejected before they reach a patient</li><li>Duplicates removed automatically</li><li>One protocol, same in every ward, with an audit trail</li></ul></div></div>
      <div class="grid">
      <div class="card"><span class="tag">NOW</span><p>Rule-based triage and order sets from structured protocols (this project).</p></div>
      <div class="card"><span class="tag">NEXT</span><p>Live data from monitors and the EHR. Clinician sign-off built in.</p></div>
      <div class="card"><span class="tag">LATER</span><p>AI drafts protocols from guidelines. The compiler verifies them before use.</p></div></div>""")
    st.caption("Academic prototype. A clinician always approves orders. Not a medical device.")
    speak(f"Stage {i + 1}, {w[0]}. {w[2]} Compiler role: {w[3]}")


{PAGES[0]: page_cc, PAGES[1]: page_patient, PAGES[2]: page_studio, PAGES[3]: page_map}[S["page"]]()
