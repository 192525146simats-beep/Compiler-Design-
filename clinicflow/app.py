import html as _html
import json
import os
import re
import time

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

from clinicc import compile_source, pretty, listing, to_orders_json
from clinicc.samples import SAMPLES
from clinicc.semantic import DRUG_MAX

st.set_page_config(page_title="ClinicFlow · Hospital Command Center", page_icon="🏥", layout="wide")

PAGES = ["🏥 Command Center", "🧾 Patient Registration", "🏢 Departments",
         "🧑‍⚕️ Patient Workflow", "🧬 Protocol Studio", "🗺 Workflow Map", "🎙 Voice Assistant"]
S = st.session_state
for k, v in {"scale": 100, "spacing": 1.6, "contrast": False, "dyslexic": False, "calm": False,
             "plain": False, "intro_done": False, "page": PAGES[0]}.items():
    S.setdefault(k, v)

esc = _html.escape

# ================================================================== hospital data
INPUT_ORDER = ["age", "weight", "bp_sys", "bp_dia", "hr", "spo2", "temp", "glucose"]
FIELDS = {"age": ("Age (years)", 0, 120, 1.0, "%.0f"), "weight": ("Weight (kg)", 1, 400, 1.0, "%.0f"),
          "bp_sys": ("Systolic BP (mmHg)", 40, 300, 1.0, "%.0f"), "bp_dia": ("Diastolic BP (mmHg)", 20, 200, 1.0, "%.0f"),
          "hr": ("Heart rate (bpm)", 20, 250, 1.0, "%.0f"), "spo2": ("SpO₂ (%)", 0, 100, 1.0, "%.0f"),
          "temp": ("Temperature (°C)", 30, 45, 0.1, "%.1f"), "glucose": ("Glucose (mg/dL)", 20, 800, 1.0, "%.0f")}
DEFAULT_VITALS = {"age": 40, "weight": 70, "bp_sys": 120, "bp_dia": 80, "hr": 75, "spo2": 98, "temp": 36.8, "glucose": 95}
NORMAL = {"bp_sys": ("Systolic BP", 90, 140, "mmHg"), "bp_dia": ("Diastolic BP", 60, 90, "mmHg"),
          "hr": ("Heart rate", 60, 100, "bpm"), "spo2": ("SpO₂", 94, 100, "%"),
          "temp": ("Temperature", 36.1, 37.8, "°C"), "glucose": ("Glucose", 70, 180, "mg/dL")}
RULE_VITALS = {"bp_sys": "Systolic BP", "bp_dia": "Diastolic BP", "hr": "Heart rate", "spo2": "SpO₂",
               "temp": "Temperature", "glucose": "Glucose", "age": "Age", "weight": "Weight"}
OPS = [">", "<", ">=", "<=", "=="]
PRIOS = ["Critical", "Urgent", "Standard"]
PRIO = {"Critical": "▲ CRITICAL", "Urgent": "● URGENT", "Standard": "■ STANDARD"}
PRIO_LVL = {"Critical": "c", "Urgent": "u", "Standard": "s"}
PASS_LABELS = {"fold": "Constant propagation and folding",
               "branch": "Branch folding and unreachable-code removal",
               "dead": "Dead-code elimination", "dup": "Duplicate-order removal"}
ICONS = {"ORDER": "📋 Order", "ALERT": "⚠ Alert", "PRESCRIBE": "💊 Prescription", "ERROR": "✖ Error"}

DEPTS = {
    "Emergency": ("🚑", "Triage, resuscitation and first response"),
    "Cardiology": ("❤️", "Heart and blood-pressure care, ECG and cardiac review"),
    "Radiology": ("🩻", "X-ray, CT, MRI and ultrasound"),
    "Laboratory": ("🧪", "Blood tests and sample analysis"),
    "Pharmacy": ("💊", "Medicines, dose checks and dispensing"),
    "ICU": ("🫁", "Critical care and breathing support"),
    "Pediatrics": ("🧒", "Care for infants and children"),
    "Orthopedics": ("🦴", "Bones, joints and fractures"),
    "Nursing": ("🩺", "Bedside care, monitoring and patient comfort"),
    "Billing": ("🧾", "Admissions, insurance and discharge paperwork"),
}


def pt(pid, name, sex, complaint, dept, priority, allergies, vit):
    return {"id": pid, "name": name, "sex": sex, "complaint": complaint, "dept": dept,
            "priority": priority, "allergies": allergies,
            "v": dict(zip(INPUT_ORDER, [float(x) for x in vit]))}


def make_patients():
    return [
        pt("P-1042", "R.K.", "Male", "Chest pain", "Emergency", "Critical", "none", (67, 72, 165, 98, 112, 91, 38.9, 110)),
        pt("P-1043", "S.M.", "Female", "High glucose", "Emergency", "Urgent", "none", (54, 80, 132, 84, 88, 97, 36.8, 245)),
        pt("P-1044", "A.D.", "Female", "Fever", "Emergency", "Standard", "paracetamol", (31, 64, 118, 76, 96, 98, 38.6, 92)),
        pt("P-1045", "L.T.", "Male", "Low oxygen", "ICU", "Critical", "none", (72, 68, 150, 92, 104, 88, 37.2, 130)),
        pt("P-1046", "N.P.", "Female", "Wrist injury", "Orthopedics", "Standard", "none", (9, 28, 104, 66, 92, 99, 36.7, 88)),
    ]


def mk(v1, op1, t1, typ, text="", dept="Nursing", drug="paracetamol", dose=500.0,
       second=False, conn="and", v2="hr", op2=">", t2=100.0):
    return {"v1": v1, "op1": op1, "t1": float(t1), "second": second, "conn": conn, "v2": v2,
            "op2": op2, "t2": float(t2), "type": typ, "text": text, "dept": dept,
            "drug": drug, "dose": float(dose)}


DEFAULT_RULES = [
    mk("age", ">=", 0, "Order", "Registration and insurance check", dept="Billing"),
    mk("bp_sys", ">", 140, "Alert", "Hypertension detected", dept="Emergency", second=True, v2="bp_dia", op2=">", t2=90),
    mk("bp_sys", ">", 140, "Order", "ECG", dept="Cardiology", second=True, v2="bp_dia", op2=">", t2=90),
    mk("bp_sys", ">", 140, "Order", "Troponin panel", dept="Laboratory", second=True, v2="hr", op2=">", t2=100),
    mk("spo2", "<", 94, "Alert", "Low oxygen saturation", dept="ICU"),
    mk("spo2", "<", 94, "Order", "Chest X-ray", dept="Radiology"),
    mk("temp", ">=", 38, "Prescribe", drug="paracetamol", dose=500),
    mk("bp_sys", ">", 160, "Order", "ECG", dept="Cardiology"),          # second pathway orders the same ECG
    mk("glucose", ">", 180, "Order", "HbA1c test", dept="Laboratory"),
    mk("age", "<", 16, "Alert", "Pediatric dose check required", dept="Pediatrics"),
]

DEPT_TEMPLATES = {
    "Emergency": [mk("hr", ">", 130, "Alert", "Emergency physician review", dept="Emergency")],
    "Cardiology": [mk("bp_sys", ">", 180, "Order", "Urgent cardiology review", dept="Cardiology")],
    "Radiology": [mk("spo2", "<", 92, "Order", "Chest CT scan", dept="Radiology")],
    "Laboratory": [mk("temp", ">=", 38.5, "Order", "Blood culture", dept="Laboratory")],
    "Pharmacy": [mk("glucose", ">", 250, "Prescribe", drug="insulin", dose=10)],
    "ICU": [mk("spo2", "<", 90, "Order", "ICU bed request", dept="ICU")],
    "Pediatrics": [mk("age", "<", 12, "Alert", "Child dosing review", dept="Pediatrics")],
    "Orthopedics": [mk("age", ">=", 70, "Order", "Bone density scan", dept="Orthopedics")],
    "Nursing": [mk("hr", ">", 110, "Alert", "Recheck vitals in 15 minutes", dept="Nursing")],
    "Billing": [mk("age", ">=", 60, "Order", "Insurance pre-authorization", dept="Billing")],
}

S.setdefault("patients", make_patients())
S.setdefault("next_id", 1047)
S.setdefault("sel", "P-1042")
S.setdefault("rules", [dict(r) for r in DEFAULT_RULES])
S.setdefault("passes", ["fold", "branch", "dead", "dup"])
S.setdefault("held", set())
S.setdefault("done", set())
S.setdefault("dept", "Emergency")
S.setdefault("sb_src", SAMPLES["Broken program (see errors)"])
S.setdefault("voice_log", [])
S.setdefault("voice_ai_history", [])

