"use strict";

const $ = id => document.getElementById(id);
const state = { data: null, trials: [], index: 0, bestIndex: 0, timer: null, playing: false, camera: null, fit: null };
const roomColors = {
  bedroom: '#315d76', bathroom: '#5c4d78', attached_bathroom: '#6d5278',
  living_room: '#375d4f', kitchen: '#6a5536', dining_room: '#695a3d',
  hallway: '#e9b949', veranda: '#3e6565', garage: '#5a4a42'
};
const format = value => Number.isFinite(Number(value)) ? Number(value).toFixed(2) : '—';
const clamp = (value, min, max) => Math.max(min, Math.min(max, value));

function svgEl(name, attrs = {}, text) {
  const el = document.createElementNS('http://www.w3.org/2000/svg', name);
  for (const [key, value] of Object.entries(attrs)) el.setAttribute(key, value);
  if (text !== undefined) el.textContent = text;
  return el;
}

$('chooseFile').addEventListener('click', () => $('fileInput').click());
$('fileInput').addEventListener('change', event => {
  if (event.target.files[0]) readFile(event.target.files[0]);
  event.target.value = '';
});
for (const name of ['dragenter', 'dragover']) $('dropZone').addEventListener(name, event => {
  event.preventDefault(); $('dropZone').classList.add('drag');
});
for (const name of ['dragleave', 'drop']) $('dropZone').addEventListener(name, event => {
  event.preventDefault(); $('dropZone').classList.remove('drag');
});
$('dropZone').addEventListener('drop', event => {
  if (event.dataTransfer.files[0]) readFile(event.dataTransfer.files[0]);
});

async function readFile(file) {
  pause();
  try {
    loadData(JSON.parse(await file.text()), file.name);
    $('loadError').hidden = true;
  } catch (error) {
    $('loadError').textContent = `Could not load run: ${error.message}`;
    $('loadError').hidden = false;
  }
}

function loadData(data, name = 'Candidate run') {
  if (!data || !Array.isArray(data.candidate_trials)) throw new Error('Expected candidate_trials in the JSON.');
  pause();
  state.data = data;
  state.trials = data.candidate_trials;
  state.index = 0;
  state.camera = null;
  state.bestIndex = state.trials.reduce((best, trial, index, trials) =>
    Number(trial.score) > Number(trials[best].score) ? index : best, 0);
  $('fileName').textContent = name;
  $('headerStatus').textContent = String(data.status || 'loaded').replaceAll('_', ' ').toUpperCase();
  $('headerDot').className = 'run-dot ' + (data.status === 'failed' ? 'bad' : data.status === 'target_reached' ? 'ok' : 'warn');
  $('bestScore').textContent = state.trials.length ? format(state.trials[state.bestIndex].score) : '—';
  $('targetScore').textContent = format(data.target_score ?? 100);
  $('trialCount').textContent = ` / ${state.trials.length}`;
  $('totalTrials').textContent = `/ ${state.trials.length}`;
  $('trialSlider').max = Math.max(0, state.trials.length - 1);
  $('trialNumber').max = state.trials.length;
  document.querySelectorAll('[data-run-control]').forEach(el => { el.disabled = !state.trials.length; });
  renderTrialList();
  renderScoreChart();
  if (state.trials.length) selectTrial(0);
  else {
    $('planSvg').replaceChildren();
    $('legend').replaceChildren();
    $('currentScore').textContent = '—';
    $('dataNote').hidden = true;
    showMessage('No trials recorded', data.errors?.at(-1)?.message || 'This run contains no candidate trials.');
  }
}

function renderTrialList() {
  const fragment = document.createDocumentFragment();
  state.trials.forEach((trial, index) => {
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'trial-row' + (index === state.bestIndex ? ' best' : '') + (trial.status === 'rejected' ? ' rejected' : '');
    btn.dataset.index = index;
    btn.setAttribute('aria-current', 'false');
    const label = document.createElement('span'); label.textContent = `Trial ${trial.trial ?? index + 1}`;
    const score = document.createElement('span'); score.className = 'score'; score.textContent = format(trial.score);
    const track = document.createElement('span'); track.className = 'score-track'; track.setAttribute('aria-hidden', 'true');
    const fill = document.createElement('i'); fill.style.width = `${clamp(Number(trial.score) || 0, 0, 100)}%`; track.append(fill);
    const status = document.createElement('small'); status.textContent = trial.status === 'rejected' ? 'Rejected' : index === state.bestIndex ? 'Best' : 'Scored';
    btn.append(label, score, track, status);
    btn.setAttribute('aria-label', `${label.textContent}, score ${score.textContent}, ${status.textContent}`);
    fragment.append(btn);
  });
  $('trialList').replaceChildren(fragment);
}

