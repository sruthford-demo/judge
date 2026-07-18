const SESSION_KEY = "judge_session";
const POLL_MS = 1500;

const APP = document.getElementById("app");
const SCOREBOARD = document.getElementById("scoreboard");
const ROOM_CODE_BADGE = document.getElementById("room-code-badge");

let session = loadSession();
let pollTimer = null;
let lastSnapshot = null;
let wakeLock = null;

function loadSession() {
  try {
    return JSON.parse(localStorage.getItem(SESSION_KEY));
  } catch {
    return null;
  }
}

function saveSession(s) {
  session = s;
  localStorage.setItem(SESSION_KEY, JSON.stringify(s));
}

function clearSession() {
  session = null;
  localStorage.removeItem(SESSION_KEY);
}

function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str ?? "";
  return div.innerHTML;
}

async function api(method, path, body, authed = true) {
  const headers = {};
  if (body !== undefined) headers["Content-Type"] = "application/json";
  if (authed && session) {
    headers["X-Player-Id"] = session.playerId;
    headers["X-Player-Token"] = session.playerToken;
  }
  const res = await fetch(path, {
    method,
    headers: Object.keys(headers).length ? headers : undefined,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const err = new Error(data.detail || `Request failed (${res.status})`);
    err.status = res.status;
    throw err;
  }
  return data;
}

function renderScoreboard(players) {
  if (!players || !players.length) {
    SCOREBOARD.classList.add("hidden");
    SCOREBOARD.innerHTML = "";
    return;
  }
  const sorted = [...players].sort((a, b) => b.score - a.score);
  SCOREBOARD.classList.remove("hidden");
  SCOREBOARD.innerHTML = sorted
    .map(
      (p) =>
        `<span class="score-pill${p.is_judge ? " judge" : ""}">${escapeHtml(p.name)}: ${p.score}${p.is_judge ? " ⚖️" : ""}</span>`
    )
    .join("");
}

async function requestWakeLock() {
  try {
    if ("wakeLock" in navigator) {
      wakeLock = await navigator.wakeLock.request("screen");
    }
  } catch {
    wakeLock = null;
  }
}

function releaseWakeLock() {
  if (wakeLock) {
    wakeLock.release().catch(() => {});
    wakeLock = null;
  }
}

function stopPolling() {
  if (pollTimer) {
    clearInterval(pollTimer);
    pollTimer = null;
  }
}

function startPolling() {
  stopPolling();
  pollTimer = setInterval(pollState, POLL_MS);
}

async function pollState() {
  if (!session) return;
  try {
    const data = await api("GET", `/api/rooms/${session.roomCode}/state`);
    handleStateResponse(data);
  } catch (err) {
    if (err.status === 404 || err.status === 403) {
      stopPolling();
      clearSession();
      renderHome("That room is no longer available. Please rejoin.");
    }
  }
}

function handleStateResponse(data) {
  const snapshot = JSON.stringify(data);
  if (snapshot === lastSnapshot) return;
  lastSnapshot = snapshot;

  if (data.phase === "game_over") {
    renderScoreboard(data.final_scores);
    ROOM_CODE_BADGE.textContent = data.room_code;
    ROOM_CODE_BADGE.classList.remove("hidden");
    renderGameOver(data);
    return;
  }

  renderScoreboard(data.players);
  ROOM_CODE_BADGE.textContent = data.room_code;
  ROOM_CODE_BADGE.classList.remove("hidden");

  if (data.phase === "lobby") {
    renderLobby(data);
  } else if (data.phase === "round") {
    routeRound(data);
  } else if (data.phase === "reveal") {
    renderRoundReveal(data);
  }
}

function routeRound(data) {
  if (data.am_i_judge) {
    renderJudgeReview(data);
  } else {
    renderMyCard(data);
  }
}

async function init() {
  if (!session) {
    renderHome();
    return;
  }
  try {
    const data = await api("GET", `/api/rooms/${session.roomCode}/state`);
    handleStateResponse(data);
    startPolling();
  } catch {
    clearSession();
    renderHome();
  }
}

// ---- Home: create or join a room ----
function renderHome(message) {
  stopPolling();
  releaseWakeLock();
  lastSnapshot = null;
  ROOM_CODE_BADGE.classList.add("hidden");
  renderScoreboard(null);
  APP.innerHTML = `
    <section class="screen">
      <p class="hint">A Heads Up-style party game &mdash; everyone plays from their own phone.</p>
      ${message ? `<p class="error">${escapeHtml(message)}</p>` : ""}
      <div class="home-grid">
        <div class="home-card">
          <h3>Host a new game</h3>
          <input id="host-name" type="text" placeholder="Your name" />
          <button id="create-room-btn" class="primary">Create Room</button>
        </div>
        <div class="home-card">
          <h3>Join a game</h3>
          <input id="join-code" type="text" placeholder="Room code" maxlength="4" />
          <input id="join-name" type="text" placeholder="Your name" />
          <button id="join-room-btn" class="primary">Join Room</button>
        </div>
      </div>
      <p id="home-error" class="error hidden"></p>
    </section>
  `;

  const errorEl = document.getElementById("home-error");
  const showError = (msg) => {
    errorEl.textContent = msg;
    errorEl.classList.remove("hidden");
  };

  document.getElementById("create-room-btn").addEventListener("click", async () => {
    const name = document.getElementById("host-name").value.trim();
    if (!name) return showError("Enter your name.");
    try {
      const joined = await api("POST", "/api/rooms", { host_name: name }, false);
      saveSession({
        roomCode: joined.room_code,
        playerId: joined.player_id,
        playerToken: joined.player_token,
      });
      const state = await api("GET", `/api/rooms/${joined.room_code}/state`);
      handleStateResponse(state);
      startPolling();
    } catch (err) {
      showError(err.message);
    }
  });

  document.getElementById("join-room-btn").addEventListener("click", async () => {
    const code = document.getElementById("join-code").value.trim().toUpperCase();
    const name = document.getElementById("join-name").value.trim();
    if (!code || !name) return showError("Enter the room code and your name.");
    try {
      const joined = await api("POST", `/api/rooms/${code}/join`, { name }, false);
      saveSession({
        roomCode: joined.room_code,
        playerId: joined.player_id,
        playerToken: joined.player_token,
      });
      const state = await api("GET", `/api/rooms/${joined.room_code}/state`);
      handleStateResponse(state);
      startPolling();
    } catch (err) {
      showError(err.message);
    }
  });
}

// ---- Lobby ----
function renderLobby(data) {
  releaseWakeLock();
  const isHost = session.playerId === data.host_player_id;
  const rows = data.players
    .map((p) => `<li>${escapeHtml(p.name)}${p.id === data.host_player_id ? " (host)" : ""}</li>`)
    .join("");
  const canStart = data.players.length >= 4;

  APP.innerHTML = `
    <section class="screen lobby-screen">
      <h2>Waiting for players</h2>
      <p class="hint">Share this code with everyone:</p>
      <p class="room-code-big">${escapeHtml(data.room_code)}</p>
      <ul class="player-list">${rows}</ul>
      ${
        isHost
          ? `<button id="start-btn" class="primary" ${canStart ? "" : "disabled"}>Start Game</button>
             ${canStart ? "" : `<p class="hint">Need at least 4 players (${data.players.length}/4).</p>`}`
          : `<p class="hint">Waiting for the host to start the game&hellip;</p>`
      }
      <p id="lobby-error" class="error hidden"></p>
    </section>
  `;

  if (isHost) {
    document.getElementById("start-btn").addEventListener("click", async () => {
      try {
        lastSnapshot = null;
        const state = await api("POST", `/api/rooms/${data.room_code}/start`);
        handleStateResponse(state);
      } catch (err) {
        const errorEl = document.getElementById("lobby-error");
        errorEl.textContent = err.message;
        errorEl.classList.remove("hidden");
      }
    });
  }
}

// ---- My card (hold to forehead) ----
function renderMyCard(data) {
  requestWakeLock();
  const card = data.my_card;
  APP.innerHTML = `
    <section class="screen forehead-screen">
      <p class="hint">Hold your phone to your forehead, screen facing out, and keep it there until the judge picks!</p>
      <div class="forehead-card">
        <img src="${escapeHtml(card.image_url)}" alt="${escapeHtml(card.text)}" />
        <p class="forehead-caption">${card.emoji} ${escapeHtml(card.text)}</p>
      </div>
    </section>
  `;
}

// ---- Judge review: pick the worst card ----
function renderJudgeReview(data) {
  releaseWakeLock();
  const cardsHtml = (data.reveal_cards || [])
    .map(
      (s) => `
        <button type="button" class="reveal-card" data-player-id="${s.player_id}">
          <img src="${escapeHtml(s.card.image_url)}" alt="${escapeHtml(s.card.text)}" />
          <span class="reveal-name">${escapeHtml(s.name)}</span>
        </button>
      `
    )
    .join("");

  APP.innerHTML = `
    <section class="screen">
      <h2>Pick the worst one!</h2>
      <p class="hint">Look at everyone's forehead and tap the worst pic.</p>
      <div class="reveal-grid">${cardsHtml}</div>
      <p id="judge-error" class="error hidden"></p>
    </section>
  `;

  document.querySelectorAll(".reveal-card").forEach((btn) => {
    btn.addEventListener("click", async () => {
      document.querySelectorAll(".reveal-card").forEach((b) => (b.disabled = true));
      try {
        lastSnapshot = null;
        const state = await api("POST", `/api/rooms/${data.room_code}/judge/pick`, {
          loser_player_id: btn.dataset.playerId,
        });
        handleStateResponse(state);
      } catch (err) {
        const errorEl = document.getElementById("judge-error");
        errorEl.textContent = err.message;
        errorEl.classList.remove("hidden");
        document.querySelectorAll(".reveal-card").forEach((b) => (b.disabled = false));
      }
    });
  });
}

// ---- Round reveal ----
function renderRoundReveal(data) {
  releaseWakeLock();
  const result = data.last_round_result;
  const submissionsHtml = result.submissions
    .map((s) => {
      const isLoser = s.player_id === result.loser.player_id;
      return `
        <div class="submission ${isLoser ? "loser" : ""}">
          <img src="${escapeHtml(s.card.image_url)}" alt="${escapeHtml(s.card.text)}" />
          <p class="submission-name">${escapeHtml(s.name)}${isLoser ? " \u{1F447}" : ""}</p>
        </div>
      `;
    })
    .join("");

  APP.innerHTML = `
    <section class="screen">
      <h2>${escapeHtml(result.judge_name)} judged&hellip;</h2>
      <p class="hint">Worst pic of the round: <strong>${escapeHtml(result.loser.name)}</strong> (+1 point)</p>
      <div class="submissions-grid">${submissionsHtml}</div>
      <button id="next-round-btn" class="primary">Next Round</button>
    </section>
  `;
  document.getElementById("next-round-btn").addEventListener("click", async () => {
    try {
      lastSnapshot = null;
      const state = await api("POST", `/api/rooms/${data.room_code}/next-round`);
      handleStateResponse(state);
    } catch (err) {
      alert(err.message);
    }
  });
}

// ---- Game over ----
function renderGameOver(data) {
  releaseWakeLock();
  const isHost = session.playerId === data.host_player_id;
  const rows = data.final_scores
    .map((p) => `<li>${escapeHtml(p.name)} &mdash; ${p.score}</li>`)
    .join("");
  APP.innerHTML = `
    <section class="screen">
      <h2>\u{1F3C6} ${escapeHtml(data.winner.name)} wins!</h2>
      <ol class="final-scores">${rows}</ol>
      ${
        isHost
          ? `<button id="new-game-btn" class="primary">Play Again</button>`
          : `<p class="hint">Waiting for the host to start a new game&hellip;</p>`
      }
    </section>
  `;
  if (isHost) {
    document.getElementById("new-game-btn").addEventListener("click", async () => {
      try {
        lastSnapshot = null;
        const state = await api("POST", `/api/rooms/${data.room_code}/new-game`);
        handleStateResponse(state);
      } catch (err) {
        alert(err.message);
      }
    });
  }
}

init();