# ================================================================== styling
CSS = """
@import url('https://fonts.googleapis.com/css2?family=Atkinson+Hyperlegible:wght@400;700&family=Inter:wght@400;600;700&family=JetBrains+Mono:wght@500;700&display=swap');
@property --n{syntax:'<integer>';initial-value:0;inherits:false}
:root{__VARS__}
.stApp{background:var(--bg);line-height:__LS__}
.stApp h1,.stApp h2,.stApp h3,.stApp h4,.stApp p,.stApp li,.stApp label,.stApp textarea,.stApp button,.stApp [data-testid="stCaptionContainer"]{font-family:var(--font)!important;color:var(--fg)}
.block-container p,.block-container li,.block-container label,.block-container textarea,.block-container code{font-size:__FS__rem!important}
.block-container .element-container{animation:fade .45s both}
*:focus-visible{outline:3px solid var(--ac)!important;outline-offset:2px!important}
section[data-testid="stSidebar"]{background:var(--side)}
section[data-testid="stSidebar"] :is(p,label,span,div,h1,h2,h3){color:var(--sf)}
section[data-testid="stSidebar"] div[role="radiogroup"] label{padding:.5rem .8rem;border-radius:10px;width:100%;transition:background .2s,transform .2s}
section[data-testid="stSidebar"] div[role="radiogroup"] label:hover{transform:translateX(4px)}
section[data-testid="stSidebar"] div[role="radiogroup"] label:has(input:checked){background:var(--ac)}
section[data-testid="stSidebar"] div[role="radiogroup"] label:has(input:checked) *{color:var(--ao)}
.logo{display:flex;gap:.6rem;align-items:center;font-size:1.4rem;font-weight:700}
.logo i{font-style:normal;background:var(--ac);color:var(--ao)!important;border-radius:10px;padding:.1rem .5rem;animation:beat 2.4s ease-in-out infinite}
.subt{font-family:'JetBrains Mono',monospace;letter-spacing:.2em;font-size:.62rem;opacity:.85;margin:.2rem 0 1rem}
.skip{position:absolute;left:-999px;background:var(--ac);color:var(--ao)!important;padding:.5rem 1rem;border-radius:8px;font-weight:700}
.skip:focus{left:8px;top:8px;z-index:9999}
.sr{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0);white-space:nowrap}
h2.pg{font-size:1.9rem;font-weight:700;margin:.1rem 0 .2rem}
.type{display:block;overflow:hidden;white-space:nowrap;width:0;animation:typing 1s steps(30,end) forwards}
.mut{color:var(--mut)}
.pill{display:inline-flex;gap:.5rem;align-items:center;border:2px solid var(--ac);border-radius:999px;padding:.2rem .8rem;font:700 .78rem 'JetBrains Mono',monospace;color:var(--fg)}
.dot{position:relative;width:.6rem;height:.6rem;border-radius:50%;background:#1fa35c}
.dot::after{content:"";position:absolute;inset:0;border-radius:50%;background:#1fa35c;animation:ping 1.6s ease-out infinite}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:1rem;margin:1rem 0}
.card{background:var(--card);color:var(--fg);border:2px solid var(--ln);border-radius:16px;padding:1rem 1.2rem;animation:rise .5s both}
.card *{color:var(--fg)}
.card h3{margin:.1rem 0 .5rem}
.kpi{border-top:6px solid var(--ac);transition:transform .2s}.kpi:hover{transform:translateY(-4px)}
.kpi:nth-child(2){animation-delay:.08s}.kpi:nth-child(3){animation-delay:.16s}.kpi:nth-child(4){animation-delay:.24s}
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
.feed li:nth-child(2){animation-delay:.15s}.feed li:nth-child(3){animation-delay:.3s}.feed li:nth-child(4){animation-delay:.45s}.feed li:nth-child(5){animation-delay:.6s}.feed li:nth-child(6){animation-delay:.75s}
.feed li.c{border-left-color:#c62828}
.vit{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:.7rem}
.vit div{background:var(--bg);border-radius:12px;padding:.7rem;border:2px solid var(--ln);animation:pop .5s both;transition:transform .2s}
.vit div:hover{transform:scale(1.04)}
.vit div:nth-child(2){animation-delay:.07s}.vit div:nth-child(3){animation-delay:.14s}.vit div:nth-child(4){animation-delay:.21s}.vit div:nth-child(5){animation-delay:.28s}.vit div:nth-child(6){animation-delay:.35s}
.vit b{display:block;font:700 1.5rem 'JetBrains Mono',monospace}
.tl{list-style:none;padding:0;margin:.5rem 0 .5rem .6rem;border-left:4px solid var(--ac)}
.tl li{padding:.3rem 0 .6rem 1rem;position:relative;animation:slide .6s both}
.tl li::before{content:"✔";position:absolute;left:-1.05rem;top:.2rem;background:var(--ac);color:var(--ao);border-radius:50%;width:1.4rem;height:1.4rem;text-align:center;font-size:.8rem;line-height:1.4rem}
.tl li:nth-child(2){animation-delay:.15s}.tl li:nth-child(3){animation-delay:.3s}.tl li:nth-child(4){animation-delay:.45s}.tl li:nth-child(5){animation-delay:.6s}
.stages{display:flex;flex-wrap:wrap;gap:.5rem;margin:.6rem 0}
.st{border:2px solid var(--ln);border-radius:12px;padding:.4rem .8rem;font-weight:600;background:var(--card);color:var(--fg);animation:pop .5s both}
.st:nth-child(2){animation-delay:.1s}.st:nth-child(3){animation-delay:.2s}.st:nth-child(4){animation-delay:.3s}
.st.ok{border-color:#1fa35c}.st.err{border-color:#c62828}.st.wait{border-style:dashed}
.det{border-left:8px solid var(--ac)}
.tag{display:inline-block;font:700 .7rem 'JetBrains Mono',monospace;background:var(--ac);color:var(--ao)!important;border-radius:6px;padding:.1rem .45rem;margin-right:.3rem}
.msg{border-radius:12px;padding:.6rem 1rem;margin:.4rem 0;background:var(--card);color:var(--fg);border:2px solid var(--ln);border-left-width:10px;animation:slide .4s both}
.msg *{color:var(--fg)}
.msg.ok{border-left-color:#1fa35c}.msg.err{border-left-color:#d93636}.msg.warn{border-left-color:#e29a00}.msg.info{border-left-color:#2f6fdb}
.stButton>button,.stDownloadButton>button,.stFormSubmitButton>button{background:var(--side);border:2px solid var(--ac);border-radius:12px;font-weight:700;min-height:2.8rem;transition:transform .15s,background .2s}
.stButton>button p,.stDownloadButton>button p,.stFormSubmitButton>button p{color:var(--sf)!important}
.stButton>button:hover,.stDownloadButton>button:hover,.stFormSubmitButton>button:hover{background:var(--ac);transform:translateY(-2px)}
.stButton>button:hover p,.stDownloadButton>button:hover p,.stFormSubmitButton>button:hover p{color:var(--ao)!important}
div[data-baseweb="textarea"],div[data-baseweb="base-input"]{background:var(--card)!important}
.stApp textarea{font-family:'JetBrains Mono',monospace!important;color:var(--fg)!important;background:var(--card)!important;border:2px solid var(--ln)!important;border-radius:12px}
.sec{border-left:8px solid var(--ac);margin-top:1.4rem}
.rule{background:var(--card);color:var(--fg);border:2px solid var(--ln);border-radius:12px;padding:.5rem .9rem;margin:.3rem 0;animation:slide .4s both}
.depts{display:grid;grid-template-columns:repeat(auto-fit,minmax(165px,1fr));gap:.8rem;margin:.6rem 0}
.dept{background:var(--bg);color:var(--fg);border:2px solid var(--ln);border-radius:16px;padding:.8rem 1rem;animation:pop .5s both;animation-delay:var(--d);transition:transform .2s,border-color .2s}
.dept:hover{transform:translateY(-5px) rotate(-.5deg);border-color:var(--ac)}
.dept .ic{font-size:1.8rem;display:inline-block;animation:bob 2.6s ease-in-out infinite}
.dept:nth-child(2n) .ic{animation-delay:.4s}.dept:nth-child(3n) .ic{animation-delay:.9s}
.dept b{display:block}
.dept .n{font:700 1.5rem 'JetBrains Mono',monospace;color:var(--ac)}
.dept.busy{animation:pop .5s both,ringp 2s ease-out infinite;animation-delay:var(--d),0s}
.mini{height:8px;background:var(--ln);border-radius:6px;overflow:hidden;margin-top:.4rem}
.mini i{display:block;height:100%;background:var(--ac);width:0;animation:fill 1.2s ease forwards}
.dh{display:flex;align-items:center;gap:1rem;flex-wrap:wrap}
.dh div{flex:1 1 220px}
.bigic{font-size:3rem;display:inline-block;animation:bob 2.6s ease-in-out infinite}
.ring{width:120px;height:120px}
.ring circle{fill:none;stroke-width:9}
.ring .bg{stroke:var(--ln)}
.ring .fg{stroke:var(--ac);stroke-linecap:round;stroke-dasharray:283;stroke-dashoffset:283;transform:rotate(-90deg);transform-origin:50% 50%;animation:ringfill 1.4s ease forwards}
.ring text{font:700 20px 'JetBrains Mono',monospace;fill:var(--fg)}
.dchip{display:inline-block;border:2px solid var(--ac);border-radius:999px;padding:.15rem .8rem;margin:.15rem;animation:pop .4s both}
.road{position:relative;height:36px;overflow:hidden;border-bottom:3px dashed var(--ln);margin:.7rem 0}
.road span{position:absolute;bottom:2px;font-size:1.5rem;left:-8%;animation:drive 10s linear infinite}
.road span.back{transform:scaleX(-1);animation:driveback 13s linear infinite;animation-delay:-4s}
.ticker{overflow:hidden;white-space:nowrap;border:2px solid var(--ln);border-radius:999px;background:var(--card);color:var(--fg);padding:.3rem 0;margin:.4rem 0}
.ticker div{display:inline-block;padding-left:100%;animation:marq 32s linear infinite}
.ticker:hover div{animation-play-state:paused}
.ecgbar{width:100%;height:46px;display:block}
.ecgbar path{fill:none;stroke:var(--ac);stroke-width:2.5;vector-effect:non-scaling-stroke;stroke-dasharray:1400;stroke-dashoffset:1400;animation:trace 4s linear infinite}
.okrow{display:flex;align-items:center;gap:.8rem}
.chk{width:56px;height:56px}
.chk circle{fill:none;stroke:#1fa35c;stroke-width:3;stroke-dasharray:151;stroke-dashoffset:151;animation:draw .7s forwards}
.chk path{fill:none;stroke:#1fa35c;stroke-width:4;stroke-dasharray:50;stroke-dashoffset:50;animation:draw .5s .6s forwards}
.flowsvg{width:100%;max-width:660px;display:block;margin:.4rem 0}
.flowsvg rect{fill:var(--card);stroke:var(--ac);stroke-width:2.5}
.flowsvg text{font:700 13px 'JetBrains Mono',monospace;fill:var(--fg)}
.flowsvg .fl{stroke:var(--ac);stroke-width:3;stroke-dasharray:6 6;fill:none;animation:dash 1s linear infinite}
.how{display:flex;flex-wrap:wrap;gap:.6rem;margin:.6rem 0}
.how div{flex:1 1 220px;background:var(--card);color:var(--fg);border:2px solid var(--ln);border-radius:14px;padding:.7rem 1rem;animation:glow 8s infinite}
.how div:nth-child(2){animation-delay:2.5s}.how div:nth-child(3){animation-delay:5s}
.how b{display:block;color:var(--fg)}
.how small{font:700 .68rem 'JetBrains Mono',monospace;letter-spacing:.1em;color:var(--ac)}
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
.splash{min-height:78vh;background:#0f2a43;border-radius:28px;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:1rem;text-align:center;padding:2rem;margin-top:1rem}
.splash .mark{font-size:3rem;font-weight:700;background:#0e9aa7;color:#fff;border-radius:18px;width:84px;height:84px;display:grid;place-items:center;animation:beat 1.2s ease-in-out infinite}
.splash h2{font-size:2.8rem;margin:0;color:#e8f1f7!important;animation:rise .8s .3s both}
.splash p{margin:0;color:#e8f1f7!important;animation:rise .8s .5s both}
.splash svg{width:min(640px,90%);height:70px}
.splash svg path{fill:none;stroke:#2fd3df;stroke-width:3;vector-effect:non-scaling-stroke;stroke-dasharray:1400;stroke-dashoffset:1400;animation:trace 2.6s linear forwards;filter:drop-shadow(0 0 6px #2fd3df)}
.splash ul{list-style:none;padding:0;margin:0;text-align:left;font:600 .95rem 'JetBrains Mono',monospace}
.splash li{opacity:0;color:#e8f1f7!important;animation:rise .5s both}
.splash li::before{content:"✔ ";color:#2fd3df}
.splash li:nth-child(1){animation-delay:.8s}.splash li:nth-child(2){animation-delay:1.5s}.splash li:nth-child(3){animation-delay:2.2s}.splash li:nth-child(4){animation-delay:2.9s}
.splash .pbar{width:min(360px,80%);height:8px;background:#ffffff33;border-radius:8px;overflow:hidden}
.splash .pbar span{display:block;height:100%;background:#2fd3df;width:0;animation:fillp 4.2s linear forwards}
@keyframes fade{from{opacity:0}to{opacity:1}}
@keyframes rise{from{opacity:0;transform:translateY(12px)}to{opacity:1;transform:none}}
@keyframes slide{from{opacity:0;transform:translateX(-18px)}to{opacity:1;transform:none}}
@keyframes pop{from{opacity:0;transform:scale(.85)}to{opacity:1;transform:none}}
@keyframes bob{50%{transform:translateY(-5px)}}
@keyframes beat{0%,100%{transform:scale(1)}50%{transform:scale(1.12)}}
@keyframes ping{to{transform:scale(3);opacity:0}}
@keyframes ringp{0%{box-shadow:0 0 0 0 rgba(14,154,167,.55)}100%{box-shadow:0 0 0 16px rgba(14,154,167,0)}}
@keyframes typing{to{width:100%}}
@keyframes fill{to{width:var(--w)}}
@keyframes ringfill{to{stroke-dashoffset:var(--off)}}
@keyframes trace{to{stroke-dashoffset:0}}
@keyframes draw{to{stroke-dashoffset:0}}
@keyframes dash{to{stroke-dashoffset:-12}}
@keyframes drive{from{left:-8%}to{left:104%}}
@keyframes driveback{from{left:104%}to{left:-8%}}
@keyframes marq{to{transform:translateX(-100%)}}
@keyframes count{from{--n:0}to{--n:var(--to)}}
@keyframes fillp{to{width:100%}}
@keyframes glow{0%,12%,100%{box-shadow:none}6%{box-shadow:0 0 0 3px var(--ac)}}
@keyframes introOut{to{opacity:0;visibility:hidden}}
__CALM__
"""

