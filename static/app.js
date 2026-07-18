const MIN_PLAYERS = 4;

const APP = document.getElementById("app");
const SCOREBOARD = document.getElementById("scoreboard");

const state = {
  players: [],
  prompt: null,
  phase: null,
  currentPlayerId: null,
  lastRoundResult: null,
};

async function api(method, path, body) {
  const res = await fetch(path, {
    method,
    headers: body !== undefined ? { "Content-Type": "application/json" } : undefined,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    throw new Error(data.detail || `Request failed (${res.status})`);
  }
  return data;
}

function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str ?? "";
  return div.innerHTML;
}

function blankify(text) {
  return escapeHtml(text).replace("___", '<span class="blank">______</span>');
}

function renderScoreboard() {
  if (!state.players.length) {
    SCOREBOARD.classList.add("hidden");
    SCOREBOARD.innerHTML = "";
    return;
  }
  const sorted = [...state.players].sort((a, b) => b.score - a.score);
  SCOREBOARD.classList.remove("hidden");
  SCOREBOARD.innerHTML = sorted
    .map((p) => `<span class="score-pill">${escapeHtml(p.name)}: ${p.score}</span>`)
    .join("");
}

function updateFromGameState(gs) {
  state.players = gs.players;
  state.prompt = gs.prompt;
  state.phase = gs.phase;
  state.currentPlayerId = gs.current_player_id;
  state.lastRoundResult = gs.last_round_result;
  renderScoreboard();
}

function routeFromPhase() {
  if (state.phase === "submitting") {
    renderPassDevice();
  } else if (state.phase === "judging") {
    renderAskJudge();
  } else if (state.phase === "reveal") {
    renderReveal(state.lastRoundResult);
  }
}

async function init() {
  try {
    const gs = await api("GET", "/api/game");
    if (gs.phase === "game_over") {
      state.players = gs.final_scores;
      renderScoreboard();
      renderGameOver(gs);
      return;
    }
    updateFromGameState(gs);
    routeFromPhase();
  } catch (err) {
    renderSetup();
  }
}

// ---- Setup screen ----
function renderSetup() {
  state.players = [];
  renderScoreboard();
  APP.innerHTML = `
    <section class="screen">
      <h2>Start a new game</h2>
      <p class="hint">Enter at least ${MIN_PLAYERS} player names. Claude will judge every round.</p>
      <div id="player-inputs"></div>
      <button id="add-player" type="button">+ Add player</button>
      <button id="start-game" type="button" class="primary">Start Game</button>
      <p id="setup-error" class="error hidden"></p>
    </section>
  `;
  const inputsEl = document.getElementById("player-inputs");

  function addInput(value) {
    const row = document.createElement("div");
    row.className = "player-input-row";
    const input = document.createElement("input");
    input.type = "text";
    input.className = "player-name";
    input.placeholder = "Player name";
    input.value = value || "";
    const removeBtn = document.createElement("button");
    removeBtn.type = "button";
    removeBtn.className = "remove-player";
    removeBtn.textContent = "✕";
    removeBtn.addEventListener("click", () => {
      if (inputsEl.children.length > 1) row.remove();
    });
    row.appendChild(input);
    row.appendChild(removeBtn);
    inputsEl.appendChild(row);
  }

  for (let i = 0; i < MIN_PLAYERS; i++) addInput();

  document.getElementById("add-player").addEventListener("click", () => addInput());

  document.getElementById("start-game").addEventListener("click", async () => {
    const names = [...inputsEl.querySelectorAll(".player-name")]
      .map((i) => i.value.trim())
      .filter(Boolean);
    const errorEl = document.getElementById("setup-error");
    if (names.length < MIN_PLAYERS) {
      errorEl.textContent = `Enter at least ${MIN_PLAYERS} player names.`;
      errorEl.classList.remove("hidden");
      return;
    }
    try {
      const gs = await api("POST", "/api/game", { player_names: names });
      updateFromGameState(gs);
      routeFromPhase();
    } catch (err) {
      errorEl.textContent = err.message;
      errorEl.classList.remove("hidden");
    }
  });
}

// ---- Pass-device interstitial ----
function renderPassDevice() {
  const player = state.players.find((p) => p.id === state.currentPlayerId);
  APP.innerHTML = `
    <section class="screen pass-screen">
      <h2>Pass the device to</h2>
      <p class="player-name-big">${escapeHtml(player ? player.name : "")}</p>
      <button id="ready-btn" class="primary">I'm ready</button>
    </section>
  `;
  document.getElementById("ready-btn").addEventListener("click", async () => {
    try {
      const hand = await api("GET", `/api/game/players/${state.currentPlayerId}/hand`);
      renderHand(hand);
    } catch (err) {
      alert(err.message);
    }
  });
}

