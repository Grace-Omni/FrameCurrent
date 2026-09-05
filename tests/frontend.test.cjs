// Execute the real controller with a small DOM substitute, not a browser.
// No provider calls, API credentials, generated media or third-party dependencies.
const { test } = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const root = path.resolve(__dirname, "..");
const source = fs.readFileSync(path.join(root, "web/app.js"), "utf8");
const html = fs.readFileSync(path.join(root, "web/index.html"), "utf8");

class Element {
  constructor() {
    this.value = ""; this.textContent = ""; this.dataset = {}; this.style = {};
    this.hidden = false; this.disabled = false; this.children = []; this.listeners = {};
    this.selectedOptions = [{ textContent: "稳定跟随" }]; this.currentTime = 0;
    const classes = new Set();
    this.classList = {
      add: (...names) => names.forEach((name) => classes.add(name)),
      remove: (...names) => names.forEach((name) => classes.delete(name)),
      toggle: (name, force) => { const on = force ?? !classes.has(name); on ? classes.add(name) : classes.delete(name); return on; },
      contains: (name) => classes.has(name),
    };
  }
  setAttribute(name, value) { this[name] = String(value); }
  removeAttribute(name) { delete this[name]; }
  addEventListener(name, callback) { (this.listeners[name] ||= new Set()).add(callback); }
  removeEventListener(name, callback) { this.listeners[name]?.delete(callback); }
  fire(name) { this.listeners[name]?.forEach((callback) => callback({ preventDefault() {} })); }
  closest() { return this.parent ||= new Element(); }
  querySelector(selector) { this.queries ||= new Map(); if (!this.queries.has(selector)) this.queries.set(selector, new Element()); return this.queries.get(selector); }
  append(...children) { this.children.push(...children); }
  replaceChildren(...children) { this.children = [...children]; }
  pause() {} load() {} focus() {} scrollIntoView() {}
  play() { return Promise.resolve(); }
  setCustomValidity(value) { this.validationMessage = value; }
  showModal() { this.open = true; }
  close(value = "") { this.returnValue = value; this.open = false; this.fire("close"); }
}

async function harness(active = null) {
  const nodes = new Map();
  const get = (selector) => {
    if (!nodes.has(selector)) nodes.set(selector, new Element());
    return nodes.get(selector);
  };
  for (const match of html.matchAll(/<[^>]+\bid="([^"]+)"[^>]*>/g)) {
    const node = get(`#${match[1]}`);
    node.value = match[0].match(/\bvalue="([^"]*)"/)?.[1] || "";
    node.hidden = /\bhidden\b/.test(match[0]);
  }
  get("#clipDuration").value = "10";
  get("#resolution").value = "480P";
  const cards = [...html.matchAll(/<button[^>]+data-preset="([^"]+)"/g)].map((match) => {
    const node = new Element(); node.dataset.preset = match[1]; return node;
  });
  const radios = (name, values) => values.map((value) => { const node = new Element(); node.value = value; node.name = name; return node; });
  const groups = {
    "[data-preset]": cards,
    'input[name="aspectRatio"]': radios("aspectRatio", ["9:16", "16:9"]),
    'input[name="durationMode"]': radios("durationMode", ["fixed", "unlimited"]),
    "[data-duration]": [30, 60, 300, 600].map((value) => { const node = new Element(); node.dataset.duration = String(value); return node; }),
  };
  let fetcher = async (url) => ({ ok: true, json: async () => url === "/api/health"
    ? { ok: true, app_id: "framecurrent", active_session: active }
    : { session_id: active?.session_id, status: "generating", clips: [], config: { preset: active?.preset, duration_seconds: 30, total_clips: 3, aspect_ratio: "16:9" } } });
  const requests = [];
  const stored = new Map();
  let timerId = 0;
  const timers = new Map();
  const context = vm.createContext({
    console, AbortController, URL, crypto: require("node:crypto").webcrypto,
    document: { querySelector: get, querySelectorAll: (selector) => groups[selector] || [], body: new Element(), createElement: () => new Element() },
    window: {
      localStorage: { getItem: (key) => stored.get(key) || null, setItem: (key, value) => stored.set(key, value) },
      setTimeout: (callback) => { timers.set(++timerId, callback); return timerId; },
      clearTimeout: (id) => timers.delete(id), setInterval: () => 1,
      confirm: () => false, prompt: () => null,
    },
    requestAnimationFrame: () => 1, cancelAnimationFrame() {},
    fetch: (url, options) => { requests.push({ url, options }); return fetcher(url, options); },
  });
  vm.runInContext(source + `\nglobalThis.api = { state, initialization, checkHealth, updateStartEligibility, selectChannel, updateDuration, renderSavedClips, friendlyError, verifyApiKey, requestPaidStartConfirmation, startSession, request, reconcilePendingStart, pendingStartEntry };`, context);
  await context.api.initialization;
  return { ...context.api, get, cards, requests, timers, fetchWith: (fn) => { fetcher = fn; } };
}

