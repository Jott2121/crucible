"""
Additional tests targeting surviving mutants in src/train.py.

These tests independently verify:
1. The hyperparameters used to construct each candidate model in `_candidates()`.
2. The behavior of `evaluate()` -- in particular the >=0.5 threshold used to
   convert probabilities to predictions, and that all metrics are computed
   from the correct arguments.
"""
from __future__ import annotations
import numpy as np
import pandas as pd
import pytest
from sklearn.base import BaseEstimator, ClassifierMixin
from sklearn.metrics import average_precision_score, brier_score_loss, confusion_matrix, f1_score, precision_score, recall_score, roc_auc_score
from sklearn.pipeline import Pipeline
from src.train import RANDOM_STATE, ModelResult, _candidates, evaluate

def test_candidates_keys_exact():
    cands = _candidates()
    assert set(cands.keys()) == {'LogisticRegression', 'RandomForest', 'XGBoost'}

def test_logistic_regression_hyperparams():
    lr = _candidates()['LogisticRegression']
    assert lr.max_iter == 2000
    assert lr.class_weight == 'balanced'
    assert lr.random_state == RANDOM_STATE

def test_random_forest_hyperparams():
    rf = _candidates()['RandomForest']
    assert rf.n_estimators == 400
    assert rf.max_depth is None
    assert rf.min_samples_leaf == 2
    assert rf.class_weight == 'balanced'
    assert rf.n_jobs == -1
    assert rf.random_state == RANDOM_STATE

def test_xgboost_hyperparams():
    xgb = _candidates()['XGBoost']
    assert xgb.n_estimators == 400
    assert xgb.max_depth == 4
    assert xgb.learning_rate == pytest.approx(0.05, rel=1e-06)
    assert xgb.subsample == pytest.approx(0.9, rel=1e-06)
    assert xgb.colsample_bytree == pytest.approx(0.9, rel=1e-06)
    assert xgb.scale_pos_weight == pytest.approx(5.0, rel=1e-06)
    assert xgb.objective == 'binary:logistic'
    assert xgb.eval_metric == 'logloss'
    assert xgb.random_state == RANDOM_STATE
    assert xgb.n_jobs == -1
    assert xgb.tree_method == 'hist'

class ColumnProbaClassifier(BaseEstimator, ClassifierMixin):
    """A deterministic fake classifier whose predict_proba is directly read
    from a fixed column 'p' of the input DataFrame. This lets us fully
    control the probabilities seen by `evaluate()` without depending on any
    real model's stochastic training behavior."""

    def fit(self, X, y):
        self.classes_ = np.array([0, 1])
        return self

    def predict_proba(self, X):
        p = np.asarray(X['p'], dtype=float)
        return np.column_stack([1 - p, p])

    def predict(self, X):
        p = np.asarray(X['p'], dtype=float)
        return (p >= 0.5).astype(int)

def _make_pipeline():
    return Pipeline(steps=[('clf', ColumnProbaClassifier())])

def _make_train_data():
    y_train = pd.Series([0] * 10 + [1] * 10)
    p_train = [0.1] * 10 + [0.9] * 10
    X_train = pd.DataFrame({'p': p_train})
    return (X_train, y_train)
