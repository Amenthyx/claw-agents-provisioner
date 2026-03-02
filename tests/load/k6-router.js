// ===================================================================
// k6-router.js -- Load Test for Model Router Service (:9095)
// ===================================================================
//
// Tests the /v1/chat/completions endpoint (OpenAI-compatible gateway)
// and supporting endpoints (/health, /v1/models, /api/router/status).
//
// Target: P95 < 200ms at 100 req/s
// Stages: ramp up (30s) -> sustained (2m) -> ramp down (30s)
//
// Run:
//   k6 run --env K6_AUTH_TOKEN=<token> tests/load/k6-router.js
//   k6 run --out json=results/router.json tests/load/k6-router.js
// ===================================================================

import http from "k6/http";
import { check, sleep } from "k6";
import { Counter, Trend } from "k6/metrics";
import {
  CONFIG,
  authHeaders,
  checkResponse,
  uniqueId,
} from "./k6-config.js";

// ── Custom metrics ──────────────────────────────────────────────────

const chatCompletionErrors = new Counter("router_chat_errors");
const chatCompletionLatency = new Trend("router_chat_latency", true);
const healthErrors = new Counter("router_health_errors");
const modelsErrors = new Counter("router_models_errors");

// ── k6 options ──────────────────────────────────────────────────────

export const options = {
  stages: [
    { duration: "30s", target: 100 },   // Ramp up to 100 VUs
    { duration: "2m", target: 100 },     // Sustained load at 100 VUs
    { duration: "30s", target: 0 },      // Ramp down
  ],

  thresholds: {
    http_req_duration: ["p(95)<200"],     // P95 < 200ms
    http_req_failed: ["rate<0.01"],       // Error rate < 1%
    router_chat_latency: ["p(95)<200"],   // Chat completions P95 < 200ms
    router_chat_errors: ["count<50"],     // Max 50 chat errors
  },

  tags: {
    service: "router",
    port: "9095",
    test_type: "load",
  },
};

// ── Test scenarios ──────────────────────────────────────────────────

const BASE = CONFIG.routerUrl;

/**
 * Health check -- lightweight, should always be fast.
 */
function testHealth() {
  const res = http.get(`${BASE}/health`, {
    headers: authHeaders(),
    tags: { endpoint: "health" },
  });

  const ok = check(res, {
    "health: status 200": (r) => r.status === 200,
    "health: has status field": (r) => {
      try {
        return JSON.parse(r.body).status !== undefined;
      } catch (_e) {
        return false;
      }
    },
  });

  if (!ok) healthErrors.add(1);
}

/**
 * List models -- GET /v1/models (OpenAI-compatible).
 */
function testListModels() {
  const res = http.get(`${BASE}/v1/models`, {
    headers: authHeaders(),
    tags: { endpoint: "models" },
  });

  const ok = check(res, {
    "models: status 200": (r) => r.status === 200,
    "models: has data array": (r) => {
      try {
        return Array.isArray(JSON.parse(r.body).data);
      } catch (_e) {
        return false;
      }
    },
  });

  if (!ok) modelsErrors.add(1);
}

/**
 * Chat completions -- POST /v1/chat/completions (core endpoint).
 * This is the primary load target.
 */
function testChatCompletions() {
  const payload = JSON.stringify({
    model: "auto",
    messages: [
      {
        role: "user",
        content: `k6 load test message ${uniqueId()}`,
      },
    ],
    max_tokens: 50,
    temperature: 0.7,
  });

  const res = http.post(`${BASE}/v1/chat/completions`, payload, {
    headers: authHeaders(),
    tags: { endpoint: "chat_completions" },
  });

  chatCompletionLatency.add(res.timings.duration);

  const ok = check(res, {
    "chat: status 200": (r) => r.status === 200,
    "chat: has choices": (r) => {
      try {
        const body = JSON.parse(r.body);
        return body.choices && body.choices.length > 0;
      } catch (_e) {
        return false;
      }
    },
    "chat: has usage": (r) => {
      try {
        return JSON.parse(r.body).usage !== undefined;
      } catch (_e) {
        return false;
      }
    },
  });

  if (!ok) chatCompletionErrors.add(1);
}

/**
 * Router status -- GET /api/router/status.
 */
function testRouterStatus() {
  const res = http.get(`${BASE}/api/router/status`, {
    headers: authHeaders(),
    tags: { endpoint: "router_status" },
  });

  checkResponse(res, "router_status");
}

// ── Main VU function ────────────────────────────────────────────────

export default function () {
  // Weighted distribution: chat completions are 70% of traffic
  const rand = Math.random();

  if (rand < 0.70) {
    testChatCompletions();
  } else if (rand < 0.85) {
    testHealth();
  } else if (rand < 0.95) {
    testListModels();
  } else {
    testRouterStatus();
  }

  // Small random sleep to avoid lock-step behavior
  sleep(Math.random() * 0.5 + 0.1);
}

// ── Lifecycle hooks ─────────────────────────────────────────────────

export function setup() {
  // Verify router is reachable before starting load test
  const res = http.get(`${BASE}/health`, {
    headers: authHeaders(),
    timeout: "10s",
  });

  if (res.status !== 200) {
    console.warn(
      `Router health check returned ${res.status} -- test may produce errors`
    );
  }

  return { startTime: new Date().toISOString() };
}

export function teardown(data) {
  console.log(`Router load test started at: ${data.startTime}`);
  console.log(`Router load test completed at: ${new Date().toISOString()}`);
}
