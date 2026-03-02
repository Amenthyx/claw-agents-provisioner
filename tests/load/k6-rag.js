// ===================================================================
// k6-rag.js -- Load Test for RAG Pipeline Service (:9097)
// ===================================================================
//
// Tests ingest and search operations on the RAG pipeline.
// Endpoints: /api/rag/ingest (POST), /api/rag/search (POST),
//            /v1/search (POST), /api/rag/status (GET), /health.
//
// Target: P95 < 500ms at 50 req/s
// Stages: ramp up (30s) -> sustained (2m) -> ramp down (30s)
//
// Run:
//   k6 run --env K6_AUTH_TOKEN=<token> tests/load/k6-rag.js
//   k6 run --out json=results/rag.json tests/load/k6-rag.js
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

const ingestErrors = new Counter("rag_ingest_errors");
const searchErrors = new Counter("rag_search_errors");
const ingestLatency = new Trend("rag_ingest_latency", true);
const searchLatency = new Trend("rag_search_latency", true);

// ── k6 options ──────────────────────────────────────────────────────

export const options = {
  stages: [
    { duration: "30s", target: 50 },     // Ramp up to 50 VUs
    { duration: "2m", target: 50 },      // Sustained load at 50 VUs
    { duration: "30s", target: 0 },      // Ramp down
  ],

  thresholds: {
    http_req_duration: ["p(95)<500"],     // P95 < 500ms
    http_req_failed: ["rate<0.01"],       // Error rate < 1%
    rag_ingest_latency: ["p(95)<500"],
    rag_search_latency: ["p(95)<500"],
    rag_ingest_errors: ["count<25"],
    rag_search_errors: ["count<25"],
  },

  tags: {
    service: "rag",
    port: "9097",
    test_type: "load",
  },
};

// ── Test data ───────────────────────────────────────────────────────

const BASE = CONFIG.ragUrl;

const SAMPLE_DOCUMENTS = [
  {
    title: "Deployment Guide",
    content:
      "To deploy a Claw agent, run `claw.sh deploy` with the appropriate " +
      "configuration file. Ensure Docker is running and all environment " +
      "variables are set via the .env file.",
  },
  {
    title: "Router Configuration",
    content:
      "The model router supports multi-provider routing with automatic " +
      "failover. Configure primary and fallback models in strategy.json " +
      "for each task type: coding, simple_chat, analysis, creative.",
  },
  {
    title: "Security Best Practices",
    content:
      "Enable bearer token authentication on all HTTP endpoints. Configure " +
      "rate limiting via CLAW_RATE_LIMIT_PER_MINUTE. Use the vault for " +
      "API key encryption. Enable audit logging for compliance.",
  },
  {
    title: "Memory Service Architecture",
    content:
      "The conversation memory service persists chat history using SQLite " +
      "with full-text search. Conversations are linked to agents via " +
      "agent_id. The search API supports fuzzy matching.",
  },
  {
    title: "Fine-tuning with LoRA",
    content:
      "Claw supports LoRA and QLoRA fine-tuning for local models. " +
      "Datasets are stored in finetune/datasets/ with metadata.json " +
      "per dataset. Use the adapter selector for task-specific matching.",
  },
  {
    title: "Billing and Cost Tracking",
    content:
      "All LLM API calls are tracked with token counts and cost estimates. " +
      "Set budget alerts via the billing module. Cloud costs use provider " +
      "pricing; local costs estimate GPU electricity usage.",
  },
];

const SEARCH_QUERIES = [
  "How do I deploy an agent?",
  "Configure model routing",
  "Security authentication setup",
  "Memory service search API",
  "Fine-tuning LoRA configuration",
  "Billing cost tracking alerts",
  "Docker deployment steps",
  "Rate limiting configuration",
  "API key encryption vault",
  "Hardware requirements GPU",
];

// ── Test scenarios ──────────────────────────────────────────────────

/**
 * Health check -- RAG service availability.
 */
