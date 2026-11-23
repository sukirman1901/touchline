# Adopted upstream code

- Repository: https://github.com/mradovic38/football-analysis
- Revision: `1aaac243cc41924f80c0fc904cb0f1ce8c9ecc7d`
- Source: `speed_estimation/speed_estimator.py`
- License: MIT, included verbatim in LICENSE.
- This is an adapted module, not a claim of an unchanged upstream copy.
- Removed verbose docstrings/type annotations; retained scale/distance/time and
  deque moving-average code structure.
- Patched zero-filled startup, missing projection=0 and speed clipping.
- `app.motion.MetricMotion` enforces metric input, timestamps, short gaps,
  nonfinite/outlier rejection and shot-qualified track identity.
- Tests: `tests/test_motion.py`, `tests/test_metrics.py`.
- No UI layouts were imported from the reference repository.
