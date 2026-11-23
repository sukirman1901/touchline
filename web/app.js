"use strict";
const $ = id => document.getElementById(id);
const video = $("video");
const projectId = new URLSearchParams(location.search).get("project") || "legacy";
const projectUrl = path => `${path}${path.includes("?") ? "&" : "?"}project=${encodeURIComponent(projectId)}`;
const exportKey = `touchline.export.${projectId}`;
const state = {project: null, events: [], filter: "all", draft: null, marking: null, groups: new Map()};
const outcomes = {completed: "Sampai ke rekan", intercepted: "Dipotong lawan", out: "Keluar lapangan", unknown: "Belum diketahui"};
const colors = {completed: "#64d494", intercepted: "#ff6b67", out: "#ff6b67", unknown: "#ffb04e"};
const svgNS = "http://www.w3.org/2000/svg";
let toastTimer;

function time(value, precise = false) {
  const safe = Math.max(0, Number(value) || 0);
  const ticks = precise ? Math.round(safe * 100) : Math.floor(safe) * 100;
  const minutes = Math.floor(ticks / 6000).toString().padStart(2, "0");
  const seconds = ((ticks % 6000) / 100).toFixed(precise ? 2 : 0).padStart(precise ? 5 : 2, "0");
  return `${minutes}:${seconds}`;
}
function notify(message) {
  $("toast").textContent = message;
  $("toast").hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { $("toast").hidden = true; }, 3500);
}
async function api(path, body) {
  const response = await fetch(projectUrl(path), body === undefined ? {} : {
    method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify(body)
  });
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || `Permintaan gagal (${response.status}).`);
  return data;
}
function element(tag, attrs = {}, text) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(attrs)) node.setAttribute(key, value);
  if (text !== undefined) node.textContent = text;
  return node;
}
function shape(tag, attrs) {
  const node = document.createElementNS(svgNS, tag);
  for (const [key, value] of Object.entries(attrs)) node.setAttribute(key, value);
  return node;
}
function icon(name) {
  const node = shape("svg", {class: "icon", "aria-hidden": "true"});
  node.append(shape("use", {href: `/icons.svg#${name}`}));
  return node;
}
function seek(value) {
  video.currentTime = Math.max(0, Math.min(state.project?.duration || 75, value));
  draw();
}
function groundArc(x, y, rx, ry) {
  // OpenCV reference: start=-30°, end=240° (270° arc, open above the feet).
  const point = angle => [x + rx * Math.cos(angle * Math.PI / 180),
    y + ry * Math.sin(angle * Math.PI / 180)];
  const a = point(-30), b = point(240);
  return `M${a[0]},${a[1]} A${rx},${ry} 0 1 1 ${b[0]},${b[1]}`;
}
function ring(group, position, color, radius = 23, dashed = false) {
  group.append(shape("path", {d: groundArc(position[0] * 1280, position[1] * 720,
    radius, radius * 8 / 23), fill: "none", stroke: color, "stroke-width": 3,
    "stroke-dasharray": dashed ? "6 5" : "none"}));
}
function trajectoryAt(path, timestamp) {
  if (!path?.length) return null;
  let low = 0, high = path.length;
  while (low < high) {
    const mid = (low + high) >> 1;
    if (path[mid].time < timestamp) low = mid + 1;
    else high = mid;
  }
  if (path[low] && Math.abs(path[low].time - timestamp) < 1e-6) return path[low];
  if (!low || low >= path.length) return null;
  const a = path[low - 1], b = path[low];
  if (b.time - a.time > .21 || a.segment !== b.segment || a.track !== b.track) return null;
  const weight = (timestamp - a.time) / (b.time - a.time);
  return {...a, position: a.position.map((v, i) => v + (b.position[i] - v) * weight)};
}
function carrier(group, sample) {
  // One carrier layer per track, even when both live inference and an event
  // describe the same possession. The later event/draft has display priority.
  if (sample.track != null) {
    for (const node of [...group.children]) {
      if (node.getAttribute("data-carrier-track") === String(sample.track)) node.remove();
      if (node.getAttribute("data-player-track") === String(sample.track)) {
        for (const ring of node.querySelectorAll("ellipse,path")) ring.remove();
      }
    }
  }
  const marker = shape("g", {"data-carrier-track": sample.track ?? "unknown"});
  const x = sample.position[0] * 1280, y = sample.position[1] * 720;
  const color = sample.team_color || "#b6bdb9";
  const radius = Math.max(18, Math.min(42, (sample.width || .025) * 1280 * .9));
  marker.append(shape("path", {d: groundArc(x, y, radius, radius * .29),
    fill: "none", stroke: color, "stroke-width": 2.4}));
  const top = y - (sample.height || .09) * 720 - 10;
  marker.append(shape("path", {d: `M${x - 6},${top - 9} L${x + 6},${top - 9} L${x},${top} Z`,
    fill: color, opacity: .95}));
  group.append(marker);
}
function ballTrail(group, path, timestamp) {
  const current = trajectoryAt(path, timestamp);
  if (!current) return;
  const points = path.filter(p => p.time >= timestamp - .4 && p.time < timestamp);
  points.push({...current, time: timestamp});
  for (let i = 1; i < points.length; i++) {
    const a = points[i - 1], b = points[i];
    if (b.time - a.time > .21 || a.segment !== b.segment || a.track !== b.track) continue;
    const opacity = Math.max(0, 1 - (timestamp - b.time) / .4);
    group.append(shape("line", {x1: a.position[0] * 1280, y1: a.position[1] * 720,
      x2: b.position[0] * 1280, y2: b.position[1] * 720, stroke: "#27eadc",
      "stroke-width": 8, "stroke-linecap": "round", opacity: opacity * .35}));
    group.append(shape("line", {x1: a.position[0] * 1280, y1: a.position[1] * 720,
      x2: b.position[0] * 1280, y2: b.position[1] * 720, stroke: "#8ffff1",
      "stroke-width": 2, "stroke-linecap": "round", opacity: opacity * .8}));
  }
}
function drawEvent(group, event, timestamp, draft = false) {
  if (!event.source || !event.target || (!draft && !(event.start <= timestamp && timestamp <= event.end))) return;
  if (event.provenance === "automatic" && event.trajectory) {
    if (!$("show-tracks").checked && !event.reviewed) return;
    if (event.kind === "pass") ballTrail(group, event.trajectory, timestamp);
    else {
      const sample = trajectoryAt(event.trajectory, timestamp);
      if (sample) carrier(group, sample);
    }
    return;
  }
  const color = event.kind === "pass" ? colors[event.outcome] : colors.unknown;
  const dashed = draft || !event.reviewed;
  if (event.kind === "pass") {
    const [x1, y1] = [event.source[0] * 1280, event.source[1] * 720];
    const [x2, y2] = [event.target[0] * 1280, event.target[1] * 720];
    group.append(shape("line", {x1, y1, x2, y2, stroke: color, "stroke-width": 3,
      "stroke-dasharray": dashed ? "8 6" : "none"}));
    const angle = Math.atan2(y2 - y1, x2 - x1);
    const size = Math.hypot(x2 - x1, y2 - y1) * .05;
    const points = [[x2 - size * Math.cos(angle - Math.PI / 4), y2 - size * Math.sin(angle - Math.PI / 4)],
      [x2, y2], [x2 - size * Math.cos(angle + Math.PI / 4), y2 - size * Math.sin(angle + Math.PI / 4)]];
    group.append(shape("polyline", {points: points.map(p => p.join(",")).join(" "), fill: "none", stroke: color, "stroke-width": 3}));
    ring(group, event.source, color, 23, dashed);
  } else {
    const p = Math.min(1, Math.max(0, (timestamp - event.start) / (event.end - event.start || 1)));
    ring(group, event.source.map((v, i) => v + (event.target[i] - v) * p), color, 23, dashed);
  }
}
function draw() {
  const timestamp = video.currentTime;
  $("current-time").textContent = time(timestamp, true);
  $("seek").value = timestamp;
  $("playhead").style.left = `${Math.min(100, timestamp / (state.project?.duration || 75) * 100)}%`;
  const sourceSeconds = Math.floor(timestamp + (state.project?.sourceOffset ?? 5910));
  $("source-time").textContent = `SUMBER ${Math.floor(sourceSeconds / 3600).toString().padStart(2, "0")}:${time(sourceSeconds % 3600)}`;
  const group = shape("g", {});
  const map = $("pitch-map");
  map.hidden = true;
  // Preserve existing observations while the replacement analysis is unavailable.
  // Neutral rings are explicitly detections, never inferred ball ownership.
  if ($("show-tracks").checked && state.project?.automatic?.players?.length) {
    const frames = state.project.automatic.players;
    let low = 0, high = frames.length;
    while (low < high) {
      const mid = (low + high) >> 1;
      if (frames[mid].time < timestamp) low = mid + 1;
      else high = mid;
    }
    const exact = frames[low] && Math.abs(frames[low].time - timestamp) < 1e-6;
    const a = exact ? frames[low] : frames[low - 1], b = frames[low];
    if (a && b && a.segment === b.segment && b.time - a.time <= .21) {
      const field = state.project.automatic.metrics?.field;
      const projected = a.players.filter(p => p.pitch);
      if (field && projected.length) {
        map.hidden = false;
        map.setAttribute("viewBox", `-2 -2 ${field.length+4} ${field.width+4}`);
        map.replaceChildren(shape("rect", {x:0,y:0,width:field.length,height:field.width,
          fill:"none",stroke:"#8a9c88","stroke-width":.5}),
          shape("line", {x1:field.length/2,y1:0,x2:field.length/2,y2:field.width,
            stroke:"#8a9c88","stroke-width":.5}),
          shape("circle", {cx:field.length/2,cy:field.width/2,r:9.15,
            fill:"none",stroke:"#8a9c88","stroke-width":.5}));
        for (const p of projected) {
          const dot = shape("circle", {cx:p.pitch[0],cy:p.pitch[1],r:1.3,
            fill:p.team_color || "#7c8580",stroke:"#26392d","stroke-width":.3});
          const title = shape("title", {});
          title.textContent = `T${p.track}${p.speed_kmh == null ? "" : ` · ${p.speed_kmh.toFixed(1)} km/jam`}`;
          dot.append(title); map.append(dot);
        }
      }
      const next = new Map(b.players.map(p => [p.track, p]));
      for (const player of a.players) {
        const target = next.get(player.track);
        if (!target) continue;
        const weight = exact ? 0 : (timestamp - a.time) / (b.time - a.time);
        const position = player.position.map((v, i) => v + (target.position[i] - v) * weight);
        const radius = Math.max(12, Math.min(36, player.width * 1280 * .75));
        const color = player.role === "referee" ? "#f5bc55" : player.team_color || "#b6bdb9";
        const playerLayer = shape("g", {"data-player-track": player.track});
        ring(playerLayer, position, color, radius, player.role === "referee");
        if (player.role === "goalkeeper") ring(playerLayer, position, color, radius + 5);
        const label = shape("text", {x: position[0] * 1280, y: position[1] * 720 + 22,
          "text-anchor": "middle", "font-size": 12, "font-weight": 600,
          fill: color});
        label.textContent = `T${player.track}${player.speed_kmh == null ? "" : ` · ${player.speed_kmh.toFixed(1)} km/j`}`;
        playerLayer.append(label);
        group.append(playerLayer);
      }
    }
    const owner = trajectoryAt(state.project.automatic.owners, timestamp);
    if (owner) carrier(group, owner);
    ballTrail(group, state.project.automatic.balls, timestamp);
  } else if ($("show-tracks").checked && state.project) {
    const frame = Math.floor(timestamp * state.project.fps) + 1;
    const rows = state.groups.get(frame) || state.groups.get(frame - 1) || [];
    for (const row of rows) {
      if (row.kind === "ball") {
        group.append(shape("circle", {cx: row.position[0] * 1280, cy: row.position[1] * 720,
          r: 6, fill: "none", stroke: "#fff", "stroke-width": 2}));
      } else {
        ring(group, row.position, "#e8eeea", 18);
      }
    }
  }
  if ($("show-events").checked) {
    for (const event of state.events) if (event.id !== state.draft?.id) drawEvent(group, event, timestamp);
  }
  if (state.draft) {
    drawEvent(group, state.draft, timestamp, true);
    if (!state.draft.trajectory) {
      if (state.draft.source) ring(group, state.draft.source, "#ffb04e", 23, true);
      if (state.draft.target) ring(group, state.draft.target, "#edf0eb", 23, true);
    }
  }
  $("overlay").replaceChildren(group);
}
function renderStats(stats) {
  $("stat-total").textContent = stats.total;
  $("stat-completion").textContent = stats.completion === null ? "—" : `${stats.completion}%`;
  $("stat-context").textContent = `${stats.reviewed} hasil terverifikasi · ${stats.unknown} belum diketahui · ${stats.unreviewed} belum direview`;
}
function renderEvents() {
  $("event-count").textContent = state.events.length;
  const list = $("event-list");
  const markers = $("timeline-markers");
  list.replaceChildren();
  markers.replaceChildren();
  for (const event of state.events) {
    const marker = element("button", {class: `timeline-marker ${event.kind}`, title: `${time(event.start)} · ${event.kind === "pass" ? "Umpan" : "Penguasaan"}`,
      "aria-label": `Buka kejadian ${time(event.start)}`});
    marker.style.left = `${event.start / state.project.duration * 100}%`;
    marker.style.width = `${(event.end - event.start) / state.project.duration * 100}%`;
    marker.onclick = () => openEvent(event);
    markers.append(marker);
    if (state.filter !== "all" && !(state.filter === "unreviewed" ? !event.reviewed : event.kind === state.filter)) continue;
    const button = element("button", {class: `event-row${event.id === state.draft?.id ? " active" : ""}`});
    const title = element("div");
    const automatic = event.provenance === "automatic";
    title.append(element("strong", {}, event.kind === "pass" ?
      (automatic && event.outcome === "unknown" ? "Kandidat umpan" : outcomes[event.outcome]) :
      (automatic ? "Estimasi penguasaan" : "Penguasaan · manual")));
    title.append(element("small", {}, event.player || "Ditandai pelatih"));
    const status = element("span", {class: `status-tag${event.reviewed ? " confirmed" : ""}`},
      event.reviewed ? "Diperiksa" : automatic ? "AI · perlu diperiksa" : "Belum direview");
    button.append(element("span", {class: "mono"}, time(event.start, true)), title, status);
    button.onclick = () => openEvent(event);
    list.append(button);
  }
  if (!list.children.length) {
    const empty = element("div", {class: "empty-state"});
    const content = element("div");
    content.append(element("h3", {}, state.events.length ? "Tidak ada kejadian pada filter ini" : "Belum ada kandidat kejadian"));
    content.append(element("p", {}, state.events.length ? "Pilih filter lain untuk melihat kejadian tersimpan." :
      "Hasil analisis otomatis muncul di sini. Penandaan manual tersedia untuk koreksi."));
    empty.append(icon("film"), content);
    list.append(empty);
  }
  draw();
}
async function refreshEvents() {
  const data = await api("/api/events");
  state.events = data.events;
  renderStats(data.stats);
  renderEvents();
}
function markMode(mode) {
  state.marking = mode;
  $("stage").classList.toggle("marking", !!mode);
  $("mark-instruction").hidden = !mode;
  $("mark-instruction").textContent = mode === "source" ? "Klik kaki pemain pada awal kejadian" : "Klik posisi akhir pada momen ini";
  $("mark-source").classList.toggle("armed", mode === "source");
  $("mark-target").classList.toggle("armed", mode === "target");
  if (mode) {
    video.pause();
    $("stage").scrollIntoView({behavior: "instant", block: "center"});
    $("stage").focus({preventScroll: true});
  }
}
function syncDraft() {
  if (!state.draft) return;
  if (state.draft.kind !== $("kind").value || Math.abs(state.draft.start - Number($("start").value)) > 1e-6 ||
      Math.abs(state.draft.end - Number($("end").value)) > 1e-6) {
    delete state.draft.trajectory;
    state.draft.provenance = "coach";
  }
  Object.assign(state.draft, {kind: $("kind").value, start: Number($("start").value),
    end: Number($("end").value), player: $("player").value, outcome: $("outcome").value,
    note: $("note").value, reviewed: $("reviewed").checked});
  for (const [key, ids] of [["source", ["sx", "sy"]], ["target", ["tx", "ty"]]]) {
    const next = ids.every(id => $(id).value !== "") ? ids.map(id => Number($(id).value) / 100) : null;
    if (!next || !state.draft[key] || next.some((v, i) => Math.abs(v - state.draft[key][i]) > 1e-10)) {
      state.draft[key] = next;
      delete state.draft.trajectory;
      state.draft.provenance = "coach";
    }
  }
  $("outcome-field").hidden = state.draft.kind === "possession";
  $("geometry-note").textContent = state.draft.trajectory ?
    "Lintasan otomatis dari sampel video. Mengubah posisi mengalihkannya ke anotasi manual." : state.draft.kind === "pass" ?
    "Garis menghubungkan dua posisi manual, bukan lintasan bola." :
    "Gerak lingkaran di antara dua titik manual. Buat interval baru jika arah atau kamera berubah.";
  $("save-status").textContent = "Draf belum disimpan";
  updatePositionButtons();
  draw();
}
function updatePositionButtons() {
  for (const key of ["source", "target"]) {
    const point = state.draft?.[key];
    const button = $(`mark-${key}`);
    button.classList.toggle("chosen", !!point);
    button.replaceChildren(icon("target"), element("span", {}, point ?
      `${(point[0] * 100).toFixed(1)}%, ${(point[1] * 100).toFixed(1)}%` : "Pilih di video"));
    button.setAttribute("aria-label", `Pilih posisi ${key === "source" ? "awal" : "akhir"} di video`);
  }
}
function openEvent(event = null) {
  if (state.draft && !confirm("Tutup perubahan yang belum disimpan?")) return;
  video.pause();
  const start = Math.round(Math.min(video.currentTime, state.project.duration - 1) * 1000) / 1000;
  state.draft = event ? structuredClone(event) : {kind: "pass", start, end: Math.min(start + 2, state.project.duration),
    source: null, target: null, outcome: "unknown", note: "", player: "", reviewed: false};
  $("overview").hidden = true;
  $("editor").hidden = false;
  $("editor-heading").textContent = event ? "Review kejadian" : "Tandai kejadian";
  $("form-error").hidden = true;
  $("delete-event").hidden = !event;
  for (const key of ["kind", "start", "end", "outcome", "note", "player"]) {
    $(key).value = ["start", "end"].includes(key) ? state.draft[key].toFixed(3) : state.draft[key];
  }
  $("reviewed").checked = state.draft.reviewed;
  window.refreshDropdowns();
  for (const [key, ids] of [["source", ["sx", "sy"]], ["target", ["tx", "ty"]]]) {
    ids.forEach((id, index) => $(id).value = state.draft[key] ? String(state.draft[key][index] * 100) : "");
  }
  markMode(null);
  syncDraft();
  if (event) seek(event.start);
  renderEvents();
  $("editor-heading").scrollIntoView({block: "nearest"});
}
function closeEditor(force = false) {
  if (!force && state.draft && !confirm("Tutup perubahan yang belum disimpan?")) return;
  state.draft = null;
  markMode(null);
  $("editor").hidden = true;
  $("overview").hidden = false;
  $("save-status").textContent = "Semua perubahan tersimpan di Mac ini";
  renderEvents();
}
function setPosition(x, y) {
  if (!state.marking || !state.draft) return;
  const ids = state.marking === "source" ? ["sx", "sy"] : ["tx", "ty"];
  $(ids[0]).value = (x * 100).toFixed(2);
  $(ids[1]).value = (y * 100).toFixed(2);
  $(state.marking === "source" ? "start" : "end").value = video.currentTime.toFixed(3);
  syncDraft();
  markMode(null);
  notify("Posisi dan waktu dicatat.");
}
$("stage").addEventListener("click", event => {
  if (!state.marking) return;
  const rect = video.getBoundingClientRect();
  const ratio = (video.videoWidth || 1280) / (video.videoHeight || 720);
  const width = Math.min(rect.width, rect.height * ratio), height = width / ratio;
  const x = (event.clientX - rect.left - (rect.width - width) / 2) / width;
  const y = (event.clientY - rect.top - (rect.height - height) / 2) / height;
  if (x >= 0 && x <= 1 && y >= 0 && y <= 1) setPosition(x, y);
});
$("event-form").oninput = syncDraft;
$("event-form").onsubmit = async event => {
  event.preventDefault();
  syncDraft();
  $("save-event").disabled = true;
  $("form-error").hidden = true;
  try {
    if (!state.draft.source || !state.draft.target) throw new Error("Tandai kedua posisi pada video, atau isi koordinatnya.");
    await api("/api/events", state.draft);
    closeEditor(true);
    await refreshEvents();
    notify("Kejadian tersimpan di Mac.");
  } catch (error) {
    $("form-error").textContent = error.message;
    $("form-error").hidden = false;
  } finally { $("save-event").disabled = false; }
};
$("delete-event").onclick = async () => {
  if (!confirm("Hapus kejadian ini?")) return;
  try {
    await api("/api/events/delete", {id: state.draft.id});
    closeEditor(true);
    await refreshEvents();
    notify("Kejadian dihapus.");
  } catch (error) { notify(error.message); }
};
$("mark-source").onclick = () => markMode("source");
$("mark-target").onclick = () => markMode("target");
$("cancel-edit").onclick = () => closeEditor();
$("new-event").onclick = () => openEvent();
document.querySelectorAll("[data-filter]").forEach(button => {
  button.onclick = () => {
    state.filter = button.dataset.filter;
    document.querySelectorAll("[data-filter]").forEach(b => b.setAttribute("aria-pressed", b === button));
    renderEvents();
  };
});
async function togglePlayback() {
  if (video.paused) { try { await video.play(); } catch (error) { notify(`Video tidak bisa diputar: ${error.message}`); } }
  else video.pause();
}
$("play").onclick = togglePlayback;
$("back").onclick = () => { video.pause(); seek(video.currentTime - 1 / (state.project?.fps || 30)); };
$("forward").onclick = () => { video.pause(); seek(video.currentTime + 1 / (state.project?.fps || 30)); };
$("seek").oninput = event => seek(Number(event.target.value));
$("speed").onchange = event => { video.playbackRate = Number(event.target.value); };
video.muted = true;
$("mute").onclick = () => {
  video.muted = !video.muted;
  $("mute").replaceChildren(icon(video.muted ? "volumemute" : "volumehigh"));
  $("mute").setAttribute("aria-label", video.muted ? "Aktifkan suara" : "Matikan suara");
  $("mute").title = video.muted ? "Aktifkan suara" : "Matikan suara";
  $("mute").setAttribute("aria-pressed", video.muted);
};
$("fullscreen").onclick = async () => {
  try {
    if (document.fullscreenElement) await document.exitFullscreen();
    else await $("stage").requestFullscreen();
  } catch { notify("Layar penuh tidak tersedia di browser ini."); }
};
video.onplay = () => { $("play").replaceChildren(icon("pause")); $("play").setAttribute("aria-label", "Jeda video"); };
video.onpause = () => { $("play").replaceChildren(icon("play")); $("play").setAttribute("aria-label", "Putar video"); };
video.onloadedmetadata = () => { $("play").disabled = false; seek(Math.min(2, video.duration / 10)); };
video.onerror = () => {
  $("load-state").hidden = false;
  $("load-state").classList.add("error");
  $("load-state").textContent = "Video gagal dimuat. Pastikan server berjalan, lalu buka kembali proyek dari beranda.";
};
video.addEventListener("timeupdate", draw);
video.addEventListener("seeked", draw);
if ("requestVideoFrameCallback" in video) {
  function videoFrame() { draw(); video.requestVideoFrameCallback(videoFrame); }
  video.requestVideoFrameCallback(videoFrame);
}
$("show-tracks").onchange = draw;
$("show-events").onchange = draw;
document.addEventListener("keydown", event => {
  if (["INPUT", "TEXTAREA", "SELECT", "BUTTON", "SUMMARY"].includes(event.target.tagName) ||
      document.querySelector("dialog[open]")) return;
  if (event.code === "Space") { event.preventDefault(); togglePlayback(); }
  if (event.code === "ArrowLeft") { event.preventDefault(); $("back").click(); }
  if (event.code === "ArrowRight") { event.preventDefault(); $("forward").click(); }
  if (event.code === "Escape") markMode(null);
});
$("help-button").onclick = () => $("help-dialog").showModal();
$("help-close").onclick = () => $("help-dialog").close();
$("export-open").onclick = () => $("export-dialog").showModal();
$("export-close").onclick = () => $("export-dialog").close();
let exportPoll;
async function checkExport(id) {
  try {
    const job = await api(`/api/jobs/${id}`);
    if (job.state === "done") {
      $("export-status").textContent = "Video siap. Anotasi terverifikasi dan audio sudah digabung.";
      $("download").href = job.url;
      $("download").hidden = false;
      $("export-submit").disabled = false;
      localStorage.removeItem(exportKey);
    } else if (job.state === "error") {
      throw new Error(job.error);
    } else {
      $("export-status").textContent = `Memproses video… ${job.progress}%`;
      exportPoll = setTimeout(() => checkExport(id), 1500);
    }
  } catch (error) {
    $("export-status").textContent = `Ekspor berhenti: ${error.message}`;
    $("export-submit").disabled = false;
    localStorage.removeItem(exportKey);
  }
}
$("export-form").onsubmit = async event => {
  event.preventDefault();
  $("export-submit").disabled = true;
  $("download").hidden = true;
  $("export-status").textContent = "Menyiapkan video…";
  try {
    const job = await api("/api/export", {start: Number($("export-start").value), end: Number($("export-end").value)});
    localStorage.setItem(exportKey, job.id);
    clearTimeout(exportPoll);
    checkExport(job.id);
  } catch (error) {
    $("export-status").textContent = error.message;
    $("export-submit").disabled = false;
  }
};
async function init() {
  try {
    state.project = await api("/api/project");
    document.title = `Touchline — ${state.project.name}`;
    $("project-name").textContent = state.project.name;
    $("project-subtitle").textContent = `${state.project.clip} · ${time(state.project.duration)} video`;
    $("breadcrumb-name").textContent = state.project.name;
    $("total-time").textContent = ` / ${time(state.project.duration, true)}`;
    document.querySelectorAll(".timeline-ruler span").forEach((node, index) => {
      node.textContent = time(state.project.duration * index / 5);
    });
    $("stage").style.aspectRatio = `${state.project.width} / ${state.project.height}`;
    $("overlay").setAttribute("preserveAspectRatio", "none");
    video.setAttribute("aria-label", state.project.name);
    video.src = projectUrl("/media");
    state.events = state.project.events;
    for (const row of state.project.observations) {
      if (!state.groups.has(row.frame)) state.groups.set(row.frame, []);
      state.groups.get(row.frame).push(row);
    }
    updateAnalysisStatus(state.project.automatic);
    if (state.project.automatic?.status === "pending" || state.project.automatic?.job?.status === "running") {
      setTimeout(awaitAnalysis, 5000);
    }
    for (const id of ["seek", "start", "end", "export-start", "export-end"]) $(id).max = state.project.duration;
    $("export-end").value = state.project.duration;
    $("load-state").hidden = true;
    $("export-open").disabled = false;
    $("new-event").disabled = false;
    for (let index = 0; index < 10; index++) {
      const timestamp = index * state.project.duration / 10;
      const thumb = element("button", {class: "film-frame", title: time(timestamp, true),
        "aria-label": `Ke cuplikan ${time(timestamp, true)}`});
      thumb.style.backgroundPosition = `${index * 100 / 9}% center`;
      if (projectId !== "legacy") {
        thumb.style.backgroundImage = "none";
        thumb.textContent = time(timestamp);
      }
      thumb.onclick = () => { video.pause(); seek(timestamp); };
      $("filmstrip").append(thumb);
    }
    renderStats(state.project.stats);
    renderEvents();
    if (video.readyState >= 1) { $("play").disabled = false; seek(Math.min(2, video.duration / 10)); }
    const job = localStorage.getItem(exportKey);
    if (job) { $("export-submit").disabled = true; checkExport(job); }
  } catch (error) {
    $("load-state").textContent = `Gagal memuat proyek: ${error.message}. Muat ulang untuk mencoba lagi.`;
    $("load-state").classList.add("error");
  }
}
function updateAnalysisStatus(analysis) {
  const modules = analysis?.modules;
  $("pipeline-status").textContent = modules ?
    `Tracking tersedia · tim ${analysis.teams?.length ? "terkelompok" : "belum teridentifikasi"} · kalibrasi ${modules.calibration?.status === "ready" ? "tersedia" : "belum tersedia"}.` :
    "Hasil pipeline terpadu belum tersedia.";
  $("team-legend").replaceChildren();
  for (const team of analysis?.teams || []) {
    const label = element("span"), swatch = element("i", {"aria-hidden":"true"});
    swatch.style.backgroundColor = team.color;
    label.append(swatch, document.createTextNode(`${team.name} · estimasi jersey`));
    $("team-legend").append(label);
  }
  $("metric-summary").textContent = modules?.calibration?.status === "ready" ?
    "Speed dan jarak memakai posisi terkalibrasi; celah tracking dikecualikan." :
    "Speed, jarak, heatmap, kontrol ruang dan minimap menunggu model titik lapangan yang sesuai.";
  const running = analysis?.job?.status === "running";
  if (analysis?.status === "ready") {
    const {sampled, detected, accepted} = analysis.coverage;
    $("coverage").textContent = `Bola: ${detected}/${sampled} sampel terdeteksi; ${accepted} lolos filter temporal.`;
    $("analysis-status").textContent = running ? `AI · ${analysis.job.progress}%` : "AI · estimasi";
    $("analysis-status").title = "Penguasaan dan umpan merupakan kandidat otomatis, belum diverifikasi pelatih.";
  } else {
    $("analysis-status").textContent = "AI · menunggu hasil";
    $("coverage").textContent = "Analisis otomatis belum tersedia untuk klip ini.";
  }
}
async function awaitAnalysis() {
  try {
    const analysis = await api("/api/analysis");
    state.project.automatic = analysis;
    updateAnalysisStatus(analysis);
    if (analysis.job?.status === "error") {
      notify("Analisis terhenti. Hasil sebelumnya tetap tersedia.");
    } else if (analysis.job?.status === "running") {
      setTimeout(awaitAnalysis, 5000);
    } else if (analysis.status === "ready") {
      await refreshEvents();
      notify(analysis.events?.length ?
        "Analisis selesai. Kandidat kejadian tersedia untuk diperiksa." :
        "Analisis selesai; belum ada kandidat kejadian yang lolos filter.");
    } else if (analysis.status === "pending") {
      setTimeout(awaitAnalysis, 10000);
    }
  } catch {
    $("analysis-status").textContent = "AI · koneksi terputus";
    $("analysis-status").title = "Muat ulang setelah server kembali tersedia.";
  }
}
init();
