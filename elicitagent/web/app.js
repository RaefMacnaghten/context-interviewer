"use strict";

const $ = (sel) => document.querySelector(sel);
let config = null;
let view = null;
let editing = null; // id of the item being edited
let whyOpen = false; // the "why this question" panel
const openSources = new Set(); // item ids whose source passage is expanded

function el(tag, attrs = {}, ...children) {
  const node = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (v === undefined || v === null || v === false) continue;
    if (k === "class") node.className = v;
    else if (k.startsWith("on")) node.addEventListener(k.slice(2), v);
    else node.setAttribute(k, v === true ? "" : v);
  }
  for (const c of children.flat()) {
    if (c === null || c === undefined || c === false) continue;
    node.append(c instanceof Node ? c : document.createTextNode(String(c)));
  }
  return node;
}

async function api(path, body) {
  const res = await fetch(path, body === undefined ? {} : {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data.error || res.statusText);
  return data;
}

const STATE_GLYPH = { confirmed: "✓", assumed: "~", open: "?", conflict: "!", "not available here": "⊘",
  listed: "·", "looking again": "·", estimating: "·", rejected: "×" };
// The words the person sees for three internal values ("must hold", "nice if possible", "not available here") come
// from the server's one list (elicitagent/labels.py), so a rename is one edit there.
function shown(word) {
  return (config && config.labels && config.labels[word]) || word;
}
function shownLower(word) {
  const w = shown(word);
  return w === word ? w : w.toLowerCase();
}

function stateChip(state, text) {
  const w = shown(state);
  const label = text || (w.charAt(0).toUpperCase() + w.slice(1));
  return el("span", { class: `chip st-${stateClass(state)}` }, el("span", { class: "glyph", "aria-hidden": "true" }, STATE_GLYPH[state] || "·"), label);
}

// The step bar under the top bar: Folder, Reading, Interview, Review, Brief.
function renderSteps(on) {
  const names = ["Folder", "Reading", "Interview", "Review", "Brief"];
  const at = names.indexOf(on);
  $("#steps").replaceChildren(...names.map((n, i) => el("span", { class: i < at ? "done" : i === at ? "on" : "", "aria-current": i === at ? "step" : null },
    el("b", { "aria-hidden": "true" }, i < at ? "✓" : String(i + 1)), n)));
}

function stateClass(state) {
  if (state === "listed" || state === "looking again" || state === "estimating") return "pending";
  return state === "not available here" ? "unavailable" : state;
}

// ---------------------------------------------------------------- start

async function init() {
  config = await api("/api/config");
  const taskSelect = $("#task-select");
  for (const t of config.tasks) taskSelect.append(el("option", { value: t.folder }, `${t.name} (${t.folder})`));
  taskSelect.addEventListener("change", () => { $("#folder-input").value = ""; fillIntent(taskSelect.value); loadTree(); });
  $("#folder-input").addEventListener("input", (ev) => {
    fillIntent(ev.target.value.trim() || taskSelect.value);
    clearTimeout(treeTimer);
    treeTimer = setTimeout(loadTree, 300);
  });
  fillIntent(taskSelect.value);
  loadTree();
  const ruleSelect = $("#rule-select");
  for (const r of config.rules) {
    const thr = r.threshold === null || r.threshold === undefined ? "" : `, ${r.threshold_name} = ${r.threshold}`;
    ruleSelect.append(el("option", { value: r.name }, `${r.label}${thr}`));
  }
  $("#model-select").value = config.default_model;
  $("#limit-input").value = config.limit_start;
  $("#start-form").addEventListener("submit", start);
  renderSteps("Folder");
  const m = location.hash.match(/^#s=([0-9a-f]+)$/);
  if (m) {
    try {
      view = await api(`/api/session/${m[1]}`);
      $("#start").hidden = true;
      $("#interview").hidden = false;
      render();
      if (view.status === "reading") poll();
    } catch (e) {
      location.hash = "";
    }
  }
}

// Change 2: once a folder is chosen, and before reading starts, show its files and sub-folders as a tree, marking
// which will be read and which are skipped, and why. Reading starts only when the person presses the button.
let treeTimer = null;
let treeSeq = 0;
async function loadTree() {
  const folder = $("#folder-input").value.trim() || $("#task-select").value;
  const pane = $("#tree-pane");
  const seq = ++treeSeq;
  let t;
  try {
    t = await api(`/api/tree?folder=${encodeURIComponent(folder)}`);
  } catch (e) {
    t = { ok: false, message: e.message };
  }
  if (seq !== treeSeq) return; // a newer choice has been made
  const button = $("#start-form button[type=submit]");
  button.disabled = !t.ok;
  const head = el("div", { class: "ph" },
    el("span", { class: "tree-title" }, "Files in this folder"),
    t.folder ? el("span", { class: "src" }, t.folder) : null);
  if (!t.tree) {
    pane.replaceChildren(head, el("div", { class: "pb" }, el("p", { class: "callout quiet tree-msg" }, t.message)));
    return;
  }
  const summary = `${t.files} ${t.files === 1 ? "file" : "files"}: ${t.to_read} will be read` +
    (t.skipped ? `, ${t.skipped} skipped` : "") + ". Nothing is read until you press \"Read the folder\".";
  pane.replaceChildren(head, el("div", { class: "pb" }, ...[
    t.ok ? null : el("p", { class: "callout quiet tree-msg" }, t.message),
    el("p", { class: "tree-summary" }, summary),
    el("ul", { class: "tree", role: "tree" }, t.tree.children.map(treeNode))].filter(Boolean)));
}

function treeNode(n) {
  if (n.type === "dir") {
    return el("li", { class: "tree-dir", role: "treeitem" },
      el("div", { class: "tree-row" }, el("span", { class: "tree-name" }, `${n.name}/`),
        n.reason ? el("span", { class: "tree-status skip" }, `Skipped: ${n.reason}`) : el("span", { class: "tree-kind" }, "Folder")),
      n.children.length ? el("ul", { role: "group" }, n.children.map(treeNode)) : null);
  }
  return el("li", { class: `tree-file ${n.read ? "read" : "skip"}`, role: "treeitem" },
    el("div", { class: "tree-row" },
      el("span", { class: "tree-name" }, n.name),
      el("span", { class: "tree-kind" }, n.kind),
      el("span", { class: `tree-status ${n.read ? "read" : "skip"}` }, n.read ? "Will be read" : `Skipped: ${n.reason}`)));
}

// The box is pre-filled from the task folder's intent.txt so the person can edit it. A folder with no such file
// leaves it empty. Only a pre-filled value is replaced: what the person typed themselves is kept.
let prefilled = "";
function fillIntent(folder) {
  const box = $("#intent-input");
  if (box.value.trim() && box.value !== prefilled) return;
  // accept the materials folder or the task folder, relative (with or without "./") or absolute
  const wanted = folder.trim().replace(/\/+$/, "").replace(/^\.\//, "");
  const t = config.tasks.find((x) => {
    const task = x.folder.replace(/\/materials$/, "");
    return [x.folder, task].some((f) => wanted === f || wanted.endsWith("/" + f));
  });
  prefilled = t ? t.intent : "";
  box.value = prefilled;
}

async function start(ev) {
  ev.preventDefault();
  const err = $("#start-error");
  err.hidden = true;
  const folder = $("#folder-input").value.trim() || $("#task-select").value;
  const button = $("#start-form button[type=submit]");
  button.disabled = true;
  lastStart = {
    folder,
    intent: $("#intent-input").value,
    rule: $("#rule-select").value,
    model: $("#model-select").value,
    limit: $("#limit-input").value.trim() || "none",
  };
  try {
    view = await api("/api/session", lastStart);
  } catch (e) {
    err.textContent = e.message;
    err.hidden = false;
    button.disabled = false;
    button.textContent = "Read the folder";
    return;
  }
  button.disabled = false;
  location.hash = `s=${view.id}`;
  $("#start").hidden = true;
  $("#interview").hidden = false;
  render();
  if (view.status === "reading") poll();
}

// ---------------------------------------------------------------- reading (change 3)

// The page asks the server how far reading has got, about twice a second, and shows exactly that: which step is
// running, which file, how many items are back. Nothing is estimated in the browser except the seconds ticking
// between two answers from the server.
let lastStart = null;
let pollTimer = null;
let viewAt = 0;
let pollMisses = 0;
async function poll() {
  clearTimeout(pollTimer);
  try {
    view = await api(`/api/session/${view.id}`);
    viewAt = Date.now();
    pollMisses = 0;
  } catch (e) {
    // the reading goes on in the tool; one missed answer is not a failure. Give up after about 15 seconds.
    if (++pollMisses < 10) { pollTimer = setTimeout(poll, 1500); return; }
    pollMisses = 0;
    view = { ...view, status: "failed", error: `Lost contact with the tool: ${e.message}. It may still be reading; reload the page to look again.` };
  }
  render();
  if (view.status === "reading") pollTimer = setTimeout(poll, 500);
}

function elapsed(st) {
  if (st.seconds === null || st.seconds === undefined) return "";
  const extra = st.state === "on" && viewAt ? (Date.now() - viewAt) / 1000 : 0;
  return `${Math.floor(st.seconds + extra)} s`;
}

function renderReading(pane) {
  const p = view.progress;
  const failed = view.status === "failed";
  const files = p.files || [];
  const listed = view.items.length;
  const read = files.filter((f) => f.read).length;
  const skipped = files.length - read;
  pane.className = `panel q-pane ${failed ? "bad" : ""}`;
  pane.append(el("div", { class: "ph" },
    failed ? el("span", { class: "glyph bad", "aria-hidden": "true" }, "!") : el("span", { class: "spin", "aria-hidden": "true" }),
    failed ? "Reading stopped" : "Reading the folder"));
  const body = el("div", { class: "pb" });
  pane.append(body);
  if (failed) {
    body.append(
      el("div", { class: "callout bad", role: "alert" }, view.error || "Something went wrong."),
      el("p", { class: "small" }, "Nothing was guessed. No question was asked. Your folder was not changed."),
      el("div", { class: "brow" },
        el("button", { class: "b pr", onclick: retry }, "Try again"),
        el("button", { class: "b", onclick: backToStart }, "Choose another folder")));
  } else if (files.length) {
    body.append(el("p", { class: "read-head" }, `${files.length} ${files.length === 1 ? "file" : "files"}. ` +
      (skipped ? `${read} read. ${skipped} I cannot read.` : (files.length === 1 ? "It is read." : "All are read."))));
  }
  const list = el("ol", { class: "read-steps" });
  for (const st of p.steps) {
    const count = st.of ? `${st.n ?? 0} of ${st.of}` : (st.key === "first" && st.n ? `${st.n} ${st.n === 1 ? "item" : "items"}` : "");
    const right = st.state === "on" ? [count, elapsed(st)].filter(Boolean).join(" · ")
      : st.state === "done" ? `${st.summary} · ${elapsed(st)}` : st.state === "failed" ? "stopped here" : "";
    list.append(el("li", { class: `read-step ${st.state}` },
      el("span", { class: "read-mark", "aria-hidden": "true" },
        st.state === "done" ? "✓" : st.state === "failed" ? "!" : st.state === "on" ? el("span", { class: "spin" }) : ""),
      el("div", { class: "read-body" },
        el("div", { class: "read-label" }, el("span", {}, st.label), right ? el("span", { class: "read-count" }, right) : null),
        st.state === "on" || st.state === "failed" ? el("div", { class: "read-detail" }, st.detail) : null)));
  }
  body.append(list);
  if (files.length) {
    const table = el("div", { class: "read-files", role: "table", "aria-label": "Files" },
      el("div", { class: "frow hd2", role: "row" }, el("span", { role: "columnheader" }, "File"), el("span", { role: "columnheader" }, "Status")));
    for (const f of files) {
      table.append(el("div", { class: `frow ${f.read ? "" : "ex"}`, role: "row" },
        el("span", { class: "fn", role: "cell" }, f.name),
        el("span", { role: "cell", class: f.read ? "ok-text" : "muted" },
          f.read ? (f.items ? `✓ Read. ${f.items} ${f.items === 1 ? "item" : "items"}` : "✓ Read") : `Not read: ${f.reason}`)));
    }
    body.append(table);
  }
  if (!failed) {
    body.append(el("p", { class: "callout quiet" },
      `So far: ${listed} ${listed === 1 ? "item" : "items"} on the right, each with its document and exact passage. ` +
      "No question is asked until reading is finished."));
  }
}

async function retry() {
  if (!lastStart) return backToStart();
  try {
    view = await api("/api/session", lastStart);
  } catch (e) {
    view = { ...view, status: "failed", error: e.message };
    render();
    return;
  }
  location.hash = `s=${view.id}`;
  render();
  if (view.status === "reading") poll();
}

function backToStart() {
  clearTimeout(pollTimer);
  location.hash = "";
  $("#interview").hidden = true;
  $("#start").hidden = false;
  document.querySelectorAll("aside.left > .why").forEach((n) => n.remove());
  $("#meter").hidden = true;
  $("#task-name").hidden = true;
  renderSteps("Folder");
}

// ---------------------------------------------------------------- interview

async function reply(action, value, who) {
  const q = view.question;
  whyOpen = false;
  try {
    view = await api(`/api/session/${view.id}/reply`, { item: q.item, action, value, who });
  } catch (e) {
    alert(e.message);
    return;
  }
  render();
}

// Stage 7: the source passage expands in place with a few lines of context, highlighted. No file viewer.
function sourceView(key, documentName, passage, context, compact = false) {
  if (!documentName || !passage || documentName === "the person") return null;
  const open = openSources.has(key);
  const toggle = el("button", { class: "source-toggle", "aria-expanded": open ? "true" : "false",
    onclick: () => { open ? openSources.delete(key) : openSources.add(key); render(); } },
    `${open ? "Hide" : "Show"} source: ${documentName}`);
  const wrap = el("div", { class: "source" }, toggle);
  if (!open) {
    if (!compact) wrap.append(el("div", { class: "source-quote" }, `"${passage}"`));
    return wrap;
  }
  const box = el("div", { class: "source-context" });
  if (context) {
    const n0 = context.line - context.before.length;
    context.before.forEach((l, i) => box.append(el("div", { class: "ctx" }, el("span", { class: "ln" }, n0 + i), el("span", {}, l))));
    context.match.forEach((l, i) => box.append(el("div", { class: "ctx hit" }, el("span", { class: "ln" }, context.line + i), el("span", {}, l))));
    context.after.forEach((l, i) => box.append(el("div", { class: "ctx" }, el("span", { class: "ln" }, context.line + context.match.length + i), el("span", {}, l))));
  } else {
    box.append(el("div", { class: "ctx hit" }, passage));
  }
  wrap.append(box);
  return wrap;
}

function pct(p) { return `${Math.round(p * 100)}%`; }
function yn(b) { return b ? "yes" : "no"; }
function num(x) { return Math.round(x * 1000) / 1000; }

async function renderWhy(container, itemId) {
  let data;
  try {
    data = await api(`/api/session/${view.id}/why/${itemId}`);
  } catch (e) {
    container.replaceChildren(el("p", { class: "callout bad" }, e.message));
    return;
  }
  const d = data.decided;
  const head = el("div", { class: "ph" }, el("span", {}, "Why this question"), el("span", { class: "sp" }), el("span", { class: "ro" }, "Read-only"));
  if (d.chance_wrong === null || d.chance_wrong === undefined) {
    // the clash between the person's intent and the folder's goal: never went to the ask table
    container.replaceChildren(head, el("div", { class: "pb" },
      el("dl", { class: "kv" }, [el("dt", {}, "Kind of question"), el("dd", {}, `${d.question_kind}, cost ${d.question_cost}`),
        el("dt", {}, "Rule"), el("dd", {}, "None: what you typed never goes to the ask table.")]),
      el("p", { class: "why-reason" }, d.reason),
      el("p", { class: "small" }, "Taken from the gap trace. Nothing here can be changed.")));
    return;
  }
  const rows = [
    ["Chance a guess is wrong", `${pct(d.chance_wrong)} (the model's estimate)`],
    ["Could a mistake be undone?", `${yn(d.can_undo)} (the model's answer)`],
    ["Would you notice a mistake?", `${yn(d.would_notice)} (the model's answer)`],
    ["Harm if wrong", `${d.harm_band} (${d.harm})`],
    ["Kind of question", `${d.question_kind}, cost ${d.question_cost}`],
    ["Rule", `${data.rule_label}${d.threshold !== null ? `, ${data.threshold_name} = ${d.threshold}` : ""}: ${data.rule_test}`],
  ];
  let working = null;
  if (d.rule === "cost-weighted") {
    const lhs = num(d.chance_wrong * d.harm), rhs = num(d.threshold * d.question_cost);
    working = `${num(d.chance_wrong)} x ${d.harm} = ${lhs}, against ${d.threshold} x ${d.question_cost} = ${rhs}: ${lhs >= rhs - 1e-9 ? "at least as big, so ask" : "smaller, so do not ask"}.`;
  } else if (d.rule === "confidence-only") {
    working = `${num(d.chance_wrong)} against ${d.threshold}: ${d.chance_wrong >= d.threshold - 1e-9 ? "at or above, so ask" : "below, so do not ask"}.`;
  }
  container.replaceChildren(head, el("div", { class: "pb" }, ...[
    el("dl", { class: "kv" }, rows.flatMap(([k, v]) => [el("dt", {}, k), el("dd", {}, v)])),
    working ? el("p", { class: "why-working" }, working) : null,
    data.clash && d.way === "ask" ? el("p", { class: "why-working" }, "A clash is always asked, whatever this arithmetic says: the plan settles a clash by a choose question that shows both sides.") : null,
    !data.clash && /, and questions remain\./.test(d.reason || "") ? el("p", { class: "why-working" }, "The tool cannot guess this item, so it is asked while questions remain, whatever this arithmetic says. The arithmetic only decides items the tool could guess.") : null,
    el("p", { class: "why-reason" }, d.reason),
    el("p", { class: "small" }, `Order of value: (chance wrong x harm) / cost = ${num(d.chance_wrong * d.harm / d.question_cost)}. Higher comes first.`),
    el("p", { class: "small" }, "Taken from the gap trace. Nothing here can be changed."),
  ].filter(Boolean)));
}

async function control(itemId, action, value) {
  try {
    view = await api(`/api/session/${view.id}/item`, { item: itemId, action, value });
  } catch (e) {
    alert(e.message);
    return;
  }
  editing = null;
  render();
}

function itemControls(it) {
  if (view.finished) return null;
  if (it.rejected) {
    return el("div", { class: "ctl" }, el("button", { class: "cb", onclick: () => control(it.id, "restore") }, "Restore"));
  }
  return el("div", { class: "ctl" },
    it.can_confirm ? el("button", { class: "cb", title: "The value is right", "aria-label": `Confirm: ${it.label}`, onclick: () => control(it.id, "confirm") }, "Confirm") : null,
    el("button", { class: "cb", title: "Change the value", "aria-label": `Edit: ${it.label}`, onclick: () => { editing = it.id; renderItems(); } }, "Edit"),
    el("button", { class: "cb", title: "This does not belong in the brief", "aria-label": `Reject: ${it.label}`, onclick: () => control(it.id, "reject") }, "Reject"),
  );
}

function editBox(it) {
  const input = el("input", { type: "text", value: it.value || "", "aria-label": `New value for ${it.label}` });
  const save = () => control(it.id, "edit", input.value);
  input.addEventListener("keydown", (ev) => { if (ev.key === "Enter") save(); if (ev.key === "Escape") { editing = null; renderItems(); } });
  setTimeout(() => input.focus(), 0);
  return el("div", { class: "edit-box" }, input,
    el("button", { class: "b sm pr", onclick: save }, "Save"),
    el("button", { class: "b sm", onclick: () => { editing = null; renderItems(); } }, "Cancel"));
}

// Plan change 1: a waiting or open item can be answered on the end screen. The values the documents give are
// offered as buttons (only when the item's values come from the folder); anything else can be typed.
function reviewAnswer(it) {
  const documented = (it.sources && it.sources.length) || (it.document && it.passage_found);
  const box = el("input", { type: "text", placeholder: "Your answer", "aria-label": `Your answer: ${it.label}` });
  const send = (v) => reviewReply(it.id, v);
  box.addEventListener("keydown", (ev) => { if (ev.key === "Enter") send(box.value); });
  const picks = (documented ? it.candidates || [] : []).slice(0, 4).map((c) => el("button", { class: "b sm", onclick: () => send(c) }, c));
  return el("div", { class: "rv-answer" }, picks.length ? el("div", { class: "brow" }, picks) : null,
    el("div", { class: "typed" }, box, el("button", { class: "b sm", onclick: () => send(box.value) }, "Answer")));
}

async function reviewReply(itemId, value) {
  try {
    view = await api(`/api/session/${view.id}/review`, { item: itemId, value });
  } catch (e) {
    alert(e.message);
    return;
  }
  render();
}

async function finish() {
  view = await api(`/api/session/${view.id}/finish`, {});
  render();
}

function render() {
  const badge = $("#model-badge");
  badge.hidden = false;
  badge.className = "badge " + (view.model_kind === "simulated" ? "sim" : "real");
  badge.textContent = view.model_kind === "simulated" ? "Simulated model" : `Model: ${view.model}`;
  $("#run-label").textContent = `Run ${view.run} · ${view.run_label}`;
  const task = $("#task-name");
  task.hidden = false;
  task.replaceChildren("Brief for ", el("b", {}, view.task));
  renderMeter();
  if (view.status === "reading" || view.status === "failed") {
    renderSteps("Reading");
    document.querySelectorAll("aside.left > .why").forEach((n) => n.remove());
    const pane = $("#question-pane");
    pane.replaceChildren();
    renderReading(pane);
    $("#progress-pane").replaceChildren();
    $("#progress-pane").hidden = true;
    renderItems();
    renderBrief();
    return;
  }
  renderSteps(view.finished ? "Brief" : (!view.question && !view.at_limit) ? "Review" : "Interview");
  $("#progress-pane").hidden = false;
  renderQuestion();
  renderProgress();
  renderItems();
  renderBrief();
  const current = document.querySelector(".items-list li.current");
  if (current) current.scrollIntoView({ block: "nearest", behavior: "smooth" });
}

// P7 and P8: at the limit, say how much more seems needed, and let the person continue or stop.
function renderLimit(pane) {
  const need = view.at_limit;
  pane.className = "panel q-pane warn";
  pane.append(
    el("div", { class: "ph" }, el("span", { class: "glyph", "aria-hidden": "true" }, "◷"), "You have reached your question limit"),
    el("div", { class: "pb" },
      el("p", { class: "lead" }, `Your limit is ${view.limit} ${view.limit === 1 ? "question" : "questions"}, and ${view.question_count} ${view.question_count === 1 ? "has" : "have"} been asked. ` +
        need.message),
      el("p", { class: "callout warn" }, "The most important questions came first."),
      el("div", { class: "brow" },
        el("button", { class: "b pr", onclick: () => limitChoice("continue") }, need.button),
        el("button", { class: "b", onclick: () => limitChoice("stop") }, "Stop here")),
      el("p", { class: "small" }, "If you stop: anything that cannot be undone, any fact about a named person, anything with nothing to guess from and any clash is left open for the agent to ask; the rest is guessed and marked assumed.")),
  );
}

async function limitChoice(action) {
  try {
    view = await api(`/api/session/${view.id}/limit`, { action });
  } catch (e) {
    alert(e.message);
    return;
  }
  render();
}

// P10: one end screen. Review everything once, see what waits, then write the brief.
function renderEndScreen(pane) {
  const live = view.items.filter((i) => !i.rejected);
  const waiting = live.filter((i) => i.state === "open" || i.state === "conflict");
  const assumed = live.filter((i) => i.state === "assumed");
  const unavailable = live.filter((i) => i.state === "not available here");
  const section = (title, note, items, state, extra) => items.length ? el("div", { class: "review-section" },
    el("div", { class: "sec-h" }, title, el("span", { class: "cnt" }, String(items.length))),
    el("p", { class: "small" }, note),
    el("ul", { class: "review-list" }, items.map((it) => el("li", { class: `rv st-${stateClass(state || it.state)}` },
      el("a", { href: `#item-${it.id}`, onclick: (ev) => { ev.preventDefault(); document.getElementById(`item-${it.id}`).scrollIntoView({ block: "center", behavior: "smooth" }); } }, it.label),
      it.value && it.state === "assumed" ? el("span", { class: "muted" }, `: ${it.value}`) : null,
      it.state === "open" || it.state === "conflict" ? el("span", { class: `tag ${it.must_hold_or_nice === "must hold" ? "must" : "nice"} rv-tag` }, shown(it.must_hold_or_nice)) : null,
      extra ? extra(it) : null)))) : null;
  pane.className = "panel q-pane";
  pane.append(
    el("div", { class: "ph" }, el("span", { class: "glyph", "aria-hidden": "true" }, "◉"), "Review before the brief is written"),
    el("div", { class: "pb" }, ...[
      // the "Still open" block is shown once, at the top of the brief in progress beside this screen
      el("p", {}, `No more questions. Asked ${view.question_count}. Check the brief in progress once: confirm, edit or reject anything. Then write it.`),
      section("Waiting", "Not settled. Answer any you can here; the brief passes the rest to the agent as \"ask before you do this\".", waiting, null, reviewAnswer),
      section("Guessed and marked", "The tool guessed these. Confirm or edit any you can.", assumed, "assumed"),
      section(shown("not available here"), "You could not answer these, and the folder does not hold them. Say who could, if you know.", unavailable, "not available here", (it) => {
        const box = el("input", { type: "text", value: it.who_could || "", placeholder: "Who could?", "aria-label": `Who could answer: ${it.label}` });
        box.addEventListener("change", () => control(it.id, "who could", box.value));
        return box;
      }),
      el("button", { class: "b pr big", onclick: finish }, "Write the brief"),
    ].filter(Boolean)),
  );
}

// A very small Markdown view for the brief: headings, lists, bold, italics, quotes. Text is escaped first.
function briefHtml(md) {
  const esc = (t) => t.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  const slug = (t) => t.toLowerCase().replace(/[^a-z0-9 -]/g, "").trim().replace(/ /g, "-");
  const inline = (t) => esc(t).replace(/\[([^\]]+)\]\(#([a-z0-9-]+)\)/g, '<a href="#$2" data-brief-link="$2">$1</a>')
    .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>").replace(/(^|\s)_(.+?)_(?=\s|$|[.,;])/g, "$1<em>$2</em>");
  const out = [];
  let inList = false;
  for (const line of md.split("\n")) {
    const li = line.match(/^- (.*)$/);
    if (li) { if (!inList) { out.push("<ul>"); inList = true; } out.push(`<li>${inline(li[1])}</li>`); continue; }
    if (inList) { out.push("</ul>"); inList = false; }
    if (line.startsWith("# ")) out.push(`<h2>${inline(line.slice(2))}</h2>`);
    else if (line.startsWith("## ")) out.push(`<h3 id="brief-${slug(line.slice(3))}">${inline(line.slice(3))}</h3>`);
    else if (line.startsWith("> ")) out.push(`<blockquote>${inline(line.slice(2))}</blockquote>`);
    else if (line.trim()) out.push(`<p>${inline(line)}</p>`);
  }
  if (inList) out.push("</ul>");
  return out.join("\n");
}

function renderProgress() {
  const counts = {};
  for (const it of view.items) counts[it.state] = (counts[it.state] || 0) + 1;
  const order = ["confirmed", "assumed", "open", "conflict", "not available here"];
  $("#progress-pane").replaceChildren(el("div", { class: "pb" }, ...[
    el("div", {}, `Questions asked: ${view.question_count}${view.limit !== null ? ` of ${view.limit}` : ""} · ${view.questions_left} waiting`),
    el("div", { class: "legend" }, order.filter((s) => counts[s]).map((s) => stateChip(s, `${counts[s]} ${shownLower(s)}`))),
    el("div", {}, `Read ${view.documents.length} documents: `, ...view.documents.flatMap((d, i) => [i ? " " : "", el("span", { class: "src" }, d)])),
    view.skipped.length ? el("div", {}, `Not read: ${view.skipped.map((s) => `${s.name} (${s.reason})`).join("; ")}`) : null,
  ].filter(Boolean)));
}

function renderQuestion() {
  const pane = $("#question-pane");
  document.querySelectorAll("aside.left > .why").forEach((n) => n.remove());
  pane.replaceChildren();
  pane.className = "panel q-pane";
  if (view.finished) {
    pane.append(
      el("div", { class: "ph" }, el("span", { class: "glyph ok", "aria-hidden": "true" }, "✓"), "The brief is written"),
      el("div", { class: "pb" },
        el("p", { class: "small" }, `Saved in ${view.run_dir}.`),
        el("div", { class: "brow" },
          el("a", { class: "b pr", href: `/api/session/${view.id}/brief.md` }, "Download the brief"),
          el("a", { class: "b", href: `/api/session/${view.id}/gap-trace.jsonl` }, "Download the gap trace")),
        el("p", { class: "again" }, el("a", { href: "/", onclick: () => { location.hash = ""; } }, "Start another"))),
    );
    return;
  }
  if (view.at_limit) {
    renderLimit(pane);
    return;
  }
  const q = view.question;
  if (!q) {
    renderEndScreen(pane);
    return;
  }
  pane.className = "panel q-pane q-card";
  const item = view.items.find((i) => i.id === q.item);
  const answerBox = el("input", { type: "text", placeholder: "Type your answer", "aria-label": "Your answer" });
  const replies = el("div", { class: "brow replies" });
  const opts = el("div", { class: "opts" });
  if (q.kind === "confirm") {
    opts.append(el("button", { class: "opt pick", onclick: () => reply("answer", q.value) },
      el("span", { class: "rd", "aria-hidden": "true" }), el("span", {}, "Yes, that is right")));
  }
  let clash = null;
  if (q.kind === "choose" && q.sources && q.sources.length) {
    const withYou = q.sources.some((src) => src.person);
    clash = el("div", { class: "clash" }, el("p", { class: "clash-title" },
      withYou ? "What you typed and the folder disagree. Which is right?" : "The documents disagree. Which is right?"));
    const cards = el("div", { class: "cmp" });
    for (const src of q.sources) {
      cards.append(el("button", { class: "clash-option", onclick: () => reply("answer", src.value) },
        el("span", { class: "clash-value" }, src.value),
        el("span", { class: `src ${src.person ? "you" : ""}` }, src.person ? "what you typed on the start page" : `from ${src.document}`)));
    }
    clash.append(cards);
  } else if (q.kind === "choose") {
    for (const c of q.candidates) opts.append(el("button", { class: "opt", onclick: () => reply("answer", c) }, el("span", { class: "rd", "aria-hidden": "true" }), el("span", {}, c)));
  }
  const typed = el("div", { class: "typed" }, answerBox,
    el("button", { class: "b", onclick: () => reply("answer", answerBox.value) }, q.kind === "open" ? "Answer" : "Something else"));
  replies.append(
    el("button", { class: "b", title: "The item stays open. The question still counts.", onclick: () => reply("skip") }, "↷ Skip"));
  const whoBox = el("input", { type: "text", placeholder: "Who could? (optional)", "aria-label": "Who could answer this? (optional)" });
  pane.append(...[
    el("div", { class: "q-head" },
      el("span", { class: "q-num" }, `Question ${view.question_count + 1}`),
      el("span", { class: "kind" }, `${q.kind} question`),
      el("span", { class: "sp" }),
      el("button", { class: `b sm why-toggle ${whyOpen ? "on" : ""}`, "aria-expanded": whyOpen ? "true" : "false", onclick: () => { whyOpen = !whyOpen; render(); } },
        whyOpen ? "Hide why" : "Why this question?")),
    el("p", { class: "question-text qq" }, q.text),
    el("p", { class: "reason q-why" }, q.reason),
    item ? sourceView(`q-${item.id}`, item.document, item.passage, item.context) : null,
    clash,
    clash && item ? el("div", { class: "clash-sources" }, item.sources.map((src, i) => sourceView(`q-${item.id}-${i}`, src.document, src.passage, src.context))) : null,
    opts.childNodes.length ? opts : null,
    typed,
    replies,
    el("div", { class: "cant-answer" },
      el("button", { class: "b", title: "Asking you again will not help. The tool stops asking and records who to go to.", onclick: () => reply("I can't answer this", null, whoBox.value) }, "⊘ I can't answer this"),
      whoBox),
  ].filter(Boolean));
  if (whyOpen) {
    const box = el("div", { class: "panel why" }, el("div", { class: "pb" }, el("p", { class: "small" }, "Loading...")));
    pane.after(box);
    renderWhy(box, q.item);
  }
}

// Display only: the "Still open" block at the top of the brief in progress, on the main screen and beside the end
// screen; it is built in one place only, so it shows once. Each line links to
// the item's row under its heading. It is rebuilt on every render, so it changes as items are settled.
function goToItem(id) {
  const row = document.getElementById(`item-${id}`);
  if (row) {
    row.scrollIntoView({ block: "center", behavior: "smooth" });
    row.classList.add("flash");
    setTimeout(() => row.classList.remove("flash"), 1200);
  }
}

function stillOpenBlock() {
  const list = view.still_open;
  const box = el("section", { class: "still-open", "aria-label": "Still open" },
    el("div", { class: "so-h" }, "Still open", list && list.length ? el("span", { class: "cnt" }, String(list.length)) : null));
  if (!list) {
    box.append(el("p", { class: "small" }, "Worked out when reading is finished."));
  } else if (!list.length) {
    box.append(el("p", { class: "small" }, "Nothing is still open: every item is settled."));
  } else {
    box.append(el("ul", { class: "so-list" }, list.map((it) => el("li", {},
      stateChip(it.state),
      el("div", {},
        el("a", { href: `#item-${it.id}`, onclick: (ev) => { ev.preventDefault(); goToItem(it.id); } }, it.label),
        el("div", { class: "so-where" }, `${it.heading} · ${shown(it.must_hold_or_nice)}`))))));
  }
  return box;
}

function renderItems() {
  const pane = $("#items-pane");
  const currentId = view.question && !view.finished ? view.question.item : null;
  const counts = {};
  for (const it of view.items) if (!it.rejected) counts[it.state] = (counts[it.state] || 0) + 1;
  const order = ["confirmed", "assumed", "open", "conflict", "not available here"];
  const reading = view.status !== "ready";
  pane.replaceChildren(...[
    el("div", { class: "ph" }, el("span", {}, reading ? "The brief in progress, as items arrive" : "The brief in progress"),
      el("span", { class: "sp" }), reading ? null : el("span", { class: "small" }, "On each item: confirm, edit, reject")),
  ].filter(Boolean));
  const body = el("div", { class: "pb" });
  pane.append(body);
  body.append(stillOpenBlock());
  if (!reading) body.append(el("div", { class: "legend" }, order.filter((s) => counts[s]).map((s) => stateChip(s, `${counts[s]} ${shownLower(s)}`))));
  if (!view.intent && !reading) body.append(el("p", { class: "callout quiet doc-request" }, "You did not say what you want the agent to do, so the goal comes from the folder."));
  for (const heading of view.headings) {
    const items = view.items.filter((i) => i.heading === heading);
    body.append(el("div", { class: "sec-h" }, heading, el("span", { class: "cnt" }, items.length ? String(items.length) : "")));
    if (!items.length) {
      body.append(el("div", { class: "empty-row" }, reading ? "Nothing yet." : "Nothing here yet."));
      continue;
    }
    const list = el("ul", { class: "items-list" });
    for (const it of items) {
      const state = it.rejected ? "rejected" : it.state;
      const classes = ["entry", `st-${stateClass(state)}`, it.id === currentId ? "current" : "", it.rejected ? "rejected" : ""].join(" ").trim();
      const said = it.way === "said by the person";
      const tags = [
        el("span", { class: `tag ${said ? "you" : it.stated_or_inferred}` }, said ? "your intent" : it.stated_or_inferred),
        el("span", { class: `tag ${it.must_hold_or_nice === "must hold" ? "must" : "nice"}` }, shown(it.must_hold_or_nice)),
        it.way_tag ? el("span", { class: "tag way" }, it.way_tag) : null,
        it.document ? el("span", { class: "src" }, it.document) : null,
        it.source === "person" && !said ? el("span", { class: "src you" }, "settled by you") : null,
        it.id === currentId ? el("span", { class: "now-tag" }, "this question") : null,
      ].filter(Boolean);
      list.append(el("li", { class: classes, id: `item-${it.id}` },
        stateChip(state, it.rejected ? "Rejected" : (state === "not available here" && it.who_could ? `${shown(state)}: ${it.who_could}` : null)),
        el("div", { class: "tx" }, el("span", { class: "item-label" }, it.label), it.value && it.state !== "conflict" ? el("span", { class: "item-value" }, `: ${it.value}`) : null),
        editing === it.id || reading ? null : itemControls(it),
        el("div", { class: "mt" }, tags),
        el("div", { class: "below" }, ...[
          it.sources && it.sources.length ? el("div", { class: "clash-note" },
            (it.sources.some((src) => src.person) ? "Your intent and the folder disagree: " : "Documents disagree: ")
              + it.sources.map((src) => `${src.value} (${src.person ? "you" : src.document})`).join(" vs ")) : null,
          it.passage ? sourceView(`i-${it.id}`, it.document, it.passage, it.context, true) : null,
          ...(it.sources || []).map((src, n) => sourceView(`i-${it.id}-${n}`, src.document, src.passage, src.context, true)),
          editing === it.id ? editBox(it) : null,
        ].filter(Boolean)),
      ));
    }
    body.append(list);
  }
}

function renderBrief() {
  const pane = $("#brief-pane");
  pane.hidden = !view.brief;
  $("#items-pane").hidden = Boolean(view.brief);
  if (!view.brief) return;
  const body = el("div", { class: "brief-view doc" });
  body.innerHTML = briefHtml(view.brief); // escaped in briefHtml
  // links in the brief go to a heading in the brief, without touching the page's own address (it holds the session)
  body.addEventListener("click", (ev) => {
    const a = ev.target.closest("a[data-brief-link]");
    if (!a) return;
    ev.preventDefault();
    const h = document.getElementById(`brief-${a.dataset.briefLink}`);
    if (h) h.scrollIntoView({ block: "start", behavior: "smooth" });
  });
  pane.replaceChildren(body);
}

function renderMeter() {
  const m = $("#meter");
  if (view.status !== "ready") { m.hidden = true; return; }
  m.hidden = false;
  // Plan change 2: the person sees the limit as a number of questions; question cost stays in the why panel.
  const limit = view.limit;
  const used = view.question_count;
  const frac = limit ? Math.min(1, used / limit) : (limit === 0 ? 1 : 0);
  m.replaceChildren(...[
    el("span", {}, el("b", {}, String(used)), limit !== null ? ` of ${limit} ${limit === 1 ? "question" : "questions"} asked`
      : ` ${used === 1 ? "question" : "questions"} asked`),
    limit !== null ? el("span", { class: "bar2", role: "img", "aria-label": `${used} of ${limit} questions asked` },
      el("i", { class: frac >= 1 ? "hot" : "", style: `width:${Math.round(frac * 100)}%` })) : null,
  ].filter(Boolean));
}

init().catch((e) => {
  $("#start-error").textContent = e.message;
  $("#start-error").hidden = false;
});