CALM = """*,*::before,*::after{animation:none!important;transition:none!important}
.num{--n:var(--to)!important}.bar span,.mini i{width:var(--w)!important}
.intro{display:none!important}.type{width:100%!important}
.ring .fg{stroke-dashoffset:var(--off)!important}
.chk circle,.chk path,.ecgbar path{stroke-dashoffset:0!important}
.ticker div{padding-left:.8rem!important;white-space:normal!important}"""


def html(s: str):
    st.markdown("".join(line.strip() for line in s.splitlines()), unsafe_allow_html=True)


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


ECG = ("M0 40 L120 40 L140 40 L150 12 L162 56 L174 4 L186 40 L320 40 L340 40 L350 12 L362 56 L374 4 "
       "L386 40 L520 40 L540 40 L550 12 L562 56 L574 4 L586 40 L720 40 L740 40 L750 12 L762 56 L774 4 L786 40 L900 40")


def splash():
    html(f"""<div class="splash">
      <div class="mark">+</div><h2>ClinicFlow</h2>
      <p>Hospital-wide workflow automation, powered by compiler technology</p>
      <svg viewBox="0 0 900 60" preserveAspectRatio="none" aria-hidden="true"><path d="{ECG}"/></svg>
      <ul><li>Registering patients</li><li>Checking safety rules</li><li>Optimizing department workflows</li><li>Generating orders</li></ul>
      <div class="pbar"><span></span></div></div>""")
    time.sleep(4.5)
    S["intro_done"] = True
    st.rerun()


def intro():
    pass


# ================================================================== UI helpers
def msg(kind, text):
    icon = {"ok": "✔ Success", "err": "✖ Error", "warn": "⚠ Warning", "info": "ℹ Tip"}[kind]
    role = "alert" if kind == "err" else "status"
    html(f'<div class="msg {kind}" role="{role}"><b>{icon}:</b> {esc(text)}</div>')


def kpis(items):
    """items: (label, integer, sub text, suffix). One html block so the grid works."""
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
    html(f'<h2 class="pg type">{esc(title)}</h2><p class="mut">{esc(lead)}</p>')


def section(num, title, lead):
    html(f'<div class="card sec"><span class="tag">MODULE {num}</span><h3>{esc(title)}</h3><p>{esc(lead)}</p></div>')


def ring(pct, label):
    off = round(283 - 283 * pct / 100, 1)
    return (f'<svg class="ring" viewBox="0 0 100 100" role="img" aria-label="{esc(label)}">'
            f'<circle class="bg" cx="50" cy="50" r="45"/><circle class="fg" cx="50" cy="50" r="45" style="--off:{off}"/>'
            f'<text x="50" y="56" text-anchor="middle">{pct}%</text></svg>')


def vit_tiles(v):
    t = ""
    for key, (label, lo, hi, unit) in NORMAL.items():
        x = v[key]
        b = badge("▲ HIGH", "c") if x > hi else badge("▼ LOW", "c") if x < lo else badge("✔ NORMAL", "s")
        t += f"<div>{esc(label)}<b>{x:g} <small>{unit}</small></b>{b}</div>"
    return f'<div class="vit">{t}</div>'


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


# ================================================================== voice assistant
# Groq model can be changed in Streamlit Secrets using GROQ_MODEL.
try:
    GROQ_MODEL = str(st.secrets.get("GROQ_MODEL", "") or "").strip()
