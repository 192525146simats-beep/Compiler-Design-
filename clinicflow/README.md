# ClinicFlow: Next-Gen Clinical Workflow Automation Using Compiler Technology

ML risk model (Pima Indians Diabetes) + a mini compiler for clinical rules, shown in Streamlit.

## Modules
1. Clinical Input & Syntax Analysis: lexer, recursive-descent parser, AST
2. Clinical Logic & Intermediate Code Generation: semantic checks, three-address code
3. Workflow Optimization & Automated Code Generation: constant folding, dead-rule
   elimination, duplicate removal, priority scheduling, Python code generation

## Run
pip install -r requirements.txt
python -m src.train
streamlit run app.py
