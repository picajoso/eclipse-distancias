// Ruta al Eclipse 2026 — frontend Leaflet.
// API servida en el mismo origen (FastAPI monta /app). Las llamadas son relativas.

const API = ""; // mismo origen
let ORIGIN = { name: "Madrid", lat: 40.4168, lon: -3.7038 };

// DESTS se carga dinámicamente desde el backend: las poblaciones de la franja
// MÁS CERCANAS al origen (por carretera). Ya no es una lista curada fija: cambia
// con el origen (radios crecientes). Verde = totalidad.
let DESTS = [];

const map = L.map("map", { zoomControl: true }).setView([41.5, -3.5], 6);

const osm = L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
  maxZoom: 19, attribution: "© OpenStreetMap",
}).addTo(map);

const sat = L.tileLayer(
  "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
  { maxZoom: 19, attribution: "© Esri" }
);

L.control.layers({ "Mapa": osm, "Satélite": sat }, null, { position: "topright" }).addTo(map);

// --- Capas del eclipse (IGN) ----------------------------------------------
let obscLayer = null, totalLayer = null;

function obscColor(pct) {
  if (pct >= 100) return "#dc2626";   // totalidad
  if (pct >= 97.5) return "#fb923c";  // parcial profundo (Madrid)
  if (pct >= 95) return "#f59e0b";
  return "#fde68a";
}
function durColor(s) {
  const stops = [[10, "#fef08a"], [30, "#fcd34d"], [50, "#fbbf24"], [70, "#f59e0b"], [90, "#ea580c"], [110, "#b91c1c"]];
  let c = stops[0][1];
  for (const [v, col] of stops) if (s >= v) c = col;
  return c;
}
async function loadOverlays() {
  try {
    const r = await fetch(`${API}/eclipse/overlays`);
    if (!r.ok) return;
    const d = await r.json();
    if (d.obscuration) {
      obscLayer = L.geoJSON(d.obscuration, {
        style: (f) => ({ fillColor: obscColor(f.properties.pct), color: "#000", weight: 0.3, opacity: 0.35, fillOpacity: 0.4, interactive: false }),
        onEachFeature: (f, l) => l.bindTooltip(`Oscur. ${f.properties.pct}%`),
      });
      if (document.getElementById("layer-obsc").checked) obscLayer.addTo(map);
    }
    if (d.totality) {
      totalLayer = L.geoJSON(d.totality, {
        style: (f) => ({ fillColor: durColor(f.properties.dur_s), color: "#7f1d1d", weight: 0.5, opacity: 0.5, fillOpacity: 0.35, interactive: false }),
        onEachFeature: (f, l) => l.bindTooltip(`Totalidad ≥ ${f.properties.dur_s}s`),
      });
      if (document.getElementById("layer-total").checked) totalLayer.addTo(map);
    }
  } catch (e) { /* sin capas, la app sigue funcionando */ }
}

let routeLayer = null;
let routeBubble = null;
let destMarker = null;
let currentDest = null;
let poisOn = false;
const poiLayer = L.layerGroup().addTo(map);
const townMarkers = {};

// --- Origen ----------------------------------------------------------------
function dotIcon(kind) {
  const colors = { total: "#36d399", partial: "#f5a623", origin: "#4d8dff", unk: "#6b7280" };
  const c = colors[kind] || colors.unk;
  return L.divIcon({
    className: "",
    html: `<span style="display:block;width:13px;height:13px;border-radius:50%;background:${c};border:2px solid #0f1115;box-shadow:0 0 0 1px ${c}"></span>`,
    iconSize: [13, 13], iconAnchor: [6.5, 6.5],
  });
}
const originMarker = L.marker([ORIGIN.lat, ORIGIN.lon], {
  icon: dotIcon("origin"), title: ORIGIN.name,
}).addTo(map).bindTooltip(ORIGIN.name + " (origen)");

// --- Destinos: las poblaciones de totalidad más cercanas al origen ----------
function clearTownMarkers() {
  for (const k in townMarkers) { map.removeLayer(townMarkers[k]); delete townMarkers[k]; }
}

async function loadDestinations() {
  try {
    const r = await fetch(`${API}/destinations?from_lat=${ORIGIN.lat}&from_lon=${ORIGIN.lon}`);
    if (!r.ok) return;
    DESTS = await r.json();
    clearTownMarkers();
    for (const d of DESTS) d.circ = { is_total: true, totality_duration_s: d.dur, contacts: {}, sun_at_maximum: null };
    // Marcadores solo para las más cercanas (evita saturar); el resto es accesible vía la lista.
    for (const d of DESTS.slice(0, 18)) {
      const m = L.marker([d.lat, d.lon], { icon: dotIcon("total"), title: d.name })
        .addTo(map).bindTooltip(`${d.name} · ${d.dur}s · ${d.driving_km} km`);
      m.on("click", () => selectDest(d));
      townMarkers[`${d.lat},${d.lon}`] = m;
    }
  } catch (e) { /* sin destinos, la app sigue */ }
  const title = document.getElementById("dest-title");
  if (title) title.textContent = `Totalidad más cercana a ${ORIGIN.name}`;
  renderDestList();
}