except Exception:
    GROQ_MODEL = ""
GROQ_MODEL = GROQ_MODEL or os.getenv("GROQ_MODEL", "openai/gpt-oss-20b")
VOICE_LANGS = {"English (India)": "en-IN", "English (US)": "en-US", "தமிழ் (Tamil)": "ta-IN",
               "हिन्दी (Hindi)": "hi-IN", "తెలుగు (Telugu)": "te-IN"}

MIC_HTML = """
<style>
 body{font-family:Inter,sans-serif;margin:0}
 #mic{font-size:18px;font-weight:700;padding:12px 22px;border-radius:14px;border:2px solid #0e9aa7;
      background:#0f2a43;color:#fff;cursor:pointer}
 #mic.on{background:#c62828;border-color:#c62828;animation:p 1s infinite}
 #mic:focus-visible{outline:3px solid #0e9aa7;outline-offset:2px}
 #st{margin:.6rem 0 .3rem;font-weight:600;color:#12263a}
 #tx{min-height:2.2rem;padding:.5rem .8rem;border:2px dashed #9fb3c2;border-radius:10px;color:#12263a;background:#fff}
 @keyframes p{50%{transform:scale(1.06)}}
</style>
<button id="mic" aria-label="Start or stop listening">🎤 Tap and speak</button>
<div id="st" role="status" aria-live="polite">Ready</div>
<div id="tx" aria-live="polite"></div>
<script>
const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
const btn = document.getElementById('mic'), st = document.getElementById('st'), tx = document.getElementById('tx');

function sendToStreamlit(text){
  const doc = window.parent.document;
  const inp = doc.querySelector('input[aria-label="Voice question"]');
  if(!inp){ st.textContent = "Could not find the question box. Type your question instead."; return; }
  const setter = Object.getOwnPropertyDescriptor(window.parent.HTMLInputElement.prototype, 'value').set;
  inp.focus();
  setter.call(inp, text);
  inp.dispatchEvent(new Event('input', {bubbles:true}));
  inp.dispatchEvent(new KeyboardEvent('keydown', {key:'Enter', code:'Enter', keyCode:13, which:13, bubbles:true}));
  st.textContent = "Thinking…";
}

if(!SR){
  st.textContent = "Speech recognition is not supported here. Use Chrome or Edge, or type your question.";
  btn.disabled = true;
}else{
  const rec = new SR();
  rec.lang = "__LANG__"; rec.interimResults = true; rec.continuous = false;
  let listening = false, finalText = "";
  btn.onclick = () => {
    if(listening){ rec.stop(); return; }
    try{ window.parent.speechSynthesis.cancel(); }catch(e){}
    finalText = ""; tx.textContent = "";
    try{ rec.start(); }catch(e){}
  };
  rec.onstart = () => { listening = true; btn.classList.add('on'); btn.textContent = "⏹ Listening… tap to stop"; st.textContent = "Listening"; };
  rec.onresult = (e) => {
    let interim = "";
    for(let i = e.resultIndex; i < e.results.length; i++){
      const r = e.results[i];
      if(r.isFinal) finalText += r[0].transcript; else interim += r[0].transcript;
    }
    tx.textContent = finalText + interim;
  };
  rec.onerror = (e) => { st.textContent = "Microphone error: " + e.error + ". Allow microphone access in the browser."; };
  rec.onend = () => {
    listening = false; btn.classList.remove('on'); btn.textContent = "🎤 Tap and speak";
    if(finalText.trim()) sendToStreamlit(finalText.trim());
    else if(st.textContent === "Listening") st.textContent = "I did not hear anything. Try again.";
  };
}
</script>
"""

NAV_WORDS = [("patient workflow", 3), ("workflow map", 5), ("command center", 0), ("dashboard", 0),
             ("registration", 1), ("register", 1), ("department", 2), ("protocol", 4),
             ("studio", 4), ("map", 5), ("voice", 6)]


def local_intent(q):
    """Hospital commands answered offline. Returns text, or None if not a built-in command."""
    t = q.lower().strip()
    if re.search(r"\b(open|go to|show|take me to|navigate)\b", t):
        for word, i in NAV_WORDS:
            if word in t:
                S["page"] = PAGES[i]
                name = re.sub(r"^\W+", "", PAGES[i])
                return f"Opening {name}."
    if "high contrast" in t:
        S["contrast"] = "off" not in t
        return "High contrast is now " + ("off." if "off" in t else "on.")
    if "reduce motion" in t or "calm mode" in t:
        S["calm"] = "off" not in t
        return "Reduced motion is now " + ("off." if "off" in t else "on.")
    if re.search(r"(bigger|larger|increase).*(text|font)", t):
        S["scale"] = min(160, S["scale"] + 10)
        return f"Text size is now {S['scale']} percent."
    if re.search(r"(smaller|decrease|reduce).*(text|font)", t):
        S["scale"] = max(80, S["scale"] - 10)
        return f"Text size is now {S['scale']} percent."

    m = re.search(r"p-?\s?(\d{4})", t)
    if m and (p := byid(f"P-{m.group(1)}")):
        v = p["v"]
        return (f"{p['id']}, {p['name']}, {v['age']:g} years, {p['complaint']}, {p['priority']} priority in {p['dept']}. "
                f"Blood pressure {v['bp_sys']:g} over {v['bp_dia']:g}, heart rate {v['hr']:g}, "
                f"oxygen {v['spo2']:g} percent, temperature {v['temp']:g} degrees, glucose {v['glucose']:g}. "
                f"Allergies: {p['allergies']}.")
    if re.search(r"how many patients|number of patients", t):
        return f"There are {len(S['patients'])} patients registered."
    if "critical" in t and "patient" in t:
        c = [p for p in S["patients"] if p["priority"] == "Critical"]
        return (f"{len(c)} critical patients: " + ", ".join(f"{p['id']} with {p['complaint']}" for p in c) + ".") if c \
            else "There are no critical patients."
    if re.search(r"open tasks|pending tasks", t):
        tasks = build_tasks(results())
        return f"There are {sum(x['released'] and not x['done'] for x in tasks)} open tasks across all departments."
    if "alert" in t:
        al = [x for x in build_tasks(results()) if x["kind"] == "ALERT" and x["released"]]
        return ("Active alerts: " + "; ".join(f"{x['pid']} {x['dept']}, {x['detail']}" for x in al[:5]) + ".") if al \
            else "There are no active alerts."
    return None


def ask_claude(q):
    """General-purpose ClinicFlow AI using the Groq chat-completions API."""
    # Streamlit Cloud Secrets take priority over environment variables.
    api_key = None
    try:
        api_key = st.secrets.get("GROQ_API_KEY")
    except Exception:
        api_key = None

    if not api_key:
        api_key = os.getenv("GROQ_API_KEY")

    api_key = str(api_key).strip() if api_key else ""
    if not api_key:
        return (
            "Groq API key is missing. Add GROQ_API_KEY to your Streamlit "
            "app Secrets, save, and reboot the app."
        )

    try:
        from groq import Groq

        client = Groq(api_key=api_key, timeout=60.0, max_retries=2)

        # Keep a short conversation history for follow-up questions.
        messages = [
            {
                "role": "system",
                "content": (
                    "You are ClinicFlow AI Voice, a friendly and concise assistant "
                    "inside a hospital workflow demonstration application. Answer "
                    "questions about general knowledge, science, technology, education, "
                    "programming, mathematics, history, languages, and daily life. "
                    "The selected speech language is "
                    + str(S.get("voice_lang_name", S.get("floating_voice_lang", "English (India)")))
                    + ". Reply in the language used by the user, using natural spoken "
                    "wording and normally 2 to 6 sentences. Avoid Markdown tables. "
                    "For medical topics, provide general educational information only: "
                    "do not diagnose, prescribe, or recommend patient-specific doses. "
                    "For emergencies, advise contacting local emergency services and "
                    "a qualified clinician. Do not request, infer, or expose "
                    "patient-identifying information. This is an academic demonstration, "
                    "not a clinical decision system. Do not claim to have searched the "
                    "web or accessed live information."
                ),
            }
        ]

        # Add the last few AI conversation turns, but not built-in local commands.
        for old_q, old_a in S.get("voice_ai_history", [])[-4:]:
            messages.append({"role": "user", "content": old_q})
            messages.append({"role": "assistant", "content": old_a})

        messages.append({"role": "user", "content": q})

        chat_completion = client.chat.completions.create(
            messages=messages,
            model=GROQ_MODEL,
            temperature=0.4,
            max_completion_tokens=700,
        )

        answer = chat_completion.choices[0].message.content
        answer = (answer or "").strip()
        return answer or "I could not prepare an answer. Please try asking another way."

    except ImportError:
        return "The Groq package is missing. Add groq to requirements.txt and redeploy."
    except Exception as error:
        error_name = type(error).__name__

        if error_name == "AuthenticationError":
            return (
                "Groq rejected the API key. Check GROQ_API_KEY in Streamlit Cloud "
                "Secrets, then save and reboot the app."
            )
        if error_name == "RateLimitError":
            return (
                "The Groq API usage limit has been reached. Please wait and try again "
                "later, or check your Groq account limits."
            )
        if error_name in ("APIConnectionError", "APITimeoutError"):
            return "ClinicFlow could not connect to Groq. Please try again shortly."
        if error_name == "BadRequestError":
            return (
                "Groq did not accept the request or model. Check GROQ_MODEL in "
                "Streamlit Secrets and make sure the selected model is available."
            )
        return (
            f"ClinicFlow AI connection failed ({error_name}). "
            "Please check your Groq API configuration and try again."
        )


