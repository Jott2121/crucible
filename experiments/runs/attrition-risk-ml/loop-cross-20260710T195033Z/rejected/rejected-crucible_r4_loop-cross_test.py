import json

import pandas as pd

import train


class _FakeResult:
    def __init__(self, name):
        self.name = name
        self.pipeline = "trained-pipeline"
        self.roc_auc = 1

    def to_dict(self):
        return {"name": self.name, "marker": "held-out metrics"}


def test_run_writes_metrics_to_lowercase_metrics_json(monkeypatch, tmp_path):
    models_dir = tmp_path / "models"
    reports_dir = tmp_path / "reports"
    models_dir.mkdir()
    reports_dir.mkdir()

    X = pd.DataFrame({"feature": range(10)})
    y = pd.Series([0, 0, 0, 0, 0, 1, 1, 1, 1, 1])

    monkeypatch.setattr(train, "MODELS_DIR", models_dir)
    monkeypatch.setattr(train, "REPORTS_DIR", reports_dir)
    monkeypatch.setattr(train, "load_and_prepare", lambda: (X, y, None))
    monkeypatch.setattr(train, "_candidates", lambda: {"winner": object()})
    monkeypatch.setattr(train, "build_preprocessor", lambda X_train: "preprocessor")
    monkeypatch.setattr(train, "Pipeline", lambda steps: {"steps": steps})
    monkeypatch.setattr(
        train,
        "evaluate",
        lambda name, pipe, X_train, X_test, y_train, y_test: _FakeResult(name),
    )
    monkeypatch.setattr(train.joblib, "dump", lambda *args, **kwargs: None)

    train.run()

    metrics_path = reports_dir / "metrics.json"
    assert metrics_path.is_file()
    assert not (reports_dir / "METRICS.JSON").exists()

    with metrics_path.open() as fh:
        saved_metrics = json.load(fh)

    assert saved_metrics["winner"]["name"] == "winner"
    assert saved_metrics["winner"]["marker"] == "held-out metrics"
