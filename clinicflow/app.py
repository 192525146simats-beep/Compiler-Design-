import json
import pandas as pd
import streamlit as st

from src.config import CM_PNG, METRICS
from src.predict import predict_risk
from src.compiler import run_pipeline
from src.compiler.module1_syntax import ast_to_text
from src.compiler.module3_optimize import execute

st.set_page_config(page_title="ClinicFlow", page_icon="🩺", layout="wide")

DEFAULT_RULES = '''# `risk` is the ML-predicted diabetes probability (0 to 1)
if risk > 0.7 then alert "High diabetes risk - refer to physician"
if risk > 0.4 and age > 40 then alert "Moderate risk - schedule follow-up"
if glucose > 100 + 25 then order FastingGlucoseTest
if glucose > 100 + 25 then order FastingGlucoseTest
if glucose > 140 and bmi > 30 then order HbA1c
if bmi >= 30 then prescribe LifestyleCounselling
if age > 45 then order AnnualScreening
if 2 > 3 then alert "This rule can never fire"
'''

# ---------------- Sidebar: patient data ----------------
with st.sidebar:
    st.header("Patient data")
    p = {
        "pregnancies": st.number_input("Pregnancies", 0, 20, 2),
        "glucose": st.slider("Glucose (mg/dL)", 40, 250, 148),
        "bp": st.slider("Blood pressure (mm Hg)", 30, 140, 72),
        "skin": st.slider("Skin thickness (mm)", 0, 100, 35),
        "insulin": st.slider("Insulin (µU/mL), 0 = not measured", 0, 850, 0),
        "bmi": st.slider("BMI", 10.0, 70.0, 33.6),
        "dpf": st.slider("Diabetes pedigree function", 0.05, 2.5, 0.627),
        "age": st.slider("Age", 18, 90, 50),
    }

risk = predict_risk(p)
env = {**p, "risk": round(risk, 3)}

st.title("🩺 ClinicFlow")
st.caption("Next-Gen Clinical Workflow Automation Using Compiler Technology")

rules = st.text_area("Clinical rules (editable)", DEFAULT_RULES, height=250)
res = run_pipeline(rules, set(env))


def gate(n):
    """Shows errors for module n; returns True if module n can display results."""
    f = res["failed_at"]
    if f == n:
        for e in res["errors"]:
            st.error(e)
        return False
    if f and f < n:
        st.warning(f"Fix the errors in Module {f} first.")
        return False
    return True


t_out, t1, t2, t3, t_ml = st.tabs(
    ["Patient workflow", "1 · Syntax analysis", "2 · Intermediate code",
     "3 · Optimization & codegen", "ML model"])

with t_out:
    c1, c2 = st.columns([1, 2])
    c1.metric("Predicted diabetes risk", f"{risk:.0%}")
    c1.progress(min(risk, 1.0))
    with c2:
        if res["failed_at"]:
            st.error("Rules have errors. See the module tabs.")
        else:
            fired = execute(res["opt_prog"], env)
            st.subheader("Generated clinical workflow")
            for kind, arg in fired:
                {"alert": st.error, "order": st.info, "prescribe": st.success}[kind](
                    f"**{kind.upper()}**: {arg}")
            if not fired:
                st.write("No actions triggered.")

with t1:
    if gate(1):
        st.success(f"Syntax valid: {len(res['tokens'])} tokens, {len(res['ast'])} statements")
        st.subheader("Token stream")
        st.dataframe(pd.DataFrame([vars(t) for t in res["tokens"]]),
                     use_container_width=True, height=260)
        st.subheader("Abstract syntax tree")
        st.code(ast_to_text(res["ast"]), language="text")
    elif res["tokens"]:
        st.dataframe(pd.DataFrame([vars(t) for t in res["tokens"]]), height=200)

with t2:
    if gate(2):
        for w in res["warnings"]:
            st.warning(w)
        st.success("Semantics valid")
        st.subheader("Three-address code (before optimization)")
        st.code("\n".join(res["tac"]), language="text")

with t3:
    if gate(3):
        a, b = len(res["tac"]), len(res["tac_opt"])
        m1, m2, m3 = st.columns(3)
        m1.metric("IR instructions before", a)
        m2.metric("After optimization", b)
        m3.metric("Reduction", f"{round((a - b) / a * 100) if a else 0}%")
        st.subheader("Optimization passes")
        for line in res["log"]:
            st.write("• " + line)
        st.subheader("Optimized intermediate code")
        st.code("\n".join(res["tac_opt"]), language="text")
        st.subheader("Generated Python workflow")
        st.code(res["python"], language="python")
        st.download_button("Download generated code", res["python"], "workflow.py")

with t_ml:
    if METRICS.exists():
        m = json.loads(METRICS.read_text())
        st.write(f"**Dataset:** Pima Indians Diabetes ({m['train_rows']} train / {m['test_rows']} test rows)")
        st.write(f"**Selected model:** {m['best_model']}")
        c1, c2 = st.columns(2)
        c1.metric("Test accuracy", m["test_accuracy"])
        c2.metric("Test ROC-AUC", m["test_roc_auc"])
        st.write("Cross-validation ROC-AUC per candidate:")
        st.json(m["cv_roc_auc"])
        if CM_PNG.exists():
            st.image(str(CM_PNG), width=380)
    st.caption("Educational prototype. Not for real clinical decisions.")