def handle_voice():
    q = (S.get("voice_q") or "").strip()
    if not q:
        return
    ans = local_intent(q)
    src = "Built-in"
    if ans is None:
        ans, src = ask_claude(q), "AI"
        S["voice_ai_history"].append((q, ans))
        S["voice_ai_history"] = S["voice_ai_history"][-8:]
    S["voice_log"].append((q, ans, src))
    S["voice_speak"] = ans
    S["voice_q"] = ""


def say(text, lang):
    """Speak automatically through the parent page (the mic tap already gave permission)."""
    safe = json.dumps(text).replace("</", "<\\/")
    components.html(f"""<script>
      // {time.time()}
      try {{
        const w = window.parent; w.speechSynthesis.cancel();
        const u = new w.SpeechSynthesisUtterance({safe}); u.lang = "{lang}"; u.rate = 0.97;
        w.speechSynthesis.speak(u);
      }} catch (e) {{}}
    </script>""", height=0)


def clear_voice():
    S["voice_log"] = []
    S["voice_ai_history"] = []


# ================================================================== compiler glue
def byid(pid):
    return next((p for p in S["patients"] if p["id"] == pid), None)


def safe_text(t):
    return re.sub(r'["\r\n]', " ", t).strip() or "Unnamed"


def cond_text(r):
    c = f'{r["v1"]} {r["op1"]} {r["t1"]:g}'
    if r["second"]:
        c += f' {r["conn"]} {r["v2"]} {r["op2"]} {r["t2"]:g}'
    return c


def rule_plain(r):
    def part(v, op, t):
        return f"{RULE_VITALS[v]} {op} {t:g}"
    cond = part(r["v1"], r["op1"], r["t1"])
    if r["second"]:
        cond += f' {r["conn"].upper()} ' + part(r["v2"], r["op2"], r["t2"])
    if r["type"] == "Prescribe":
        act = f'Prescribe {r["drug"].title()} {r["dose"]:g} {DRUG_MAX[r["drug"]][1]} (Pharmacy)'
    else:
        act = f'{r["type"]} {r.get("dept", "Nursing")}: {r["text"]}'
    return cond, act


def build_source(p, rules):
    """Patient details + hospital rules -> ClinicalScript. Returns (source, blocked messages)."""
    L = [f"// {p['id']}: generated from clinical input and clinical logic"]
    for k in INPUT_ORDER:
        L.append(f"let {k} = {p['v'][k]:g};")
    blocked, allergies = [], (p["allergies"] or "").lower()
    for r in rules:
        if r["type"] == "Prescribe":
            if r["drug"] in allergies:
                blocked.append(f'{r["drug"].title()} was not prescribed: an allergy is recorded for {p["name"]}.')
                continue
            act = f'prescribe "{r["drug"].title()}" {r["dose"]:g} {DRUG_MAX[r["drug"]][1]};'
        else:
            act = f'{r["type"].lower()} "{r.get("dept", "Nursing")}: {safe_text(r["text"])}";'
        L.append(f"if {cond_text(r)} then {{\n    {act}\n}}")
    return "\n".join(L) + "\n", blocked


def compile_patient(p):
    src, blocked = build_source(p, S["rules"])
    r = compile_source(src, S["passes"])
    r["src"], r["blocked"] = src, blocked
    return r


def results():
    return {p["id"]: compile_patient(p) for p in S["patients"]}


def route(kind, text):
    if kind == "PRESCRIBE":
        return "Pharmacy"
    if ":" in text and text.split(":", 1)[0].strip() in DEPTS:
        return text.split(":", 1)[0].strip()
    t = text.lower()
    if "ecg" in t or "echo" in t:
        return "Cardiology"
    if re.search(r"\b(ct|mri|x-ray|xray|scan|ultrasound)\b", t):
        return "Radiology"
    if re.search(r"(panel|test|blood|troponin|culture)", t):
        return "Laboratory"
    return "Nursing"


def detail(kind, text):
    if kind != "PRESCRIBE" and ":" in text and text.split(":", 1)[0].strip() in DEPTS:
        return text.split(":", 1)[1].strip()
    return text


def build_tasks(res):
    out = []
    for p in S["patients"]:
        r = res[p["id"]]
        if not r["ok"]:
            continue
        for k, t in r["run_opt"]:
            key = f'{p["id"]}|{k}|{t}'
            out.append({"pid": p["id"], "name": p["name"], "kind": k, "dept": route(k, t),
                        "detail": detail(k, t), "key": key,
                        "released": key not in S["held"], "done": key in S["done"]})
    return out


def dept_grid(tasks):
    cells = ""
    for i, (name, (ic, _)) in enumerate(DEPTS.items()):
        mine = [t for t in tasks if t["dept"] == name and t["released"]]
        total = len(mine)
        done = sum(t["done"] for t in mine)
        pct = round(100 * done / total) if total else 0
        opn = total - done
        cells += (f'<div class="dept{" busy" if opn >= 3 else ""}" style="--d:{i * 0.06:.2f}s" role="group" '
                  f'aria-label="{name}: {opn} open of {total} tasks">'
                  f'<span class="ic" aria-hidden="true">{ic}</span><b>{name}</b>'
                  f'<span class="n">{opn}</span> open of {total}'
                  f'<div class="mini" aria-hidden="true"><i style="--w:{pct}%"></i></div></div>')
    return f'<div class="depts">{cells}</div>'


def pick_patient(key):
    ids = [p["id"] for p in S["patients"]]
    if not ids:
        msg("warn", "No patients yet. Register one in Patient Registration.")
        return None
    cur = S["sel"] if S["sel"] in ids else ids[0]
    S["sel"] = st.selectbox("Patient", ids, index=ids.index(cur), key=f"pick_{key}",
                            format_func=lambda i: f"{i} · {byid(i)['name']} · {byid(i)['complaint']}")
    return byid(S["sel"])


# ---------------------------------------------------------------- callbacks
def toggle_done(key):
    (S["done"].add if S.get("dn_" + key) else S["done"].discard)(key)


def toggle_held(key):
    (S["held"].discard if S.get("ap_" + key) else S["held"].add)(key)


def remove_patient(pid):
    S["patients"][:] = [p for p in S["patients"] if p["id"] != pid]
    for k in [k for k in S.keys() if str(k).startswith("pick_")]:
        del S[k]


def open_patient(pid):
    S["sel"] = pid
    S["page"] = PAGES[3]


def add_rule():
    typ = S["r_type"]
    text = (S.get("r_text") or "").strip()
    if typ != "Prescribe" and not text:
        S["rule_err"] = "Type a message or order name before adding the rule."
        return
    S["rule_err"] = ""
    S["rules"].append({
        "v1": S["r_v1"], "op1": S["r_op1"], "t1": float(S["r_t1"]),
        "second": bool(S.get("r_second")), "conn": S.get("r_conn", "and"),
        "v2": S.get("r_v2", "hr"), "op2": S.get("r_op2", ">"), "t2": float(S.get("r_t2", 100.0)),
        "type": typ, "text": text, "dept": S.get("r_dept", "Nursing"),
        "drug": S.get("r_drug", "paracetamol"), "dose": float(S.get("r_dose", 500.0))})
    S["r_text"] = ""


def delete_rule(i):
    if 0 <= i < len(S["rules"]):
        S["rules"].pop(i)


def reset_rules():
    S["rules"] = [dict(r) for r in DEFAULT_RULES]


def clear_rules():
    S["rules"] = []


def add_template(d):
    for r in DEPT_TEMPLATES[d]:
        if r not in S["rules"]:
            S["rules"].append(dict(r))


def set_passes():
    S["passes"] = list(S["passes_w"])


def load_sandbox():
    text = SAMPLES[S["sb_pick"]]
    S["sb_src"] = text
    S["sb_editor"] = text


# ================================================================== sidebar
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
if not S["intro_done"] and not S["calm"]:
    splash()
    st.stop()
html('<div id="main" tabindex="-1"></div>')


