# ClinicFlow: Next-Gen Clinical Workflow Automation Using Compiler Technology

A machine-learning risk model (Pima Indians Diabetes dataset) plus a mini compiler for
clinical rules, delivered as a Streamlit app.

## Modules
1. **Clinical Input & Syntax Analysis**: lexer, recursive-descent parser, AST, line-level syntax errors
2. **Clinical Logic & Intermediate Code Generation**: semantic checks, three-address code
3. **Workflow Optimization & Automated Code Generation**: constant folding, dead-rule elimination,
   duplicate removal, priority scheduling, Python code generation

## Run locally
    pip install -r requirements.txt
    streamlit run app.py

On first launch the app trains the model itself (it downloads the dataset automatically)
and saves `models/risk_model.joblib`, `models/metrics.json`, `models/confusion_matrix.png`.
Commit those three files so later launches start instantly.

If you are offline: download `diabetes.csv` from Kaggle
(uciml/pima-indians-diabetes-database), then use **Model Performance > Train on uploaded CSV**.

## Structure
    app.py                  Streamlit UI (8 pages)
    src/ui.py               styling + animated ECG hero
    src/data.py             dataset loader with fallbacks
    src/train.py            trains 3 models, keeps the best
    src/predict.py          risk prediction (+ baseline fallback)
    src/compiler/           module1_syntax, module2_ir, module3_optimize