async function setOrigin(name, lat, lon) {
  ORIGIN = { name, lat, lon };
  showAllDest = false;
  const input = document.getElementById("origin-input");
  if (input) input.value = name;
  originMarker.setLatLng([lat, lon]);
  originMarker.bindTooltip(
    currentDest ? name : name + " (origen)",
    currentDest ? { permanent: true, direction: "right", className: "map-label", offset: [10, 0] } : {}
  );
  updateOriginEclipse();
  await loadDestinations();
  if (currentDest) computeRoute(currentDest);
  else map.setView([lat, lon], 6);
}

async function updateOriginEclipse() {
  // Avisa si el origen ya está en la franja de totalidad (eclipse visible al 100%).
  const el = document.getElementById("origin-eclipse");
  if (!el) return;
  el.className = "origin-notice";
  el.innerHTML = "";
  try {
    const c = await fetchEclipse(ORIGIN.lat, ORIGIN.lon);
    if (c.is_total) {
      const tb = c.contacts.total_begin ? c.contacts.total_begin.slice(11, 16) : "—";
      const te = c.contacts.total_end ? c.contacts.total_end.slice(11, 16) : "—";
      el.className = "origin-notice show total";
      el.innerHTML = `☀️ <strong>${ORIGIN.name}</strong> está dentro de la franja de <b>totalidad</b>: podrás ver el eclipse completo desde allí. Totalidad <b>${tb}–${te}</b> CEST (${c.totality_duration_s}s).`;
    } else {
      const pct = Math.round((c.magnitude || 0) * 1000) / 10;
      el.className = "origin-notice show partial";
      el.innerHTML = `Desde <strong>${ORIGIN.name}</strong> el eclipse será <strong>parcial</strong> (~${pct}%). Para ver la totalidad, elige un destino de la franja verde.`;
    }
  } catch (e) { /* sin aviso si falla la consulta */ }
}

async function fetchEclipse(lat, lon) {
  const r = await fetch(`${API}/eclipse/circumstances?lat=${lat}&lon=${lon}`);
  if (!r.ok) throw new Error(`eclipse ${r.status}`);
  return r.json();
}

// --- Popup de circunstancias ----------------------------------------------
function fmtTime(iso) { return iso ? iso.slice(11, 16) : "—"; } // el backend ya da CEST; +02:00
function fmtDrive(min) { return min >= 60 ? `${Math.floor(min / 60)}h ${String(min % 60).padStart(2, "0")}` : `${min} min`; }

function popupHtml(d, c) {
  const total = c.is_total;
  const tag = total
    ? `<span class="big total">TOTALIDAD ✓</span>`
    : `<span class="big partial">PARCIAL ${pct(c)}</span>`;
  const dur = total ? `<div class="row"><span>Duración totalidad</span><b>${c.totality_duration_s}s</b></div>` : "";
  const warn = (c.sun_at_maximum && c.sun_at_maximum.alt < 10)
    ? `<div class="warn">⚠ Sol muy bajo (${c.sun_at_maximum.alt}°): busca horizonte W despejado.</div>` : "";
  return `
    <div class="popup">
      <h3>${d.name}</h3>
      ${tag}
      <div class="row"><span>Máximo</span><b>${fmtTime(c.contacts.maximum)} CEST</b></div>
      ${total ? `<div class="row"><span>Totalidad</span><b>${fmtTime(c.contacts.total_begin)}–${fmtTime(c.contacts.total_end)}</b></div>` : ""}
      ${dur}
      <div class="row"><span>Magnitud</span><b>${c.magnitude}</b></div>
      ${warn}
      <button data-act="route" data-lat="${d.lat}" data-lon="${d.lon}">Calcular ruta desde ${ORIGIN.name}</button>
    </div>`;
}

function pct(c) {
  return `${Math.round((c.magnitude || 0) * 1000) / 10}%`;
}

// Click en el mapa: circunstancias en ese punto + opción de enrutar
map.on("click", (e) => {
  const { lat, lng } = e.latlng;
  L.popup().setLatLng(e.latlng).setContent(
    `<div class="popup"><span class="muted">Consultando eclipse…</span></div>`
  ).openOn(map);
  fetchEclipse(lat, lng).then((c) => {
    const d = { name: `Punto (${lat.toFixed(3)}, ${lng.toFixed(3)})`, lat, lon };
    L.popup().setLatLng(e.latlng).setContent(popupHtml(d, c)).openOn(map);
  }).catch(() => {
    L.popup().setLatLng(e.latlng).setContent(
      `<div class="popup"><span class="muted">No se pudo consultar el eclipse.</span></div>`
    ).openOn(map);
  });
});