$('trialList').addEventListener('click', event => {
  const row = event.target.closest('.trial-row');
  if (row) { pause(); selectTrial(Number(row.dataset.index)); }
});

function renderScoreChart() {
  const svg = $('scoreChart'); svg.replaceChildren();
  if (!state.trials.length) return;
  const x = index => 3 + index / Math.max(1, state.trials.length - 1) * 236;
  const y = score => 62 - clamp(Number(score) || 0, 0, 100) * .56;
  for (const score of [0, 50, 100]) svg.append(svgEl('line', { x1: 0, x2: 242, y1: y(score), y2: y(score), stroke: '#293640', 'stroke-width': .5 }));
  svg.append(svgEl('polyline', { points: state.trials.map((trial, index) => `${x(index)},${y(trial.score)}`).join(' '), fill: 'none', stroke: '#8ea0ad', 'stroke-width': 1 }));
  svg.append(svgEl('circle', { cx: x(state.bestIndex), cy: y(state.trials[state.bestIndex].score), r: 3, fill: '#e9b949' }));
  svg.append(svgEl('line', { id: 'chartCursor', x1: 3, x2: 3, y1: 0, y2: 66, stroke: '#54d6d6', 'stroke-width': 1 }));
}
$('scoreChart').addEventListener('click', event => {
  if (!state.trials.length) return;
  const rect = $('scoreChart').getBoundingClientRect();
  pause(); selectTrial(Math.round((event.clientX - rect.left) / rect.width * (state.trials.length - 1)));
});

function selectTrial(index) {
  if (!state.trials.length || !Number.isFinite(index)) return;
  const oldRow = $('trialList').children[state.index];
  oldRow?.setAttribute('aria-current', 'false');
  state.index = clamp(Math.round(index), 0, state.trials.length - 1);
  const row = $('trialList').children[state.index];
  row.setAttribute('aria-current', 'true');
  row.scrollIntoView({ block: 'nearest', behavior: 'instant' });
  $('trialNumber').value = state.index + 1;
  $('trialSlider').value = state.index;
  $('trialSlider').setAttribute('aria-valuetext', `Trial ${state.trials[state.index].trial ?? state.index + 1}, score ${format(state.trials[state.index].score)}`);
  $('currentScore').textContent = format(state.trials[state.index].score);
  $('firstBtn').disabled = $('prevBtn').disabled = state.index === 0;
  $('lastBtn').disabled = $('nextBtn').disabled = state.index === state.trials.length - 1;
  const x = 3 + state.index / Math.max(1, state.trials.length - 1) * 236;
  $('chartCursor')?.setAttribute('x1', x); $('chartCursor')?.setAttribute('x2', x);
  renderCanvas();
  if ($('detailsDialog').open) renderDetails();
}

