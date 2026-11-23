"use strict";
const $ = id => document.getElementById(id);
const video = $("video");
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
  const response = await fetch(path, body === undefined ? {} : {
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
function seek(value) {
  video.currentTime = Math.max(0, Math.min(state.project?.duration || 75, value));
  draw();
}
function ring(group, position, color, radius = 23, dashed = false) {
  group.append(shape("ellipse", {cx: position[0] * 1280, cy: position[1] * 720,
    rx: radius, ry: radius * 8 / 23, fill: "none", stroke: color, "stroke-width": 3,
    "stroke-dasharray": dashed ? "6 5" : "none"}));
}
function drawEvent(group, event, timestamp, draft = false) {
  if (!event.source || !event.target || (!draft && !(event.start <= timestamp && timestamp <= event.end))) return;
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
  const sourceSeconds = Math.floor(timestamp + (state.project?.sourceOffset || 5910));
  $("source-time").textContent = `SUMBER ${Math.floor(sourceSeconds / 3600).toString().padStart(2, "0")}:${time(sourceSeconds % 3600)}`;
  const group = shape("g", {});
  if ($("show-tracks").checked && state.project) {
    const frame = Math.floor(timestamp * state.project.fps) + 1;
    // Hold a sampled observation for at most one skipped frame; never bridge long gaps.
    const rows = state.groups.get(frame) || state.groups.get(frame - 1) || [];
    for (const row of rows) {
      if (row.kind === "ball") {
        group.append(shape("circle", {cx: row.position[0] * 1280, cy: row.position[1] * 720,
          r: 8, fill: "none", stroke: "#edf0eb", "stroke-width": 2}));
      } else {
        const color = row.team === "Cluster A" ? "#ffb04e" : "#65b9f4";
        ring(group, row.position, color, 15);
        const label = shape("text", {x: row.position[0] * 1280, y: row.position[1] * 720 + 20,
          fill: "#fff", "font-size": 12, "text-anchor": "middle", "paint-order": "stroke",
          stroke: "#111413", "stroke-width": 3, "font-family": "sans-serif"});
        label.textContent = `T${row.track}`;
        group.append(label);
      }
    }
  }
  if ($("show-events").checked) {
    for (const event of state.events) if (event.id !== state.draft?.id) drawEvent(group, event, timestamp);
  }
  if (state.draft) {
    drawEvent(group, state.draft, timestamp, true);
    if (state.draft.source) ring(group, state.draft.source, "#ffb04e", 23, true);
    if (state.draft.target) ring(group, state.draft.target, "#edf0eb", 23, true);
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
    const marker = element("button", {class: "timeline-marker", title: `${time(event.start)} · ${event.kind === "pass" ? "Umpan" : "Penguasaan"}`,
      "aria-label": `Buka kejadian ${time(event.start)}`});
    marker.style.left = `${event.start / state.project.duration * 100}%`;
    marker.style.width = `${(event.end - event.start) / state.project.duration * 100}%`;
    marker.onclick = () => openEvent(event);
    markers.append(marker);
    if (state.filter !== "all" && !(state.filter === "unreviewed" ? !event.reviewed : event.kind === state.filter)) continue;
    const button = element("button", {class: `event-row${event.id === state.draft?.id ? " active" : ""}`});
    const title = element("div");
    title.append(element("strong", {}, event.kind === "pass" ? outcomes[event.outcome] : "Penguasaan · lintasan manual"));
    title.append(element("small", {}, event.player || (event.kind === "pass" ? "Umpan · ditandai pelatih" : "Dua titik posisi · pelatih")));
    const status = element("span", {class: `status-tag${event.reviewed ? " confirmed" : ""}`}, event.reviewed ? "Diperiksa" : "Belum direview");
    button.append(element("span", {class: "mono"}, time(event.start, true)), title, status);
    button.onclick = () => openEvent(event);
    list.append(button);
  }
  if (!list.children.length) {
    const empty = element("div", {class: "empty-state"});
    const content = element("div");
    content.append(element("h3", {}, state.events.length ? "Tidak ada kejadian pada filter ini." : "Mulai dari satu momen."));
    content.append(element("p", {}, state.events.length ? "Pilih filter lain atau tandai kejadian baru." : "Jeda saat bola dilepas, lalu tandai pengumpan dan penerimanya."));
    empty.append(element("span", {class: "empty-number"}, "01"), content);
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
  Object.assign(state.draft, {kind: $("kind").value, start: Number($("start").value),
    end: Number($("end").value), player: $("player").value, outcome: $("outcome").value,
    note: $("note").value, reviewed: $("reviewed").checked});
  for (const [key, ids] of [["source", ["sx", "sy"]], ["target", ["tx", "ty"]]]) {
    state.draft[key] = ids.every(id => $(id).value !== "") ? ids.map(id => Number($(id).value) / 100) : null;
  }
  $("outcome-field").hidden = state.draft.kind === "possession";
  $("geometry-note").textContent = state.draft.kind === "pass" ?
    "Garis menghubungkan dua titik yang Anda tandai. Bukan rekonstruksi lintasan bola." :
    "Lingkaran bergerak lurus di antara dua titik manual. Pecah interval jika arah atau kamera berubah.";
  updatePositionButtons();
  draw();
}
function updatePositionButtons() {
  for (const key of ["source", "target"]) {
    const point = state.draft?.[key];
    const button = $(`mark-${key}`);
    button.classList.toggle("chosen", !!point);
    button.textContent = point ? `${key === "source" ? "Awal" : "Akhir"}: ${(point[0] * 100).toFixed(1)}%, ${(point[1] * 100).toFixed(1)}% · ubah` :
      `Pilih posisi ${key === "source" ? "awal" : "akhir"} di video`;
  }
}
function openEvent(event = null) {
  if (state.draft && !confirm("Tutup perubahan yang belum disimpan?")) return;
  video.pause();
  const start = Math.min(video.currentTime, state.project.duration - 1);
  state.draft = event ? structuredClone(event) : {kind: "pass", start, end: Math.min(start + 2, state.project.duration),
    source: null, target: null, outcome: "unknown", note: "", player: "", reviewed: false};
  $("overview").hidden = true;
  $("editor").hidden = false;
  $("editor-heading").textContent = event ? "Review kejadian" : "Tandai kejadian";
  $("form-error").hidden = true;
  $("delete-event").hidden = !event;
  for (const key of ["kind", "start", "end", "outcome", "note", "player"]) $(key).value = state.draft[key];
  $("reviewed").checked = state.draft.reviewed;
  for (const [key, ids] of [["source", ["sx", "sy"]], ["target", ["tx", "ty"]]]) {
    ids.forEach((id, index) => $(id).value = state.draft[key] ? (state.draft[key][index] * 100).toFixed(2) : "");
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
  $("mute").textContent = video.muted ? "Suara mati" : "Suara aktif";
  $("mute").setAttribute("aria-pressed", video.muted);
};
video.onplay = () => { $("play").textContent = "Jeda"; $("play").setAttribute("aria-label", "Jeda video"); };
video.onpause = () => { $("play").textContent = "Putar"; $("play").setAttribute("aria-label", "Putar video"); };
video.onloadedmetadata = () => { $("play").disabled = false; seek(2); };
video.onerror = () => {
  $("load-state").hidden = false;
  $("load-state").classList.add("error");
  $("load-state").textContent = "Video gagal dimuat. Pastikan server berjalan dan file sumber tersedia di Downloads.";
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
      localStorage.removeItem("touchline.export");
    } else if (job.state === "error") {
      throw new Error(job.error);
    } else {
      $("export-status").textContent = `Memproses video… ${job.progress}%`;
      exportPoll = setTimeout(() => checkExport(id), 1500);
    }
  } catch (error) {
    $("export-status").textContent = `Ekspor berhenti: ${error.message}`;
    $("export-submit").disabled = false;
    localStorage.removeItem("touchline.export");
  }
}
$("export-form").onsubmit = async event => {
  event.preventDefault();
  $("export-submit").disabled = true;
  $("download").hidden = true;
  $("export-status").textContent = "Menyiapkan video…";
  try {
    const job = await api("/api/export", {start: Number($("export-start").value), end: Number($("export-end").value)});
    localStorage.setItem("touchline.export", job.id);
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
    state.events = state.project.events;
    for (const row of state.project.observations) {
      if (!state.groups.has(row.frame)) state.groups.set(row.frame, []);
      state.groups.get(row.frame).push(row);
    }
    const ballFrames = new Set(state.project.observations.filter(row => row.kind === "ball").map(row => row.frame)).size;
    const sampled = Math.floor(state.project.duration * state.project.fps / 2);
    $("coverage").textContent = `Bola teramati di ${(100 * ballFrames / sampled).toFixed(1)}% frame sampel`;
    for (const id of ["seek", "start", "end", "export-start", "export-end"]) $(id).max = state.project.duration;
    $("export-end").value = state.project.duration;
    $("load-state").hidden = true;
    $("export-open").disabled = false;
    $("new-event").disabled = false;
    renderStats(state.project.stats);
    renderEvents();
    if (video.readyState >= 1) { $("play").disabled = false; seek(2); }
    const job = localStorage.getItem("touchline.export");
    if (job) { $("export-submit").disabled = true; checkExport(job); }
  } catch (error) {
    $("load-state").textContent = `Gagal memuat proyek: ${error.message}. Muat ulang untuk mencoba lagi.`;
    $("load-state").classList.add("error");
  }
}
init();
