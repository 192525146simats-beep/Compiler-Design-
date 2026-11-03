import json
import joblib
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from sklearn.ensemble import GradientBoostingClassifier, RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (ConfusionMatrixDisplay, accuracy_score,
                             classification_report, roc_auc_score)
from sklearn.model_selection import cross_val_score, train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from .config import CM_PNG, FEATURES, METRICS, MODEL, RAW, TARGET, clean


def load_data():
    RAW.parent.mkdir(parents=True, exist_ok=True)
    if RAW.exists():
        return pd.read_csv(RAW)
    from sklearn.datasets import fetch_openml
    df = fetch_openml("diabetes", version=1, as_frame=True).frame
    df = df.rename(columns={
        "preg": "Pregnancies", "plas": "Glucose", "pres": "BloodPressure",
        "skin": "SkinThickness", "insu": "Insulin", "mass": "BMI",
        "pedi": "DiabetesPedigreeFunction", "age": "Age", "class": TARGET})
    df[TARGET] = (df[TARGET] == "tested_positive").astype(int)
    df.to_csv(RAW, index=False)
    return df


def make_pipeline(clf):
    return Pipeline([("impute", SimpleImputer(strategy="median")),
                     ("scale", StandardScaler()),
                     ("clf", clf)])


def main():
    df = clean(load_data())
    X, y = df[list(FEATURES.values())], df[TARGET]
    X_tr, X_te, y_tr, y_te = train_test_split(
        X, y, test_size=0.2, stratify=y, random_state=42)

    candidates = {
        "LogisticRegression": LogisticRegression(max_iter=1000),
        "RandomForest": RandomForestClassifier(n_estimators=300, random_state=42),
        "GradientBoosting": GradientBoostingClassifier(random_state=42),
    }
    cv = {}
    for name, clf in candidates.items():
        cv[name] = cross_val_score(make_pipeline(clf), X_tr, y_tr,
                                   cv=5, scoring="roc_auc").mean()
        print(f"{name:20s} CV ROC-AUC = {cv[name]:.3f}")

    best = max(cv, key=cv.get)
    model = make_pipeline(candidates[best]).fit(X_tr, y_tr)
    proba = model.predict_proba(X_te)[:, 1]
    pred = (proba >= 0.5).astype(int)

    metrics = {
        "best_model": best,
        "cv_roc_auc": {k: round(v, 4) for k, v in cv.items()},
        "test_accuracy": round(accuracy_score(y_te, pred), 4),
        "test_roc_auc": round(roc_auc_score(y_te, proba), 4),
        "report": classification_report(y_te, pred, output_dict=True),
        "train_rows": len(X_tr), "test_rows": len(X_te),
    }
    MODEL.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, MODEL)
    METRICS.write_text(json.dumps(metrics, indent=2))
    ConfusionMatrixDisplay.from_predictions(y_te, pred)
    plt.title(f"{best} - confusion matrix")
    plt.savefig(CM_PNG, bbox_inches="tight")
    print(f"\nBest: {best} | accuracy={metrics['test_accuracy']} "
          f"| ROC-AUC={metrics['test_roc_auc']}")


if __name__ == "__main__":
    main()
