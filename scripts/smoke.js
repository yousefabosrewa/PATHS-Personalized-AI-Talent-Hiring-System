/**
 * PATHS — k6 smoke test (PATHS-180)
 *
 * Verifies that the key API surfaces respond within budget at 1 RPS sustained.
 * Run against staging before every production deploy:
 *
 *   k6 run scripts/smoke.js \
 *       -e BASE_URL=https://api-staging.paths.ai \
 *       -e FRONTEND_URL=https://staging.paths.ai \
 *       -e RECRUITER_EMAIL=smoke@example.com \
 *       -e RECRUITER_PASSWORD=SmokeTest1!
 *
 * Pass/fail thresholds:
 *   - HTTP errors        < 1 %
 *   - p95 response time  < 500 ms   (< 200 ms for cached reads)
 *
 * Prerequisites:  k6 ≥ 0.47   https://k6.io/docs/get-started/installation/
 */

import http from "k6/http";
import { check, sleep } from "k6";
import { Rate, Trend } from "k6/metrics";

// ── Configuration ─────────────────────────────────────────────────────────
const BASE_URL      = __ENV.BASE_URL      || "http://localhost:8001";
const FRONTEND_URL  = __ENV.FRONTEND_URL  || "http://localhost:3000";
const EMAIL         = __ENV.RECRUITER_EMAIL    || "smoke@paths.local";
const PASSWORD      = __ENV.RECRUITER_PASSWORD || "SmokeTest1!";

// ── Custom metrics ────────────────────────────────────────────────────────
const errorRate   = new Rate("errors");
const loginTrend  = new Trend("login_duration");
const readTrend   = new Trend("read_duration");
const agentTrend  = new Trend("agent_trigger_duration");

// ── Test options ──────────────────────────────────────────────────────────
export const options = {
  scenarios: {
    smoke: {
      executor: "constant-arrival-rate",
      rate: 1,          // 1 iteration/second
      timeUnit: "1s",
      duration: "60s",
      preAllocatedVUs: 5,
      maxVUs: 10,
    },
  },
  thresholds: {
    // Overall error rate must stay below 1 %
    errors: ["rate<0.01"],
    // All responses (p95) under 500 ms
    http_req_duration: ["p(95)<500"],
    // Cached reads are faster — tighten the budget
    read_duration: ["p(95)<200"],
    // Agent triggers are async — just confirm they don't time out
    agent_trigger_duration: ["p(95)<500"],
    // Login
    login_duration: ["p(95)<400"],
  },
};

// ── Shared state ──────────────────────────────────────────────────────────
let token = "";
let orgId = "";

// ── Setup — runs once before the test ────────────────────────────────────
export function setup() {
  const loginRes = http.post(
    `${BASE_URL}/api/v1/auth/login`,
    JSON.stringify({ email: EMAIL, password: PASSWORD }),
    { headers: { "Content-Type": "application/json" } }
  );

  const ok = check(loginRes, {
    "setup: login 200": (r) => r.status === 200,
    "setup: token present": (r) => {
      try { return Boolean(JSON.parse(r.body).access_token); }
      catch { return false; }
    },
  });

  if (!ok) {
    console.error(`Setup login failed: ${loginRes.status} — ${loginRes.body}`);
    return { token: "", orgId: "" };
  }

  const body = JSON.parse(loginRes.body);
  return { token: body.access_token, orgId: body.organization_id || "" };
}

// ── Main VU function ──────────────────────────────────────────────────────
export default function (data) {
  const authHeaders = {
    headers: {
      Authorization: `Bearer ${data.token}`,
      "Content-Type": "application/json",
      "X-Correlation-ID": `smoke-${Date.now()}`,
    },
  };

  // 1. Health check (unauthenticated)
  {
    const res = http.get(`${BASE_URL}/api/v1/health`, { tags: { name: "health" } });
    check(res, { "health 200": (r) => r.status === 200 }) || errorRate.add(1);
    readTrend.add(res.timings.duration);
  }

  sleep(0.2);

  // 2. Auth — /me (cached read)
  if (data.token) {
    const res = http.get(`${BASE_URL}/api/v1/auth/me`, authHeaders);
    const ok = check(res, { "me 200": (r) => r.status === 200 });
    ok || errorRate.add(1);
    readTrend.add(res.timings.duration);
  }

  sleep(0.2);

  // 3. Jobs list (cached read — tests DB round-trip)
  if (data.token && data.orgId) {
    const res = http.get(
      `${BASE_URL}/api/v1/jobs?limit=10`,
      { ...authHeaders, tags: { name: "jobs_list" } }
    );
    const ok = check(res, {
      "jobs list 200": (r) => r.status === 200,
      "jobs list is array": (r) => {
        try { return Array.isArray(JSON.parse(r.body)); }
        catch { return false; }
      },
    });
    ok || errorRate.add(1);
    readTrend.add(res.timings.duration);
  }

  sleep(0.2);

  // 4. Candidates list
  if (data.token) {
    const res = http.get(
      `${BASE_URL}/api/v1/candidates?limit=10`,
      { ...authHeaders, tags: { name: "candidates_list" } }
    );
    const ok = check(res, { "candidates 200/403": (r) => [200, 403].includes(r.status) });
    ok || errorRate.add(1);
    readTrend.add(res.timings.duration);
  }

  sleep(0.2);

  // 5. Dashboard stats
  if (data.token) {
    const res = http.get(
      `${BASE_URL}/api/v1/dashboard/stats`,
      { ...authHeaders, tags: { name: "dashboard_stats" } }
    );
    const ok = check(res, { "dashboard 200/403": (r) => [200, 403].includes(r.status) });
    ok || errorRate.add(1);
    readTrend.add(res.timings.duration);
  }

  sleep(0.2);

  // 6. Frontend marketing page (GET /)
  {
    const res = http.get(FRONTEND_URL, { tags: { name: "marketing_home" } });
    const ok = check(res, { "frontend / 200": (r) => r.status === 200 });
    ok || errorRate.add(1);
    readTrend.add(res.timings.duration);
  }

  sleep(0.2);

  // 7. Frontend pricing page
  {
    const res = http.get(`${FRONTEND_URL}/pricing`, { tags: { name: "marketing_pricing" } });
    const ok = check(res, { "frontend /pricing 200": (r) => r.status === 200 });
    ok || errorRate.add(1);
    readTrend.add(res.timings.duration);
  }

  sleep(0.2);
}

// ── Teardown — print summary ──────────────────────────────────────────────
export function teardown(data) {
  console.log(`Smoke test finished. Token was ${data.token ? "present" : "MISSING"}.`);
}
