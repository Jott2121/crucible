import numpy as np
import pytest
from pathlib import Path

from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from xgboost import XGBClassifier

import train


# ---------------------------------------------------------------------------
# Module-level constants
# ---------------------------------------------------------------------------

def test_random_state_value():
    assert train.RANDOM_STATE == 42


def test_models_dir_is_correct_path_and_exists():
    assert isinstance(train.MODELS_DIR, Path)
    assert train.MODELS_DIR.name == "models"
    assert train.MODELS_DIR.exists()
    assert train.MODELS_DIR.is_dir()


def test_reports_dir_is_correct_path_and_exists():
    assert isinstance(train.REPORTS_DIR, Path)
    assert train.REPORTS_DIR.name == "reports"
    assert train.REPORTS_DIR.exists()
    assert train.REPORTS_DIR.is_dir()


def test_models_and_reports_dirs_share_same_parent():
    assert train.MODELS_DIR.parent == train.REPORTS_DIR.parent


# ---------------------------------------------------------------------------
# _candidates()
# ---------------------------------------------------------------------------

def test_candidates_returns_expected_keys():
    candidates = train._candidates()
    assert set(candidates.keys()) == {"LogisticRegression", "RandomForest", "XGBoost"}


def test_candidates_returns_expected_types():
    candidates = train._candidates()
    assert isinstance(candidates["LogisticRegression"], LogisticRegression)
    assert isinstance(candidates["RandomForest"], RandomForestClassifier)
    assert isinstance(candidates["XGBoost"], XGBClassifier)


def test_logistic_regression_hyperparameters():
    lr = train._candidates()["LogisticRegression"]
    assert lr.max_iter == 2000
    assert lr.class_weight == "balanced"
    assert lr.random_state == 42


def test_random_forest_hyperparameters():
    rf = train._candidates()["RandomForest"]
    assert rf.n_estimators == 400
    assert rf.max_depth is None
    assert rf.min_samples_leaf == 2
    assert rf.class_weight == "balanced"
    assert rf.n_jobs == -1
    assert rf.random_state == 42


def test_xgboost_hyperparameters():
    xgb = train._candidates()["XGBoost"]
    assert xgb.n_estimators == 400
    assert xgb.max_depth == 4
    assert xgb.learning_rate == pytest.approx(0.05, rel=1e-6)
    assert xgb.subsample == pytest.approx(0.9, rel=1e-6)
    assert xgb.colsample_bytree == pytest.approx(0.9, rel=1e-6)
    assert xgb.scale_pos_weight == pytest.approx(5.0, rel=1e-6)
    assert xgb.random_state == 42
    assert xgb.n_jobs == -1
    assert xgb.tree_method == "hist"


def test_candidates_returns_fresh_instances_each_call():
    c1 = train._candidates()
    c2 = train._candidates()
    assert c1["LogisticRegression"] is not c2["LogisticRegression"]
    assert c1["RandomForest"] is not c2["RandomForest"]
    assert c1["XGBoost"] is not c2["XGBoost"]


# ---------------------------------------------------------------------------
# ModelResult.to_dict()
# ---------------------------------------------------------------------------

def test_model_result_to_dict_basic_values():
    confusion = np.array([[50, 3], [4, 20]])
    result = train.ModelResult(
        name="TestModel",
        pipeline=None,
        roc_auc=0.812345,
        pr_auc=0.634567,
        f1=0.71,
        precision=0.65,
        recall=0.80,
        brier=0.123,
        cv_roc_auc_mean=0.79,
        cv_roc_auc_std=0.02,
        confusion=confusion,
        classification_report_str="dummy report",
    )
    d = result.to_dict()

    assert d["name"] == "TestModel"
    assert d["roc_auc"] == pytest.approx(0.812345, rel=1e-6)
    assert d["pr_auc"] == pytest.approx(0.634567, rel=1e-6)
    assert d["f1"] == pytest.approx(0.71, rel=1e-6)
    assert d["precision"] == pytest.approx(0.65, rel=1e-6)
    assert d["recall"] == pytest.approx(0.80, rel=1e-6)
    assert d["brier"] == pytest.approx(0.123, rel=1e-6)
    assert d["cv_roc_auc_mean"] == pytest.approx(0.79, rel=1e-6)
    assert d["cv_roc_auc_std"] == pytest.approx(0.02, rel=1e-6)
    assert d["confusion"] == [[50, 3], [4, 20]]


def test_model_result_to_dict_excludes_pipeline_and_report():
    confusion = np.array([[0, 0], [0, 0]])
    result = train.ModelResult(
        name="EmptyModel",
        pipeline=None,
        roc_auc=0.0,
        pr_auc=0.0,
        f1=0.0,
        precision=0.0,
        recall=0.0,
        brier=0.0,
        cv_roc_auc_mean=0.0,
        cv_roc_auc_std=0.0,
        confusion=confusion,
        classification_report_str="empty report",
    )
    d = result.to_dict()

    assert "pipeline" not in d
    assert "classification_report_str" not in d
    assert d["confusion"] == [[0, 0], [0, 0]]


def test_model_result_to_dict_zero_metrics():
    confusion = np.array([[1, 0], [0, 1]])
    result = train.ModelResult(
        name="ZeroModel",
        pipeline=None,
        roc_auc=0.0,
        pr_auc=0.0,
        f1=0.0,
        precision=0.0,
        recall=0.0,
        brier=0.0,
        cv_roc_auc_mean=0.0,
        cv_roc_auc_std=0.0,
        confusion=confusion,
        classification_report_str="",
    )
    d = result.to_dict()
    for key in ("roc_auc", "pr_auc", "f1", "precision", "recall", "brier",
                "cv_roc_auc_mean", "cv_roc_auc_std"):
        assert d[key] == pytest.approx(0.0, abs=1e-9)


def test_model_result_to_dict_keys_complete():
    confusion = np.array([[10, 2], [1, 5]])
    result = train.ModelResult(
        name="KeysModel",
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
    expected_keys = {
        "name", "roc_auc", "pr_auc", "f1", "precision", "recall",
        "brier", "cv_roc_auc_mean", "cv_roc_auc_std", "confusion",
    }
    assert set(d.keys()) == expected_keys
