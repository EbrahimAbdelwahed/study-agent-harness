const replay = document.querySelector("[data-replay]");
const counter = document.querySelector("[data-scene-count]");
const progress = document.querySelector(".timeline-track i");
const params = new URLSearchParams(location.search);
const fixedScene = Number(params.get("scene"));
const startScene = Number(params.get("startScene"));
const durations = [6000, 8000, 9000, 9000, 4000, 3000];
const totalDuration = durations.reduce((sum, duration) => sum + duration, 0);
const validScene = (value) => Number.isInteger(value) && value >= 1 && value <= durations.length;
const requestedScene = validScene(fixedScene) ? fixedScene : validScene(startScene) ? startScene : 1;
let scene = requestedScene;
let sceneStartedAt = performance.now();
let timelineStartedAt = sceneStartedAt - durations.slice(0, scene - 1).reduce((sum, duration) => sum + duration, 0);
let paused = validScene(fixedScene);
let frame;

if (paused) document.body.classList.add("fixed-scene");

function bind(selector, value) {
  document.querySelectorAll(`[data-bind="${selector}"]`).forEach((node) => {
    node.textContent = String(value);
  });
}

async function loadTrace() {
  const response = await fetch("flywheel-data.json", { cache: "no-store" });
  if (!response.ok) throw new Error(`Flywheel trace unavailable: ${response.status}`);
  const trace = await response.json();
  bind("feature_title", trace.feature.title);
  bind("run_id", trace.run_id);
  bind("worker_id", trace.worker.id);
  bind("worker_scope", trace.worker.scope);
  bind("worker_invariant", trace.worker.invariant);
  bind("worker_verify", trace.worker.verification);
  bind("runtime_command", trace.runtime.command);
  bind("runtime_fixture", trace.runtime.fixture);
  bind("runtime_snapshot", trace.runtime.snapshot);
  bind("runtime_replay", trace.runtime.replay);
  bind("runtime_proof", trace.runtime.proof);
  bind("test_status", trace.gates.tests.status);
  bind("semantic_status", trace.gates.semantic_review.status);
  bind("review_artifact", trace.gates.semantic_review.artifact);
  bind("architecture_artifact", trace.gates.architecture_review.artifact);
  bind("manifest_artifact", trace.handoff.manifest);
  bind("validation_artifact", trace.handoff.validation);
  bind("handoff_artifact", trace.handoff.durable_memory);
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
      if (scene === durations.length) {
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
  progress.style.width = "0%";
}

replay.addEventListener("pointerdown", () => replay.classList.add("pressed"));
replay.addEventListener("pointerup", () => replay.classList.remove("pressed"));
replay.addEventListener("pointercancel", () => replay.classList.remove("pressed"));
replay.addEventListener("click", restart);

loadTrace().catch((error) => {
  console.error(error);
  document.querySelector(".runtime-label").textContent = "trace unavailable";
});

activate(scene);
frame = requestAnimationFrame(tick);
window.addEventListener("pagehide", () => cancelAnimationFrame(frame));
