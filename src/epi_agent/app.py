from __future__ import annotations

import json
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from . import __version__
from .models import EventInput
from .service import EPIAgentService


class EPIRequestHandler(BaseHTTPRequestHandler):
    service = EPIAgentService()

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/":
            self._send_html(_dashboard_html())
            return
        if parsed.path == "/api/health":
            self._send_json({"status": "ok", "version": __version__})
            return
        if parsed.path == "/api/events":
            params = parse_qs(parsed.query)
            limit = int(params.get("limit", ["50"])[0])
            self._send_json({"events": self.service.recent_cards(limit=limit)})
            return
        if parsed.path == "/api/macro/releases":
            params = parse_qs(parsed.query)
            limit = int(params.get("limit", ["20"])[0])
            self._send_json({"releases": self.service.recent_macro_releases(limit=limit)})
            return
        if parsed.path == "/api/pricing/signals":
            params = parse_qs(parsed.query)
            limit = int(params.get("limit", ["20"])[0])
            self._send_json({"signals": self.service.pricing_signals(limit=limit)})
            return
        if parsed.path == "/api/dashboard":
            params = parse_qs(parsed.query)
            tab = params.get("tab", ["all"])[0]
            sort = params.get("sort", ["bias_desc"])[0]
            limit = int(params.get("limit", ["80"])[0])
            self._send_json(self.service.dashboard(tab=tab, limit=limit, sort=sort))
            return
        self._send_json({"error": "not_found"}, status=HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/api/markets/sync":
            payload = self._read_json()
            tab = payload.get("tab", "all")
            limit_per_tag = int(payload.get("limit_per_tag", 30))
            enrich_orderbook = bool(payload.get("enrich_orderbook", False))
            max_orderbooks = int(payload.get("max_orderbooks", 25))
            result = self.service.sync_markets(
                tab=tab,
                limit_per_tag=limit_per_tag,
                enrich_orderbook=enrich_orderbook,
                max_orderbooks=max_orderbooks,
            )
            self._send_json(result, status=HTTPStatus.CREATED)
            return

        if parsed.path == "/api/macro/releases":
            try:
                result = self.service.submit_macro_release(self._read_json())
            except KeyError:
                self._send_json({"error": "event_name is required"}, status=HTTPStatus.BAD_REQUEST)
                return
            except Exception as exc:  # noqa: BLE001 - boundary handler should return JSON.
                self._send_json({"error": str(exc)}, status=HTTPStatus.BAD_REQUEST)
                return
            self._send_json(result, status=HTTPStatus.CREATED)
            return

        if parsed.path == "/api/macro/sync":
            payload = self._read_json()
            try:
                result = self.service.sync_macro_calendar(
                    country=payload.get("country", "United States"),
                    limit=int(payload.get("limit", 50)),
                )
            except Exception as exc:  # noqa: BLE001 - optional upstream boundary.
                self._send_json({"error": str(exc)}, status=HTTPStatus.BAD_GATEWAY)
                return
            self._send_json(result, status=HTTPStatus.CREATED)
            return

        if parsed.path != "/api/events":
            self._send_json({"error": "not_found"}, status=HTTPStatus.NOT_FOUND)
            return

        try:
            payload = self._read_json()
            event = EventInput(
                summary=payload["summary"],
                source_type=payload.get("source_type", "manual"),
                source_url=payload.get("source_url"),
            )
            live_markets = bool(payload.get("live_markets", True))
            card = self.service.submit_event(event, live_markets=live_markets)
        except KeyError:
            self._send_json({"error": "summary is required"}, status=HTTPStatus.BAD_REQUEST)
            return
        except Exception as exc:  # noqa: BLE001 - boundary handler should return JSON.
            self._send_json({"error": str(exc)}, status=HTTPStatus.BAD_GATEWAY)
            return

        self._send_json(card.to_dict(), status=HTTPStatus.CREATED)

    def log_message(self, format: str, *args: object) -> None:
        return

    def _read_json(self) -> dict:
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length).decode("utf-8")
        return json.loads(body or "{}")

    def _send_json(self, payload: dict, status: HTTPStatus = HTTPStatus.OK) -> None:
        body = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_html(self, html: str) -> None:
        body = html.encode("utf-8")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def run(host: str = "127.0.0.1", port: int = 8080) -> None:
    server = ThreadingHTTPServer((host, port), EPIRequestHandler)
    print(f"EPI Agent MVP running at http://{host}:{port}")
    server.serve_forever()


