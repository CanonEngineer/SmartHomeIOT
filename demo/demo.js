/**
 * Demo Lab standalone (GitHub Pages) — simulação 100% no browser.
 * Não depende do backend Python; ideal para botão "Abrir Interface" no README.
 */
(() => {
  const $ = (sel) => document.querySelector(sel);
  const logList = $("#log-list");
  const expList = $("#exp-list");
  let latencySeries = [];
  let syncPulse = 0;
  let sqi = 92;

  const state = {
    sensors: { temperature: 24.5, humidity: 55, light: 62, motion: false },
    actuators: {
      led: false,
      buzzer: false,
      relay: { "1": false, "2": false, "3": false, "4": false },
      servo: { "porta-1": 0, "porta-2": 0, arm: 45 },
      door: { main: false, garage: false },
    },
    boards: {
      arduino: { online: true, sync: true },
      raspberry: { online: true, sync: true },
    },
    last_event: "Demo Lab (modo browser)",
    sync_pulse: 0,
    sync_quality_index: 92,
    pair_skew_ms: 18,
  };

  function pushLog(text) {
    const li = document.createElement("li");
    li.innerHTML = `<strong>${new Date().toLocaleTimeString()}</strong> — ${text}`;
    logList.prepend(li);
    while (logList.children.length > 40) logList.removeChild(logList.lastChild);
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
  }

  function render() {
    const s = state.sensors;
    const a = state.actuators;
    const boards = state.boards;
    $("#m-temp").textContent = `${s.temperature.toFixed(1)}°C`;
    $("#m-hum").textContent = `${s.humidity.toFixed(0)}%`;
    $("#m-light").textContent = `${s.light.toFixed(0)}%`;
    $("#m-motion").textContent = s.motion ? "SIM" : "NÃO";
    $("#last-event").textContent = state.last_event;
    $("#sync-status").textContent = `SYNC OK #${state.sync_pulse}`;
    $("#sqi-status").textContent = `SQI ${sqi.toFixed(0)}`;
    $("#r-sqi").textContent = sqi.toFixed(1);
    $("#r-p50").textContent = `${(8 + Math.random() * 4).toFixed(1)} ms`;
    $("#r-p95").textContent = `${(18 + Math.random() * 8).toFixed(1)} ms`;
    $("#r-skew").textContent = `${state.pair_skew_ms.toFixed(1)} ms`;
    setPill($("#ws-status"), true, "DEMO online", "offline");

    $("#bulb-sala").setAttribute("fill", a.relay["1"] ? "#ffe082" : "#3d4f4c");
    $("#bulb-cozinha").setAttribute("fill", a.relay["2"] ? "#ffe082" : "#3d4f4c");
    $("#led-indicator").setAttribute("fill", a.led ? "#7CFFB2" : "#35524e");
    $("#buzzer-indicator").setAttribute("fill", a.buzzer ? "#e07a5f" : "#35524e");
    $("#door-main-panel").classList.toggle("open", a.door.main);
    $("#door-garage-panel").classList.toggle("open", a.door.garage);
    $("#servo-arm-1").setAttribute("transform", `rotate(${a.servo["porta-1"]})`);
    $("#servo-arm-2").setAttribute("transform", `rotate(${a.servo["porta-2"]})`);
    $("#servo-arm-3").setAttribute("transform", `rotate(${-a.servo.arm})`);
    $("#servo-arm-slider").value = a.servo.arm;
    $("#servo-arm-value").textContent = `${a.servo.arm}°`;
    $("#motion-blob").setAttribute("opacity", s.motion ? "0.9" : "0.15");
    $("#arduino-status-text").textContent = boards.arduino.online ? "ONLINE" : "OFFLINE";
    $("#raspberry-status-text").textContent = boards.raspberry.online ? "ONLINE" : "OFFLINE";
    drawChart(latencySeries);
  }

  function setPill(el, online, onlineText, offlineText) {
    el.classList.toggle("online", online);
    el.classList.toggle("offline", !online);
    el.textContent = online ? onlineText : offlineText;
  }

  function pulse(event) {
    const t0 = performance.now();
    state.sync_pulse = (state.sync_pulse + 1) % 1000;
    state.last_event = event;
    state.pair_skew_ms = 10 + Math.random() * 40;
    sqi = Math.max(60, Math.min(99, sqi + (Math.random() * 4 - 1.5)));
    state.sync_quality_index = sqi;
    latencySeries.push(performance.now() - t0 + 4 + Math.random() * 12);
    if (latencySeries.length > 40) latencySeries.shift();
    pushLog(event);
    render();
  }

  function applyAction(payload) {
    const a = state.actuators;
    if (payload.action === "led") a.led = !!payload.on;
    if (payload.action === "buzzer") a.buzzer = !!payload.on;
    if (payload.action === "relay") a.relay[String(payload.channel)] = !!payload.on;
    if (payload.action === "door") {
      a.door[payload.door_id] = !!payload.open;
      const angle = payload.open ? 90 : 0;
      if (payload.door_id === "main") a.servo["porta-1"] = angle;
      if (payload.door_id === "garage") a.servo["porta-2"] = angle;
    }
    if (payload.action === "servo") a.servo[payload.servo_id] = Number(payload.angle);
    if (payload.action === "simulate") {
      const sc = payload.scenario;
      if (sc === "welcome") {
        a.led = true; a.relay["1"] = true; a.door.main = true; a.servo["porta-1"] = 90; a.servo.arm = 120;
      } else if (sc === "garage") {
        a.door.garage = true; a.servo["porta-2"] = 90; a.relay["2"] = true;
      } else if (sc === "alarm") {
        a.buzzer = true; a.led = true; a.relay["1"] = true; a.relay["2"] = true; state.sensors.motion = true;
      } else if (sc === "night") {
        a.door.main = false; a.door.garage = false; a.servo["porta-1"] = 0; a.servo["porta-2"] = 0;
        a.relay["1"] = false; a.relay["2"] = false; a.led = false; a.buzzer = false; a.servo.arm = 0;
      } else if (sc === "sync_test") {
        a.servo["porta-1"] = 90; a.led = true;
      }
    }
    pulse(payload.action === "simulate" ? `Cenário ${payload.scenario}` : `Ação ${payload.action}`);
  }

  function runExperiment(name) {
    pushLog(`Experimento (demo): ${name}`);
    if (name === "fault_injection") sqi = 55;
    if (name === "sync_latency") sqi = 94;
    const id = Math.random().toString(16).slice(2, 8);
    const li = document.createElement("li");
    li.innerHTML = `<strong>${name}</strong> · SQI ${sqi.toFixed(0)} · demo-id ${id}`;
    expList.prepend(li);
    pulse(`Experimento ${name}`);
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
      applyAction(payload);
    });
  });

  document.querySelectorAll("button[data-scenario]").forEach((btn) => {
    btn.addEventListener("click", () => applyAction({ action: "simulate", scenario: btn.dataset.scenario }));
  });

  document.querySelectorAll("button[data-experiment]").forEach((btn) => {
    btn.addEventListener("click", () => runExperiment(btn.dataset.experiment));
  });

  $("#servo-arm-slider").addEventListener("input", (e) => {
    applyAction({ action: "servo", servo_id: "arm", angle: Number(e.target.value) });
  });

  // Sensor drift + heartbeat visual
  setInterval(() => {
    const t = Date.now() / 1000;
    state.sensors.temperature = 23.5 + 2.2 * Math.sin(t / 18);
    state.sensors.humidity = 50 + 7 * Math.sin(t / 25);
    state.sensors.light = 55 + 25 * Math.sin(t / 30);
    state.sensors.motion = state.actuators.door.main || Math.random() < 0.05;
    syncPulse++;
    state.sync_pulse = syncPulse % 1000;
    render();
  }, 2000);

  pushLog("Demo Lab carregado (GitHub Pages — sem backend)");
  render();
})();