# ================================================================== pages
def page_cc():
    res = results()
    tasks = build_tasks(res)
    head("Command Center", "Live view of every department, patient and automated workflow in the hospital.")
    alerts = [t for t in tasks if t["kind"] == "ALERT" and t["released"]]
    ticker = "   ✦   ".join(f'{t["pid"]} · {t["dept"]}: {t["detail"]}' for t in alerts) or "No active alerts"
    html(f"""<span class="pill"><span class="dot" aria-hidden="true"></span>Workflow engine online</span>
      <span class="mut">&nbsp;Demo data</span>
      <div class="road" aria-hidden="true"><span>🚑</span><span class="back">🚑</span></div>
      <div class="ticker" aria-hidden="true"><div>⚠ {esc(ticker)}</div></div>""")
    open_n = sum(t["released"] and not t["done"] for t in tasks)
    crit = sum(p["priority"] == "Critical" for p in S["patients"])
    reds = [r["stats"]["reduction"] for r in res.values() if r["ok"]]
    kpis([("Patients", len(S["patients"]), "registered today", ""),
          ("Critical", crit, "need immediate attention", ""),
          ("Open tasks", open_n, "across all departments", ""),
          ("Steps removed", round(sum(reds) / len(reds)) if reds else 0, "average per patient workflow", "%")])
    html('<div class="card"><h3>Department workload</h3>' + dept_grid(tasks) + "</div>")
    html(f'<svg class="ecgbar" viewBox="0 0 900 60" preserveAspectRatio="none" aria-hidden="true"><path d="{ECG}"/></svg>')

    c1, c2 = st.columns(2)
    with c1:
        html('<div class="card"><h3>Triage queue</h3></div>')
        q = pd.DataFrame([(p["id"], p["name"], p["complaint"], f'{DEPTS[p["dept"]][0]} {p["dept"]}',
                           PRIO[p["priority"]],
                           sum(1 for t in tasks if t["pid"] == p["id"] and t["released"] and not t["done"]))
                          for p in S["patients"]],
                         columns=["ID", "Patient", "Complaint", "Department", "Priority", "Open tasks"])
        st.dataframe(q, hide_index=True)
    with c2:
        items = "".join(f'<li class="c"><b>⚠ {esc(t["pid"])}</b> {esc(t["dept"])}: {esc(t["detail"])}</li>'
                        for t in alerts[:6]) or "<li>No active alerts.</li>"
        html(f'<div class="card"><h3>Live alerts</h3><ul class="feed" aria-live="polite">{items}</ul></div>')

    beds = [("ICU", 18, 20), ("Emergency", 42, 50), ("Cardiology", 26, 40), ("General ward", 88, 120)]
    bars = "".join(f'<div>{n} · {a} of {b}</div><div class="bar" role="img" aria-label="{n} {round(100 * a / b)} percent">'
                   f'<span style="--w:{round(100 * a / b)}%"></span></div>' for n, a, b in beds)
    html(f'<div class="card"><h3>Bed occupancy</h3>{bars}</div>')
    speak(f"Command center. {len(S['patients'])} patients registered, {crit} critical, {open_n} open tasks across departments.")


def page_register():
    head("Patient Registration", "Enter a new patient’s details and vitals. Their hospital workflow starts as soon as they are registered.")
    hint("Fill in the form and press Register. The patient then appears in every department that has work for them.")
    with st.form("reg_form", clear_on_submit=True):
        a, b, c = st.columns(3)
        name = a.text_input("Patient name or initials")
        sex = b.selectbox("Sex", ["Female", "Male", "Other"])
        complaint = c.text_input("Main complaint")
        d, e, f = st.columns(3)
        dept = d.selectbox("Arrival department", list(DEPTS))
        prio = e.selectbox("Triage priority", PRIOS, index=2)
        allergies = f.text_input("Known allergies (or 'none')", value="none")
        st.markdown("**Vitals**")
        vals, cols = {}, st.columns(4)
        for n, k in enumerate(INPUT_ORDER):
            label, lo, hi, step, fm = FIELDS[k]
            vals[k] = cols[n % 4].number_input(label, min_value=float(lo), max_value=float(hi),
                                               value=float(DEFAULT_VITALS[k]), step=step, format=fm, key="reg_" + k)
        submitted = st.form_submit_button("✔ Register patient")
    if submitted:
        if not name.strip() or not complaint.strip():
            msg("err", "Enter the patient’s name (or initials) and the main complaint.")
        else:
            pid = f"P-{S['next_id']}"
            S["next_id"] += 1
            S["patients"].append({"id": pid, "name": name.strip(), "sex": sex, "complaint": complaint.strip(),
                                  "dept": dept, "priority": prio, "allergies": allergies.strip() or "none",
                                  "v": {k: float(x) for k, x in vals.items()}})
            S["sel"] = pid
            html(f'<div class="card okrow"><svg class="chk" viewBox="0 0 52 52" aria-hidden="true">'
                 f'<circle cx="26" cy="26" r="24"/><path d="M14 27 l8 8 l16 -17"/></svg>'
                 f'<div><b>Patient {esc(pid)} registered</b><br>{esc(name)} · {esc(complaint)} · {esc(dept)}</div></div>')
            msg("ok", f"{pid} is now in the hospital workflow. Open Patient Workflow or Departments to see their orders.")

    st.markdown(f"**Registered patients ({len(S['patients'])})**")
    for p in S["patients"]:
        c1, c2, c3 = st.columns([7, 2, 2])
        with c1:
            html(f'<div class="rule"><b>{esc(p["id"])}</b> · {esc(p["name"])} · {p["v"]["age"]:g} y · {esc(p["sex"])} · '
                 f'{esc(p["complaint"])} · {DEPTS[p["dept"]][0]} {esc(p["dept"])} · {PRIO[p["priority"]]} · '
                 f'Allergies: {esc(p["allergies"])}</div>')
        c2.button("Open", key=f"op_{p['id']}", on_click=open_patient, args=(p["id"],), help=f"Open workflow for {p['id']}")
        c3.button("🗑 Remove", key=f"rm_{p['id']}", on_click=remove_patient, args=(p["id"],), help=f"Remove {p['id']}")


def page_depts():
    res = results()
    tasks = build_tasks(res)
    head("Departments", "Each department sees its own work, generated from every patient’s compiled workflow.")
    names = list(DEPTS)
    d = st.radio("Department", names, index=names.index(S["dept"]), horizontal=True, key="dept_w",
                 format_func=lambda n: f"{DEPTS[n][0]} {n}")
    S["dept"] = d
    ic, desc = DEPTS[d]
    mine = [t for t in tasks if t["dept"] == d and t["released"]]
    total = len(mine)
    done = sum(t["done"] for t in mine)
    pct = round(100 * done / total) if total else 0
    rg = ring(pct, f"{d} completion {pct} percent")
    html(f'<div class="card dh"><span class="bigic" aria-hidden="true">{ic}</span>'
         f'<div><h3>{esc(d)}</h3><p>{esc(desc)}</p></div>{rg}</div>')
    arriving = [p for p in S["patients"] if p["dept"] == d]
    kpis([("Tasks", total, "released to this department", ""), ("Done", done, "completed", ""),
          ("Open", total - done, "still to do", ""), ("Arrivals", len(arriving), "patients arrived here", "")])

    st.markdown(f"**Task list: tick each task when it is done**")
    if not mine:
        msg("info", f"No released tasks for {d} yet. Add a rule or template below, or release orders in Protocol Studio.")
    for t in mine:
        st.checkbox(f'{t["pid"]} · {t["name"]} — {ICONS[t["kind"]]}: {t["detail"]}', value=t["done"],
                    key="dn_" + t["key"], on_change=toggle_done, args=(t["key"],))
    if arriving:
        st.markdown("**Patients who arrived at this department**")
        st.dataframe(pd.DataFrame([(p["id"], p["name"], p["complaint"], PRIO[p["priority"]]) for p in arriving],
                                  columns=["ID", "Patient", "Complaint", "Priority"]), hide_index=True)
    with st.expander(f"📑 {d} protocol templates"):
        for r in DEPT_TEMPLATES[d]:
            cond, act = rule_plain(r)
            html(f'<div class="rule">IF {esc(cond)} → THEN {esc(act)}</div>')
        st.button(f"➕ Add {d} templates to the hospital protocol", key=f"tpl_{d}", on_click=add_template, args=(d,))
    speak(f"{d} department. {total} tasks released, {done} done, {total - done} open.")


