import logging

import numpy as np
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import Ridge
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, OrdinalEncoder, StandardScaler

from ml.features import CAT_FEATURES, FEATURES, NUM_FEATURES, TARGET

log = logging.getLogger("ml")


def regression_metrics(y_true, y_pred) -> dict:
    y_true = np.asarray(y_true, dtype=float)
    y_pred = np.asarray(y_pred, dtype=float)
    err = y_true - y_pred
    ss_res = float(np.sum(err ** 2))
    ss_tot = float(np.sum((y_true - y_true.mean()) ** 2))
    return {
        "r2": 1.0 - ss_res / ss_tot if ss_tot > 0 else float("nan"),
        "mape_pct": float(np.mean(np.abs(err) / y_true) * 100.0),
        "rmse_rub": float(np.sqrt(np.mean(err ** 2))),
        "mae_rub": float(np.mean(np.abs(err))),
    }


class _Clipped:
    def __init__(self, model):
        self.model = model

    def fit(self, X, y):
        self.model.fit(X, y)
        return self

    def predict(self, X):
        return np.clip(self.model.predict(X), 0, None)


def make_ridge() -> _Clipped:
    pre = ColumnTransformer([
        ("cat", OneHotEncoder(handle_unknown="ignore"), CAT_FEATURES),
        ("num", Pipeline([("imp", SimpleImputer(strategy="median")), ("sc", StandardScaler())]), NUM_FEATURES),
    ])
    return _Clipped(Pipeline([("pre", pre), ("model", Ridge(alpha=1.0))]))


def make_boosting(seed: int):
    try:
        from catboost import CatBoostRegressor
    except ImportError:
        from sklearn.ensemble import HistGradientBoostingRegressor
        log.warning("catboost is not installed, falling back to HistGradientBoostingRegressor")
        pre = ColumnTransformer(
            [("cat", OrdinalEncoder(handle_unknown="use_encoded_value", unknown_value=np.nan), CAT_FEATURES)],
            remainder="passthrough")
        mask = [True] * len(CAT_FEATURES) + [False] * len(NUM_FEATURES)
        model = Pipeline([("pre", pre),
                          ("model", HistGradientBoostingRegressor(
                              categorical_features=mask, max_iter=400, learning_rate=0.06,
                              random_state=seed))])
        return "sklearn_hgb", _Clipped(model)

    class _Cat:
        def __init__(self):
            self.m = CatBoostRegressor(iterations=800, depth=8, learning_rate=0.05, loss_function="RMSE",
                                       random_seed=seed, verbose=False, allow_writing_files=False)

        def fit(self, X, y):
            self.m.fit(X, y, cat_features=CAT_FEATURES)
            return self

        def predict(self, X):
            return np.clip(self.m.predict(X), 0, None)

    return "catboost", _Cat()


def train_and_evaluate(train, test, seed: int):
    X_tr, y_tr = train[FEATURES], train[TARGET].to_numpy()
    X_te, y_te = test[FEATURES], test[TARGET].to_numpy()
    primary_name, primary = make_boosting(seed)
    models = {"ridge": make_ridge(), primary_name: primary}
    metrics = {}
    for name, m in models.items():
        m.fit(X_tr, y_tr)
        metrics[name] = regression_metrics(y_te, m.predict(X_te))
        metrics[name].update(n_train=len(train), n_test=len(test))
        log.info("test metrics [%s]: R2=%.4f MAPE=%.2f%% RMSE=%.0f RUB MAE=%.0f RUB (train=%d, test=%d)",
                 name, metrics[name]["r2"], metrics[name]["mape_pct"], metrics[name]["rmse_rub"],
                 metrics[name]["mae_rub"], len(train), len(test))
    return primary_name, models, metrics
