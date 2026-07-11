import json

import numpy as np
import pandas as pd
import pytest
from sklearn.metrics import f1_score as sklearn_f1_score

import train


class FixedProbabilityPipeline:
    def __init__(self, probabilities):
        self.probabilities = np.asarray(probabilities)

    def fit(self, X, y):
        return self

    def predict_proba(self, X):
        return np.column_stack([1.0 - self.probabilities, self.probabilities])


def test_evaluate_explicitly_requests_five_stratified_cv_folds(monkeypatch):
    captured = {}

    class RecordingStratifiedKFold:
        def __init__(self, *args, **kwargs):
            captured["args"] = args
            captured["kwargs"] = kwargs

    monkeypatch.setattr(train, "StratifiedKFold", RecordingStratifiedKFold)
    monkeypatch.setattr(
        train,
        "cross_val_score",
        lambda *args, **kwargs: np.array([0.6, 0.7, 0.8, 0.9, 1.0]),
    )

    X_train = pd.DataFrame({"feature": range(10)})
    y_train = pd.Series([0, 1] * 5)
    X_test = pd.DataFrame({"feature": range(4)})
    y_test = pd.Series([0, 1, 0, 1])

    result = train.evaluate(
        "fixed",
        FixedProbabilityPipeline([0.1, 0.9, 0.2, 0.8]),
        X_train,
        X_test,
        y_train,
        y_test,
    )

    assert captured["args"] == ()
    assert captured["kwargs"] == {
        "n_splits": 5,
        "shuffle": True,
        "random_state": train.RANDOM_STATE,
    }
    assert result.cv_roc_auc_mean == pytest.approx(0.8, rel=1e-6)


def test_evaluate_uses_integer_labels_for_half_probability_threshold(monkeypatch):
    monkeypatch.setattr(
        train,
        "cross_val_score",
        lambda *args, **kwargs: np.array([0.5, 0.5, 0.5, 0.5, 0.5]),
    )

    expected_predictions = np.array([1, 0, 1, 0], dtype=int)
    seen = {}

    def checking_f1_score(y_true, y_pred):
        observed = np.asarray(y_pred)
        seen["predictions"] = observed.copy()
        assert observed.dtype == np.dtype(int)
        assert np.array_equal(observed, expected_predictions)
        return sklearn_f1_score(y_true, y_pred)

    monkeypatch.setattr(train, "f1_score", checking_f1_score)

    X_train = pd.DataFrame({"feature": range(10)})
    y_train = pd.Series([0, 1] * 5)
    X_test = pd.DataFrame({"feature": range(4)})
    y_test = pd.Series([1, 0, 1, 0])

    result = train.evaluate(
        "fixed",
        FixedProbabilityPipeline([0.5, 0.49, 0.8, 0.1]),
        X_train,
        X_test,
        y_train,
        y_test,
    )

    assert np.array_equal(seen["predictions"], expected_predictions)
    assert result.f1 == pytest.approx(1.0, rel=1e-6)


def test_run_writes_metrics_to_lowercase_metrics_json(monkeypatch, tmp_path):
    X = pd.DataFrame({"feature": range(10)})
    y = pd.Series([0, 1] * 5)

    monkeypatch.setattr(train, "MODELS_DIR", tmp_path / "models")
    monkeypatch.setattr(train, "REPORTS_DIR", tmp_path / "reports")
    train.MODELS_DIR.mkdir()
    train.REPORTS_DIR.mkdir()

    monkeypatch.setattr(train, "load_and_prepare", lambda: (X, y, None))
    monkeypatch.setattr(train, "_candidates", lambda: {"OnlyModel": "placeholder"})
    monkeypatch.setattr(train, "build_preprocessor", lambda X_train: "passthrough")

    def fake_evaluate(name, pipe, X_train, X_test, y_train, y_test):
        return train.ModelResult(
            name=name,
            pipeline=pipe,
            roc_auc=0.75,
            pr_auc=0.5,
            f1=0.4,
            precision=0.5,
            recall=0.3333333333333333,
            brier=0.2,
            cv_roc_auc_mean=0.7,
            cv_roc_auc_std=0.1,
            confusion=np.array([[1, 0], [1, 0]]),
            classification_report_str="report",
        )

    monkeypatch.setattr(train, "evaluate", fake_evaluate)

    results = train.run()

    metrics_path = train.REPORTS_DIR / "metrics.json"
    assert metrics_path.exists()
    with metrics_path.open() as fh:
        metrics = json.load(fh)

    assert set(results) == {"OnlyModel"}
    assert metrics["OnlyModel"]["name"] == "OnlyModel"
    assert metrics["OnlyModel"]["roc_auc"] == pytest.approx(0.75, rel=1e-6)
    assert metrics["OnlyModel"]["confusion"] == [[1, 0], [1, 0]]
