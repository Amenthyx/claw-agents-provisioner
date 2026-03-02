// ===================================================================
// k6-memory.js -- Load Test for Conversation Memory Service (:9096)
// ===================================================================
//
// Tests store, retrieve, and search operations on the memory service.
// Endpoints: /api/memory/conversations (POST/GET), /api/memory/search,
//            /api/memory/stats, /health.
//
// Target: P95 < 100ms at 50 req/s
// Stages: ramp up (30s) -> sustained (2m) -> ramp down (30s)
//
// Run:
//   k6 run --env K6_AUTH_TOKEN=<token> tests/load/k6-memory.js
//   k6 run --out json=results/memory.json tests/load/k6-memory.js
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

const storeErrors = new Counter("memory_store_errors");
const retrieveErrors = new Counter("memory_retrieve_errors");
const searchErrors = new Counter("memory_search_errors");
const storeLatency = new Trend("memory_store_latency", true);
const retrieveLatency = new Trend("memory_retrieve_latency", true);
const searchLatency = new Trend("memory_search_latency", true);

// ── k6 options ──────────────────────────────────────────────────────

export const options = {
  stages: [
    { duration: "30s", target: 50 },     // Ramp up to 50 VUs
    { duration: "2m", target: 50 },      // Sustained load at 50 VUs
    { duration: "30s", target: 0 },      // Ramp down
  ],

  thresholds: {
    http_req_duration: ["p(95)<100"],     // P95 < 100ms
    http_req_failed: ["rate<0.01"],       // Error rate < 1%
    memory_store_latency: ["p(95)<100"],
    memory_retrieve_latency: ["p(95)<100"],
    memory_search_latency: ["p(95)<150"], // Search allowed slightly higher
    memory_store_errors: ["count<25"],
    memory_retrieve_errors: ["count<25"],
    memory_search_errors: ["count<25"],
  },

  tags: {
    service: "memory",
    port: "9096",
    test_type: "load",
  },
};

// ── Test data ───────────────────────────────────────────────────────

const BASE = CONFIG.memoryUrl;

// Pre-generated conversation IDs for retrieve/search tests
// The store tests will populate these during the run.
const SAMPLE_MESSAGES = [
  "How do I deploy my AI agent to production?",
  "What models are available for coding tasks?",
  "Can you explain the billing system?",
  "How does the RAG pipeline work?",
  "What security features are enabled?",
  "Help me configure the router for multi-model routing.",
  "How do I set up fine-tuning with LoRA?",
  "What are the hardware requirements for local models?",
];

// ── Test scenarios ──────────────────────────────────────────────────

/**
 * Health check -- memory service availability.
 */
function testHealth() {
  const res = http.get(`${BASE}/health`, {
    headers: authHeaders(),
    tags: { endpoint: "memory_health" },
  });

  checkResponse(res, "memory_health");
}

/**
 * Store conversation -- POST /api/memory/conversations.
 * Creates a new conversation with a message.
 */
function testStoreConversation() {
  const convId = uniqueId();
  const payload = JSON.stringify({
    conversation_id: convId,
    agent_id: "k6-test-agent",
    messages: [
      {
        role: "user",
        content: SAMPLE_MESSAGES[Math.floor(Math.random() * SAMPLE_MESSAGES.length)],
        timestamp: new Date().toISOString(),
      },
      {
        role: "assistant",
        content: "This is a load test response for memory storage verification.",
        timestamp: new Date().toISOString(),
      },
    ],
  });

  const res = http.post(`${BASE}/api/memory/conversations`, payload, {
    headers: authHeaders(),
    tags: { endpoint: "memory_store" },
  });

  storeLatency.add(res.timings.duration);

  const ok = check(res, {
    "store: status 200 or 201": (r) =>
      r.status === 200 || r.status === 201,
    "store: response time < 200ms": (r) => r.timings.duration < 200,
  });

  if (!ok) storeErrors.add(1);

  return convId;
}

/**
 * Retrieve conversations -- GET /api/memory/conversations.
 * Lists existing conversations.
 */
function testRetrieveConversations() {
  const res = http.get(`${BASE}/api/memory/conversations`, {
    headers: authHeaders(),
    tags: { endpoint: "memory_retrieve" },
  });

  retrieveLatency.add(res.timings.duration);

  const ok = check(res, {
    "retrieve: status 200": (r) => r.status === 200,
    "retrieve: is JSON": (r) => {
      try {
        JSON.parse(r.body);
        return true;
      } catch (_e) {
        return false;
      }
    },
  });

  if (!ok) retrieveErrors.add(1);
}

/**
 * Search messages -- POST /api/memory/search.
 * Searches across stored conversations.
 */
function testSearchMessages() {
  const queries = [
    "deploy",
    "billing",
    "security",
    "router",
    "model",
    "configuration",
    "fine-tuning",
    "hardware",
  ];

  const payload = JSON.stringify({
    query: queries[Math.floor(Math.random() * queries.length)],
    limit: 10,
  });

  const res = http.post(`${BASE}/api/memory/search`, payload, {
    headers: authHeaders(),
    tags: { endpoint: "memory_search" },
  });

  searchLatency.add(res.timings.duration);

  const ok = check(res, {
    "search: status 200": (r) => r.status === 200,
    "search: is JSON": (r) => {
      try {
        JSON.parse(r.body);
        return true;
      } catch (_e) {
        return false;
      }
    },
  });

  if (!ok) searchErrors.add(1);
}

/**
 * Memory stats -- GET /api/memory/stats.
 */
function testMemoryStats() {
  const res = http.get(`${BASE}/api/memory/stats`, {
    headers: authHeaders(),
    tags: { endpoint: "memory_stats" },
  });

  checkResponse(res, "memory_stats");
}

// ── Main VU function ────────────────────────────────────────────────

export default function () {
  // Weighted distribution:
  //   40% store (write-heavy to test persistence)
  //   25% retrieve
  //   25% search
  //   5% stats
  //   5% health
  const rand = Math.random();

  if (rand < 0.40) {
    testStoreConversation();
  } else if (rand < 0.65) {
    testRetrieveConversations();
  } else if (rand < 0.90) {
    testSearchMessages();
  } else if (rand < 0.95) {
    testMemoryStats();
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
      `Memory health check returned ${res.status} -- test may produce errors`
    );
  }

  return { startTime: new Date().toISOString() };
}

export function teardown(data) {
  console.log(`Memory load test started at: ${data.startTime}`);
  console.log(`Memory load test completed at: ${new Date().toISOString()}`);
}
