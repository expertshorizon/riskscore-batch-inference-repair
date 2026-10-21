Batch risk scoring specification

The service reads requests from /app/fixtures/scoring_requests.jsonl and scores each one against
/app/fixtures/model_catalog.json, /app/fixtures/feature_snapshots.jsonl,
/app/fixtures/calibrators.json, /app/fixtures/residual_samples.jsonl, and
/app/fixtures/isotonic_fits.jsonl. It writes
/app/output/scores.jsonl and /app/output/run_manifest.json.

Request identity: case_id and entity_id must each be present and a non-empty string, or the
request fails with invalid_request.

Numeric validation: everywhere this specification requires a value to be a number, including
feature values, model weights, intercept, interaction weights, clip bounds, coverage, drift limit
values, half-life, rollout weight, minimum effective samples, residual values, residual weights,
and request thresholds, that value must be a finite real number, or the request fails with
invalid_feature. This is true regardless of which section of this document the field belongs to;
the more specific codes named elsewhere (invalid_model, invalid_residual, invalid_request, and so
on) apply only once a value has already passed this numeric check, to a further problem with its
value, shape, or ordering.

Model selection: for a request's event_time, an active model is eligible when the event time falls
within [valid_from, valid_to) with valid_to of null meaning unbounded, and its segment either
equals the request's segment, is an ancestor of it (the request's segment may be a dot-separated
hierarchy such as "retail.premium", whose ancestors are "retail.premium" itself dropped down to
"retail"), or is the wildcard segment "*". Among eligible models, prefer the most specific segment
match (exact, then nearest ancestor, then farther ancestors, then the wildcard last), then the
latest valid_from, then the highest revision, then the smallest model_id as a final tiebreak. No
eligible model is model_unavailable.

Snapshot selection: max_age_sec must be a number by the rule above, and a negative value is
invalid_request. Among feature snapshots for the request's entity_id observed at or before
event_time, pick the most recently observed one; when two snapshots share the same observed_at,
prefer the one whose snapshot_id sorts first as a string. Its age (event_time minus observed_at)
may equal max_age_sec but must not exceed it, otherwise snapshot_stale. No matching snapshot is
snapshot_unavailable.

Feature preparation: the selected snapshot's values must be an object, or invalid_feature. A
model's weights and defaults/clip/mean/scale mappings must be objects,
required must be an array, and interactions must be an array, or invalid_model. For every feature
referenced by the model's weights or interactions, take the snapshot value or the model default
when absent. A value absent from both with the feature listed as required is missing_feature.
Clip each raw value to the model's configured bounds first, then standardize using the model's
mean and scale (standardized = (clipped - mean) / scale). A non-positive scale is invalid_model. A
clip entry, when present for a feature, must be a two-element list holding a lower and an upper
bound in that order; an entry that is not a two-element list, or whose lower bound exceeds its
upper bound, is invalid_model.

Feature freshness: a model may declare feature_half_life_sec. When it is absent or null the
standardized values are used as they are. Otherwise it must be a positive number, or invalid_model,
and every standardized value is multiplied by a decay factor that is 1 at zero age and halves for
every whole multiple of the half-life that the selected snapshot's age spans, decaying continuously
in between. The decayed values are what scoring and the feature digest use. Drift is always evaluated on the standardized values before any freshness decay is applied.

Scoring: raw_score is the logistic transform of the model intercept plus the sum of weight times
decayed feature value for each weight, plus for each interaction entry [factor_1, ..., factor_k,
weight] (two or more factors followed by a weight) the term weight times the product of the named
factors' decayed values. An interaction entry's factor count is checked first, and fewer than two
factors is invalid_model regardless of whether the trailing weight is numeric.

Calibration: apply the model's named piecewise-linear calibrator to raw_score. A calibrator must
list at least two points, each a two-element [x, y] pair, with strictly increasing x and
nondecreasing y in [0, 1]; any violation of this is invalid_calibrator. Values outside the point
range clamp to the nearest endpoint; values between two points interpolate linearly. An unknown
calibrator_id is calibrator_unavailable.

Rollout blending: a model may declare shadow_calibrator_id to run a replacement calibrator
alongside the current one. When it is absent or null the calibrated score is the primary
calibrator's output. Otherwise the model must also declare rollout_weight. As with every other optional
field in this specification, an absent key and a null value mean the same thing here, so a
rollout_weight that is absent or null is invalid_model, a value that is present but not a number is
invalid_feature by the numeric rule above, and a number outside 0 to 1 inclusive is invalid_model.
Both calibrators are applied to the same raw_score. The calibrated
score is the primary output weighted by one minus rollout_weight plus the shadow output weighted by
rollout_weight, so a rollout_weight of 0 reproduces the primary calibrator exactly and a
rollout_weight of 1 reproduces the shadow calibrator exactly. An unknown shadow_calibrator_id is
calibrator_unavailable.