def _dashboard_html() -> str:
    css = Path(__file__).with_name("dashboard.css").read_text(encoding="utf-8")
    html = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>EPI Agent MVP</title>
  <style>__CSS__</style>
</head>
<body>
  <main class="shell">
    <section class="topbar">
      <div>
        <p class="eyebrow">OKX Onchain OS Research Agent</p>
        <h1>Market Pricing Dashboard</h1>
      </div>
      <div class="top-actions">
        <label><input id="deep-book" type="checkbox"> Deep book</label>
        <button id="sync-markets" type="button">Sync Markets</button>
        <button id="refresh" type="button" class="secondary">Refresh</button>
      </div>
    </section>

    <nav id="market-tabs" class="tabs"></nav>

    <section class="summary-grid">
      <article class="metric"><span>Total markets</span><strong id="metric-total">0</strong></article>
      <article class="metric"><span>Bias candidates</span><strong id="metric-biased">0</strong></article>
      <article class="metric"><span>Severe / Moderate</span><strong id="metric-risk">0 / 0</strong></article>
      <article class="metric"><span>Structure flags</span><strong id="metric-structure">0</strong></article>
      <article class="metric"><span>Deep books</span><strong id="metric-books">0</strong></article>
      <article class="metric"><span>Ending soon</span><strong id="metric-ending">0</strong></article>
      <article class="metric"><span>Model gaps</span><strong id="metric-model-gaps">0</strong></article>
      <article class="metric"><span>Avg confidence</span><strong id="metric-confidence">0%</strong></article>
    </section>

    <section class="content-grid">
      <div class="market-panel">
        <div class="section-title">
          <div>
            <h2>Pricing Bias Candidates</h2>
            <p id="sync-state" class="subtle">Sync Polymarket markets to populate the dashboard.</p>
          </div>
          <select id="bucket-filter">
            <option value="">All buckets</option>
            <option value="severe">Severe</option>
            <option value="moderate">Moderate</option>
            <option value="watch">Watch</option>
            <option value="none">None</option>
          </select>
          <select id="sort-select">
            <option value="bias_desc">Bias score</option>
            <option value="structure_flags">Structure flags</option>
            <option value="depth_low">Book depth low</option>
            <option value="depth_imbalance">Depth imbalance</option>
            <option value="spread_desc">Spread high</option>
            <option value="liquidity_asc">Liquidity low</option>
            <option value="liquidity_desc">Liquidity high</option>
            <option value="ending_soon">Ending soon</option>
            <option value="confidence_asc">Confidence low</option>
            <option value="benchmark_desc">Benchmark high</option>
            <option value="benchmark_asc">Benchmark low</option>
            <option value="volume_desc">Volume high</option>
          </select>
        </div>
        <div class="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Market</th>
                <th>Benchmark</th>
                <th>Spread</th>
                <th>Depth</th>
                <th>Liquidity</th>
                <th>Bucket</th>
                <th>Ends</th>
              </tr>
            </thead>
            <tbody id="market-rows"></tbody>
          </table>
        </div>
      </div>

      <aside class="side-panel">
        <section>
          <h2>Ending Soon</h2>
          <div id="ending-soon" class="mini-list"></div>
        </section>
        <section>
          <h2>Sources & Logic</h2>
          <dl class="logic-list">
            <div><dt>Live source</dt><dd>Polymarket Gamma API</dd></div>
            <div><dt>Benchmark</dt><dd>CLOB midpoint when synced, then bid/ask midpoint, outcome price, last trade</dd></div>
            <div><dt>Bias now</dt><dd>spread, liquidity, depth, volume, staleness, ending soon, missing price</dd></div>
            <div><dt>Fair pricing</dt><dd>macro surprise + market sensitivity -> log-odds fair probability</dd></div>
          </dl>
        </section>
        <section>
          <h2>Macro Release Lab</h2>
          <form id="macro-form" class="stack-form">
            <input id="macro-name" required placeholder="Release name">
            <div class="field-grid three">
              <input id="macro-actual" type="number" step="0.0001" required placeholder="Actual">
              <input id="macro-forecast" type="number" step="0.0001" required placeholder="Forecast">
              <input id="macro-previous" type="number" step="0.0001" placeholder="Previous">
            </div>
            <div class="field-grid two">
              <input id="macro-benchmark" type="number" min="0.01" max="0.99" step="0.001" placeholder="Benchmark 0-1">
              <select id="macro-direction">
                <option value="1">Positive to YES</option>
                <option value="-1">Negative to YES</option>
                <option value="0">Neutral</option>
              </select>
            </div>
            <div class="field-grid three">
              <input id="macro-sensitivity" type="number" min="0" max="2" step="0.05" value="0.35" placeholder="Sensitivity">
              <input id="macro-reliability" type="number" min="0" max="1" step="0.05" value="0.8" placeholder="Reliability">
              <input id="macro-std" type="number" min="0" step="0.0001" placeholder="Std">
            </div>
            <button type="submit">Price Macro</button>
          </form>
          <div id="macro-estimate" class="estimate-box"></div>
        </section>
        <section>
          <h2>Recent Macro</h2>
          <div id="macro-releases" class="mini-list"></div>
        </section>
        <section>
          <h2>Manual Event Lab</h2>
      <form id="event-form">
        <textarea id="summary" required placeholder="Paste an event: CPI came in higher than expected; Fed cut probabilities fell..."></textarea>
        <div class="controls">
          <select id="source-type">
            <option value="manual">manual</option>
            <option value="news">news</option>
            <option value="official">official</option>
            <option value="economic_calendar">economic_calendar</option>
            <option value="polling">polling</option>
            <option value="government">government</option>
            <option value="social">social</option>
          </select>
              <label><input id="live-markets" type="checkbox" checked> Live Polymarket</label>
          <button type="submit">Analyze</button>
        </div>
      </form>
        </section>
      </aside>
    </section>

    <section>
      <div class="section-title">
        <h2>Macro Pricing Signals</h2>
      </div>
      <div id="pricing-signals" class="cards signal-cards"></div>
    </section>

    <section>
      <div class="section-title">
        <h2>Research Journal</h2>
      </div>
      <div id="events" class="cards compact"></div>
    </section>
  </main>
  <script>
    let selectedTab = "all";
    let dashboardData = null;

    const form = document.querySelector("#event-form");
    const macroForm = document.querySelector("#macro-form");
    const events = document.querySelector("#events");
    const refresh = document.querySelector("#refresh");
    const syncMarkets = document.querySelector("#sync-markets");
    const tabs = document.querySelector("#market-tabs");
    const bucketFilter = document.querySelector("#bucket-filter");
    const sortSelect = document.querySelector("#sort-select");
    const deepBook = document.querySelector("#deep-book");
    const marketRows = document.querySelector("#market-rows");
    const endingSoon = document.querySelector("#ending-soon");
    const syncState = document.querySelector("#sync-state");
    const macroReleases = document.querySelector("#macro-releases");
    const macroEstimate = document.querySelector("#macro-estimate");
    const pricingSignals = document.querySelector("#pricing-signals");

    async function loadDashboard() {
      const res = await fetch(`/api/dashboard?tab=${selectedTab}&sort=${sortSelect.value}&limit=120`);
      dashboardData = await res.json();
      renderTabs(dashboardData.tabs || []);
      renderSummary(dashboardData.summary || {});
      renderMarkets();
      renderEndingSoon(dashboardData.ending_soon || []);
      renderEvents(dashboardData.recent_events || []);
      renderMacroReleases(dashboardData.recent_macro_releases || []);
      renderPricingSignals(dashboardData.pricing_signals || []);
      syncState.textContent = dashboardData.latest_sync
        ? `Latest market sync: ${formatDate(dashboardData.latest_sync)}`
        : "Sync Polymarket markets to populate the dashboard.";
    }

    function pct(value) {
      return value === null || value === undefined ? "n/a" : `${(value * 100).toFixed(1)}%`;
    }

    function money(value) {
      if (value === null || value === undefined) return "n/a";
      if (value >= 1000000) return `$${(value / 1000000).toFixed(1)}m`;
      if (value >= 1000) return `$${(value / 1000).toFixed(1)}k`;
      return `$${Number(value).toFixed(0)}`;
    }

    function formatDate(value) {
      if (!value) return "n/a";
      return new Date(value).toLocaleString();
    }

    function shortDate(value) {
      if (!value) return "n/a";
      return new Date(value).toLocaleDateString(undefined, { month: "short", day: "numeric" });
    }

    function renderTabs(items) {
      tabs.innerHTML = items.map(tab => `<button class="${tab.id === selectedTab ? "active" : ""}" data-tab="${tab.id}" type="button">${tab.label}</button>`).join("");
    }

    function renderSummary(summary) {
      const buckets = summary.bias_buckets || {};
      document.querySelector("#metric-total").textContent = summary.total_markets || 0;
      document.querySelector("#metric-biased").textContent = summary.bias_candidates || 0;
      document.querySelector("#metric-risk").textContent = `${buckets.severe || 0} / ${buckets.moderate || 0}`;
      document.querySelector("#metric-structure").textContent = summary.structure_flags || 0;
      document.querySelector("#metric-books").textContent = summary.orderbook_markets || 0;
      document.querySelector("#metric-ending").textContent = summary.ending_soon || 0;
      document.querySelector("#metric-model-gaps").textContent = dashboardData?.pricing_signal_summary?.actionable || 0;
      document.querySelector("#metric-confidence").textContent = pct(summary.avg_benchmark_confidence || 0);
    }

    function renderMarkets() {
      const bucket = bucketFilter.value;
      const markets = (dashboardData?.markets || []).filter(m => !bucket || m.bias_bucket === bucket);
      marketRows.innerHTML = markets.map(renderMarketRow).join("") || `<tr><td colspan="7" class="empty-cell">No markets synced for this tab yet.</td></tr>`;
    }

    function renderMarketRow(market) {
      const reasons = (market.bias_reasons || []).join(", ") || "baseline ok";
      return `<tr>
        <td>
          <strong>${market.question}</strong>
          <span>${reasons}</span>
        </td>
        <td>${pct(market.benchmark_probability)}<span>${market.benchmark_source}</span></td>
        <td>${pct(market.spread)}</td>
        <td>${depthLabel(market)}</td>
        <td>${money(market.liquidity)}</td>
        <td><b class="bucket ${market.bias_bucket}">${market.bias_bucket}</b></td>
        <td>${shortDate(market.end_date)}</td>
      </tr>`;
    }

    function depthLabel(market) {
      if (market.orderbook_bid_depth === null || market.orderbook_bid_depth === undefined) return "n/a";
      const total = Number(market.orderbook_bid_depth || 0) + Number(market.orderbook_ask_depth || 0);
      const imbalance = market.orderbook_depth_imbalance === null || market.orderbook_depth_imbalance === undefined
        ? "n/a"
        : market.orderbook_depth_imbalance.toFixed(2);
      return `${total.toFixed(0)}<span>imb ${imbalance}</span>`;
    }

    function renderEndingSoon(markets) {
      endingSoon.innerHTML = markets.map(market => `
        <article>
          <strong>${market.question}</strong>
          <span>${shortDate(market.end_date)} / ${pct(market.benchmark_probability)} / ${market.bias_bucket}</span>
        </article>
      `).join("") || '<p class="empty">No ending-soon markets in this tab.</p>';
    }

    function renderEvents(items) {
      events.innerHTML = items.map(renderCard).join("") || '<p class="empty">No Event Cards yet.</p>';
    }

    function renderMacroReleases(items) {
      macroReleases.innerHTML = items.map(item => `
        <article>
          <strong>${item.event_name}</strong>
          <span>${formatDate(item.release_time)} / surprise z ${item.surprise_z ?? "n/a"}</span>
        </article>
      `).join("") || '<p class="empty">No macro releases yet.</p>';
    }

    function renderMacroEstimate(result) {
      if (!result?.fair_probability_estimate) {
        macroEstimate.innerHTML = '<p class="empty">Release saved. Add a benchmark to price it.</p>';
        return;
      }
      const estimate = result.fair_probability_estimate;
      macroEstimate.innerHTML = `
        <dl>
          <div><dt>Benchmark</dt><dd>${pct(estimate.benchmark_probability)}</dd></div>
          <div><dt>Fair</dt><dd>${pct(estimate.fair_probability)}</dd></div>
          <div><dt>Delta</dt><dd>${pct(estimate.model_delta)}</dd></div>
          <div><dt>Confidence</dt><dd>${pct(estimate.confidence_score)}</dd></div>
        </dl>
      `;
    }

    function renderPricingSignals(items) {
      pricingSignals.innerHTML = items.map(signal => `
        <article class="card signal-card">
          <div class="card-head">
            <span>${signal.release_name}</span>
            <strong class="bucket ${signal.bucket}">${signal.bucket}</strong>
          </div>
          <h3>${signal.question}</h3>
          <dl>
            <div><dt>Benchmark</dt><dd>${pct(signal.benchmark_probability)}</dd></div>
            <div><dt>Fair</dt><dd>${pct(signal.fair_probability)}</dd></div>
            <div><dt>Gap</dt><dd>${pct(signal.repricing_gap)}</dd></div>
            <div><dt>Confidence</dt><dd>${pct(signal.confidence_score)}</dd></div>
          </dl>
          <p>${(signal.reasons || []).join(", ")}</p>
        </article>
      `).join("") || '<p class="empty">No model repricing gaps yet. Submit a macro release after syncing markets.</p>';
    }

    function renderCard(card) {
      const markets = (card.affected_markets || []).slice(0, 3).map(m => `<li>${m.question} <span>${pct(m.probability)}</span></li>`).join("");
      const range = card.after_probability_estimate ? `${pct(card.after_probability_estimate[0])} - ${pct(card.after_probability_estimate[1])}` : "n/a";
      return `<article class="card">
        <div class="card-head">
          <span>${card.vertical}</span>
          <strong>${card.market_repricing_status}</strong>
        </div>
        <h3>${card.event_summary}</h3>
        <dl>
          <div><dt>Type</dt><dd>${card.event_type}</dd></div>
          <div><dt>Market</dt><dd>${pct(card.market_price)}</dd></div>
          <div><dt>Fair range</dt><dd>${range}</dd></div>
          <div><dt>Confidence</dt><dd>${pct(card.confidence_score)}</dd></div>
        </dl>
        <p>${card.reasoning}</p>
        <ul>${markets}</ul>
      </article>`;
    }

    tabs.addEventListener("click", async (event) => {
      const button = event.target.closest("button[data-tab]");
      if (!button) return;
      selectedTab = button.dataset.tab;
      await loadDashboard();
    });

    bucketFilter.addEventListener("change", renderMarkets);
    sortSelect.addEventListener("change", loadDashboard);

    syncMarkets.addEventListener("click", async () => {
      syncMarkets.disabled = true;
      syncMarkets.textContent = "Syncing";
      try {
        await fetch("/api/markets/sync", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            tab: "all",
            limit_per_tag: 40,
            enrich_orderbook: document.querySelector("#deep-book").checked,
            max_orderbooks: 30
          })
        });
        await loadDashboard();
      } finally {
        syncMarkets.disabled = false;
        syncMarkets.textContent = "Sync Markets";
      }
    });

    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      const button = form.querySelector("button");
      button.disabled = true;
      button.textContent = "Analyzing";
      try {
        await fetch("/api/events", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            summary: document.querySelector("#summary").value,
            source_type: document.querySelector("#source-type").value,
            live_markets: document.querySelector("#live-markets").checked
          })
        });
        form.reset();
        document.querySelector("#live-markets").checked = true;
        await loadDashboard();
      } finally {
        button.disabled = false;
        button.textContent = "Analyze";
      }
    });

    macroForm.addEventListener("submit", async (event) => {
      event.preventDefault();
      const button = macroForm.querySelector("button");
      button.disabled = true;
      button.textContent = "Pricing";
      try {
        const res = await fetch("/api/macro/releases", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            event_name: document.querySelector("#macro-name").value,
            source: "manual",
            actual: document.querySelector("#macro-actual").value,
            forecast: document.querySelector("#macro-forecast").value,
            previous: document.querySelector("#macro-previous").value,
            surprise_std: document.querySelector("#macro-std").value,
            benchmark_probability: document.querySelector("#macro-benchmark").value,
            direction: document.querySelector("#macro-direction").value,
            market_sensitivity: document.querySelector("#macro-sensitivity").value,
            source_reliability: document.querySelector("#macro-reliability").value
          })
        });
        const result = await res.json();
        renderMacroEstimate(result);
        renderPricingSignals(result.market_pricing_signals || []);
        macroForm.reset();
        document.querySelector("#macro-sensitivity").value = "0.35";
        document.querySelector("#macro-reliability").value = "0.8";
        await loadDashboard();
      } finally {
        button.disabled = false;
        button.textContent = "Price Macro";
      }
    });

    refresh.addEventListener("click", loadDashboard);
    loadDashboard();
  </script>
</body>
</html>"""
    return html.replace("__CSS__", css)