test("first run defaults to a 30-second output and tells the user why start is disabled", async () => {
  const h = await harness();
  assert.equal(h.state.durationSeconds, 30);
  assert.equal(h.get("#startButton").disabled, true);
  assert.match(h.get("#startHelp").textContent, /API Key/);
  assert.equal(h.get("#healthText").textContent, "本机服务已连接");
  assert.equal(h.requests.some((entry) => entry.url.endsWith("/start")), false);
});

test("every preset hides program settings; only custom reveals them", async () => {
  const h = await harness();
  h.selectChannel("custom_channel", false);
  assert.equal(h.get("#customProgramSettings").hidden, false);
  for (const card of h.cards.filter((card) => card.dataset.preset !== "custom_channel")) {
    h.selectChannel(card.dataset.preset, false);
    assert.equal(h.get("#customProgramSettings").hidden, true);
  }
});

test("refresh discovers a running non-default channel without submitting generation", async () => {
  const h = await harness({ session_id: "offline-active", preset: "travel_aerial" });
  assert.equal(h.state.activeChannelId, "travel_aerial");
  assert.equal(h.state.sessionId, "offline-active");
  assert.equal(h.requests.filter((entry) => entry.options.method === "POST").length, 0);
});

test("changing channels keeps the active generation visible and blocks a conflicting start", async () => {
  const h = await harness({ session_id: "offline-active", preset: "travel_aerial" });
  h.selectChannel("cinematic_scifi");
  h.state.keyVerified = true;
  h.updateStartEligibility();
  assert.equal(h.get("#activeNotice").hidden, false);
  assert.match(h.get("#startHelp").textContent, /另一个频道/);
  await h.startSession({ preventDefault() {} });
  assert.equal(h.requests.some((entry) => entry.url.endsWith("/start")), false);
});

test("service disconnect displays recovery guidance and prevents paid starts", async () => {
  const h = await harness();
  h.fetchWith(async () => { throw new Error("offline"); });
  await h.checkHealth();
  assert.equal(h.state.serverStatus, "offline");
  assert.equal(h.get("#connectionNotice").hidden, false);
  assert.match(h.get("#startHelp").textContent, /重新启动本机/);
  h.fetchWith(async () => ({ ok: true, json: async () => ({ ok: true, app_id: "framecurrent" }) }));
  await h.checkHealth();
  assert.equal(h.get("#connectionNotice").hidden, true);
});

test("an unrelated localhost service is not accepted as FrameCurrent", async () => {
  const h = await harness();
  h.fetchWith(async () => ({ ok: true, json: async () => ({ ok: true }) }));
  await h.checkHealth();
  assert.equal(h.state.serverStatus, "offline");
});

test("health recovers a new running task even while the same channel displays an older result", async () => {
  const h = await harness();
  h.state.sessionId = "old-complete";
  h.state.channelSessions.hand_drawn_fantasy = "old-complete";
  h.fetchWith(async (url) => ({ ok: true, json: async () => url === "/api/health"
    ? { ok: true, app_id: "framecurrent", active_session: { session_id: "new-running", preset: "hand_drawn_fantasy" } }
    : { session_id: "new-running", status: "generating", clips: [], config: { preset: "hand_drawn_fantasy", duration_seconds: 30, total_clips: 3 } } }));
  await h.checkHealth();
  assert.equal(h.state.sessionId, "new-running");
  assert.equal(h.state.busy, true);
  assert.equal(h.requests.some((entry) => entry.url.endsWith("/start")), false);
});

test("changing the next output length does not erase completed-program telemetry", async () => {
  const h = await harness();
  h.state.sessionId = "offline-complete";
  h.get("#generatedTime").textContent = "00:30 / 00:30";
  h.get("#durationMinutes").value = "5";
  h.get("#durationSeconds").value = "0";
  h.updateDuration();
  assert.equal(h.get("#generatedTime").textContent, "00:30 / 00:30");
});

