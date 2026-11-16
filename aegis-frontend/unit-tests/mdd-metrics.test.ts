import test from "node:test";
import assert from "node:assert/strict";

import { formatMddMetricValue } from "../src/lib/mdd-metrics";

test("missing developer-reported MDD metrics display as Not reported", () => {
  assert.equal(formatMddMetricValue(null), "Not reported");
  assert.equal(formatMddMetricValue(undefined), "Not reported");
  assert.equal(formatMddMetricValue(0.72), "0.72");
  assert.equal(formatMddMetricValue("0.61"), "0.61");
});