function testHealth() {
  const res = http.get(`${BASE}/health`, {
    headers: authHeaders(),
    tags: { endpoint: "rag_health" },
  });

  checkResponse(res, "rag_health");
}

/**
 * RAG status -- GET /api/rag/status.
 */
function testRagStatus() {
  const res = http.get(`${BASE}/api/rag/status`, {
    headers: authHeaders(),
    tags: { endpoint: "rag_status" },
  });

  checkResponse(res, "rag_status");
}

/**
 * Ingest document -- POST /api/rag/ingest.
 * Adds a document to the RAG index.
 */
function testIngest() {
  const doc =
    SAMPLE_DOCUMENTS[Math.floor(Math.random() * SAMPLE_DOCUMENTS.length)];

  const payload = JSON.stringify({
    document_id: uniqueId(),
    title: doc.title,
    content: doc.content,
    metadata: {
      source: "k6-load-test",
      timestamp: new Date().toISOString(),
      category: "documentation",
    },
  });

  const res = http.post(`${BASE}/api/rag/ingest`, payload, {
    headers: authHeaders(),
    tags: { endpoint: "rag_ingest" },
  });

  ingestLatency.add(res.timings.duration);

  const ok = check(res, {
    "ingest: status 200 or 201": (r) =>
      r.status === 200 || r.status === 201,
    "ingest: response time < 1s": (r) => r.timings.duration < 1000,
  });

  if (!ok) ingestErrors.add(1);
}

/**
 * Search -- POST /api/rag/search.
 * Performs semantic search on the RAG index.
 */
function testSearch() {
  const query =
    SEARCH_QUERIES[Math.floor(Math.random() * SEARCH_QUERIES.length)];

  const payload = JSON.stringify({
    query: query,
    top_k: 5,
    min_score: 0.1,
  });

  const res = http.post(`${BASE}/api/rag/search`, payload, {
    headers: authHeaders(),
    tags: { endpoint: "rag_search" },
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
    "search: response time < 1s": (r) => r.timings.duration < 1000,
  });

  if (!ok) searchErrors.add(1);
}

/**
 * V1 Search -- POST /v1/search (OpenAI-compatible search endpoint).
 */
function testV1Search() {
  const query =
    SEARCH_QUERIES[Math.floor(Math.random() * SEARCH_QUERIES.length)];

  const payload = JSON.stringify({
    query: query,
    max_results: 3,
  });

  const res = http.post(`${BASE}/v1/search`, payload, {
    headers: authHeaders(),
    tags: { endpoint: "rag_v1_search" },
  });

  searchLatency.add(res.timings.duration);

  const ok = check(res, {
    "v1_search: status 200": (r) => r.status === 200,
    "v1_search: is JSON": (r) => {
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

// ── Main VU function ────────────────────────────────────────────────

export default function () {
  // Weighted distribution:
  //   30% ingest (simulate ongoing document ingestion)
  //   40% search (primary read operation)
  //   15% v1 search (alternative API)
  //   10% status
  //   5% health
  const rand = Math.random();

  if (rand < 0.30) {
    testIngest();
  } else if (rand < 0.70) {
    testSearch();
  } else if (rand < 0.85) {
    testV1Search();
  } else if (rand < 0.95) {
    testRagStatus();
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
      `RAG health check returned ${res.status} -- test may produce errors`
    );
  }

  // Seed a few documents so search tests have data to find
  for (let i = 0; i < 3; i++) {
    const doc = SAMPLE_DOCUMENTS[i];
    http.post(
      `${BASE}/api/rag/ingest`,
      JSON.stringify({
        document_id: `k6-seed-${i}`,
        title: doc.title,
        content: doc.content,
        metadata: { source: "k6-seed" },
      }),
      { headers: authHeaders() }
    );
  }

  return { startTime: new Date().toISOString() };
}

export function teardown(data) {
  console.log(`RAG load test started at: ${data.startTime}`);
  console.log(`RAG load test completed at: ${new Date().toISOString()}`);
}
