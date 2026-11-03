import joblib
import pandas as pd
from .config import FEATURES, MODEL, clean

_model = None


def load_model():
    global _model
    if _model is None:
        if not MODEL.exists():          # auto-train on first run (e.g. Streamlit Cloud)
            from .train import main
            main()
        _model = joblib.load(MODEL)
    return _model


def predict_risk(inputs: dict) -> float:
    """inputs uses DSL names (glucose, bmi, ...). Returns probability 0..1."""
    row = pd.DataFrame([{col: float(inputs[k]) for k, col in FEATURES.items()}])
    return float(load_model().predict_proba(clean(row))[0, 1])