// Cablear botones dentro de popups
map.on("popupopen", (e) => {
  const btn = e.popup.getElement()?.querySelector?.("button[data-act='route']");
  if (!btn) return;
  btn.addEventListener("click", () => {
    const lat = parseFloat(btn.dataset.lat), lon = parseFloat(btn.dataset.lon);
    selectDest({ name: btn.closest(".popup")?.querySelector("h3")?.textContent || "Destino", lat, lon });
    map.closePopup();
  });
});

// --- Selección de destino + ruta ------------------------------------------
function selectDest(d) {
  currentDest = d;
  destMarker && map.removeLayer(destMarker);
  destMarker = L.circleMarker([d.lat, d.lon], {
    radius: 8, color: "#2563eb", weight: 2, fillColor: "#2563eb", fillOpacity: 0.4,
  }).addTo(map);
  originMarker.bindTooltip(ORIGIN.name, { permanent: true, direction: "right", className: "map-label", offset: [10, 0] });
  destMarker.bindTooltip(d.name, { permanent: true, direction: "right", className: "map-label", offset: [10, 0] });
  computeRoute(d);
  if (poisOn) loadPois(d);
  highlightDest(d);
}

async function computeRoute(d) {
  document.getElementById("route-empty").hidden = true;
  const info = document.getElementById("route-info");
  info.hidden = false;
  info.innerHTML = `<div class="muted">Calculando ruta a ${d.name}…</div>`;
  try {
    const r = await fetch(`${API}/route?to_lat=${d.lat}&to_lon=${d.lon}&from_lat=${ORIGIN.lat}&from_lon=${ORIGIN.lon}`);
    if (!r.ok) throw new Error(`route ${r.status}`);
    const data = await r.json();
    drawRoute(data, d);
    renderRoute(data, d);
  } catch (e) {
    info.innerHTML = `<div class="muted">No se pudo calcular la ruta: ${e.message}</div>`;
  }
}

function routeBubbleHtml(data) {
  const hh = Math.floor(data.duration_s / 3600);
  const mm = Math.round((data.duration_s % 3600) / 60);
  const dep = data.plan.suggested_departure ? data.plan.suggested_departure.slice(11, 16) : "—";
  return `<div style="line-height:1.45">
    <div><b>${Math.round(data.distance_m / 1000)} km</b> · <b>${hh} h ${mm} min</b> en coche</div>
    <div style="font-size:11px;color:#555">Salida recomendada <b style="color:#2563eb">${dep} CEST</b></div>
  </div>`;
}

function drawRoute(data, d) {
  routeLayer && map.removeLayer(routeLayer);
  routeBubble && map.removeLayer(routeBubble);
  routeLayer = L.layerGroup([
    L.geoJSON(data.geometry, { style: { color: "#ffffff", weight: 7, opacity: 0.7 } }),
    L.geoJSON(data.geometry, { style: { color: "#2563eb", weight: 4, opacity: 0.95 } }),
  ]).addTo(map);
  const coords = data.geometry.coordinates || [];
  if (coords.length) {
    const m = coords[Math.floor(coords.length / 2)];
    routeBubble = L.tooltip({
      permanent: true, direction: "top", offset: [0, -10], className: "route-bubble", interactive: false,
    }).setLatLng([m[1], m[0]]).setContent(routeBubbleHtml(data)).addTo(map);
  }
  map.fitBounds(L.latLngBounds([ORIGIN.lat, ORIGIN.lon], [d.lat, d.lon]).pad(0.2));
}

function renderRoute(data, d) {
  const p = data.plan;
  const hh = Math.floor(data.duration_s / 3600);
  const mm = Math.round((data.duration_s % 3600) / 60);
  const depart = p.suggested_departure ? fmtTime(p.suggested_departure) : "—";
  const evtLabel = p.key_event === "total_begin" ? "inicio totalidad" : "máximo";
  const warn = p.low_sun_warning ? `<div class="warn">⚠ Sol bajo al máximo (${p.sun_alt_at_maximum}°).</div>` : "";
  document.getElementById("route-info").innerHTML = `
    <div class="stat"><span>Destino</span><b>${d.name}</b></div>
    <div class="stat"><span>Distancia</span><b>${Math.round(data.distance_m / 1000)} km</b></div>
    <div class="stat"><span>Tiempo coche</span><b>${hh} h ${mm} min</b></div>
    <div class="stat"><span>${p.is_total ? "✓ Totalidad" : "Parcial"}</span><b>${p.is_total ? "Sí" : "No"}</b></div>
    ${warn}
    <div class="depart">
      <div class="lbl">Salida recomendada (llegar al ${evtLabel} ${fmtTime(p.key_event_at)} con ${p.buffer_min}′ de margen)</div>
      <div class="val">${depart} CEST</div>
    </div>`;
}

