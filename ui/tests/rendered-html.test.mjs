import assert from "node:assert/strict";
import { access, readFile } from "node:fs/promises";
import test from "node:test";

async function render() {
  const workerUrl = new URL("../dist/server/index.js", import.meta.url);
  workerUrl.searchParams.set("test", `${process.pid}-${Date.now()}`);
  const { default: worker } = await import(workerUrl.href);
  return worker.fetch(new Request("http://localhost/", { headers: { accept: "text/html" } }), { ASSETS: { fetch: async () => new Response("Not found", { status: 404 }) } }, { waitUntil() {}, passThroughOnException() {} });
}

test("server renders the WEALTH OS observation interface", async () => {
  const response = await render();
  assert.equal(response.status, 200);
  const html = await response.text();
  assert.match(html, /<title>WEALTH OS — Observe &amp; Validate<\/title>/i);
  assert.match(html, /Dynamic research runtime/);
  assert.match(html, /SYSTEM OBSERVING/);
  assert.match(html, /STRATEGY ARENA/);
  assert.match(html, /REPLAY TIME · AMERICA\/NEW_YORK/);
  assert.doesNotMatch(html, /codex-preview|Your site is taking shape|Building your site/i);
});

test("UI values are traceable to the deterministic real-data artifact and expose uncertainty", async () => {
  const data = await readFile(new URL("../app/run-data.json", import.meta.url), "utf8");
  const page = await readFile(new URL("../app/page.tsx", import.meta.url), "utf8");
  assert.match(data, /REAL HISTORICAL DATASET/);
  assert.match(data, /Yahoo Finance Chart API/);
  assert.match(data, /857fb33f23fa1dca4cdd5bf922cd743e7a60627b6e0f78ac9c4b89ea3797f755/);
  assert.match(page, /INSUFFICIENT DATA/);
  assert.match(page, /Decision View|DECISION TRACE/);
  assert.match(page, /LEDGER \/ P&amp;L|LEDGER \/ P&L/);
  assert.match(page, /FACT/);
  assert.match(page, /UNCERTAINTY/);
  assert.match(page, /RESET RUN/);
  assert.match(page, /EVENT STREAM/);
  assert.match(page, /run-data\.json/);
  assert.match(page, /aria-label="Previous event"/);
  assert.match(page, /aria-label="Next event"/);
  assert.match(page, /STEP ▶/);
  assert.doesNotMatch(page, /run-data\.ts/);
  await assert.rejects(access(new URL("../app/_sites-preview/SkeletonPreview.tsx", import.meta.url)));
});
