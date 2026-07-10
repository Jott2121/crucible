import json
import numpy as np
import pandas as pd
import pytest
from sklearn.metrics import classification_report
import train

def test_candidates_have_explicit_required_estimator_configuration(monkeypatch):
    constructed = {}

    class SpyEstimator:

        def __init__(self, **kwargs):
            self.kwargs = kwargs

    def random_forest_spy(**kwargs):
        constructed['RandomForest'] = kwargs
        return SpyEstimator(**kwargs)

    def xgboost_spy(**kwargs):
        constructed['XGBoost'] = kwargs
        return SpyEstimator(**kwargs)
    monkeypatch.setattr(train, 'RandomForestClassifier', random_forest_spy)
    monkeypatch.setattr(train, 'XGBClassifier', xgboost_spy)
    candidates = train._candidates()
    assert set(candidates) == {'LogisticRegression', 'RandomForest', 'XGBoost'}
    assert constructed['RandomForest']['max_depth'] is None
    assert constructed['RandomForest']['n_estimators'] == 400
    assert constructed['XGBoost']['objective'] == 'binary:logistic'
    assert constructed['XGBoost']['eval_metric'] == 'logloss'
    assert constructed['XGBoost']['tree_method'] == 'hist'

def test_evaluate_computes_metrics_threshold_and_cross_validation_contract(monkeypatch):
    X_train = pd.DataFrame({'feature': range(10)})
    y_train = pd.Series([0, 1] * 5)
    X_test = pd.DataFrame({'feature': range(4)})
    y_test = pd.Series([0, 1, 1, 0])

    class FakePipe:

        def __init__(self):
            self.fit_arguments = None
            self.predict_argument = None

        def fit(self, X, y):
            self.fit_arguments = (X, y)
            return self

        def predict_proba(self, X):
            self.predict_argument = X
            return np.array([[0.5, 0.5], [0.4, 0.6], [0.6, 0.4], [0.9, 0.1]])
    pipe = FakePipe()
    cv_scores = np.array([0.2, 0.4, 0.6, 0.8, 1.0])

    def fake_cross_val_score(estimator, X, y, scoring, cv, n_jobs):
        assert estimator is pipe
        assert X is X_train
        assert y is y_train
        assert scoring == 'roc_auc'
        assert n_jobs == -1
        assert cv.n_splits == 5
        assert cv.shuffle is True
        assert cv.random_state == train.RANDOM_STATE
        return cv_scores
    monkeypatch.setattr(train, 'cross_val_score', fake_cross_val_score)
    result = train.evaluate('demo', pipe, X_train, X_test, y_train, y_test)
    expected_predictions = np.array([1, 1, 0, 0])
    assert pipe.fit_arguments == (X_train, y_train)
    assert pipe.predict_argument is X_test
    assert result.name == 'demo'
    assert result.pipeline is pipe
    assert result.roc_auc == pytest.approx(0.75, rel=1e-06)
    assert result.pr_auc == pytest.approx(5 / 6, rel=1e-06)
    assert result.f1 == pytest.approx(0.5, rel=1e-06)
    assert result.precision == pytest.approx(0.5, rel=1e-06)
    assert result.recall == pytest.approx(0.5, rel=1e-06)
    assert result.brier == pytest.approx(0.195, rel=1e-06)
    assert result.cv_roc_auc_mean == pytest.approx(0.6, rel=1e-06)
    assert result.cv_roc_auc_std == pytest.approx(np.std(cv_scores), rel=1e-06)
    assert np.array_equal(result.confusion, np.array([[1, 1], [1, 1]]))
    assert result.classification_report_str == classification_report(y_test, expected_predictions, digits=3)

def test_evaluate_uses_zero_precision_when_no_positive_predictions(monkeypatch):
    X_train = pd.DataFrame({'feature': range(10)})
    y_train = pd.Series([0, 1] * 5)
    X_test = pd.DataFrame({'feature': range(4)})
    y_test = pd.Series([0, 1, 1, 0])

    class AlwaysNegativePipe:

        def fit(self, X, y):
            return self

        def predict_proba(self, X):
            return np.array([[0.9, 0.1]] * len(X))
    monkeypatch.setattr(train, 'cross_val_score', lambda *args, **kwargs: np.array([0.5] * 5))
    result = train.evaluate('always-negative', AlwaysNegativePipe(), X_train, X_test, y_train, y_test)
    assert result.precision == pytest.approx(0.0, rel=1e-06)
    assert result.recall == pytest.approx(0.0, rel=1e-06)
    assert result.f1 == pytest.approx(0.0, rel=1e-06)
    assert np.array_equal(result.confusion, np.array([[2, 0], [2, 0]]))
