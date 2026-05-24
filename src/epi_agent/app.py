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
        self._send_json({"error": "not_found"}, status=HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
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
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>EPI Agent MVP</title>
  <style>{css}</style>
</head>
<body>
  <main class="shell">
    <section class="input-panel">
      <div>
        <p class="eyebrow">OKX Onchain OS Research Agent</p>
        <h1>Event Probability Intelligence</h1>
      </div>
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
    <section>
      <div class="section-title">
        <h2>Research Journal</h2>
        <button id="refresh" type="button">Refresh</button>
      </div>
      <div id="events" class="cards"></div>
    </section>
  </main>
  <script>
    const form = document.querySelector("#event-form");
    const events = document.querySelector("#events");
    const refresh = document.querySelector("#refresh");

    async function loadEvents() {{
      const res = await fetch("/api/events?limit=20");
      const data = await res.json();
      events.innerHTML = data.events.map(renderCard).join("") || '<p class="empty">No Event Cards yet.</p>';
    }}

    function pct(value) {{
      return value === null || value === undefined ? "n/a" : `${{(value * 100).toFixed(1)}}%`;
    }}

    function renderCard(card) {{
      const markets = (card.affected_markets || []).slice(0, 3).map(m => `<li>${{m.question}} <span>${{pct(m.probability)}}</span></li>`).join("");
      const range = card.after_probability_estimate ? `${{pct(card.after_probability_estimate[0])}} - ${{pct(card.after_probability_estimate[1])}}` : "n/a";
      return `<article class="card">
        <div class="card-head">
          <span>${{card.vertical}}</span>
          <strong>${{card.market_repricing_status}}</strong>
        </div>
        <h3>${{card.event_summary}}</h3>
        <dl>
          <div><dt>Type</dt><dd>${{card.event_type}}</dd></div>
          <div><dt>Market</dt><dd>${{pct(card.market_price)}}</dd></div>
          <div><dt>Fair range</dt><dd>${{range}}</dd></div>
          <div><dt>Confidence</dt><dd>${{pct(card.confidence_score)}}</dd></div>
        </dl>
        <p>${{card.reasoning}}</p>
        <ul>${{markets}}</ul>
      </article>`;
    }}

    form.addEventListener("submit", async (event) => {{
      event.preventDefault();
      const button = form.querySelector("button");
      button.disabled = true;
      button.textContent = "Analyzing";
      try {{
        await fetch("/api/events", {{
          method: "POST",
          headers: {{ "Content-Type": "application/json" }},
          body: JSON.stringify({{
            summary: document.querySelector("#summary").value,
            source_type: document.querySelector("#source-type").value,
            live_markets: document.querySelector("#live-markets").checked
          }})
        }});
        form.reset();
        document.querySelector("#live-markets").checked = true;
        await loadEvents();
      }} finally {{
        button.disabled = false;
        button.textContent = "Analyze";
      }}
    }});

    refresh.addEventListener("click", loadEvents);
    loadEvents();
  </script>
</body>
</html>"""