test("a recovered start is retired only after its exact request ID is confirmed", async () => {
  const h = await harness();
  const channel = h.state.activeChannelId;
  const old = h.pendingStartEntry(channel, "old-fingerprint");
  h.fetchWith(async () => ({ ok: true, json: async () => ({ session_id: "different-task" }) }));
  await h.reconcilePendingStart(channel, "recovered-task");
  assert.equal(h.state.pendingRequestIds[channel].id, old.id);
  h.fetchWith(async () => ({ ok: true, json: async () => ({ session_id: "recovered-task" }) }));
  await h.reconcilePendingStart(channel, "recovered-task");
  assert.equal(h.state.pendingRequestIds[channel], undefined);
  assert.notEqual(h.pendingStartEntry(channel, "new-fingerprint").id, old.id);
  assert.equal(h.requests.some((entry) => entry.url.endsWith("/start")), false);
});

test("saved clips link only to same-session media and clear on channel change", async () => {
  const h = await harness();
  h.renderSavedClips({ session_id: "offline", clips: [{ url: "/media/offline/clip-001.mp4", duration: 10 }, { url: "https://example.com/clip.mp4" }, { url: "/media/offline/../other/clip.mp4" }] });
  assert.equal(h.get("#savedClips").hidden, false);
  assert.equal(h.get("#savedClipLinks").children.length, 1);
  assert.match(h.get("#savedClipLinks").children[0].download, /FrameCurrent/);
  h.renderSavedClips({ clips: [] });
  assert.equal(h.get("#savedClips").hidden, true);
  assert.equal(h.get("#savedClipLinks").children.length, 0);
});

test("editing a Key while verification is in flight cannot authorize the replacement", async () => {
  const h = await harness();
  let finish;
  h.fetchWith(() => new Promise((resolve) => { finish = resolve; }));
  h.get("#apiKey").value = "offline:example-a";
  const pending = h.verifyApiKey();
  h.get("#apiKey").value = "offline:example-b";
  finish({ ok: true, json: async () => ({ ok: true }) });
  await pending;
  assert.equal(h.state.keyVerified, false);
  assert.equal(h.state.verifiedKey, "");
  assert.match(h.get("#keyStatus").textContent, /已改变/);
});

test("cancelling the paid dialog returns no approval and makes no request", async () => {
  const h = await harness();
  const before = h.requests.length;
  const pending = h.requestPaidStartConfirmation();
  assert.match(h.get("#paidDialogDetail").textContent, /成片00:30/);
  h.get("#cancelPaidDialog").fire("click");
  assert.equal(await pending, null);
  assert.equal(h.requests.length, before);
});

test("unlimited mode requires a valid explicit cap and cancelling is free", async () => {
  const h = await harness();
  h.state.durationMode = "unlimited";
  const pending = h.requestPaidStartConfirmation();
  assert.equal(h.get("#paidDialogBudgetField").hidden, false);
  assert.equal(h.get("#confirmPaidStart").disabled, true);
  h.get("#confirmMaxBudget").value = "151";
  h.get("#confirmMaxBudget").fire("input");
  assert.equal(h.get("#confirmPaidStart").disabled, true);
  h.get("#confirmMaxBudget").value = "1";
  h.get("#confirmMaxBudget").fire("input");
  assert.equal(h.get("#confirmPaidStart").disabled, false);
  h.get("#paidDialog").close();
  assert.equal(await pending, null);
});

test("explicit fixed-length confirmation returns the reviewed estimate, without itself submitting", async () => {
  const h = await harness();
  const before = h.requests.length;
  const pending = h.requestPaidStartConfirmation();
  h.get("#confirmPaidStart").fire("click");
  assert.equal(await pending, 1.5);
  assert.equal(h.requests.length, before);
});

test("a request timeout aborts once without automatically retrying a paid POST", async () => {
  const h = await harness();
  h.fetchWith((_url, options) => new Promise((_resolve, reject) => options.signal.addEventListener("abort", () => reject(new Error("aborted")))));
  const before = h.requests.length;
  const pending = h.request("/api/session/start", { method: "POST", body: "{}" });
  [...h.timers.values()].at(-1)();
  await assert.rejects(pending, /aborted/);
  assert.equal(h.requests.length, before + 1);
});

test("environment errors have actionable guidance instead of content-safety advice", async () => {
  const h = await harness();
  assert.match(h.friendlyError("本地环境未就绪"), /doctor.command/);
  assert.match(h.friendlyError("已有一个生成任务正在运行"), /另一个频道/);
  assert.doesNotMatch(h.friendlyError("视频下载未通过文件检查"), /内容安全/);
});
