import numpy as np
import pytest
from pathlib import Path

import train


def test_random_state_constant():
    assert train.RANDOM_STATE == 42


def test_models_dir_and_reports_dir_are_paths_and_exist():
    assert isinstance(train.MODELS_DIR, Path)
    assert isinstance(train.REPORTS_DIR, Path)
    assert train.MODELS_DIR.name == "models"
    assert train.REPORTS_DIR.name == "reports"
    # mkdir(exist_ok=True) is called at import time
    assert train.MODELS_DIR.exists()
    assert train.REPORTS_DIR.exists()


def test_candidates_returns_expected_keys():
    candidates = train._candidates()
    assert set(candidates.keys()) == {"LogisticRegression", "RandomForest", "XGBoost"}


def test_candidates_logistic_regression_params():
    lr = train._candidates()["LogisticRegression"]
    assert lr.max_iter == 2000
    assert lr.class_weight == "balanced"
    assert lr.random_state == 42


def test_candidates_random_forest_params():
    rf = train._candidates()["RandomForest"]
    assert rf.n_estimators == 400
    assert rf.max_depth is None
    assert rf.min_samples_leaf == 2
    assert rf.class_weight == "balanced"
    assert rf.random_state == 42
    assert rf.n_jobs == -1


def test_candidates_xgboost_params():
    xgb = train._candidates()["XGBoost"]
    assert xgb.n_estimators == 400
    assert xgb.max_depth == 4
    assert xgb.learning_rate == pytest.approx(0.05, rel=1e-9)
    assert xgb.subsample == pytest.approx(0.9, rel=1e-9)
    assert xgb.colsample_bytree == pytest.approx(0.9, rel=1e-9)
    assert xgb.scale_pos_weight == pytest.approx(5.0, rel=1e-9)
    assert xgb.random_state == 42
    assert xgb.n_jobs == -1


def test_candidates_returns_new_instances_each_call():
    c1 = train._candidates()
    c2 = train._candidates()
    assert c1["LogisticRegression"] is not c2["LogisticRegression"]
    assert c1["RandomForest"] is not c2["RandomForest"]
    assert c1["XGBoost"] is not c2["XGBoost"]


def test_model_result_to_dict_contains_expected_keys_and_values():
    confusion = np.array([[10, 2], [3, 5]])
    result = train.ModelResult(
        name="TestModel",
        pipeline=None,
        roc_auc=0.85,
        pr_auc=0.6,
        f1=0.5,
        precision=0.4,
        recall=0.7,
        brier=0.15,
        cv_roc_auc_mean=0.8,
        cv_roc_auc_std=0.05,
        confusion=confusion,
        classification_report_str="report text",
    )
    d = result.to_dict()

    assert d["name"] == "TestModel"
    assert d["roc_auc"] == pytest.approx(0.85, rel=1e-9)
    assert d["pr_auc"] == pytest.approx(0.6, rel=1e-9)
    assert d["f1"] == pytest.approx(0.5, rel=1e-9)
    assert d["precision"] == pytest.approx(0.4, rel=1e-9)
    assert d["recall"] == pytest.approx(0.7, rel=1e-9)
    assert d["brier"] == pytest.approx(0.15, rel=1e-9)
    assert d["cv_roc_auc_mean"] == pytest.approx(0.8, rel=1e-9)
    assert d["cv_roc_auc_std"] == pytest.approx(0.05, rel=1e-9)
    assert d["confusion"] == [[10, 2], [3, 5]]
    # "pipeline" and "classification_report_str" should not be included
    assert "pipeline" not in d
    assert "classification_report_str" not in d


def test_model_result_to_dict_confusion_is_list_not_ndarray():
    confusion = np.array([[1, 0], [0, 1]])
    result = train.ModelResult(
        name="M",
        pipeline=None,
        roc_auc=0.5,
        pr_auc=0.5,
        f1=0.0,
        precision=0.0,
        recall=0.0,
        brier=0.5,
        cv_roc_auc_mean=0.5,
        cv_roc_auc_std=0.0,
        confusion=confusion,
        classification_report_str="",
    )
    d = result.to_dict()
    assert isinstance(d["confusion"], list)
    assert not isinstance(d["confusion"], np.ndarray)


def test_model_result_dataclass_fields_are_stored_unmodified():
    confusion = np.array([[7, 1], [2, 4]])
    result = train.ModelResult(
        name="StoredModel",
        pipeline="fake_pipeline_placeholder",
        roc_auc=0.777,
        pr_auc=0.333,
        f1=0.111,
        precision=0.222,
        recall=0.444,
        brier=0.055,
        cv_roc_auc_mean=0.7,
        cv_roc_auc_std=0.02,
        confusion=confusion,
        classification_report_str="dummy report",
    )
    assert result.name == "StoredModel"
    assert result.pipeline == "fake_pipeline_placeholder"
    assert result.roc_auc == pytest.approx(0.777, rel=1e-9)
    assert result.pr_auc == pytest.approx(0.333, rel=1e-9)
    assert result.f1 == pytest.approx(0.111, rel=1e-9)
    assert result.precision == pytest.approx(0.222, rel=1e-9)
    assert result.recall == pytest.approx(0.444, rel=1e-9)
    assert result.brier == pytest.approx(0.055, rel=1e-9)
    assert result.cv_roc_auc_mean == pytest.approx(0.7, rel=1e-9)
    assert result.cv_roc_auc_std == pytest.approx(0.02, rel=1e-9)
    assert np.array_equal(result.confusion, confusion)
    assert result.classification_report_str == "dummy report"