// --- Servicios (POIs vía Overpass) ----------------------------------------
const POI_STYLE = {
  viewpoint: { color: "#36d399", r: 6 },
  parking: { color: "#4d8dff", r: 5 },
  lodging: { color: "#b07cff", r: 5 },
};
async function loadPois(d) {
  poiLayer.clearLayers();
  try {
    const r = await fetch(`${API}/pois?lat=${d.lat}&lon=${d.lon}&radius=8000`);
    if (!r.ok) throw new Error(`pois ${r.status}`);
    const fc = await r.json();
    for (const f of fc.features) {
      const st = POI_STYLE[f.properties.kind] || { color: "#888", r: 5 };
      L.circleMarker([f.geometry.coordinates[1], f.geometry.coordinates[0]], {
        radius: st.r, color: st.color, weight: 1.5, fillColor: st.color, fillOpacity: 0.5,
      }).bindTooltip(`${f.properties.name} · ${f.properties.kind}`).addTo(poiLayer);
    }
  } catch (e) { /* Overpass a veces cae: no rompemos la app */ }
}

// --- Lista lateral de destinos (ordenada por cercanía) ---------------------
let selectedName = null;
const REC_COUNT = 12;
let showAllDest = false;
function renderDestList() {
  const ul = document.getElementById("destinations");
  ul.innerHTML = "";
  const sorted = [...DESTS].sort((a, b) => (b.score ?? -1) - (a.score ?? -1));
  const shown = showAllDest ? sorted : sorted.slice(0, REC_COUNT);
  for (const d of shown) {
    const li = document.createElement("li");
    const meta = `${d.dur}s · ${fmtDrive(d.driving_min)}`;
    const star = !showAllDest && sorted.indexOf(d) < 3 ? "⭐ " : "";
    li.innerHTML = `<span class="dot total"></span><span>${star}${d.name}</span><span class="meta">${meta}</span>`;
    li.onclick = () => selectDest(d);
    if (d.name === selectedName) li.classList.add("active");
    ul.appendChild(li);
  }
  if (sorted.length > REC_COUNT) {
    const t = document.createElement("li");
    t.className = "toggle-all";
    t.textContent = showAllDest ? "▲ Ver menos" : `▾ Ver los ${sorted.length} más cercanos`;
    t.onclick = () => { showAllDest = !showAllDest; renderDestList(); };
    ul.appendChild(t);
  }
}
function highlightDest(d) {
  selectedName = d.name;
  renderDestList();
  map.panTo([d.lat, d.lon]);
}

// --- Arranque --------------------------------------------------------------
document.getElementById("pois-toggle").addEventListener("change", async (e) => {
  poisOn = e.target.checked;
  if (poisOn && currentDest) await loadPois(currentDest);
  else poiLayer.clearLayers();
});
for (const [id, lyr] of [["layer-obsc", () => obscLayer], ["layer-total", () => totalLayer]]) {
  document.getElementById(id).addEventListener("change", (e) => {
    const L = lyr();
    if (!L) return;
    e.target.checked ? L.addTo(map) : map.removeLayer(L);
  });
}
// Selector de origen (ciudades principales + búsqueda OSM para el resto)
const originInput = document.getElementById("origin-input");
let lastCommittedValue = "";  // #4: evita doble petición (Enter + blur->change)
function commitOrigin() {
  const q = (originInput.value || "").trim();
  if (!q || q === lastCommittedValue) return;  // ignora duplicados
  lastCommittedValue = q;
  const opt = document.querySelector(`#es-cities option[value="${CSS.escape(q)}"]`);
  if (opt && opt.dataset.lat) { setOrigin(opt.value, +opt.dataset.lat, +opt.dataset.lon); return; }
  fetch(`${API}/geocode?q=${encodeURIComponent(q)}`)
    .then((r) => (r.ok ? r.json() : []))
    .then((hits) => {
      if (hits.length) { originInput.value = hits[0].name; setOrigin(hits[0].name, hits[0].lat, hits[0].lon); }
      else alert("No encuentro esa localidad en España.");
    })
    .catch(() => alert("Error al buscar la localidad."));
}
originInput.addEventListener("change", commitOrigin);
originInput.addEventListener("keydown", (e) => { if (e.key === "Enter") { e.preventDefault(); commitOrigin(); originInput.blur(); } });

loadOverlays();
loadDestinations();    // poblaciones de totalidad más cercanas a Madrid
updateOriginEclipse(); // aviso si el origen ya está en la franja
