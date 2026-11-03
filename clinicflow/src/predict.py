
from pathlib import Path
import joblib
import pandas as pd

from src.config import MODEL_PATH

_model = None


def load_model():
    global _model

    if _model is not None:
        return _model

    if not Path(MODEL_PATH).exists():
        raise FileNotFoundError(
            "Diabetes model not found. Run the training script "
            "and generate models/risk_model.joblib."
        )

    try:
        _model = joblib.load(MODEL_PATH)
        return _model

    except Exception as exc:
        raise RuntimeError(
            "Unable to load the diabetes model. "
            "Retrain it using the same NumPy and scikit-learn "
            "versions specified in requirements.txt. "
            f"Technical detail: {type(exc).__name__}: {exc}"
        ) from exc


def predict_risk(patient):
    model = load_model()

    columns = [
        "Pregnancies",
        "Glucose",
        "BloodPressure",
        "SkinThickness",
        "Insulin",
        "BMI",
        "DiabetesPedigreeFunction",
        "Age"
    ]

    row = pd.DataFrame([[
        patient["pregnancies"],
        patient["glucose"],
        patient["bp"],
        patient["skin"],
        patient["insulin"],
        patient["bmi"],
        patient["dpf"],
        patient["age"]
    ]], columns=columns)

    probability = model.predict_proba(row)[0, 1]

    return float(probability)
