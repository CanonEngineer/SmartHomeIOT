(() => {
  const $ = (sel) => document.querySelector(sel);
  const logList = $("#log-list");
  const expList = $("#exp-list");
  let ws;
  let reconnectTimer;
  let latencySeries = [];

  function pushLog(text) {
    const li = document.createElement("li");
    const ts = new Date().toLocaleTimeString();
    li.innerHTML = `<strong>${ts}</strong> — ${text}`;
    logList.prepend(li);
    while (logList.children.length > 40) logList.removeChild(logList.lastChild);
  }

  function setPill(el, online, onlineText, offlineText) {
    el.classList.toggle("online", online);
    el.classList.toggle("offline", !online);
    el.textContent = online ? onlineText : offlineText;
  }

  function drawChart(values) {
    const canvas = $("#latency-chart");
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    const w = canvas.width;
    const h = canvas.height;
    ctx.clearRect(0, 0, w, h);
    ctx.strokeStyle = "#2a403c";
    ctx.beginPath();
    for (let y = 0; y <= h; y += 28) {
      ctx.moveTo(0, y);
      ctx.lineTo(w, y);
    }
    ctx.stroke();
    if (!values.length) return;
    const max = Math.max(10, ...values);
    ctx.strokeStyle = "#7dd3c0";
    ctx.lineWidth = 2;
    ctx.beginPath();
    values.forEach((v, i) => {
      const x = (i / Math.max(1, values.length - 1)) * (w - 8) + 4;
      const y = h - 8 - (v / max) * (h - 16);
      if (i === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    });
    ctx.stroke();
    ctx.fillStyle = "#e8b86d";
    ctx.font = "11px IBM Plex Mono";
    ctx.fillText(`n=${values.length}  max=${max.toFixed(1)}ms`, 8, 14);
  }

  function applyTelemetry(tel) {
    if (!tel) return;
    const sqi = tel.sync_quality_index ?? 0;
    const p50 = tel.command_latency_ms?.p50;
    const p95 = tel.command_latency_ms?.p95;
    const skew = tel.protocol_metrics?.last_pair_skew_ms;
    $("#r-sqi").textContent = `${Number(sqi).toFixed(1)}`;
    $("#r-p50").textContent = p50 == null ? "—" : `${p50} ms`;
    $("#r-p95").textContent = p95 == null ? "—" : `${p95} ms`;
    $("#r-skew").textContent = skew == null ? "—" : `${Number(skew).toFixed(1)} ms`;
    $("#sqi-status").textContent = `SQI ${Number(sqi).toFixed(0)}`;

    const points = (tel.series_tail || [])
      .filter((s) => s.kind === "command" && typeof s.latency_ms === "number")
      .map((s) => s.latency_ms);
    if (points.length) {
      latencySeries = points.slice(-60);
      drawChart(latencySeries);
    }
  }

  function applyState(state, telemetry) {
    if (!state) return;
    const s = state.sensors || {};
    const a = state.actuators || {};
    const boards = state.boards || {};

    $("#m-temp").textContent = `${Number(s.temperature ?? 0).toFixed(1)}°C`;
    $("#m-hum").textContent = `${Number(s.humidity ?? 0).toFixed(0)}%`;
    $("#m-light").textContent = `${Number(s.light ?? 0).toFixed(0)}%`;
    $("#m-motion").textContent = s.motion ? "SIM" : "NÃO";

    $("#last-event").textContent = state.last_event || "—";
    const synced = boards.arduino?.sync && boards.raspberry?.sync;
    $("#sync-status").textContent = synced ? `SYNC OK #${state.sync_pulse ?? 0}` : "SYNC OFF";

    if (typeof state.sync_quality_index === "number") {
      $("#sqi-status").textContent = `SQI ${state.sync_quality_index.toFixed(0)}`;
      $("#r-sqi").textContent = state.sync_quality_index.toFixed(1);
    }
    if (state.pair_skew_ms != null) {
      $("#r-skew").textContent = `${Number(state.pair_skew_ms).toFixed(1)} ms`;
    }

    const salaOn = !!(a.relay && a.relay["1"]);
    const cozOn = !!(a.relay && a.relay["2"]);
    $("#bulb-sala").setAttribute("fill", salaOn ? "#ffe082" : "#3d4f4c");
    $("#bulb-sala").setAttribute("filter", salaOn ? "url(#glow)" : "");
    $("#bulb-cozinha").setAttribute("fill", cozOn ? "#ffe082" : "#3d4f4c");
    $("#bulb-cozinha").setAttribute("filter", cozOn ? "url(#glow)" : "");

    $("#led-indicator").setAttribute("fill", a.led ? "#7CFFB2" : "#35524e");
    $("#led-indicator").setAttribute("filter", a.led ? "url(#glow)" : "");
    $("#buzzer-indicator").setAttribute("fill", a.buzzer ? "#e07a5f" : "#35524e");

    $("#door-main-panel").classList.toggle("open", !!(a.door && a.door.main));
    $("#door-garage-panel").classList.toggle("open", !!(a.door && a.door.garage));

    const s1 = (a.servo && a.servo["porta-1"]) || 0;
    const s2 = (a.servo && a.servo["porta-2"]) || 0;
    const s3 = (a.servo && a.servo.arm) || 0;
    $("#servo-arm-1").setAttribute("transform", `rotate(${s1})`);
    $("#servo-arm-2").setAttribute("transform", `rotate(${s2})`);
    $("#servo-arm-3").setAttribute("transform", `rotate(${-s3})`);
    $("#servo-arm-slider").value = s3;
    $("#servo-arm-value").textContent = `${s3}°`;

    $("#motion-blob").setAttribute("opacity", s.motion ? "0.9" : "0.15");

    const arOnline = !!boards.arduino?.online;
    const piOnline = !!boards.raspberry?.online;
    $("#arduino-status-text").textContent = arOnline ? "ONLINE" : "OFFLINE";
    $("#raspberry-status-text").textContent = piOnline ? "ONLINE" : "OFFLINE";
    $("#arduino-pulse").setAttribute("fill", arOnline ? "#80cbc4" : "#555");
    $("#raspberry-pulse").setAttribute("fill", piOnline ? "#f48fb1" : "#555");
    $("#sync-line").setAttribute("opacity", synced ? "0.85" : "0.15");
    $("#sync-dot").style.display = synced ? "block" : "none";

    if (state.sync_pulse % 2 === 0) {
      $("#board-arduino").classList.remove("board-flash");
      void $("#board-arduino").offsetWidth;
      $("#board-arduino").classList.add("board-flash");
    } else {
      $("#board-raspberry").classList.remove("board-flash");
      void $("#board-raspberry").offsetWidth;
      $("#board-raspberry").classList.add("board-flash");
    }

    if (telemetry) applyTelemetry(telemetry);
  }

  function send(payload) {
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify(payload));
      return;
    }
    const map = {
      led: "/api/led",
      buzzer: "/api/buzzer",
      relay: "/api/relay",
      servo: "/api/servo",
      door: "/api/door",
      simulate: "/api/simulate",
    };
    const url = map[payload.action];
    if (!url) return;
    const body = { ...payload };
    delete body.action;
    if (payload.action === "simulate") body.scenario = payload.scenario;
    fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    })
      .then((r) => r.json())
      .then((data) => {
        if (data.state) applyState(data.state);
        pushLog(data.scenario ? `Cenário: ${data.scenario}` : payload.action);
      });
  }

  function refreshTelemetry() {
    fetch("/api/research/telemetry")
      .then((r) => r.json())
      .then(applyTelemetry)
      .catch(() => {});
  }

  function pushExperiment(result) {
    const li = document.createElement("li");
    const id = result.experiment_id;
    li.innerHTML = `<strong>${result.name}</strong> · SQI ${result.metrics?.sync_quality_index ?? "—"} ·
      <a href="/api/research/experiments/${id}/export.csv" target="_blank">CSV</a> ·
      <a href="/api/research/experiments/${id}/export.json" target="_blank">JSON</a>`;
    expList.prepend(li);
  }

  function runExperiment(name) {
    pushLog(`Experimento iniciado: ${name}`);
    fetch("/api/research/experiments/run", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name, params: {} }),
    })
      .then((r) => r.json())
      .then((data) => {
        if (!data.ok) throw new Error(data.detail || "falha");
        pushExperiment(data.result);
        applyTelemetry(data.result.metrics);
        pushLog(`Experimento OK: ${name} (${data.result.experiment_id})`);
      })
      .catch((err) => pushLog(`Experimento falhou: ${err.message || err}`));
  }

  function connectWs() {
    const proto = location.protocol === "https:" ? "wss" : "ws";
    ws = new WebSocket(`${proto}://${location.host}/api/ws`);
    ws.onopen = () => {
      setPill($("#ws-status"), true, "WS online", "WS offline");
      pushLog("WebSocket conectado");
      clearTimeout(reconnectTimer);
    };
    ws.onclose = () => {
      setPill($("#ws-status"), false, "WS online", "WS offline");
      pushLog("WebSocket desconectado — reconectando…");
      reconnectTimer = setTimeout(connectWs, 1500);
    };
    ws.onerror = () => ws.close();
    ws.onmessage = (ev) => {
      try {
        const msg = JSON.parse(ev.data);
        if (msg.type === "state") {
          applyState(msg.data);
          if (msg.data?.last_event) pushLog(msg.data.last_event);
        }
      } catch (_) { /* ignore */ }
    };
  }

  document.querySelectorAll("button[data-action]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const action = btn.dataset.action;
      const payload = { action };
      if (action === "led" || action === "buzzer") payload.on = btn.dataset.on === "true";
      if (action === "relay") {
        payload.channel = btn.dataset.channel;
        payload.on = btn.dataset.on === "true";
      }
      if (action === "door") {
        payload.door_id = btn.dataset.door;
        payload.open = btn.dataset.open === "true";
      }
      send(payload);
    });
  });

  document.querySelectorAll("button[data-scenario]").forEach((btn) => {
    btn.addEventListener("click", () => {
      send({ action: "simulate", scenario: btn.dataset.scenario });
      pushLog(`Simulação: ${btn.dataset.scenario}`);
    });
  });

  document.querySelectorAll("button[data-experiment]").forEach((btn) => {
    btn.addEventListener("click", () => runExperiment(btn.dataset.experiment));
  });

  let servoTimer;
  $("#servo-arm-slider").addEventListener("input", (e) => {
    const angle = Number(e.target.value);
    $("#servo-arm-value").textContent = `${angle}°`;
    clearTimeout(servoTimer);
    servoTimer = setTimeout(() => {
      send({ action: "servo", servo_id: "arm", angle });
    }, 80);
  });

  fetch("/api/status")
    .then((r) => r.json())
    .then((data) => applyState(data.state, data.telemetry))
    .catch(() => pushLog("Falha ao carregar status inicial"));

  fetch("/api/logs?limit=15")
    .then((r) => r.json())
    .then((rows) => {
      rows.reverse().forEach((row) => pushLog(`${row.device}: ${row.action} ${row.detail || ""}`));
    })
    .catch(() => {});

  connectWs();
  refreshTelemetry();
  setInterval(refreshTelemetry, 2500);
  drawChart([]);
})();
