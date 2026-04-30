#!/usr/bin/env python3
"""
Build a standalone interactive stock price dashboard from downloaded parquet data.

The dashboard is written as a single HTML file and does not require a local
server or JavaScript package installation.
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATA_DIR = PROJECT_ROOT / "downloaded_stock_data"
DEFAULT_OUTPUT = PROJECT_ROOT / "stock_price_dashboard.html"
MINUTE_NS = 60_000_000_000


HTML_TEMPLATE = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Stock Prices</title>
  <style>
    :root {
      color-scheme: dark;
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      background: #050608;
      color: #f7f8fa;
    }

    * {
      box-sizing: border-box;
    }

    body {
      margin: 0;
      min-height: 100vh;
      background: radial-gradient(circle at 18% 0%, #15201a 0, transparent 30rem), #050608;
    }

    main {
      width: min(1180px, calc(100vw - 32px));
      margin: 0 auto;
      padding: 28px 0;
    }

    .topbar {
      display: flex;
      align-items: end;
      justify-content: space-between;
      gap: 24px;
      margin-bottom: 18px;
    }

    .identity {
      min-width: 0;
    }

    .symbol {
      margin: 0;
      font-size: 42px;
      line-height: 1;
      font-weight: 750;
      letter-spacing: 0;
    }

    .name {
      margin-top: 8px;
      color: #a8afb8;
      font-size: 15px;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }

    .quote {
      text-align: right;
      white-space: nowrap;
    }

    .price {
      font-size: 34px;
      line-height: 1;
      font-weight: 700;
    }

    .change {
      margin-top: 8px;
      font-size: 15px;
      font-weight: 650;
    }

    .buttons {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      margin: 16px 0 18px;
    }

    button {
      appearance: none;
      border: 1px solid #2a3038;
      background: #11151b;
      color: #d8dde4;
      border-radius: 8px;
      min-height: 38px;
      padding: 0 14px;
      font: inherit;
      font-weight: 700;
      cursor: pointer;
    }

    button:hover {
      border-color: #596273;
    }

    button.active {
      border-color: var(--accent);
      color: #061006;
      background: var(--accent);
    }

    .range-panel {
      display: flex;
      align-items: end;
      justify-content: space-between;
      gap: 20px;
      margin: 0 0 18px;
      padding: 16px 0;
      border-top: 1px solid #1c2229;
      border-bottom: 1px solid #1c2229;
    }

    .range-title {
      font-size: 13px;
      color: #89919c;
      margin-bottom: 6px;
    }

    .database-range {
      font-size: 16px;
      font-weight: 700;
    }

    .date-controls {
      display: flex;
      align-items: end;
      justify-content: flex-end;
      flex-wrap: wrap;
      gap: 10px;
    }

    label {
      display: grid;
      gap: 6px;
      color: #89919c;
      font-size: 12px;
      font-weight: 700;
    }

    input[type="date"] {
      appearance: none;
      border: 1px solid #2a3038;
      background: #0d1117;
      color: #f7f8fa;
      border-radius: 8px;
      min-height: 38px;
      padding: 0 10px;
      font: inherit;
      color-scheme: dark;
    }

    input[type="date"]:focus {
      outline: 2px solid var(--accent);
      outline-offset: 2px;
    }

    .range-error {
      min-height: 18px;
      margin: -10px 0 14px;
      color: #ff886d;
      font-size: 13px;
      font-weight: 650;
    }

    .chart-shell {
      position: relative;
      height: min(66vh, 620px);
      min-height: 420px;
      border-top: 1px solid #1c2229;
      border-bottom: 1px solid #1c2229;
    }

    canvas {
      display: block;
      width: 100%;
      height: 100%;
      cursor: crosshair;
    }

    .meta {
      display: flex;
      justify-content: space-between;
      gap: 20px;
      margin-top: 14px;
      color: #89919c;
      font-size: 13px;
    }

    @media (max-width: 720px) {
      main {
        width: min(100vw - 20px, 1180px);
        padding-top: 18px;
      }

      .topbar {
        display: block;
      }

      .quote {
        text-align: left;
        margin-top: 18px;
      }

      .symbol {
        font-size: 36px;
      }

      .range-panel {
        display: block;
      }

      .date-controls {
        justify-content: flex-start;
        margin-top: 14px;
      }

      .chart-shell {
        min-height: 360px;
        height: 58vh;
      }
    }
  </style>
</head>
<body>
  <main>
    <section class="topbar" aria-live="polite">
      <div class="identity">
        <h1 class="symbol" id="symbolLabel"></h1>
        <div class="name" id="nameLabel"></div>
      </div>
      <div class="quote">
        <div class="price" id="priceLabel"></div>
        <div class="change" id="changeLabel"></div>
      </div>
    </section>

    <nav class="buttons" id="stockButtons" aria-label="Stocks"></nav>

    <section class="range-panel" aria-label="Date range">
      <div>
        <div class="range-title">Database Range</div>
        <div class="database-range" id="databaseRangeLabel"></div>
      </div>
      <div class="date-controls">
        <label>
          <span>Start</span>
          <input id="startDateInput" type="date">
        </label>
        <label>
          <span>End</span>
          <input id="endDateInput" type="date">
        </label>
        <button id="resetRangeButton" type="button">All</button>
      </div>
    </section>

    <div class="range-error" id="rangeError" role="status"></div>

    <section class="chart-shell">
      <canvas id="chart"></canvas>
    </section>

    <section class="meta">
      <span id="rangeLabel"></span>
      <span id="pointLabel"></span>
    </section>
  </main>

  <script>
    const STOCK_DATA = __DATA__;
    const symbols = Object.keys(STOCK_DATA).sort();
    const canvas = document.getElementById("chart");
    const ctx = canvas.getContext("2d");
    const buttons = document.getElementById("stockButtons");
    const symbolLabel = document.getElementById("symbolLabel");
    const nameLabel = document.getElementById("nameLabel");
    const priceLabel = document.getElementById("priceLabel");
    const changeLabel = document.getElementById("changeLabel");
    const rangeLabel = document.getElementById("rangeLabel");
    const pointLabel = document.getElementById("pointLabel");
    const databaseRangeLabel = document.getElementById("databaseRangeLabel");
    const startDateInput = document.getElementById("startDateInput");
    const endDateInput = document.getElementById("endDateInput");
    const resetRangeButton = document.getElementById("resetRangeButton");
    const rangeError = document.getElementById("rangeError");

    let selected = symbols[0];
    let hover = null;
    let geometry = null;
    let selectedRange = null;

    const currency = new Intl.NumberFormat(undefined, {
      style: "currency",
      currency: "USD",
      maximumFractionDigits: 2
    });
    const percent = new Intl.NumberFormat(undefined, {
      style: "percent",
      minimumFractionDigits: 2,
      maximumFractionDigits: 2
    });
    const compactDate = new Intl.DateTimeFormat(undefined, {
      month: "short",
      day: "numeric"
    });
    const fullDate = new Intl.DateTimeFormat(undefined, {
      month: "short",
      day: "numeric",
      year: "numeric"
    });
    const hoverDate = new Intl.DateTimeFormat(undefined, {
      month: "short",
      day: "numeric",
      year: "numeric",
      hour: "numeric",
      minute: "2-digit"
    });

    function setAccent(color) {
      document.documentElement.style.setProperty("--accent", color);
    }

    function formatPrice(value) {
      return currency.format(value);
    }

    function formatChange(first, last) {
      const absolute = last - first;
      const ratio = first === 0 ? 0 : absolute / first;
      const sign = absolute >= 0 ? "+" : "";
      return `${sign}${formatPrice(absolute)} (${sign}${percent.format(ratio)})`;
    }

    function priceColor(points) {
      if (!points || points.p.length < 2) return "#00c805";
      return points.p[points.p.length - 1] >= points.p[0] ? "#00c805" : "#ff5000";
    }

    function computeDataBounds() {
      let min = Infinity;
      let max = -Infinity;
      for (const symbol of symbols) {
        const times = STOCK_DATA[symbol].t;
        if (!times.length) continue;
        min = Math.min(min, times[0]);
        max = Math.max(max, times[times.length - 1]);
      }
      return { min, max };
    }

    const dataBounds = computeDataBounds();

    function pad2(value) {
      return String(value).padStart(2, "0");
    }

    function toDateInputValue(timestamp) {
      const date = new Date(timestamp);
      return `${date.getFullYear()}-${pad2(date.getMonth() + 1)}-${pad2(date.getDate())}`;
    }

    function parseDateInputStart(value) {
      const parts = value.split("-").map(Number);
      if (parts.length !== 3 || parts.some(Number.isNaN)) return NaN;
      return new Date(parts[0], parts[1] - 1, parts[2], 0, 0, 0, 0).getTime();
    }

    function parseDateInputEnd(value) {
      const parts = value.split("-").map(Number);
      if (parts.length !== 3 || parts.some(Number.isNaN)) return NaN;
      return new Date(parts[0], parts[1] - 1, parts[2] + 1, 0, 0, 0, 0).getTime() - 1;
    }

    function selectedRangeLabel() {
      if (!selectedRange) return "";
      return `${fullDate.format(new Date(selectedRange.start))} - ${fullDate.format(new Date(selectedRange.end))}`;
    }

    function lowerBound(values, target) {
      let lo = 0;
      let hi = values.length;
      while (lo < hi) {
        const mid = Math.floor((lo + hi) / 2);
        if (values[mid] < target) lo = mid + 1;
        else hi = mid;
      }
      return lo;
    }

    function upperBound(values, target) {
      let lo = 0;
      let hi = values.length;
      while (lo < hi) {
        const mid = Math.floor((lo + hi) / 2);
        if (values[mid] <= target) lo = mid + 1;
        else hi = mid;
      }
      return lo;
    }

    function visiblePointsFor(points) {
      if (!points || !selectedRange) return { name: "", t: [], p: [], count: 0 };
      const startIndex = lowerBound(points.t, selectedRange.start);
      const endIndex = upperBound(points.t, selectedRange.end);
      return {
        name: points.name,
        t: points.t.slice(startIndex, endIndex),
        p: points.p.slice(startIndex, endIndex),
        count: Math.max(0, endIndex - startIndex)
      };
    }

    function pointCountText() {
      const points = visiblePointsFor(STOCK_DATA[selected]);
      return `${points.count.toLocaleString()} points in range`;
    }

    function initRangeControls() {
      if (!Number.isFinite(dataBounds.min) || !Number.isFinite(dataBounds.max)) return;

      const minValue = toDateInputValue(dataBounds.min);
      const maxValue = toDateInputValue(dataBounds.max);
      databaseRangeLabel.textContent = `${fullDate.format(new Date(dataBounds.min))} - ${fullDate.format(new Date(dataBounds.max))}`;

      for (const input of [startDateInput, endDateInput]) {
        input.min = minValue;
        input.max = maxValue;
      }

      startDateInput.value = minValue;
      endDateInput.value = maxValue;
      selectedRange = {
        start: dataBounds.min,
        end: dataBounds.max
      };
    }

    function applyDateRange() {
      const start = parseDateInputStart(startDateInput.value);
      const end = parseDateInputEnd(endDateInput.value);

      if (!Number.isFinite(start) || !Number.isFinite(end)) {
        rangeError.textContent = "Enter a valid start and end date.";
        return;
      }

      if (start > end) {
        rangeError.textContent = "Start date must be before end date.";
        return;
      }

      rangeError.textContent = "";
      selectedRange = {
        start: Math.max(start, dataBounds.min),
        end: Math.min(end, dataBounds.max)
      };
      hover = null;
      draw();
    }

    function resetDateRange() {
      startDateInput.value = toDateInputValue(dataBounds.min);
      endDateInput.value = toDateInputValue(dataBounds.max);
      applyDateRange();
    }

    function buildButtons() {
      buttons.innerHTML = "";
      for (const symbol of symbols) {
        const button = document.createElement("button");
        button.type = "button";
        button.textContent = symbol;
        button.title = STOCK_DATA[symbol].name || symbol;
        button.addEventListener("click", () => {
          selected = symbol;
          hover = null;
          updateButtons();
          draw();
        });
        buttons.appendChild(button);
      }
      updateButtons();
    }

    function updateButtons() {
      for (const button of buttons.children) {
        button.classList.toggle("active", button.textContent === selected);
      }
    }

    function resizeCanvas() {
      const rect = canvas.getBoundingClientRect();
      const dpr = window.devicePixelRatio || 1;
      const width = Math.max(320, Math.floor(rect.width));
      const height = Math.max(280, Math.floor(rect.height));
      if (canvas.width !== Math.floor(width * dpr) || canvas.height !== Math.floor(height * dpr)) {
        canvas.width = Math.floor(width * dpr);
        canvas.height = Math.floor(height * dpr);
      }
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      return { width, height };
    }

    function nearestIndex(times, target) {
      let lo = 0;
      let hi = times.length - 1;
      while (lo < hi) {
        const mid = Math.floor((lo + hi) / 2);
        if (times[mid] < target) lo = mid + 1;
        else hi = mid;
      }
      if (lo > 0 && Math.abs(times[lo - 1] - target) < Math.abs(times[lo] - target)) {
        return lo - 1;
      }
      return lo;
    }

    function labelBox(text, x, y, align = "center") {
      ctx.save();
      ctx.font = "12px Inter, system-ui, sans-serif";
      const metrics = ctx.measureText(text);
      const padX = 8;
      const width = metrics.width + padX * 2;
      const height = 24;
      let left = align === "right" ? x - width : align === "left" ? x : x - width / 2;
      left = Math.max(6, Math.min(geometry.width - width - 6, left));
      const top = Math.max(6, Math.min(geometry.height - height - 6, y));
      ctx.fillStyle = "#f7f8fa";
      roundRect(left, top, width, height, 6);
      ctx.fill();
      ctx.fillStyle = "#050608";
      ctx.textAlign = "center";
      ctx.textBaseline = "middle";
      ctx.fillText(text, left + width / 2, top + height / 2 + 0.5);
      ctx.restore();
    }

    function roundRect(x, y, width, height, radius) {
      ctx.beginPath();
      ctx.moveTo(x + radius, y);
      ctx.arcTo(x + width, y, x + width, y + height, radius);
      ctx.arcTo(x + width, y + height, x, y + height, radius);
      ctx.arcTo(x, y + height, x, y, radius);
      ctx.arcTo(x, y, x + width, y, radius);
      ctx.closePath();
    }

    function drawGrid(plot, minY, maxY, minX, maxX) {
      ctx.save();
      ctx.lineWidth = 1;
      ctx.strokeStyle = "rgba(255,255,255,0.075)";
      ctx.fillStyle = "#808894";
      ctx.font = "12px Inter, system-ui, sans-serif";
      ctx.textBaseline = "middle";
      ctx.textAlign = "right";

      for (let i = 0; i <= 4; i++) {
        const y = plot.top + (plot.height * i) / 4;
        const value = maxY - ((maxY - minY) * i) / 4;
        ctx.beginPath();
        ctx.moveTo(plot.left, y);
        ctx.lineTo(plot.right, y);
        ctx.stroke();
        ctx.fillText(formatPrice(value), plot.right - 4, y - 8);
      }

      ctx.textAlign = "center";
      ctx.textBaseline = "top";
      for (let i = 0; i <= 4; i++) {
        const x = plot.left + (plot.width * i) / 4;
        const value = minX + ((maxX - minX) * i) / 4;
        ctx.fillText(compactDate.format(new Date(value)), x, plot.bottom + 10);
      }
      ctx.restore();
    }

    function drawLine(points, plot, minY, maxY, minX, maxX, accent) {
      const times = points.t;
      const prices = points.p;
      const xScale = plot.width / Math.max(1, maxX - minX);
      const yScale = plot.height / Math.max(0.01, maxY - minY);

      ctx.save();
      ctx.lineWidth = 2.25;
      ctx.lineJoin = "round";
      ctx.lineCap = "round";
      ctx.strokeStyle = accent;
      ctx.beginPath();
      for (let i = 0; i < times.length; i++) {
        const x = plot.left + (times[i] - minX) * xScale;
        const y = plot.bottom - (prices[i] - minY) * yScale;
        if (i === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
      }
      ctx.stroke();

      const gradient = ctx.createLinearGradient(0, plot.top, 0, plot.bottom);
      gradient.addColorStop(0, accent === "#00c805" ? "rgba(0,200,5,0.18)" : "rgba(255,80,0,0.18)");
      gradient.addColorStop(1, "rgba(0,0,0,0)");
      ctx.lineTo(plot.right, plot.bottom);
      ctx.lineTo(plot.left, plot.bottom);
      ctx.closePath();
      ctx.fillStyle = gradient;
      ctx.fill();
      ctx.restore();

      return { xScale, yScale };
    }

    function drawHover(points, plot, minY, maxY, minX, maxX) {
      if (!hover || !geometry) return;
      if (hover.x < plot.left || hover.x > plot.right || hover.y < plot.top || hover.y > plot.bottom) return;

      const times = points.t;
      const prices = points.p;
      const targetTime = minX + ((hover.x - plot.left) / plot.width) * (maxX - minX);
      const index = nearestIndex(times, targetTime);
      const time = times[index];
      const price = prices[index];
      const x = plot.left + ((time - minX) / Math.max(1, maxX - minX)) * plot.width;
      const y = plot.bottom - ((price - minY) / Math.max(0.01, maxY - minY)) * plot.height;

      ctx.save();
      ctx.strokeStyle = "rgba(247,248,250,0.28)";
      ctx.lineWidth = 1;
      ctx.setLineDash([4, 6]);
      ctx.beginPath();
      ctx.moveTo(x, plot.top);
      ctx.lineTo(x, plot.bottom);
      ctx.moveTo(plot.left, y);
      ctx.lineTo(plot.right, y);
      ctx.stroke();
      ctx.setLineDash([]);

      ctx.fillStyle = "#f7f8fa";
      ctx.beginPath();
      ctx.arc(x, y, 4, 0, Math.PI * 2);
      ctx.fill();
      ctx.restore();

      labelBox(hoverDate.format(new Date(time)), x, plot.bottom + 36);
      labelBox(formatPrice(price), plot.right - 4, y - 12, "right");
      pointLabel.textContent = `${hoverDate.format(new Date(time))}  |  ${formatPrice(price)}`;
    }

    function draw() {
      if (!selected) return;
      geometry = resizeCanvas();
      const allPoints = STOCK_DATA[selected];
      const points = visiblePointsFor(allPoints);
      const accent = priceColor(points);
      setAccent(accent);

      ctx.clearRect(0, 0, geometry.width, geometry.height);
      ctx.fillStyle = "#050608";
      ctx.fillRect(0, 0, geometry.width, geometry.height);

      const plot = {
        left: 18,
        right: geometry.width - 18,
        top: 18,
        bottom: geometry.height - 46
      };
      plot.width = plot.right - plot.left;
      plot.height = plot.bottom - plot.top;

      symbolLabel.textContent = selected;
      nameLabel.textContent = allPoints.name || selected;

      if (!points || points.t.length === 0) {
        ctx.fillStyle = "#a8afb8";
        ctx.font = "16px Inter, system-ui, sans-serif";
        ctx.textAlign = "center";
        ctx.fillText("No data in selected date range", geometry.width / 2, geometry.height / 2);
        priceLabel.textContent = "--";
        changeLabel.textContent = "No data in selected range";
        changeLabel.style.color = "#a8afb8";
        rangeLabel.textContent = selectedRangeLabel();
        pointLabel.textContent = "0 points in range";
        return;
      }

      const prices = points.p;
      const times = points.t;
      const minX = times[0];
      const maxX = times[times.length - 1];
      let minY = Math.min(...prices);
      let maxY = Math.max(...prices);
      const yPad = Math.max((maxY - minY) * 0.08, maxY * 0.005, 0.5);
      minY -= yPad;
      maxY += yPad;

      const first = prices[0];
      const last = prices[prices.length - 1];
      priceLabel.textContent = formatPrice(last);
      changeLabel.textContent = formatChange(first, last);
      changeLabel.style.color = accent;
      rangeLabel.textContent = `${compactDate.format(new Date(minX))} - ${compactDate.format(new Date(maxX))}`;
      if (!hover) pointLabel.textContent = pointCountText();

      drawGrid(plot, minY, maxY, minX, maxX);
      drawLine(points, plot, minY, maxY, minX, maxX, accent);
      drawHover(points, plot, minY, maxY, minX, maxX);
    }

    canvas.addEventListener("mousemove", (event) => {
      const rect = canvas.getBoundingClientRect();
      hover = {
        x: event.clientX - rect.left,
        y: event.clientY - rect.top
      };
      draw();
    });

    canvas.addEventListener("mouseleave", () => {
      hover = null;
      pointLabel.textContent = pointCountText();
      draw();
    });

    startDateInput.addEventListener("change", applyDateRange);
    endDateInput.addEventListener("change", applyDateRange);
    resetRangeButton.addEventListener("click", resetDateRange);
    window.addEventListener("resize", draw);
    initRangeControls();
    buildButtons();
    draw();
  </script>
</body>
</html>
"""