def page_patient():
    head("Patient Workflow", "One patient, from registration to released orders.")
    p = pick_patient("wf")
    if not p:
        return
    r = compile_patient(p)
    html(f'<div class="card"><h3>{esc(p["id"])} · {esc(p["name"])}</h3>'
         f'<p>{p["v"]["age"]:g} y · {esc(p["sex"])} · {esc(p["complaint"])} · arrived at {DEPTS[p["dept"]][0]} {esc(p["dept"])} '
         f'{badge(PRIO[p["priority"]], PRIO_LVL[p["priority"]])}</p><p>Allergies: {esc(p["allergies"])}</p></div>')
    html('<div class="card"><h3>Vitals</h3>' + vit_tiles(p["v"]) + "</div>")
    for b in r["blocked"]:
        msg("warn", b)
    if not r["ok"]:
        msg("warn", "The protocol has errors. Fix them in Protocol Studio.")
        for e in r["syntax_errors"] + (r["sem"]["errors"] if r["sem"] else []):
            msg("err", e)
        return
    s = r["stats"]
    mine = [t for t in build_tasks({p["id"]: r} | {q["id"]: {"ok": False} for q in S["patients"] if q["id"] != p["id"]})
            if t["pid"] == p["id"]]
    depts = sorted({t["dept"] for t in mine})
    chips = "".join(f'<span class="dchip" style="animation-delay:{i * 0.08:.2f}s">{DEPTS[d][0]} {d}</span>' for i, d in enumerate(depts))
    c1, c2 = st.columns(2)
    with c1:
        html(f"""<div class="card"><h3>Automated workflow</h3><ol class="tl">
          <li><b>08:02</b> Registered at {esc(p['dept'])}, vitals captured</li>
          <li><b>08:03</b> Protocol compiled: {s['before']} steps simplified to {s['after']}</li>
          <li><b>08:03</b> Safety and allergy checks passed</li>
          <li><b>08:04</b> Orders routed to {len(depts)} departments</li>
          <li><b>08:04</b> Staff notified. Awaiting clinician approval</li></ol>
          <p><b>Departments involved</b></p>{chips or "<p>None</p>"}</div>""")
    with c2:
        html('<div class="card"><h3>Orders by department</h3></div>')
        st.dataframe(pd.DataFrame([(ICONS[t["kind"]], t["detail"], f'{DEPTS[t["dept"]][0]} {t["dept"]}',
                                    "Held" if not t["released"] else ("Done" if t["done"] else "Released"))
                                   for t in mine], columns=["Type", "Detail", "Department", "Status"]), hide_index=True)
        st.caption("Duplicate orders were removed by the optimizer. A clinician approves every order.")
    speak(f"{p['name']}, {p['complaint']}. {len(mine)} actions across {len(depts)} departments.")


def page_studio():
    head("Protocol Studio", "Three modules: enter clinical data, set the clinical logic, tune the workflow. Then see how the compiler made it all work.")
    hint("Each module has its own input. 'How it all works' at the bottom shows the compiler steps behind your inputs.")
    p = pick_patient("studio")
    if not p:
        return
    pid = p["id"]
    chips = st.empty()

    # ---------------- Module 1
    section(1, "Clinical Input", f"Edit {p['name']}’s details and vitals. These are the values the rules work on.")
    cols = st.columns(4)
    for n, k in enumerate(INPUT_ORDER):
        label, lo, hi, step, fm = FIELDS[k]
        p["v"][k] = cols[n % 4].number_input(label, min_value=float(lo), max_value=float(hi),
                                             value=float(p["v"][k]), step=step, format=fm, key=f"mv_{pid}_{k}")
    c1, c2 = st.columns(2)
    p["allergies"] = c1.text_input("Known allergies", value=p["allergies"], key=f"al_{pid}")
    p["priority"] = c2.selectbox("Triage priority", PRIOS, index=PRIOS.index(p["priority"]), key=f"pr_{pid}")
    html('<div class="card"><h3>Input check</h3>' + vit_tiles(p["v"]) + "</div>")

    # ---------------- Module 2
    section(2, "Clinical Logic", "Build IF … THEN rules for the whole hospital. Each rule is sent to a department.")
    a, b, c = st.columns([3, 1, 2])
    a.selectbox("IF this value", list(RULE_VITALS), format_func=RULE_VITALS.get, key="r_v1")
    b.selectbox("Comparison", OPS, key="r_op1")
    c.number_input("Number", value=100.0, step=1.0, key="r_t1")
    st.checkbox("Add a second condition", key="r_second")
    if S.get("r_second"):
        d, e, f, g = st.columns([1, 3, 1, 2])
        d.selectbox("Join with", ["and", "or"], key="r_conn")
        e.selectbox("Second value", list(RULE_VITALS), format_func=RULE_VITALS.get, key="r_v2")
        f.selectbox("Second comparison", OPS, key="r_op2")
        g.number_input("Second number", value=100.0, step=1.0, key="r_t2")
    st.selectbox("THEN", ["Alert", "Order", "Prescribe"], key="r_type")
    if S["r_type"] == "Prescribe":
        h, i_ = st.columns(2)
        h.selectbox("Drug", list(DRUG_MAX), format_func=str.title, key="r_drug")
        i_.number_input(f"Dose ({DRUG_MAX[S['r_drug']][1]})", min_value=0.0, value=500.0, step=50.0, key="r_dose")
    else:
        j, k_ = st.columns(2)
        j.selectbox("Send to department", list(DEPTS), index=list(DEPTS).index("Nursing"), key="r_dept")
        k_.text_input("Alert message" if S["r_type"] == "Alert" else "Order or test name", key="r_text")
    st.button("➕ Add rule", on_click=add_rule)
    if S.get("rule_err"):
        msg("err", S["rule_err"])
    st.markdown(f"**Hospital rules ({len(S['rules'])})**")
    for i, rule in enumerate(S["rules"]):
        cond, act = rule_plain(rule)
        c1, c2 = st.columns([7, 2])
        with c1:
            html(f'<div class="rule"><b>{i + 1}.</b> IF {esc(cond)} → THEN {esc(act)}</div>')
        c2.button("🗑 Remove", key=f"del_{i}", on_click=delete_rule, args=(i,), help=f"Remove rule {i + 1}")
    x, y, _ = st.columns([2, 2, 5])
    x.button("↺ Load starter rules", on_click=reset_rules)
    y.button("✖ Clear all rules", on_click=clear_rules)

    # ---------------- compile + logic check
    r = compile_patient(p)
    for bmsg in r["blocked"]:
        msg("warn", bmsg)
    for e in r["syntax_errors"]:
        msg("err", e)
    if r["sem"]:
        for e in r["sem"]["errors"]:
            msg("err", e)
        for w in r["sem"]["warnings"]:
            msg("warn", w)
        if not r["sem"]["errors"]:
            msg("ok", "Logic check passed: types, vital ranges and dose limits are all satisfied.")
    syn = not r["syntax_errors"]
    sem = bool(r["sem"]) and not r["sem"]["errors"]
    opt_txt = f"Optimized: {r['stats']['before']} → {r['stats']['after']} steps" if r["ok"] else "Optimization"
    states = [("Syntax check", "ok" if syn else "err"),
              ("Safety check", "wait" if not syn else ("ok" if sem else "err")),
              (opt_txt, "ok" if r["ok"] else "wait"), ("Orders generated", "ok" if r["ok"] else "wait")]
    mark = {"ok": "✔", "err": "✖", "wait": "○"}
    with chips.container():
        html('<div class="stages" role="status" aria-label="Compilation stages">' + "".join(
            f'<span class="st {cl}">{mark[cl]} {esc(t)}</span>' for t, cl in states) + "</div>")

    # ---------------- Module 3
    section(3, "Workflow Optimization", "Choose how the compiler simplifies the workflow, then approve the orders to release to departments.")
    st.multiselect("Optimizations to apply", list(PASS_LABELS), default=S["passes"],
                   format_func=PASS_LABELS.get, key="passes_w", on_change=set_passes)
    released = 0
    if not r["ok"]:
        msg("warn", "Fix the errors above before the workflow can be optimized.")
    else:
        s = r["stats"]
        kpis([("Before", s["before"], "IR instructions", ""), ("After", s["after"], "IR instructions", ""),
              ("Reduction", s["reduction"], "less work", "%"), ("Passes", s["passes"], "until nothing changed", "")])
        if r["equivalent"]:
            msg("ok", "Verified: the optimized workflow gives the same clinical actions as the original (duplicates collapsed).")
        else:
            msg("err", "The optimized workflow differs from the original. This is a compiler bug.")
        st.markdown("**Clinician approval: tick the orders to release to their departments**")
        if not r["run_opt"]:
            msg("info", "No actions were produced for this patient.")
        for k, t in r["run_opt"]:
            key = f"{pid}|{k}|{t}"
            st.checkbox(f"{ICONS[k]} · {detail(k, t)}  →  {DEPTS[route(k, t)][0]} {route(k, t)}",
                        value=key not in S["held"], key="ap_" + key, on_change=toggle_held, args=(key,))
        released = sum(1 for k, t in r["run_opt"] if f"{pid}|{k}|{t}" not in S["held"])
        if r["run_opt"]:
            msg("ok", f"{released} of {len(r['run_opt'])} actions released to departments.")
            rel = [(k, t) for k, t in r["run_opt"] if f"{pid}|{k}|{t}" not in S["held"]]
            d1, d2 = st.columns(2)
            d1.download_button("⬇ Released orders (JSON)", to_orders_json(rel), f"{pid}_orders.json")
            d2.download_button("⬇ Text report", f"{pid} released actions:\n" + "\n".join(f"- {k}: {t}" for k, t in rel),
                               f"{pid}_report.txt")

    # ---------------- how it all works
    html("""<h3 style="margin-top:2rem">How it all works</h3>
      <p class="mut">The same inputs, seen through the compiler. Each module has a matching compiler phase.</p>
      <svg class="flowsvg" viewBox="0 0 640 90" role="img" aria-label="Module 1 feeds Module 2, which feeds Module 3">
      <rect x="5" y="20" width="170" height="50" rx="12"/><text x="90" y="50" text-anchor="middle">1 · Input</text>
      <path class="fl" d="M175 45 H235"/>
      <rect x="235" y="20" width="170" height="50" rx="12"/><text x="320" y="50" text-anchor="middle">2 · Logic + IR</text>
      <path class="fl" d="M405 45 H465"/>
      <rect x="465" y="20" width="170" height="50" rx="12"/><text x="550" y="50" text-anchor="middle">3 · Optimize + Code</text></svg>
      <div class="how">
      <div><small>MODULE 1 → SYNTAX ANALYSIS</small><b>Clinical input is read, tokenized and parsed</b></div>
      <div><small>MODULE 2 → INTERMEDIATE CODE</small><b>Clinical logic becomes checked three-address code</b></div>
      <div><small>MODULE 3 → CODE GENERATION</small><b>The optimized workflow becomes executable orders</b></div></div>""")
    t1, t2, t3 = st.tabs(["① Syntax analysis", "② Intermediate code generation", "③ Automated code generation"])
    with t1:
        st.markdown(f"**ClinicalScript produced for {pid}**")
        st.code(r["src"], language="text")
        if r["syntax_errors"]:
            for e in r["syntax_errors"]:
                msg("err", e)
        else:
            msg("ok", f"No syntax errors. {len(r['tokens']) - 1} tokens and {len(r['ast']['body'])} top-level statements.")
        a, b = st.columns(2)
        with a:
            st.markdown("**Tokens (lexical analysis)**")
            st.dataframe(pd.DataFrame([{"Line": t.line, "Col": t.col, "Type": t.type, "Lexeme": t.value}
                                       for t in r["tokens"] if t.type != "EOF"]), hide_index=True)
        with b:
            st.markdown("**Parse tree (syntax analysis)**")
            st.code(pretty(r["ast"]), language="text")
    with t2:
        if not r["ok"]:
            msg("warn", "Intermediate code is generated once the program passes syntax and logic checks.")
        else:
            a, b = st.columns([2, 3])
            with a:
                st.markdown("**Symbol table**")
                st.dataframe(pd.DataFrame([{"Name": k, "Type": v} for k, v in r["sem"]["symbols"].items()]), hide_index=True)
            with b:
                st.markdown("**What the optimizer changed**")
                if r["log"]:
                    st.dataframe(pd.DataFrame(r["log"], columns=["Optimization", "What changed"]), hide_index=True)
                else:
                    st.write("No optimization was applied.")
            a, b = st.columns(2)
            a.markdown(f"**Three-address code before ({len(r['ir'])} instructions)**")
            a.code(listing(r["ir"]), language="text")
            b.markdown(f"**Three-address code after ({len(r['opt'])} instructions)**")
            b.code(listing(r["opt"]), language="text")
    with t3:
        if not r["ok"]:
            msg("warn", "Code is generated once the program passes all checks.")
        else:
            a, b = st.columns(2)
            a.markdown("**ClinicalVM assembly**")
            a.code(r["asm"], language="nasm")
            b.markdown("**Generated Python**")
            b.code(r["py"], language="python")
            st.markdown("**FHIR-style orders (simplified, for teaching)**")
            st.code(to_orders_json(r["run_opt"]), language="json")
            st.write(f"The original program produced {len(r['run_raw'])} actions. The optimized program produced "
                     f"{len(r['run_opt'])} actions, {'with the same clinical result.' if r['equivalent'] else 'but the results differ.'}")
            d1, d2 = st.columns(2)
            d1.download_button("⬇ Assembly", r["asm"], "workflow.asm")
            d2.download_button("⬇ Python", r["py"], "workflow.py")

    with st.expander("🧪 Compiler sandbox: write ClinicalScript by hand (shows syntax errors)"):
        st.selectbox("Load an example", list(SAMPLES), key="sb_pick", on_change=load_sandbox)
        kw = {} if "sb_editor" in S else {"value": S["sb_src"]}
        S["sb_src"] = st.text_area("ClinicalScript", height=220, key="sb_editor", **kw)
        sr = compile_source(S["sb_src"], S["passes"])
        for e in sr["syntax_errors"]:
            msg("err", e)
        if sr["sem"]:
            for e in sr["sem"]["errors"]:
                msg("err", e)
            for w in sr["sem"]["warnings"]:
                msg("warn", w)
        if sr["ok"]:
            msg("ok", f"Compiled: {sr['stats']['before']} → {sr['stats']['after']} steps, {len(sr['run_opt'])} actions.")
            st.code(listing(sr["opt"]), language="text")

    speak(f"Protocol studio for {p['name']}. " + (" ".join(r["syntax_errors"]) if r["syntax_errors"] else "No syntax errors. ") +
          (f"The optimizer reduced {r['stats']['before']} steps to {r['stats']['after']}. {released} actions are released." if r["ok"] else ""))


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


