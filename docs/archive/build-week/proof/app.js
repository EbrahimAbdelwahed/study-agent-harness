const replay = document.querySelector("[data-replay]");
const counter = document.querySelector("[data-scene-count]");
const progress = document.querySelector(".timeline-track i");
const params = new URLSearchParams(location.search);
const fixedScene = Number(params.get("scene"));
const startScene = Number(params.get("startScene"));
const durations = [7000, 15000, 16000, 19000, 15000, 8000];
const totalDuration = durations.reduce((sum, duration) => sum + duration, 0);

const requestedScene = Number.isInteger(fixedScene) && fixedScene >= 1 && fixedScene <= 6
  ? fixedScene
  : Number.isInteger(startScene) && startScene >= 1 && startScene <= 6
    ? startScene
    : 1;
let scene = requestedScene;
let sceneStartedAt = performance.now();
let timelineStartedAt = sceneStartedAt - durations.slice(0, scene - 1).reduce((sum, duration) => sum + duration, 0);
let paused = Boolean(fixedScene);
let frame;

if (paused) document.body.classList.add("fixed-scene");

function bind(selector, value) {
  document.querySelectorAll(`[data-bind="${selector}"]`).forEach((node) => {
    node.textContent = String(value);
  });
}

async function loadTrace() {
  const response = await fetch("demo-data.json", { cache: "no-store" });
  if (!response.ok) throw new Error(`Trace data unavailable: ${response.status}`);
  const trace = await response.json();
  bind("learner_entry", `“${trace.learner_entry}”`);
  bind("source_fixture", trace.source_state.fixture);
  bind("source_checksum", `sha256 · ${trace.source_state.checksum_sha256.slice(0, 18)}…`);
  bind("evidence_0", trace.source_state.evidence[0]);
  bind("evidence_1", trace.source_state.evidence[1]);
  bind("clarification", trace.timeline[1].detail);
  bind("selected_focus", trace.context_state.selected_focus);
  bind("initial_sequence", trace.context_state.initial_sequence);
  bind("refreshed_sequence", trace.context_state.refreshed_sequence);
  bind("parity", String(trace.parity));
  trace.gateway_trace.forEach((entry, index) => bind(`cli_${index}`, entry));
}

function activate(nextScene, now = performance.now()) {
  scene = nextScene;
  sceneStartedAt = now;
  document.body.dataset.scene = String(scene);
  counter.textContent = String(scene).padStart(2, "0");
}

function tick(now) {
  if (!paused) {
    const elapsedInScene = now - sceneStartedAt;
    if (elapsedInScene >= durations[scene - 1]) {
      if (scene === 6) {
        paused = true;
        progress.style.width = "100%";
      } else {
        activate(scene + 1, now);
      }
    }
    const elapsed = Math.min(totalDuration, now - timelineStartedAt);
    progress.style.width = `${(elapsed / totalDuration) * 100}%`;
  }
  frame = requestAnimationFrame(tick);
}

function restart() {
  const now = performance.now();
  paused = false;
  timelineStartedAt = now;
  activate(1, now);
}

replay.addEventListener("pointerdown", () => replay.classList.add("pressed"));
replay.addEventListener("pointerup", () => replay.classList.remove("pressed"));
replay.addEventListener("click", restart);

loadTrace().catch((error) => {
  console.error(error);
  document.querySelector(".runtime-label").textContent = "trace unavailable";
});

activate(scene);
frame = requestAnimationFrame(tick);
window.addEventListener("pagehide", () => cancelAnimationFrame(frame));
