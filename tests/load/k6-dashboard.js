// ===================================================================
// k6-dashboard.js -- Load Test for Fleet Dashboard Service (:9099)
// ===================================================================
//
// Tests status, agents, strategy, and monitoring endpoints.
// Endpoints: /api/status, /api/agents, /api/strategy, /api/billing,
//            /api/security, /api/monitoring, /api/config, /health.
//
// Target: P95 < 300ms at 30 req/s
// Stages: ramp up (30s) -> sustained (2m) -> ramp down (30s)
//
// Run:
//   k6 run --env K6_AUTH_TOKEN=<token> tests/load/k6-dashboard.js
//   k6 run --out json=results/dashboard.json tests/load/k6-dashboard.js
// ===================================================================

import http from "k6/http";
import { check, sleep } from "k6";
import { Counter, Trend } from "k6/metrics";
import {
  CONFIG,
  authHeaders,
  checkResponse,
} from "./k6-config.js";

// ── Custom metrics ──────────────────────────────────────────────────

const statusErrors = new Counter("dashboard_status_errors");
const agentsErrors = new Counter("dashboard_agents_errors");
const strategyErrors = new Counter("dashboard_strategy_errors");
const statusLatency = new Trend("dashboard_status_latency", true);
const agentsLatency = new Trend("dashboard_agents_latency", true);
const strategyLatency = new Trend("dashboard_strategy_latency", true);
const pageLoadLatency = new Trend("dashboard_page_load_latency", true);

// ── k6 options ──────────────────────────────────────────────────────

export const options = {
  stages: [
    { duration: "30s", target: 30 },     // Ramp up to 30 VUs
    { duration: "2m", target: 30 },      // Sustained load at 30 VUs
    { duration: "30s", target: 0 },      // Ramp down
  ],

  thresholds: {
    http_req_duration: ["p(95)<300"],     // P95 < 300ms
    http_req_failed: ["rate<0.01"],       // Error rate < 1%
    dashboard_status_latency: ["p(95)<300"],
    dashboard_agents_latency: ["p(95)<300"],
    dashboard_strategy_latency: ["p(95)<300"],
    dashboard_status_errors: ["count<15"],
    dashboard_agents_errors: ["count<15"],
    dashboard_strategy_errors: ["count<15"],
  },

  tags: {
    service: "dashboard",
    port: "9099",
    test_type: "load",
  },
};

// ── Test data ───────────────────────────────────────────────────────

const BASE = CONFIG.dashboardUrl;

// ── Test scenarios ──────────────────────────────────────────────────

/**
 * Dashboard index page -- GET / (HTML).
 * Simulates users loading the dashboard UI.
 */
function testPageLoad() {
  const res = http.get(`${BASE}/`, {
    headers: { Authorization: `Bearer ${CONFIG.authToken}` },
    tags: { endpoint: "dashboard_page" },
  });

  pageLoadLatency.add(res.timings.duration);

  check(res, {
    "page: status 200": (r) => r.status === 200,
    "page: has HTML content": (r) =>
      r.body && r.body.includes("<!DOCTYPE html") || r.body.includes("<html"),
  });
}

/**
 * API status -- GET /api/status.
 * Returns overall system status summary.
 */
function testApiStatus() {
  const res = http.get(`${BASE}/api/status`, {
    headers: authHeaders(),
    tags: { endpoint: "dashboard_status" },
  });

  statusLatency.add(res.timings.duration);

  const ok = check(res, {
    "status: 200": (r) => r.status === 200,
    "status: is JSON": (r) => {
      try {
        JSON.parse(r.body);
        return true;
      } catch (_e) {
        return false;
      }
    },
  });

  if (!ok) statusErrors.add(1);
}

/**
 * API agents -- GET /api/agents.
 * Returns list of registered agents and their status.
 */
