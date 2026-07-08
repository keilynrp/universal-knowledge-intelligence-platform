/**
 * Maps the shared quality-group <select> value (see EntityTableToolbar) to the
 * API query parameters that express it.
 *
 * The dropdown offers a single control but two kinds of thresholds:
 *  - "70%+" / "30%+" are *lower* bounds  -> min_quality
 *  - "Menor a 30%" is an *upper* bound    -> max_quality (quality_score < 0.3)
 *
 * "Menor a 30%" keeps the historical option value "0.0" for backwards-compatible
 * persisted URLs, but is now translated to an upper bound so the bucket really
 * means "below 30%" instead of "everything scored".
 */
export const UNDER_30_VALUE = "0.0";
export const UNDER_30_MAX = "0.3";

export interface QualityFilterParams {
  min_quality?: string;
  max_quality?: string;
}

export function qualityFilterParams(value: string): QualityFilterParams {
  if (!value) return {};
  if (value === UNDER_30_VALUE) return { max_quality: UNDER_30_MAX };
  return { min_quality: value };
}
