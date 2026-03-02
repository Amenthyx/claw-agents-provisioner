// ===================================================================
// k6-config.js -- Shared Configuration for Claw Agents Load Tests
// ===================================================================
//
// Central configuration for base URLs, auth tokens, thresholds,
// and shared helper functions used by all k6 load test scripts.
//
// Usage:
//   import { CONFIG, authHeaders, jsonHeaders, checkResponse } from './k6-config.js';
//
// Environment variable overrides:
//   K6_BASE_HOST       -- Override base hostname (default: localhost)
//   K6_AUTH_TOKEN       -- Bearer token for authenticated endpoints
//   K6_ROUTER_PORT      -- Router service port (default: 9095)
//   K6_MEMORY_PORT      -- Memory service port (default: 9096)
//   K6_RAG_PORT         -- RAG service port (default: 9097)
//   K6_DASHBOARD_PORT   -- Dashboard service port (default: 9099)
// ===================================================================

import { check } from "k6";
import { Counter, Trend } from "k6/metrics";

// ── Custom metrics (shared across all tests) ────────────────────────

export const errorCounter = new Counter("custom_errors");
export const responseTimeTrend = new Trend("custom_response_time", true);

// ── Configuration ───────────────────────────────────────────────────

const BASE_HOST = __ENV.K6_BASE_HOST || "localhost";
const AUTH_TOKEN = __ENV.K6_AUTH_TOKEN || "test-token-for-load-testing";

export const CONFIG = {
  baseHost: BASE_HOST,
  authToken: AUTH_TOKEN,

  // Service URLs
  routerUrl: `http://${BASE_HOST}:${__ENV.K6_ROUTER_PORT || "9095"}`,
  memoryUrl: `http://${BASE_HOST}:${__ENV.K6_MEMORY_PORT || "9096"}`,
  ragUrl: `http://${BASE_HOST}:${__ENV.K6_RAG_PORT || "9097"}`,
  dashboardUrl: `http://${BASE_HOST}:${__ENV.K6_DASHBOARD_PORT || "9099"}`,

  // Default thresholds
  thresholds: {
    router: {
      p95: 200,    // ms
      errorRate: 0.01,
    },
    memory: {
      p95: 100,    // ms
      errorRate: 0.01,
    },
    rag: {
      p95: 500,    // ms
      errorRate: 0.01,
    },
    dashboard: {
      p95: 300,    // ms
      errorRate: 0.01,
    },
  },

  // Default stages pattern: ramp up -> sustained -> ramp down
  defaultStages: {
    rampUp: "30s",
    sustained: "2m",
    rampDown: "30s",
  },
};

// ── Header helpers ──────────────────────────────────────────────────

export function authHeaders() {
  return {
    Authorization: `Bearer ${CONFIG.authToken}`,
    "Content-Type": "application/json",
  };
}

export function jsonHeaders() {
  return {
    "Content-Type": "application/json",
  };
}

// ── Response validation helper ──────────────────────────────────────

/**
 * Standard response check that validates status code and records
 * custom metrics for Grafana/Prometheus integration.
 *
 * @param {object} res - k6 HTTP response
 * @param {string} name - check label for reporting
 * @param {number} expectedStatus - expected HTTP status (default: 200)
 * @returns {boolean} whether all checks passed
 */
export function checkResponse(res, name, expectedStatus = 200) {
  const passed = check(res, {
    [`${name}: status is ${expectedStatus}`]: (r) =>
      r.status === expectedStatus,
    [`${name}: response time < 5s`]: (r) => r.timings.duration < 5000,
    [`${name}: body is not empty`]: (r) => r.body && r.body.length > 0,
  });

  // Record custom metrics
  responseTimeTrend.add(res.timings.duration, { endpoint: name });
  if (!passed) {
    errorCounter.add(1, { endpoint: name });
  }

  return passed;
}

/**
 * Generate a unique conversation/session ID for test isolation.
 * @returns {string} unique ID with k6 prefix
 */
export function uniqueId() {
  return `k6-load-${Date.now()}-${Math.random().toString(36).substring(2, 8)}`;
}