function pause() {
  clearTimeout(state.timer); state.timer = null; state.playing = false;
  $('playBtn').setAttribute('aria-pressed', 'false');
  $('playBtn').setAttribute('aria-label', 'Play trials');
  $('playIcon').setAttribute('d', 'M7 4v16l13-8z');
}
function scheduleNext() {
  clearTimeout(state.timer);
  state.timer = setTimeout(() => {
    if (!state.playing) return;
    if (state.index < state.trials.length - 1) selectTrial(state.index + 1);
    if (state.index === state.trials.length - 1) pause(); else scheduleNext();
  }, Number($('playSpeed').value));
}
function togglePlayback() {
  if (!state.trials.length) return;
  if (state.playing) { pause(); return; }
  if (state.index === state.trials.length - 1) selectTrial(0);
  if (state.trials.length < 2) return;
  state.playing = true;
  $('playBtn').setAttribute('aria-pressed', 'true');
  $('playBtn').setAttribute('aria-label', 'Pause trials');
  $('playIcon').setAttribute('d', 'M6 4h4v16H6zm8 0h4v16h-4z');
  scheduleNext();
}
$('playBtn').addEventListener('click', togglePlayback);
$('playSpeed').addEventListener('change', () => { if (state.playing) scheduleNext(); });
for (const [id, position] of [['firstBtn', () => 0], ['prevBtn', () => state.index - 1], ['nextBtn', () => state.index + 1], ['lastBtn', () => state.trials.length - 1], ['bestBtn', () => state.bestIndex]]) {
  $(id).addEventListener('click', () => { pause(); selectTrial(position()); });
}
$('trialSlider').addEventListener('input', event => { pause(); selectTrial(Number(event.target.value)); });
$('trialNumber').addEventListener('change', event => { pause(); selectTrial(Number(event.target.value) - 1); });
$('visualMode').addEventListener('change', renderCanvas);
document.addEventListener('keydown', event => {
  if (!state.trials.length || $('detailsDialog').open || event.target.closest('input,select,button,summary')) return;
  if (event.key === ' ') { event.preventDefault(); togglePlayback(); }
  if (event.key === 'ArrowLeft' || event.key === 'ArrowRight') {
    event.preventDefault(); pause(); selectTrial(state.index + (event.key === 'ArrowRight' ? 1 : -1));
  }
});
document.addEventListener('visibilitychange', () => { if (document.hidden) pause(); });

function trialVisual(trial) {
  const pre = state.data.steps?.find(step => step.name === 'preprocessing')?.execution?.result;
  const grid = pre?.candidate_grid || state.data.visualization?.candidate?.grid || trial.candidate?.grid;
  const circulation = $('visualMode').value === 'circulation';
  const candidate = circulation ? trial.candidate : trial.search_candidate || trial.candidate;
  const details = trial.circulation_details;
  const scoringRoutes = trial.evaluators?.find(e => e.evaluator_key === 'relationship_quality')?.details;
  const paths = circulation ? details?.passes?.at(-1)?.paths || scoringRoutes?.paths || [] : [];
  let note = '';
  if (!circulation && !trial.search_candidate) note = 'Original search hints were not saved in this run. Showing the saved hints after circulation.';
  if (circulation && !details) note = scoringRoutes
    ? 'Circulation passes were not saved in this run. Routes shown are from candidate scoring.'
    : 'No circulation routes were saved for this trial.';
  return { candidate, grid, paths, details, floor: pre?.generation_spec?.floor, note };
}

function showMessage(title, text) {
  $('canvasMessage').hidden = false;
  $('messageTitle').textContent = title; $('messageText').textContent = text;
  $('frontRibbon').hidden = true;
}