Isotonic recalibration: a model may declare isotonic_id, naming entries of
/app/fixtures/isotonic_fits.jsonl. Each entry carries an isotonic_id, a segment, a valid_from, a
valid_to, and an observations list of [x, y, weight] triples. An entry is eligible when its
isotonic_id matches the model's and the request's event_time falls within [valid_from, valid_to)
with valid_to of null meaning unbounded. An entry outside that window is not eligible
regardless of its segment. Among eligible
entries resolve the segment the same way residual segments are resolved: the request's exact
segment first, then each less specific ancestor, then the wildcard "*". At the first segment level
with any eligible entry, take the one with the latest valid_from, and if two share a valid_from
take whichever appears first in the file. No eligible entry at any level is isotonic_unavailable. An observations list with fewer than two entries, an entry that is not a
three-element list, a y outside [0, 1], or a non-positive weight is invalid_isotonic.

Collapse observations sharing the same x into a single point whose y is the weight-weighted mean of
their y values and whose weight is the sum of their weights, and order the result by x ascending.
The fitted levels are the nondecreasing sequence of values, one per point, that minimises the
weight-weighted sum of squared differences from those points' y values; this least-squares
monotone fit is uniquely determined by the observations. Consecutive points sharing a fitted level
form one block spanning from the first to the last of their x values.

Isotonic recalibration is applied to the blended calibrated score and its result is the calibrated
score. A value at or below the first block's lower x takes the first block's level and a value at
or above the last block's upper x takes the last block's level. A value inside some block's
[lower x, upper x] range takes that block's level. A value falling in the gap between one block's
upper x and the next block's lower x interpolates linearly between the two levels across that gap.
When a model declares no isotonic_id the calibrated score is the blended score unchanged.

Uncertainty interval: the model's coverage must be greater than 0 and at most 1, and
residual_max_age_sec must be a non-negative number; either bound violated is invalid_model. Gather
residual samples for the model whose recorded_at is at or before event_time and no older than
residual_max_age_sec. A non-positive weight is invalid_residual. A
request's segment may be a dot-separated hierarchy; consider the request's exact segment first,
then each less specific ancestor formed by dropping the last dot-separated part (for example
"retail.premium.gold" falls back to "retail.premium", then "retail"), and finally the wildcard
segment "*". A level qualifies only when it has at least one eligible sample and the effective
sample size of that level's weights, defined as the square of their sum divided by the sum of their
squares, is at least the model's min_effective_samples, which defaults to 1 when absent or null and
is invalid_model when negative. Stop at the first qualifying level and use only that level's
samples; a level that has samples but too small an effective sample size is skipped in favour of
the next one. No qualifying level at all is residual_unavailable.

A model may declare winsor_quantile, a number greater than 0 and at most 1, or invalid_model; when
it is absent or null no capping happens. Otherwise, before the radius is computed, cap the selected
level's absolute residuals: take the value at that quantile of the selected samples under exactly
the same weighted empirical rule described next, then replace every residual above that value with
it, leaving each sample's weight unchanged. The capped samples are what the radius is computed
from, at the model's coverage.

Sort the selected absolute residuals ascending and treat them as a weighted empirical distribution:
let W be the total weight and, walking the sorted samples, let C be the running cumulative weight
after including each sample. The target cumulative weight is the model's coverage fraction of W. If
the target falls exactly on or before the first sample's cumulative weight, the radius is that
sample's value; otherwise find the first sample whose cumulative weight reaches or passes the
target and linearly interpolate between the previous sample's value and this one, in proportion to
where the target falls between their two cumulative weights. The interval is
[calibrated_score - radius, calibrated_score + radius], clamped to [0, 1].

Drift and decision: the model's drift_limits must be an object, or invalid_model. A feature drifts
when its absolute standardized value exceeds the model's configured limit for that feature
(invalid_model for a negative limit). With no drift, approve when
the interval lower bound is at least approve_threshold, decline when the interval upper bound is
below decline_threshold, otherwise review. Thresholds must satisfy
0 <= decline_threshold <= approve_threshold <= 1, else invalid_request.

Any other malformed or missing data for a single request, including an unparseable event_time or
observed_at, must yield a per-request error row with error_code invalid_input rather than aborting
the batch.

Population flagging: after every request in a run has been scored, and only for a full run rather
than a single request, take the calibrated scores of the successful rows and compute their median,
where the median of an even-length sorted list is the mean of its two middle values. Then compute
the median of the absolute deviations of those same scores from that median. A successful row is
flagged outlier when the absolute deviation of its own calibrated score from the median is strictly
greater than three times that median absolute deviation, and typical otherwise; when the median
absolute deviation is zero, or there are no successful rows, every successful row is typical. Error rows are never flagged and
never contribute to either median.

Output: each score row carries exactly case_id, entity_id, model_id, snapshot_id, raw_score,
calibrated_score, confidence_interval, drift, decision, population_flag, and feature_digest (the sha256 hex digest
of the canonical JSON of the decayed feature map). Each error row includes case_id, entity_id,
status set to "error", and error_code. No other field appears on a
score row, and population_flag appears only on rows emitted by a full run, since it is undefined for
a single scored request. Numeric values are rounded to six decimals as part of scoring a request, so
a scored row already carries rounded values before anything is written. Rows are canonical
JSON with sorted keys and ordered ascending by case_id in the file. run_manifest.json reports rows,
success, error, approve, review, decline, and outlier counts, distinct_models (the number of distinct
model_id values among successful rows only), and scores_sha256, the sha256 hex digest of the exact
bytes of scores.jsonl. Re-running on the same fixtures must atomically replace both files and
produce byte-identical output.
