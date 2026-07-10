"""Tests for src/train.py — testing evaluate(), _candidates(), ModelResult,
and module-level constants without invoking the full run() pipeline (which
requires external data files)."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from xgboost import XGBClassifier

from src.train import (
    MODELS_DIR,
    RANDOM_STATE,
    REPORTS_DIR,
    ModelResult,
    _candidates,
    evaluate,
)


# --------------------------------------------------------------------------
# Module-level constants
# --------------------------------------------------------------------------

def test_random_state_value():
    assert RANDOM_STATE == 42


def test_models_dir_points_to_models_folder():
    assert MODELS_DIR.name == "models"
    assert MODELS_DIR.exists()
    assert MODELS_DIR.is_dir()


def test_reports_dir_points_to_reports_folder():
    assert REPORTS_DIR.name == "reports"
    assert REPORTS_DIR.exists()
    assert REPORTS_DIR.is_dir()


def test_models_and_reports_dirs_are_siblings():
    assert MODELS_DIR.parent == REPORTS_DIR.parent


# --------------------------------------------------------------------------
# _candidates()
# --------------------------------------------------------------------------

def test_candidates_returns_expected_keys():
    candidates = _candidates()
    assert set(candidates.keys()) == {"LogisticRegression", "RandomForest", "XGBoost"}


def test_candidates_logistic_regression_config():
    lr = _candidates()["LogisticRegression"]
    assert isinstance(lr, LogisticRegression)
    assert lr.max_iter == 2000
    assert lr.class_weight == "balanced"
    assert lr.random_state == RANDOM_STATE


def test_candidates_random_forest_config():
    rf = _candidates()["RandomForest"]
    assert isinstance(rf, RandomForestClassifier)
    assert rf.n_estimators == 400
    assert rf.max_depth is None
    assert rf.min_samples_leaf == 2
    assert rf.class_weight == "balanced"
    assert rf.random_state == RANDOM_STATE
    assert rf.n_jobs == -1


def test_candidates_xgboost_config():
    xgb = _candidates()["XGBoost"]
    assert isinstance(xgb, XGBClassifier)
    assert xgb.get_params()["n_estimators"] == 400
    assert xgb.get_params()["max_depth"] == 4
    assert xgb.get_params()["learning_rate"] == pytest.approx(0.05, rel=1e-6)
    assert xgb.get_params()["subsample"] == pytest.approx(0.9, rel=1e-6)
    assert xgb.get_params()["colsample_bytree"] == pytest.approx(0.9, rel=1e-6)
    assert xgb.get_params()["scale_pos_weight"] == pytest.approx(5.0, rel=1e-6)
    assert xgb.get_params()["objective"] == "binary:logistic"
    assert xgb.get_params()["eval_metric"] == "logloss"
    assert xgb.get_params()["random_state"] == RANDOM_STATE
    assert xgb.get_params()["tree_method"] == "hist"


def test_candidates_returns_fresh_instances_each_call():
    c1 = _candidates()
    c2 = _candidates()
    # Different object identities (fresh estimators each call)
    assert c1["LogisticRegression"] is not c2["LogisticRegression"]
    assert c1["RandomForest"] is not c2["RandomForest"]
    assert c1["XGBoost"] is not c2["XGBoost"]


# --------------------------------------------------------------------------
# ModelResult.to_dict()
# --------------------------------------------------------------------------

def test_model_result_to_dict_values():
    confusion = np.array([[10, 2], [3, 15]])
    result = ModelResult(
        name="Test",
        pipeline=None,
        roc_auc=0.85,
        pr_auc=0.75,
        f1=0.8,
        precision=0.78,
        recall=0.82,
        brier=0.12,
        cv_roc_auc_mean=0.83,
        cv_roc_auc_std=0.05,
        confusion=confusion,
        classification_report_str="report text",
    )
    d = result.to_dict()
    assert d["name"] == "Test"
    assert d["roc_auc"] == pytest.approx(0.85, rel=1e-6)
    assert d["pr_auc"] == pytest.approx(0.75, rel=1e-6)
    assert d["f1"] == pytest.approx(0.8, rel=1e-6)
    assert d["precision"] == pytest.approx(0.78, rel=1e-6)
    assert d["recall"] == pytest.approx(0.82, rel=1e-6)
    assert d["brier"] == pytest.approx(0.12, rel=1e-6)
    assert d["cv_roc_auc_mean"] == pytest.approx(0.83, rel=1e-6)
    assert d["cv_roc_auc_std"] == pytest.approx(0.05, rel=1e-6)
    assert d["confusion"] == [[10, 2], [3, 15]]
    # classification_report_str and pipeline are intentionally excluded
    assert "classification_report_str" not in d
    assert "pipeline" not in d


def test_model_result_to_dict_returns_confusion_as_plain_list_not_ndarray():
    confusion = np.array([[1, 0], [0, 1]])
    result = ModelResult(
        name="X",
        pipeline=None,
        roc_auc=0.5,
        pr_auc=0.5,
        f1=0.5,
        precision=0.5,
        recall=0.5,
        brier=0.5,
        cv_roc_auc_mean=0.5,
        cv_roc_auc_std=0.0,
        confusion=confusion,
        classification_report_str="",
    )
    d = result.to_dict()
    assert isinstance(d["confusion"], list)
    assert not isinstance(d["confusion"], np.ndarray)


# --------------------------------------------------------------------------
# evaluate()
# --------------------------------------------------------------------------

def _make_separable_data():
    """Build a perfectly linearly separable synthetic binary dataset."""
    neg_train = np.random.RandomState(1).normal(loc=-5, scale=0.3, size=25)
    pos_train = np.random.RandomState(2).normal(loc=5, scale=0.3, size=25)
    neg_test = np.random.RandomState(3).normal(loc=-5, scale=0.3, size=10)
    pos_test = np.random.RandomState(4).normal(loc=5, scale=0.3, size=10)

    X_train = pd.DataFrame({"feature": np.concatenate([neg_train, pos_train])})
    y_train = pd.Series([0] * 25 + [1] * 25)
    X_test = pd.DataFrame({"feature": np.concatenate([neg_test, pos_test])})
    y_test = pd.Series([0] * 10 + [1] * 10)
    return X_train, X_test, y_train, y_test


def test_evaluate_returns_model_result_with_expected_name():
    X_train, X_test, y_train, y_test = _make_separable_data()
    pipe = Pipeline(steps=[("model", LogisticRegression())])
    result = evaluate("MyModel", pipe, X_train, X_test, y_train, y_test)
    assert isinstance(result, ModelResult)
    assert result.name == "MyModel"


def test_evaluate_perfect_separation_metrics():
    X_train, X_test, y_train, y_test = _make_separable_data()
    pipe = Pipeline(steps=[("model", LogisticRegression())])
    result = evaluate("MyModel", pipe, X_train, X_test, y_train, y_test)

    # Perfectly separable data -> perfect ranking metrics.
    assert result.roc_auc == pytest.approx(1.0, abs=1e-9)
    assert result.pr_auc == pytest.approx(1.0, abs=1e-9)
    assert result.f1 == pytest.approx(1.0, abs=1e-9)
    assert result.precision == pytest.approx(1.0, abs=1e-9)
    assert result.recall == pytest.approx(1.0, abs=1e-9)


def test_evaluate_confusion_matrix_perfectly_diagonal():
    X_train, X_test, y_train, y_test = _make_separable_data()
    pipe = Pipeline(steps=[("model", LogisticRegression())])
    result = evaluate("MyModel", pipe, X_train, X_test, y_train, y_test)

    assert result.confusion.shape == (2, 2)
    assert result.confusion.sum() == len(y_test)
    assert result.confusion.tolist() == [[10, 0], [0, 10]]


def test_evaluate_brier_low_for_separable_data():
    X_train, X_test, y_train, y_test = _make_separable_data()
    pipe = Pipeline(steps=[("model", LogisticRegression())])
    result = evaluate("MyModel", pipe, X_train, X_test, y_train, y_test)
    # Well separated classes should produce a low Brier score.
    assert 0.0 <= result.brier < 0.1


def test_evaluate_cv_roc_auc_within_bounds():
    X_train, X_test, y_train, y_test = _make_separable_data()
    pipe = Pipeline(steps=[("model", LogisticRegression())])
    result = evaluate("MyModel", pipe, X_train, X_test, y_train, y_test)

    assert 0.0 <= result.cv_roc_auc_mean <= 1.0
    assert result.cv_roc_auc_std >= 0.0
    # Data is well separated -> expect high mean CV AUC.
    assert result.cv_roc_auc_mean >= 0.8


def test_evaluate_classification_report_is_nonempty_string():
    X_train, X_test, y_train, y_test = _make_separable_data()
    pipe = Pipeline(steps=[("model", LogisticRegression())])
    result = evaluate("MyModel", pipe, X_train, X_test, y_train, y_test)
    assert isinstance(result.classification_report_str, str)
    assert len(result.classification_report_str) > 0


def test_evaluate_pipeline_is_fitted_in_place():
    X_train, X_test, y_train, y_test = _make_separable_data()
    pipe = Pipeline(steps=[("model", LogisticRegression())])
    result = evaluate("MyModel", pipe, X_train, X_test, y_train, y_test)
    # The same pipeline object passed in should now be fitted and usable.
    assert result.pipeline is pipe
    proba = result.pipeline.predict_proba(X_test)[:, 1]
    assert proba.shape == (len(y_test),)
    assert np.all((proba >= 0.0) & (proba <= 1.0))
