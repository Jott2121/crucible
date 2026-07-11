"""Tests for src/train.py"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from sklearn.datasets import make_classification
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split
from xgboost import XGBClassifier

from src.train import (
    MODELS_DIR,
    RANDOM_STATE,
    REPORTS_DIR,
    ModelResult,
    _candidates,
    evaluate,
)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

def test_random_state_value():
    assert RANDOM_STATE == 42


def test_models_dir_and_reports_dir_exist():
    assert MODELS_DIR.exists()
    assert MODELS_DIR.is_dir()
    assert REPORTS_DIR.exists()
    assert REPORTS_DIR.is_dir()


# ---------------------------------------------------------------------------
# _candidates()
# ---------------------------------------------------------------------------

def test_candidates_keys():
    cands = _candidates()
    assert set(cands.keys()) == {"LogisticRegression", "RandomForest", "XGBoost"}


def test_candidates_logreg_params():
    lr = _candidates()["LogisticRegression"]
    assert isinstance(lr, LogisticRegression)
    assert lr.max_iter == 2000
    assert lr.class_weight == "balanced"
    assert lr.random_state == 42


def test_candidates_rf_params():
    rf = _candidates()["RandomForest"]
    assert isinstance(rf, RandomForestClassifier)
    assert rf.n_estimators == 400
    assert rf.max_depth is None
    assert rf.min_samples_leaf == 2
    assert rf.class_weight == "balanced"
    assert rf.n_jobs == -1
    assert rf.random_state == 42


def test_candidates_xgb_params():
    xgb = _candidates()["XGBoost"]
    assert isinstance(xgb, XGBClassifier)
    assert xgb.n_estimators == 400
    assert xgb.max_depth == 4
    assert xgb.learning_rate == pytest.approx(0.05)
    assert xgb.subsample == pytest.approx(0.9)
    assert xgb.colsample_bytree == pytest.approx(0.9)
    assert xgb.scale_pos_weight == pytest.approx(5.0)
    assert xgb.objective == "binary:logistic"
    assert xgb.random_state == 42


# ---------------------------------------------------------------------------
# ModelResult
# ---------------------------------------------------------------------------

def test_model_result_to_dict_values():
    confusion = np.array([[10, 2], [3, 15]])
    dummy_pipe = LogisticRegression()
    result = ModelResult(
        name="TestModel",
        pipeline=dummy_pipe,
        roc_auc=0.85,
        pr_auc=0.65,
        f1=0.7,
        precision=0.75,
        recall=0.6,
        brier=0.15,
        cv_roc_auc_mean=0.8,
        cv_roc_auc_std=0.05,
        confusion=confusion,
        classification_report_str="dummy report",
    )
    d = result.to_dict()

    assert d["name"] == "TestModel"
    assert d["roc_auc"] == pytest.approx(0.85)
    assert d["pr_auc"] == pytest.approx(0.65)
    assert d["f1"] == pytest.approx(0.7)
    assert d["precision"] == pytest.approx(0.75)
    assert d["recall"] == pytest.approx(0.6)
    assert d["brier"] == pytest.approx(0.15)
    assert d["cv_roc_auc_mean"] == pytest.approx(0.8)
    assert d["cv_roc_auc_std"] == pytest.approx(0.05)
    assert d["confusion"] == [[10, 2], [3, 15]]

    assert "pipeline" not in d
    assert "classification_report_str" not in d
    assert set(d.keys()) == {
        "name",
        "roc_auc",
        "pr_auc",
        "f1",
        "precision",
        "recall",
        "brier",
        "cv_roc_auc_mean",
        "cv_roc_auc_std",
        "confusion",
    }


def test_model_result_repr_excludes_hidden_fields():
    confusion = np.array([[1, 2], [3, 4]])
    result = ModelResult(
        name="ReprModel",
        pipeline=LogisticRegression(),
        roc_auc=0.5,
        pr_auc=0.5,
        f1=0.5,
        precision=0.5,
        recall=0.5,
        brier=0.5,
        cv_roc_auc_mean=0.5,
        cv_roc_auc_std=0.5,
        confusion=confusion,
        classification_report_str="SOME_UNIQUE_REPORT_STRING",
    )
    r = repr(result)

    assert "SOME_UNIQUE_REPORT_STRING" not in r
    assert "ReprModel" in r


# ---------------------------------------------------------------------------
# evaluate()
# ---------------------------------------------------------------------------

def _make_synthetic_split():
    X, y = make_classification(
        n_samples=200,
        n_features=5,
        n_informative=3,
        n_redundant=0,
        weights=[0.8, 0.2],
        random_state=0,
    )
    X = pd.DataFrame(X, columns=[f"f{i}" for i in range(5)])
    y = pd.Series(y)
    return train_test_split(X, y, test_size=0.25, stratify=y, random_state=0)


def test_evaluate_returns_valid_metrics_and_identity():
    X_train, X_test, y_train, y_test = _make_synthetic_split()

    pipe = LogisticRegression(max_iter=1000)
    result = evaluate("TestLR", pipe, X_train, X_test, y_train, y_test)

    assert result.name == "TestLR"
    assert result.pipeline is pipe

    assert 0.0 <= result.roc_auc <= 1.0
    assert 0.0 <= result.pr_auc <= 1.0
    assert 0.0 <= result.f1 <= 1.0
    assert 0.0 <= result.precision <= 1.0
    assert 0.0 <= result.recall <= 1.0
    assert 0.0 <= result.brier <= 1.0
    assert 0.0 <= result.cv_roc_auc_mean <= 1.0
    assert result.cv_roc_auc_std >= 0.0

    assert result.confusion.shape == (2, 2)
    assert result.confusion.sum() == len(y_test)

    assert isinstance(result.classification_report_str, str)
    assert len(result.classification_report_str) > 0


def test_evaluate_confusion_matrix_totals_match_predictions():
    X_train, X_test, y_train, y_test = _make_synthetic_split()

    pipe = LogisticRegression(max_iter=1000)
    result = evaluate("TestLR2", pipe, X_train, X_test, y_train, y_test)

    # Sum over rows of confusion matrix equals number of actual positives/negatives.
    total = result.confusion.sum()
    assert total == len(y_test)
    # All entries non-negative.
    assert (result.confusion >= 0).all()
