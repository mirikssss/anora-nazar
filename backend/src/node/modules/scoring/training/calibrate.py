"""Калибровка балла: изотоническая регрессия, кривая хранится точками (x, y) в версии модели."""

from typing import Any

import numpy as np
from sklearn.isotonic import IsotonicRegression


def isotonic_curve(raw: np.ndarray, y: np.ndarray) -> dict[str, list[float]]:
    model = IsotonicRegression(out_of_bounds="clip", y_min=0.0, y_max=1.0).fit(raw, y)
    return {
        "x": [round(float(v), 8) for v in model.X_thresholds_],
        "y": [round(float(v), 8) for v in model.y_thresholds_],
    }


def calibration(
    raw: np.ndarray, y: np.ndarray, channels: np.ndarray, *, by_channel: bool, min_positives: int, source: str
) -> dict[str, Any]:
    """Общая кривая и, если просили и хватает позитивов, отдельная кривая на канал."""
    maps = {"all": isotonic_curve(raw, y)}
    if by_channel:
        for channel in ("online", "program"):
            mask = channels == channel
            if int(y[mask].sum()) >= min_positives:
                maps[channel] = isotonic_curve(raw[mask], y[mask])
    return {"by": "channel" if by_channel else "all", "maps": maps, "source": source}
