from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw" / "diabetes.csv"
MODEL = ROOT / "models" / "risk_model.joblib"
METRICS = ROOT / "models" / "metrics.json"
CM_PNG = ROOT / "models" / "confusion_matrix.png"

# DSL variable name -> dataset column
FEATURES = {
    "pregnancies": "Pregnancies",
    "glucose": "Glucose",
    "bp": "BloodPressure",
    "skin": "SkinThickness",
    "insulin": "Insulin",
    "bmi": "BMI",
    "dpf": "DiabetesPedigreeFunction",
    "age": "Age",
}
TARGET = "Outcome"
ZERO_AS_MISSING = ["Glucose", "BloodPressure", "SkinThickness", "Insulin", "BMI"]


def clean(df):
    """In this dataset a 0 in these columns means 'not measured'."""
    df = df.copy()
    cols = [c for c in ZERO_AS_MISSING if c in df.columns]
    df[cols] = df[cols].replace(0, np.nan)
    return df