// ---- Hand view ----
function renderHand(hand) {
  let selectedId = null;
  APP.innerHTML = `
    <section class="screen">
      <div class="prompt-card">
        <span class="prompt-emoji">${state.prompt.emoji}</span>
        <p>${blankify(state.prompt.text)}</p>
      </div>
      <h3>${escapeHtml(hand.name)}'s hand</h3>
      <div id="hand-cards" class="card-grid"></div>
      <button id="play-card" class="primary" disabled>Play this card</button>
      <p id="hand-error" class="error hidden"></p>
    </section>
  `;
  const grid = document.getElementById("hand-cards");
  const playBtn = document.getElementById("play-card");

  hand.hand.forEach((card) => {
    const el = document.createElement("button");
    el.type = "button";
    el.className = "response-card";
    el.innerHTML = `<span class="card-emoji">${card.emoji}</span><span>${escapeHtml(card.text)}</span>`;
    el.addEventListener("click", () => {
      grid.querySelectorAll(".response-card").forEach((c) => c.classList.remove("selected"));
      el.classList.add("selected");
      selectedId = card.id;
      playBtn.disabled = false;
    });
    grid.appendChild(el);
  });

  playBtn.addEventListener("click", async () => {
    if (!selectedId) return;
    playBtn.disabled = true;
    try {
      const gs = await api("POST", `/api/game/players/${hand.player_id}/submit`, {
        card_id: selectedId,
      });
      updateFromGameState(gs);
      routeFromPhase();
    } catch (err) {
      const errorEl = document.getElementById("hand-error");
      errorEl.textContent = err.message;
      errorEl.classList.remove("hidden");
      playBtn.disabled = false;
    }
  });
}

// ---- Ask Claude to judge ----
function renderAskJudge() {
  APP.innerHTML = `
    <section class="screen">
      <div class="prompt-card">
        <span class="prompt-emoji">${state.prompt.emoji}</span>
        <p>${blankify(state.prompt.text)}</p>
      </div>
      <p class="hint">Everyone has submitted a card.</p>
      <button id="judge-btn" class="primary">Ask Claude to judge</button>
      <p id="judge-loading" class="hint hidden">Claude is deliberating&hellip;</p>
      <p id="judge-error" class="error hidden"></p>
    </section>
  `;
  document.getElementById("judge-btn").addEventListener("click", async () => {
    document.getElementById("judge-btn").disabled = true;
    document.getElementById("judge-loading").classList.remove("hidden");
    try {
      const result = await api("POST", "/api/game/judge", {});
      state.lastRoundResult = result;
      state.players = result.scores;
      renderScoreboard();
      renderReveal(result);
    } catch (err) {
      document.getElementById("judge-error").textContent = err.message;
      document.getElementById("judge-error").classList.remove("hidden");
      document.getElementById("judge-btn").disabled = false;
      document.getElementById("judge-loading").classList.add("hidden");
    }
  });
}

// ---- Reveal ----
function renderReveal(result) {
  const submissionsHtml = result.submissions
    .map((s) => {
      const isWinner = s.player_id === result.winner.player_id;
      return `
        <div class="submission ${isWinner ? "winner" : ""}">
          <div class="response-card static">
            <span class="card-emoji">${s.card.emoji}</span>
            <span>${escapeHtml(s.card.text)}</span>
          </div>
          <p class="submission-name">${escapeHtml(s.name)}${isWinner ? " \u{1F3C6}" : ""}</p>
        </div>
      `;
    })
    .join("");

  APP.innerHTML = `
    <section class="screen">
      <div class="prompt-card">
        <span class="prompt-emoji">${result.prompt.emoji}</span>
        <p>${blankify(result.prompt.text)}</p>
      </div>
      ${result.judge_error ? '<p class="error">Claude had trouble judging this round, so a winner was picked at random.</p>' : ""}
      <div class="roast-box">
        <p class="roast-label">The Judge says:</p>
        <p class="roast-text">&ldquo;${escapeHtml(result.roast)}&rdquo;</p>
      </div>
      <div class="submissions-grid">${submissionsHtml}</div>
      <button id="next-round-btn" class="primary">Next Round</button>
    </section>
  `;
  document.getElementById("next-round-btn").addEventListener("click", async () => {
    try {
      const gs = await api("POST", "/api/game/next-round", {});
      if (gs.phase === "game_over") {
        state.players = gs.final_scores;
        renderScoreboard();
        renderGameOver(gs);
      } else {
        updateFromGameState(gs);
        routeFromPhase();
      }
    } catch (err) {
      alert(err.message);
    }
  });
}

// ---- Game over ----
function renderGameOver(gs) {
  const rows = gs.final_scores
    .map((p) => `<li>${escapeHtml(p.name)} &mdash; ${p.score}</li>`)
    .join("");
  APP.innerHTML = `
    <section class="screen">
      <h2>\u{1F3C6} ${escapeHtml(gs.winner.name)} wins!</h2>
      <ol class="final-scores">${rows}</ol>
      <button id="new-game-btn" class="primary">New Game</button>
    </section>
  `;
  document.getElementById("new-game-btn").addEventListener("click", async () => {
    await api("POST", "/api/game/reset", {});
    renderSetup();
  });
}

init();