function renderCanvas() {
  if (!state.trials.length) return;
  const trial = state.trials[state.index], visual = trialVisual(trial), svg = $('planSvg');
  svg.replaceChildren(); $('legend').replaceChildren();
  const points = (visual.candidate?.points || []).filter(p => Number.isFinite(Number(p.x)) && Number.isFinite(Number(p.y)));
  $('dataNote').textContent = visual.note;
  $('dataNote').hidden = !visual.note;
  if (!points.length || !visual.grid?.x_positions?.length || !visual.grid?.y_positions?.length) {
    showMessage(`Trial ${trial.trial ?? state.index + 1}: no saved hints`, trial.error?.message || 'This trial has no candidate snapshot for the selected view.');
    $('visualMeta').textContent = trial.status || 'No snapshot'; return;
  }
  const grid = visual.grid, width = Number(visual.floor?.width ?? grid.x_positions.at(-1)), height = Number(visual.floor?.length ?? grid.y_positions.at(-1));
  if (!(width > 0 && height > 0)) { showMessage('Invalid grid', 'The saved floor dimensions must be positive.'); return; }
  const span = Math.max(width, height), pad = span * .09;
  state.fit = { x: -pad, y: -pad, width: width + pad * 2, height: height + pad * 2 };
  if (!state.camera) state.camera = { ...state.fit };
  setCamera(state.camera);
  $('canvasMessage').hidden = true; $('frontRibbon').hidden = false;
  svg.setAttribute('aria-label', `Trial ${trial.trial ?? state.index + 1}, ${$('visualMode').selectedOptions[0].textContent}, score ${format(trial.score)}`);
  const unit = Number(state.data.project_units_per_meter) > 0 ? Number(state.data.project_units_per_meter) : 10;
  const defs = svgEl('defs'), pattern = svgEl('pattern', { id: 'microGrid', width: unit, height: unit, patternUnits: 'userSpaceOnUse' });
  pattern.append(svgEl('path', { d: `M ${unit} 0 H 0 V ${unit}`, fill: 'none', stroke: '#1f2b34', 'stroke-width': .5, 'vector-effect': 'non-scaling-stroke' }));
  defs.append(pattern); svg.append(defs);
  svg.append(svgEl('rect', { x: 0, y: 0, width, height, fill: 'url(#microGrid)', stroke: '#e9b949', 'stroke-width': 1, 'vector-effect': 'non-scaling-stroke' }));
  const labels = { fill: '#8ea0ad', 'font-size': span * .017, 'font-family': 'Consolas, monospace' };
  for (let x = 0; x <= width; x += unit) svg.append(svgEl('text', { ...labels, x, y: height + span * .03, 'text-anchor': 'middle' }, `${Math.round(x / unit)}m`));
  for (let y = 0; y <= height; y += unit) svg.append(svgEl('text', { ...labels, x: -span * .025, y: y + span * .006, 'text-anchor': 'end' }, `${Math.round(y / unit)}m`));
  const x0 = grid.x_positions[0], x1 = grid.x_positions.at(-1), y0 = grid.y_positions[0], y1 = grid.y_positions.at(-1);
  for (const x of grid.x_positions) svg.append(svgEl('line', { x1: x, x2: x, y1: y0, y2: y1, stroke: '#33434f', 'stroke-width': .65, 'vector-effect': 'non-scaling-stroke' }));
  for (const y of grid.y_positions) svg.append(svgEl('line', { x1: x0, x2: x1, y1: y, y2: y, stroke: '#33434f', 'stroke-width': .65, 'vector-effect': 'non-scaling-stroke' }));
  for (const x of grid.x_positions) for (const y of grid.y_positions) svg.append(svgEl('circle', { cx: x, cy: y, r: span * .0045, fill: '#566773' }));
  for (const path of visual.paths) {
    if (!path.nodes?.length) continue;
    const line = svgEl('polyline', { class: 'route', points: path.nodes.map(p => `${p.x},${p.y}`).join(' '), fill: 'none', stroke: path.traffic_class === 'public' ? '#54d6d6' : '#d7a6ff', 'stroke-width': 2.5, opacity: .8, 'stroke-linecap': 'round', 'stroke-linejoin': 'round', 'vector-effect': 'non-scaling-stroke' });
    line.append(svgEl('title', {}, `${path.rule_name}: ${path.source_room_id} → ${path.destination_room_id} · ${format(path.path_efficiency_score)}% efficiency`)); svg.append(line);
  }
  if ($('visualMode').value === 'circulation') for (const point of visual.details?.removed_hallway_points || []) {
    const r = span * .015;
    const removed = svgEl('path', { d: `M ${point.x - r} ${point.y - r} l ${r * 2} ${r * 2} m 0 ${-r * 2} l ${-r * 2} ${r * 2}`, fill: 'none', stroke: '#ff7b72', 'stroke-width': 1.5, 'vector-effect': 'non-scaling-stroke' });
    removed.append(svgEl('title', {}, `${point.room_id}: removed (${point.reason})`)); svg.append(removed);
  }
  const classes = new Map((trial.hallway_classifications || []).map(p => [`${p.room_id}[${p.hint_index}]`, p.traffic_class]));
  for (const point of points) {
    const group = svgEl('g', { class: 'room-hint' });
    const dot = svgEl('circle', { cx: point.x, cy: point.y, r: span * .020, fill: roomColors[point.room_type] || '#315d76', stroke: '#e6edf3', 'stroke-width': 1, 'vector-effect': 'non-scaling-stroke' });
    dot.append(svgEl('title', {}, `${point.room_id} · ${point.room_type} · (${point.x}, ${point.y})`)); group.append(dot);
    const textAttrs = { 'text-anchor': 'middle', fill: '#f3f7fa', 'font-size': span * .023, 'font-family': 'Consolas, monospace', 'font-weight': '600', 'paint-order': 'stroke', stroke: '#070b0f', 'stroke-width': span * .013, 'stroke-linejoin': 'round', 'pointer-events': 'none' };
    group.append(svgEl('text', { ...textAttrs, x: point.x, y: Number(point.y) - span * .04 }, point.room_id));
    const traffic = classes.get(`${point.room_id}[${point.hint_index}]`);
    if (traffic && $('visualMode').value === 'circulation') group.append(svgEl('text', { ...textAttrs, x: point.x, y: Number(point.y) + span * .049, 'font-size': span * .018, fill: '#8ea0ad' }, traffic));
    svg.append(group);
  }
  const addLegend = (color, text) => {
    const item = document.createElement('span'); item.className = 'legend-item';
    const swatch = document.createElement('i'); swatch.className = 'swatch'; swatch.style.background = color;
    item.append(swatch, document.createTextNode(text)); $('legend').append(item);
  };
  for (const type of new Set(points.map(p => p.room_type))) addLegend(roomColors[type] || '#315d76', String(type || 'room').replaceAll('_', ' '));
  if ($('visualMode').value === 'circulation') {
    addLegend('#54d6d6', 'public route'); addLegend('#d7a6ff', 'private route');
    if (visual.details?.removed_hallway_points?.length) addLegend('#ff7b72', 'removed hallway ×');
  }
  $('visualMeta').textContent = `${(width / unit).toFixed(1)} × ${(height / unit).toFixed(1)} m · ${points.length} hints` + ($('visualMode').value === 'circulation' ? ` · ${visual.paths.length} routes` : '');
}

