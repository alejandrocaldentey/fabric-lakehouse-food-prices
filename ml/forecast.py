"""Predictive layer: three models, a rolling-origin backtest, a champion and a forecast.

Runs inside the pipeline right after the Diamond table is built (ADR 0009: forecasts are
computed where the definitions are governed, then published). Writes four tables:

    ml_model_registry  one row per model: errors, skill vs the baseline, champion flag
    ml_backtest        every out-of-sample prediction: country, year, actual, predicted
    ml_forecast        next year's forecast per country and model, with an 80% interval
    ml_coefficient     the regression's published coefficients (the browser simulator uses them)
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import yaml
from sklearn.ensemble import GradientBoostingRegressor

CONFIG = Path(__file__).with_name("models.yaml")
FEATURES = ["consumer_food_yoy_pct", "producer_yoy_pct", "producer_yoy_pct_lag1"]
# lineage of this Python step, read by governance/build.py
INPUTS = ["gold_price_transmission"]
OUTPUTS = ["ml_model_registry", "ml_backtest", "ml_forecast", "ml_coefficient"]


def load_config(path: Path = CONFIG) -> dict:
    return yaml.safe_load(path.read_text())


@dataclass
class Samples:
    country: np.ndarray  # country of each sample
    year: np.ndarray  # target year t+1
    x: np.ndarray  # c(t), p(t), p(t-1)
    y: np.ndarray  # c(t+1)

    def mask(self, keep: np.ndarray) -> Samples:
        return Samples(self.country[keep], self.year[keep], self.x[keep], self.y[keep])

    def __len__(self) -> int:
        return len(self.y)


def history(con) -> dict[str, dict[int, tuple]]:
    """country -> year -> (c(t), p(t), p(t-1)) from the gold table."""
    out: dict[str, dict[int, tuple]] = {}
    for country, year, c, p, p1 in con.execute(
        "SELECT country_iso3, year, consumer_food_yoy_pct, producer_yoy_pct, producer_yoy_pct_lag1 "
        "FROM gold_price_transmission ORDER BY country_iso3, year"
    ).fetchall():
        out.setdefault(country, {})[int(year)] = (c, p, p1)
    return out


def samples(hist: dict[str, dict[int, tuple]]) -> Samples:
    rows = []
    for country, years in hist.items():
        for t, feats in years.items():
            nxt = years.get(t + 1)
            if nxt and nxt[0] is not None and all(v is not None for v in feats):
                rows.append((country, t + 1, *feats, nxt[0]))
    if not rows:
        return Samples(np.array([]), np.array([], int), np.zeros((0, 3)), np.array([]))
    arr = np.array(rows, dtype=object)
    return Samples(
        arr[:, 0].astype(str),
        arr[:, 1].astype(int),
        arr[:, 2:5].astype(float),
        arr[:, 5].astype(float),
    )


# --- models -------------------------------------------------------------------------


class Naive:
    id = "naive"

    def fit(self, s: Samples) -> Naive:
        return self

    def predict(self, country: np.ndarray, x: np.ndarray) -> np.ndarray:
        return x[:, 0].copy()


class PanelDL:
    """OLS with country fixed effects: y = a(country) + b·x. Unknown countries get the mean a."""

    id = "panel_dl"

    def fit(self, s: Samples) -> PanelDL:
        self.countries = sorted(set(s.country))
        dummies = (s.country[:, None] == np.array(self.countries)[None, :]).astype(float)
        design = np.hstack([dummies, s.x])
        coef, *_ = np.linalg.lstsq(design, s.y, rcond=None)
        k = len(self.countries)
        self.alpha = dict(zip(self.countries, coef[:k], strict=True))
        self.beta = coef[k:]
        self.alpha_mean = float(np.mean(coef[:k]))
        return self

    def intercepts(self, country: np.ndarray) -> np.ndarray:
        return np.array([self.alpha.get(c, self.alpha_mean) for c in country])

    def predict(self, country: np.ndarray, x: np.ndarray) -> np.ndarray:
        return self.intercepts(country) + x @ self.beta


class GBM:
    id = "gbm"

    def fit(self, s: Samples) -> GBM:
        self.model = GradientBoostingRegressor(
            n_estimators=200, max_depth=2, learning_rate=0.05, subsample=0.8, random_state=42
        ).fit(s.x, s.y)
        return self

    def predict(self, country: np.ndarray, x: np.ndarray) -> np.ndarray:
        return self.model.predict(x)


MODELS = {m.id: m for m in (Naive, PanelDL, GBM)}
MIN_TRAIN = 30  # samples needed before a model is fitted in the backtest


# --- backtest, champion, forecast ------------------------------------------------------


def backtest(s: Samples, first_test_year: int) -> list[tuple]:
    """Rolling origin: for each test year T, train on targets < T and predict T."""
    out = []
    for t in sorted({int(y) for y in s.year if y >= first_test_year}):
        train, test = s.mask(s.year < t), s.mask(s.year == t)
        if len(train) < MIN_TRAIN or not len(test):
            continue
        for mid, cls in MODELS.items():
            pred = cls().fit(train).predict(test.country, test.x)
            for c, x, y, yhat in zip(test.country, test.x, test.y, pred, strict=True):
                out.append((mid, str(c), t, float(y), float(yhat), float(x[1])))
    return out


def score(bt: list[tuple], cfg: dict) -> dict[str, dict]:
    shock = cfg["backtest"]["shock_threshold_pct"]
    years = sorted({r[2] for r in bt})
    recent = set(years[-3:])
    stats = {}
    for mid in MODELS:
        rows = [r for r in bt if r[0] == mid]
        if not rows:
            continue
        err = np.array([r[4] - r[3] for r in rows])
        is_shock = np.array([abs(r[5]) >= shock for r in rows])
        is_recent = np.array([r[2] in recent for r in rows])
        stats[mid] = {
            "n_backtest": len(rows),
            "mae": float(np.mean(np.abs(err))),
            "rmse": float(np.sqrt(np.mean(err**2))),
            "bias": float(np.mean(err)),
            "mae_shock_years": float(np.mean(np.abs(err[is_shock]))) if is_shock.any() else None,
            "mae_recent": float(np.mean(np.abs(err[is_recent]))) if is_recent.any() else None,
            "q_lo": float(np.quantile(err, cfg["interval"]["lower_quantile"])),
            "q_hi": float(np.quantile(err, cfg["interval"]["upper_quantile"])),
        }
    naive = stats.get("naive", {}).get("mae")
    for st in stats.values():
        st["skill_vs_naive"] = (1 - st["mae"] / naive) if naive else None
    return stats


def pick_champion(stats: dict[str, dict], cfg: dict) -> str:
    """Simplest model within `tolerance` of the best error, among those that beat the baseline."""
    rule = cfg["champion"]
    order = [m["id"] for m in cfg["models"]]  # simplest first
    eligible = [
        m
        for m in order
        if m in stats
        and (m == "naive" or (stats[m]["skill_vs_naive"] or 0) >= rule["min_skill_vs_naive"])
    ]
    if not eligible:
        return "naive"
    best = min(stats[m]["mae"] for m in eligible)
    return next(m for m in eligible if stats[m]["mae"] <= best * (1 + rule["tolerance"]))


def latest_inputs(hist: dict[str, dict[int, tuple]]) -> list[tuple[str, int, tuple]]:
    """Per country, the latest year with every feature known: (country, year, features)."""
    out = []
    for country, years in hist.items():
        full = [t for t, f in years.items() if all(v is not None for v in f)]
        if full:
            t = max(full)
            out.append((country, t, years[t]))
    return out


def run(con, cfg: dict | None = None) -> str | None:
    """Build the four ml_* tables in ``con``. Returns the champion id (None without data)."""
    cfg = cfg or load_config()
    _create_tables(con)
    hist = history(con)
    s = samples(hist)
    bt = backtest(s, cfg["backtest"]["first_test_year"])
    stats = score(bt, cfg)
    if not stats:
        return None
    champion = pick_champion(stats, cfg)
    trained_through = int(max(s.year))

    con.executemany("INSERT INTO ml_backtest VALUES (?, ?, ?, ?, ?)", [r[:5] for r in bt])
    for m in cfg["models"]:
        st = stats.get(m["id"])
        if not st:
            continue
        con.execute(
            "INSERT INTO ml_model_registry VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                m["id"], m["label"], m["family"], m["formula"], m["how_it_works"],
                m["strengths"], m["weaknesses"], m["when_to_use"], m["id"] == champion,
                st["n_backtest"], st["mae"], st["rmse"], st["bias"], st["skill_vs_naive"],
                st["mae_shock_years"], st["mae_recent"], trained_through,
            ],
        )  # fmt: skip

    inputs = latest_inputs(hist)
    country = np.array([c for c, _, _ in inputs])
    x = np.array([f for _, _, f in inputs], dtype=float)
    fitted = {mid: cls().fit(s) for mid, cls in MODELS.items()}
    for mid, model in fitted.items():
        pred = model.predict(country, x)
        st = stats[mid]
        con.executemany(
            "INSERT INTO ml_forecast VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                (mid, c, t + 1, float(p), float(p + st["q_lo"]), float(p + st["q_hi"]),
                 mid == champion, float(f[0]), float(f[1]), float(f[2]))
                for (c, t, f), p in zip(inputs, pred, strict=True)
            ],
        )  # fmt: skip

    reg: PanelDL = fitted["panel_dl"]  # type: ignore[assignment]
    coef = [("slope", None, name, float(b)) for name, b in zip(FEATURES, reg.beta, strict=True)]
    coef += [("intercept", c, "country", float(a)) for c, a in reg.alpha.items()]
    coef += [("intercept", None, "mean", reg.alpha_mean)]
    con.executemany("INSERT INTO ml_coefficient VALUES ('panel_dl', ?, ?, ?, ?)", coef)
    return champion


def _create_tables(con) -> None:
    con.execute(
        """CREATE OR REPLACE TABLE ml_model_registry (
            model_id VARCHAR, label VARCHAR, family VARCHAR, formula VARCHAR,
            how_it_works VARCHAR, strengths VARCHAR, weaknesses VARCHAR, when_to_use VARCHAR,
            is_champion BOOLEAN, n_backtest INT, mae DOUBLE, rmse DOUBLE, bias DOUBLE,
            skill_vs_naive DOUBLE, mae_shock_years DOUBLE, mae_recent DOUBLE, trained_through INT)"""
    )
    con.execute(
        """CREATE OR REPLACE TABLE ml_backtest (
            model_id VARCHAR, country_iso3 VARCHAR, year INT, actual DOUBLE, predicted DOUBLE)"""
    )
    con.execute(
        """CREATE OR REPLACE TABLE ml_forecast (
            model_id VARCHAR, country_iso3 VARCHAR, target_year INT, predicted DOUBLE,
            lower_80 DOUBLE, upper_80 DOUBLE, is_champion BOOLEAN,
            input_consumer_yoy DOUBLE, input_producer_yoy DOUBLE, input_producer_yoy_lag1 DOUBLE)"""
    )
    con.execute(
        """CREATE OR REPLACE TABLE ml_coefficient (
            model_id VARCHAR, kind VARCHAR, country_iso3 VARCHAR, term VARCHAR, value DOUBLE)"""
    )