def handle_floating_voice():
    q = (S.get("floating_voice_q") or "").strip()
    if not q:
        return
    answer = local_intent(q)
    source = "Built-in"
    if answer is None:
        answer = ask_claude(q)
        source = "AI"
        S["voice_ai_history"].append((q, answer))
        S["voice_ai_history"] = S["voice_ai_history"][-8:]
    S["voice_log"].append((q, answer, source))
    S["voice_log"] = S["voice_log"][-30:]
    S["floating_voice_speak"] = answer
    S["floating_voice_q"] = ""


@st.dialog("🎙️ ClinicFlow Voice Assistant", width="large")
def floating_voice_dialog():
    st.write("Ask a question by voice or text. The assistant is available from every page.")
    lang_name = st.selectbox(
        "Voice language", list(VOICE_LANGS), key="floating_voice_lang"
    )
    lang = VOICE_LANGS[lang_name]
    mic_html = MIC_HTML.replace(
        'input[aria-label="Voice question"]',
        'input[aria-label="Ask ClinicFlow"]'
    )
    components.html(mic_html.replace("__LANG__", lang), height=150)
    st.text_input(
        "Ask ClinicFlow",
        key="floating_voice_q",
        on_change=handle_floating_voice,
        placeholder="Speak or type your question and press Enter"
    )
    answer_to_speak = S.pop("floating_voice_speak", None)
    if answer_to_speak:
        say(answer_to_speak, lang)
    for question, answer, source in reversed(S.get("voice_log", [])[-5:]):
        st.markdown(f"**{source}:** {answer}")
        st.caption(f"You asked: {question}")


def render_floating_voice_button():
    st.markdown("""
    <style>
    div[class*="st-key-clinicflow_float_launcher"] {
        position: fixed !important; right: 24px !important; bottom: 24px !important;
        z-index: 999999 !important; width: 66px !important;
    }
    div[class*="st-key-clinicflow_float_launcher"] button {
        width: 62px !important; height: 62px !important; min-height: 62px !important;
        border-radius: 50% !important; background: #0E9AA7 !important;
        color: white !important; border: 3px solid white !important;
        box-shadow: 0 5px 20px rgba(0,0,0,.30) !important; font-size: 26px !important;
    }
    div[class*="st-key-clinicflow_float_launcher"] button:hover {
        background: #0F2A43 !important; transform: scale(1.06);
    }
    </style>
    """, unsafe_allow_html=True)
    with st.container(key="clinicflow_float_launcher"):
        if st.button("🎙️", key="open_floating_clinicflow", help="Open ClinicFlow Voice Assistant"):
            floating_voice_dialog()


def page_voice():
    head("ClinicFlow AI Voice", "Your multilingual AI assistant for hospital workflows and general knowledge.")
    hint("Tap the microphone and speak naturally. ClinicFlow can answer general questions, read demo hospital information, and speak its reply aloud.")
    lang_name = st.selectbox("Voice language", list(VOICE_LANGS), key="voice_lang_name")
    lang = VOICE_LANGS[lang_name]
    components.html(MIC_HTML.replace("__LANG__", lang), height=190)
    st.text_input("Voice question", key="voice_q", on_change=handle_voice,
                  placeholder="Speak with the microphone above, or type here and press Enter")
    to_say = S.pop("voice_speak", None)
    if to_say:
        say(to_say, lang)
    for q, a, src in reversed(S["voice_log"][-8:]):
        html(f'<div class="card"><span class="tag">{esc(src.upper())}</span><p><b>You:</b> {esc(q)}</p>'
             f'<p><b>ClinicFlow:</b> {esc(a)}</p></div>')
    if S["voice_log"]:
        speak(S["voice_log"][-1][1])      # manual 🔊 button in case the browser blocks auto-speech
        st.button("🧹 Clear conversation", on_click=clear_voice)
    st.caption("Examples: “How many critical patients?”, “Tell me about P-1042”, “Open protocol studio”, "
               "“Turn on high contrast”, “Why is the sky blue?”, “Explain hypertension in simple words.”")


PAGE_RENDERERS = {
    PAGES[0]: page_cc,
    PAGES[1]: page_register,
    PAGES[2]: page_depts,
    PAGES[3]: page_patient,
    PAGES[4]: page_studio,
    PAGES[5]: page_map,
    PAGES[6]: page_voice,
}

PAGE_RENDERERS[S["page"]]()
render_floating_voice_button()