function setCamera(box) {
  state.camera = box;
  $('planSvg').setAttribute('viewBox', `${box.x} ${box.y} ${box.width} ${box.height}`);
}
$('fitBtn').addEventListener('click', () => { if (state.fit) setCamera({ ...state.fit }); });
$('planSvg').addEventListener('wheel', event => {
  if (!state.camera || $('canvasMessage').hidden === false) return;
  event.preventDefault();
  const svg = $('planSvg'), box = state.camera;
  const point = new DOMPoint(event.clientX, event.clientY).matrixTransform(svg.getScreenCTM().inverse());
  const width = clamp(box.width * Math.exp(clamp(event.deltaY, -100, 100) * .002), state.fit.width / 12, state.fit.width * 3);
  const factor = width / box.width;
  setCamera({ x: point.x - (point.x - box.x) * factor, y: point.y - (point.y - box.y) * factor, width, height: box.height * factor });
}, { passive: false });
let pan = null;
$('planSvg').addEventListener('pointerdown', event => {
  if (!state.camera || !event.isPrimary || event.button !== 0) return;
  const inverse = $('planSvg').getScreenCTM().inverse();
  pan = { clientX: event.clientX, clientY: event.clientY, box: { ...state.camera }, inverse };
  $('planSvg').setPointerCapture(event.pointerId);
});
$('planSvg').addEventListener('pointermove', event => {
  if (!pan) return;
  const start = new DOMPoint(pan.clientX, pan.clientY).matrixTransform(pan.inverse);
  const end = new DOMPoint(event.clientX, event.clientY).matrixTransform(pan.inverse);
  setCamera({ ...pan.box, x: pan.box.x - (end.x - start.x), y: pan.box.y - (end.y - start.y) });
});
$('planSvg').addEventListener('lostpointercapture', () => { pan = null; });

function renderDetails() {
  const trial = state.trials[state.index];
  $('detailsTitle').textContent = `Trial ${trial.trial ?? state.index + 1} · score ${format(trial.score)}`;
  $('trialOutcome').textContent = trial.error?.message || `Critical checks: ${trial.passed_critical_checks ? 'passed' : 'not passed'}.`;
  $('evaluatorRows').replaceChildren();
  for (const result of trial.evaluators || []) {
    const row = document.createElement('tr');
    for (const value of [String(result.evaluator_key).replaceAll('_', ' '), result.status, format(result.raw_score), format(result.contribution)]) {
      const cell = document.createElement('td'); cell.textContent = value; row.append(cell);
    }
    $('evaluatorRows').append(row);
  }
  $('rawTrial').textContent = JSON.stringify(trial, null, 2);
}
$('detailsBtn').addEventListener('click', () => { pause(); renderDetails(); $('detailsDialog').showModal(); });
$('closeDetails').addEventListener('click', () => $('detailsDialog').close());
