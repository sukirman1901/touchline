"use strict";
const $ = id => document.getElementById(id);
let active = null, pollTimer, requestSerial = 0;
const labels = {importing:"Memeriksa video", downloading:"Mengunduh dari YouTube",
  preparing:"Menyiapkan video", preview:"Siap dipilih", analyzing:"Deteksi dan tracking",
  ready:"Siap direview", error:"Perlu dicoba lagi"};
const busy = new Set(["importing", "downloading", "preparing", "analyzing"]);
const duration = n => `${Math.floor(n / 60).toString().padStart(2,"0")}:${Math.floor(n % 60).toString().padStart(2,"0")}`;
async function api(path, body) {
  const response = await fetch(path, body === undefined ? {} : {method:"POST",
    headers:{"Content-Type":"application/json"}, body:JSON.stringify(body)});
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || "Permintaan gagal.");
  return data;
}
function error(message) {
  $("intake-error").textContent = message || "";
  $("intake-error").hidden = !message;
}
function step(id) {
  for (const key of ["source","preview","analysis"]) {
    const node = $(`step-${key}`);
    if (key === id) node.setAttribute("aria-current","step");
    else node.removeAttribute("aria-current");
  }
}
function setSource(kind) {
  $("upload-pane").hidden = kind !== "upload";
  $("youtube-pane").hidden = kind !== "youtube";
  $("upload-tab").setAttribute("aria-pressed", kind === "upload");
  $("youtube-tab").setAttribute("aria-pressed", kind === "youtube");
  error("");
}
$("upload-tab").onclick = () => setSource("upload");
$("youtube-tab").onclick = () => setSource("youtube");
function reset() {
  requestSerial++;
  clearTimeout(pollTimer);
  active = null;
  history.replaceState(null,"","/");
  $("source-preview").pause();
  $("source-preview").removeAttribute("src");
  for (const id of ["job-panel","preview-panel","ready-panel","retry-job","new-source"]) $(id).hidden = true;
  $("source-form").hidden = false;
  $("video-file").value = "";
  error(""); step("source");
}
$("new-source").onclick = reset;
function showJob(item) {
  const previous = active;
  active = item;
  history.replaceState(null,"",`/?intake=${item.id}`);
  $("source-form").hidden = true;
  $("new-source").hidden = false;
  $("job-panel").hidden = !busy.has(item.state);
  $("preview-panel").hidden = item.state !== "preview";
  $("ready-panel").hidden = item.state !== "ready";
  $("retry-job").hidden = item.state !== "error";
  error(item.state === "error" ? item.error || "Pemrosesan gagal." : "");
  $("job-name").textContent = item.name;
  $("job-status").textContent = item.stage || labels[item.state];
  $("job-percent").textContent = item.state === "analyzing" ? `${item.progress || 0}%` : "";
  if (item.state === "analyzing") $("job-progress").value = item.progress || 0;
  else $("job-progress").removeAttribute("value");
  step(item.state === "preview" ? "preview" : ["ready","analyzing"].includes(item.state) ? "analysis" : "source");
  if (item.state === "preview") {
    $("preview-name").textContent = item.name;
    $("preview-meta").textContent = `${duration(item.meta.duration)} · ${item.meta.width} × ${item.meta.height} · ${item.meta.fps.toFixed(1)} fps`;
    if (previous?.id !== item.id || previous?.state !== "preview") {
      $("source-preview").src = `/preview/${item.id}`;
      $("clip-start").value = 0;
      $("clip-end").value = Math.min(60, item.meta.duration).toFixed(1);
      $("clip-start").max = $("clip-end").max = item.meta.duration;
    }
    clipSummary();
  }
  if (item.state === "ready") $("open-workspace").href = `/workspace?project=${item.id}`;
}
async function watch(identifier) {
  clearTimeout(pollTimer);
  const serial = ++requestSerial;
  try {
    const item = await api(`/api/projects/${identifier}`);
    if (serial !== requestSerial) return;
    showJob(item);
    if (busy.has(item.state)) pollTimer = setTimeout(() => watch(identifier), 1500);
    else loadProjects();
  } catch (exc) {
    if (serial !== requestSerial) return;
    error(`Status belum bisa dimuat: ${exc.message}`);
    $("retry-job").hidden = false;
    $("retry-job").dataset.reconnect = identifier;
  }
}
function uploading(name) {
  error(""); $("source-form").hidden = true; $("job-panel").hidden = false;
  $("job-name").textContent = name; $("job-status").textContent = "Mengunggah video";
  $("job-progress").value = 0; $("job-percent").textContent = "0%";
}
function upload(file) {
  if (!file) return;
  if (!file.size || file.size > 2 * 1024 ** 3) return error("Pilih video berukuran maksimal 2 GB.");
  uploading(file.name);
  const xhr = new XMLHttpRequest();
  xhr.open("POST","/api/projects/upload");
  xhr.setRequestHeader("Content-Type","application/octet-stream");
  xhr.setRequestHeader("X-Filename",encodeURIComponent(file.name));
  xhr.upload.onprogress = e => {
    if (e.lengthComputable) {
      const percent = Math.round(e.loaded / e.total * 100);
      $("job-progress").value = percent; $("job-percent").textContent = `${percent}%`;
      if (percent === 100) $("job-status").textContent = "Upload diterima, memeriksa video…";
    }
  };
  xhr.onload = () => {
    try {
      const item = JSON.parse(xhr.responseText);
      if (xhr.status >= 400) throw new Error(item.error || "Upload gagal.");
      watch(item.id); loadProjects();
    } catch (exc) { reset(); error(exc.message); }
  };
  xhr.onerror = () => { reset(); error("Upload terputus. Pastikan server berjalan, lalu pilih file lagi."); };
  xhr.send(file);
}
$("video-file").onchange = e => upload(e.target.files[0]);
for (const type of ["dragenter","dragover"]) $("dropzone").addEventListener(type,e => {
  e.preventDefault(); $("dropzone").classList.add("dragging");
});
$("dropzone").ondragleave = () => $("dropzone").classList.remove("dragging");
$("dropzone").ondrop = e => {
  e.preventDefault(); $("dropzone").classList.remove("dragging"); upload(e.dataTransfer.files[0]);
};
$("youtube-pane").onsubmit = async e => {
  e.preventDefault(); error(""); $("youtube-submit").disabled = true;
  try {
    const item = await api("/api/projects/youtube",{url:$("youtube-url").value});
    watch(item.id); loadProjects();
  } catch (exc) { error(exc.message); }
  finally { $("youtube-submit").disabled = false; }
};
function clipSummary() {
  const start = Number($("clip-start").value), end = Number($("clip-end").value);
  const valid = Number.isFinite(start) && Number.isFinite(end) && start >= 0 && end > start && end <= active.meta.duration;
  $("clip-summary").textContent = valid ? `${duration(end - start)} video akan dianalisis.` : "Pilih waktu akhir setelah waktu mulai, di dalam durasi video.";
  $("analyze-submit").disabled = !valid;
}
$("clip-start").oninput = $("clip-end").oninput = clipSummary;
$("use-playhead").onclick = () => {
  $("clip-start").value = (Math.floor($("source-preview").currentTime * 10) / 10).toFixed(1);
  clipSummary();
};
$("clip-form").onsubmit = async e => {
  e.preventDefault(); error(""); $("analyze-submit").disabled = true;
  $("source-preview").pause();
  try {
    await api(`/api/projects/${active.id}/analyze`,{start:Number($("clip-start").value),end:Number($("clip-end").value)});
    watch(active.id); loadProjects();
  } catch (exc) { error(exc.message); $("analyze-submit").disabled = false; }
};
$("retry-job").onclick = async () => {
  error(""); $("retry-job").disabled = true;
  try {
    const reconnect = $("retry-job").dataset.reconnect;
    if (reconnect) { delete $("retry-job").dataset.reconnect; await watch(reconnect); }
    else { await api(`/api/projects/${active.id}/retry`,{}); watch(active.id); }
  } catch (exc) { error(exc.message); }
  finally { $("retry-job").disabled = false; }
};
async function loadProjects() {
  try {
    const {projects} = await api("/api/projects");
    $("projects-empty").hidden = !!projects.length;
    $("projects-empty").textContent = "Belum ada proyek. Tambahkan rekaman pertama di atas.";
    $("project-list").replaceChildren();
    for (const project of projects) {
      const row = document.createElement("li"); row.className = "project-row";
      const symbol = document.createElement("span"); symbol.className = "project-symbol";
      symbol.innerHTML = '<svg class="icon" aria-hidden="true"><use href="/icons.svg#film"/></svg>';
      const copy = document.createElement("div"); copy.className = "project-copy";
      const title = document.createElement("h3"); title.textContent = project.name;
      const meta = document.createElement("p");
      meta.textContent = `${project.source === "youtube" ? "YouTube" : "Video lokal"}${project.meta ? ` · ${duration(project.meta.duration)}` : ""}`;
      copy.append(title,meta);
      const status = document.createElement("span"); status.className = "project-state"; status.textContent = labels[project.state];
      const action = document.createElement(project.state === "ready" ? "a" : "button");
      if (project.state === "ready") { action.href = `/workspace?project=${project.id}`; action.className = "button-link"; }
      else action.onclick = () => { watch(project.id); $("intake-title").scrollIntoView({block:"start"}); };
      action.textContent = project.state === "ready" ? "Buka proyek" : project.state === "preview" ? "Pilih klip" : "Lihat proses";
      action.setAttribute("aria-label",`${action.textContent}: ${project.name}`);
      row.append(symbol,copy,status,action); $("project-list").append(row);
    }
  } catch (exc) { $("projects-empty").hidden = false; $("projects-empty").textContent = `Gagal memuat proyek: ${exc.message}`; }
}
$("refresh-projects").onclick = loadProjects;
loadProjects();
const resume = new URLSearchParams(location.search).get("intake");
if (/^[a-f0-9]{32}$/.test(resume || "")) watch(resume);
