import numpy as np
import pytest
from pathlib import Path

import train
from train import ModelResult, _candidates, RANDOM_STATE, MODELS_DIR, REPORTS_DIR

from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier
from xgboost import XGBClassifier
from sklearn.pipeline import Pipeline


def test_random_state_value():
    assert RANDOM_STATE == 42


def test_models_dir_and_reports_dir_are_paths_and_exist():
    assert isinstance(MODELS_DIR, Path)
    assert isinstance(REPORTS_DIR, Path)
    assert MODELS_DIR.exists() and MODELS_DIR.is_dir()
    assert REPORTS_DIR.exists() and REPORTS_DIR.is_dir()


def test_candidates_returns_expected_keys():
    cands = _candidates()
    assert set(cands.keys()) == {"LogisticRegression", "RandomForest", "XGBoost"}


def test_candidates_logistic_regression_params():
    cands = _candidates()
    lr = cands["LogisticRegression"]
    assert isinstance(lr, LogisticRegression)
    assert lr.max_iter == 2000
    assert lr.class_weight == "balanced"
    assert lr.random_state == RANDOM_STATE


def test_candidates_random_forest_params():
    cands = _candidates()
    rf = cands["RandomForest"]
    assert isinstance(rf, RandomForestClassifier)
    assert rf.n_estimators == 400
    assert rf.max_depth is None
    assert rf.min_samples_leaf == 2
    assert rf.class_weight == "balanced"
    assert rf.n_jobs == -1
    assert rf.random_state == RANDOM_STATE


def test_candidates_xgboost_params():
    cands = _candidates()
    xgb = cands["XGBoost"]
    assert isinstance(xgb, XGBClassifier)
    assert xgb.n_estimators == 400
    assert xgb.max_depth == 4
    assert xgb.learning_rate == pytest.approx(0.05, rel=1e-6)
    assert xgb.subsample == pytest.approx(0.9, rel=1e-6)
    assert xgb.colsample_bytree == pytest.approx(0.9, rel=1e-6)
    assert xgb.scale_pos_weight == pytest.approx(5.0, rel=1e-6)
    assert xgb.objective == "binary:logistic"
    assert xgb.eval_metric == "logloss"
    assert xgb.random_state == RANDOM_STATE
    assert xgb.n_jobs == -1
    assert xgb.tree_method == "hist"


def _make_model_result(name="TestModel", confusion=None, cr_str="report"):
    if confusion is None:
        confusion = np.array([[10, 2], [3, 5]])
    pipe = Pipeline(steps=[("dummy", LogisticRegression())])
    return ModelResult(
        name=name,
        pipeline=pipe,
        roc_auc=0.85,
        pr_auc=0.65,
        f1=0.55,
        precision=0.60,
        recall=0.50,
        brier=0.12,
        cv_roc_auc_mean=0.80,
        cv_roc_auc_std=0.05,
        confusion=confusion,
        classification_report_str=cr_str,
    )


def test_model_result_to_dict_values():
    confusion = np.array([[10, 2], [3, 5]])
    result = _make_model_result(name="MyModel", confusion=confusion)
    d = result.to_dict()

    assert d["name"] == "MyModel"
    assert d["roc_auc"] == pytest.approx(0.85, rel=1e-6)
    assert d["pr_auc"] == pytest.approx(0.65, rel=1e-6)
    assert d["f1"] == pytest.approx(0.55, rel=1e-6)
    assert d["precision"] == pytest.approx(0.60, rel=1e-6)
    assert d["recall"] == pytest.approx(0.50, rel=1e-6)
    assert d["brier"] == pytest.approx(0.12, rel=1e-6)
    assert d["cv_roc_auc_mean"] == pytest.approx(0.80, rel=1e-6)
    assert d["cv_roc_auc_std"] == pytest.approx(0.05, rel=1e-6)
    assert d["confusion"] == [[10, 2], [3, 5]]


def test_model_result_to_dict_excludes_pipeline_and_report():
    result = _make_model_result()
    d = result.to_dict()
    assert "pipeline" not in d
    assert "classification_report_str" not in d


def test_model_result_to_dict_keys():
    result = _make_model_result()
    d = result.to_dict()
    expected_keys = {
        "name", "roc_auc", "pr_auc", "f1", "precision", "recall",
        "brier", "cv_roc_auc_mean", "cv_roc_auc_std", "confusion",
    }
    assert set(d.keys()) == expected_keys


def test_model_result_confusion_tolist_with_zero_matrix():
    confusion = np.zeros((2, 2), dtype=int)
    result = _make_model_result(confusion=confusion)
    d = result.to_dict()
    assert d["confusion"] == [[0, 0], [0, 0]]