function testApiAgents() {
  const res = http.get(`${BASE}/api/agents`, {
    headers: authHeaders(),
    tags: { endpoint: "dashboard_agents" },
  });

  agentsLatency.add(res.timings.duration);

  const ok = check(res, {
    "agents: 200": (r) => r.status === 200,
    "agents: is JSON": (r) => {
      try {
        JSON.parse(r.body);
        return true;
      } catch (_e) {
        return false;
      }
    },
  });

  if (!ok) agentsErrors.add(1);
}

/**
 * API strategy -- GET /api/strategy.
 * Returns the current routing strategy configuration.
 */
function testApiStrategy() {
  const res = http.get(`${BASE}/api/strategy`, {
    headers: authHeaders(),
    tags: { endpoint: "dashboard_strategy" },
  });

  strategyLatency.add(res.timings.duration);

  const ok = check(res, {
    "strategy: 200": (r) => r.status === 200,
    "strategy: is JSON": (r) => {
      try {
        JSON.parse(r.body);
        return true;
      } catch (_e) {
        return false;
      }
    },
  });

  if (!ok) strategyErrors.add(1);
}

/**
 * API billing -- GET /api/billing.
 * Returns billing/cost overview.
 */
function testApiBilling() {
  const res = http.get(`${BASE}/api/billing`, {
    headers: authHeaders(),
    tags: { endpoint: "dashboard_billing" },
  });

  checkResponse(res, "dashboard_billing");
}

/**
 * API security -- GET /api/security.
 * Returns security posture overview.
 */
function testApiSecurity() {
  const res = http.get(`${BASE}/api/security`, {
    headers: authHeaders(),
    tags: { endpoint: "dashboard_security" },
  });

  checkResponse(res, "dashboard_security");
}

/**
 * API monitoring -- GET /api/monitoring.
 * Returns system monitoring metrics.
 */
function testApiMonitoring() {
  const res = http.get(`${BASE}/api/monitoring`, {
    headers: authHeaders(),
    tags: { endpoint: "dashboard_monitoring" },
  });

  checkResponse(res, "dashboard_monitoring");
}

/**
 * API config -- GET /api/config.
 * Returns system configuration (sanitized).
 */
function testApiConfig() {
  const res = http.get(`${BASE}/api/config`, {
    headers: authHeaders(),
    tags: { endpoint: "dashboard_config" },
  });

  checkResponse(res, "dashboard_config");
}

/**
 * Health check -- dashboard service availability.
 */
function testHealth() {
  const res = http.get(`${BASE}/health`, {
    headers: authHeaders(),
    tags: { endpoint: "dashboard_health" },
  });

  checkResponse(res, "dashboard_health");
}

// ── Main VU function ────────────────────────────────────────────────

export default function () {
  // Weighted distribution simulating typical dashboard usage:
  //   15% page load (initial visits / refreshes)
  //   20% status (most polled endpoint, auto-refresh)
  //   15% agents (second most polled)
  //   15% strategy
  //   10% billing
  //   10% monitoring
  //   5% security
  //   5% config
  //   5% health
  const rand = Math.random();

  if (rand < 0.15) {
    testPageLoad();
  } else if (rand < 0.35) {
    testApiStatus();
  } else if (rand < 0.50) {
    testApiAgents();
  } else if (rand < 0.65) {
    testApiStrategy();
  } else if (rand < 0.75) {
    testApiBilling();
  } else if (rand < 0.85) {
    testApiMonitoring();
  } else if (rand < 0.90) {
    testApiSecurity();
  } else if (rand < 0.95) {
    testApiConfig();
  } else {
    testHealth();
  }

  sleep(Math.random() * 0.5 + 0.1);
}

// ── Lifecycle hooks ─────────────────────────────────────────────────

export function setup() {
  const res = http.get(`${BASE}/health`, {
    headers: authHeaders(),
    timeout: "10s",
  });

  if (res.status !== 200) {
    console.warn(
      `Dashboard health check returned ${res.status} -- test may produce errors`
    );
  }

  return { startTime: new Date().toISOString() };
}

export function teardown(data) {
  console.log(`Dashboard load test started at: ${data.startTime}`);
  console.log(`Dashboard load test completed at: ${new Date().toISOString()}`);
}