def project_relative_path(value: str) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    return PROJECT_ROOT / path


def read_stock_points(data_dir: Path, batch_size: int) -> dict[str, dict[str, Any]]:
    try:
        import pandas as pd
        import pyarrow.dataset as ds
    except ImportError as exc:
        raise RuntimeError(
            "pandas and pyarrow are required. Install dependencies in the venv first."
        ) from exc

    parquet_files = list(data_dir.rglob("*.parquet"))
    if not parquet_files:
        raise ValueError(f"No parquet files found under {data_dir}")

    dataset = ds.dataset(str(data_dir), format="parquet", partitioning="hive")
    schema_names = set(dataset.schema.names)
    required = {"symbol", "timestamp", "price"}
    missing = sorted(required - schema_names)
    if missing:
        raise ValueError(f"Missing required parquet columns: {', '.join(missing)}")

    columns = ["symbol", "timestamp", "price"]
    if "short_name" in schema_names:
        columns.append("short_name")

    points_by_symbol: dict[str, dict[int, tuple[int, float]]] = defaultdict(dict)
    names_by_symbol: dict[str, str] = {}
    rows_seen = 0
    batches_seen = 0

    scanner = dataset.scanner(columns=columns, batch_size=batch_size, use_threads=True)
    for batch in scanner.to_batches():
        batches_seen += 1
        df = batch.to_pandas()
        rows_seen += len(df)
        if df.empty:
            continue

        df = df.dropna(subset=["symbol", "timestamp", "price"])
        if df.empty:
            continue

        df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce", utc=True)
        df = df.dropna(subset=["timestamp"])
        if df.empty:
            continue

        df["timestamp_ns"] = df["timestamp"].astype("int64")
        df["minute_ms"] = (df["timestamp_ns"] // MINUTE_NS) * 60_000
        df = df.sort_values("timestamp_ns").drop_duplicates(
            ["symbol", "minute_ms"], keep="last"
        )

        has_name = "short_name" in df.columns
        for row in df.itertuples(index=False):
            symbol = str(row.symbol)
            price = float(row.price)
            minute_ms = int(row.minute_ms)
            timestamp_ns = int(row.timestamp_ns)

            existing = points_by_symbol[symbol].get(minute_ms)
            if existing is None or timestamp_ns >= existing[0]:
                points_by_symbol[symbol][minute_ms] = (timestamp_ns, price)

            if has_name:
                short_name = getattr(row, "short_name", None)
                if short_name and symbol not in names_by_symbol:
                    names_by_symbol[symbol] = str(short_name)

        if batches_seen % 2_000 == 0:
            print(
                f"processed {batches_seen:,} parquet batches, "
                f"{rows_seen:,} raw rows",
                flush=True,
            )

    if not points_by_symbol:
        raise ValueError(f"No usable stock rows found under {data_dir}")

    stock_data: dict[str, dict[str, Any]] = {}
    for symbol, minute_points in sorted(points_by_symbol.items()):
        sorted_points = sorted(minute_points.items())
        stock_data[symbol] = {
            "name": names_by_symbol.get(symbol, symbol),
            "t": [minute_ms for minute_ms, _point in sorted_points],
            "p": [round(point[1], 4) for _minute_ms, point in sorted_points],
            "count": len(sorted_points),
        }

    return stock_data


def downsample_stock_data(
    stock_data: dict[str, dict[str, Any]],
    max_points_per_symbol: int,
) -> dict[str, dict[str, Any]]:
    if max_points_per_symbol <= 0:
        return stock_data

    for points in stock_data.values():
        count = len(points["t"])
        if count <= max_points_per_symbol:
            continue

        step = (count - 1) / (max_points_per_symbol - 1)
        indexes = sorted({round(i * step) for i in range(max_points_per_symbol)})
        points["t"] = [points["t"][index] for index in indexes]
        points["p"] = [points["p"][index] for index in indexes]
        points["count"] = len(indexes)

    return stock_data


def write_dashboard(stock_data: dict[str, dict[str, Any]], output_path: Path) -> None:
    data_json = json.dumps(stock_data, separators=(",", ":"))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        HTML_TEMPLATE.replace("__DATA__", data_json),
        encoding="utf-8",
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build an interactive stock price HTML dashboard from parquet files."
    )
    parser.add_argument(
        "--data-dir",
        default=str(DEFAULT_DATA_DIR),
        help="Folder containing downloaded parquet files. Defaults to downloaded_stock_data.",
    )
    parser.add_argument(
        "--output",
        default=str(DEFAULT_OUTPUT),
        help="HTML file to write. Defaults to stock_price_dashboard.html.",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=250_000,
        help="PyArrow scanner batch size.",
    )
    parser.add_argument(
        "--max-points-per-symbol",
        type=int,
        default=0,
        help="Optionally downsample each symbol after minute aggregation. 0 keeps all points.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    data_dir = project_relative_path(args.data_dir).resolve()
    output_path = project_relative_path(args.output).resolve()

    try:
        stock_data = read_stock_points(data_dir, args.batch_size)
        stock_data = downsample_stock_data(stock_data, args.max_points_per_symbol)
        write_dashboard(stock_data, output_path)
    except (RuntimeError, ValueError) as exc:
        print(f"error: {exc}")
        return 1

    symbol_count = len(stock_data)
    point_count = sum(points["count"] for points in stock_data.values())
    print(f"wrote {output_path}")
    print(f"included {point_count:,} minute-level points across {symbol_count} symbols")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
