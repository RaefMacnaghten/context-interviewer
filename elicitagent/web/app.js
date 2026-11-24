"use strict";

const $ = (sel) => document.querySelector(sel);
let config = null;
let view = null;

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

function stateClass(state) {
  return state === "cannot be done" ? "cannot" : state;
}

// ---------------------------------------------------------------- start

async function init() {
  config = await api("/api/config");
  const taskSelect = $("#task-select");
  for (const t of config.tasks) taskSelect.append(el("option", { value: t.folder }, `${t.name} (${t.folder})`));
  taskSelect.addEventListener("change", fillRequest);
  fillRequest();
  const ruleSelect = $("#rule-select");
  for (const r of config.rules) {
    const thr = r.threshold === null || r.threshold === undefined ? "" : `, ${r.threshold_name} = ${r.threshold}`;
    ruleSelect.append(el("option", { value: r.name }, `${r.label}${thr}`));
  }
  $("#model-select").value = config.default_model;
  $("#start-form").addEventListener("submit", start);
  const m = location.hash.match(/^#s=([0-9a-f]+)$/);
  if (m) {
    try {
      view = await api(`/api/session/${m[1]}`);
      $("#start").hidden = true;
      $("#interview").hidden = false;
      render();
    } catch (e) {
      location.hash = "";
    }
  }
}

function fillRequest() {
  const t = config.tasks.find((x) => x.folder === $("#task-select").value);
  if (t) $("#request-input").value = t.request;
}

async function start(ev) {
  ev.preventDefault();
  const err = $("#start-error");
  err.hidden = true;
  const folder = $("#folder-input").value.trim() || $("#task-select").value;
  const button = $("#start-form button[type=submit]");
  button.disabled = true;
  button.textContent = "Reading the folder. With a real model this takes a minute or two.";
  try {
    view = await api("/api/session", {
      folder,
      request: $("#request-input").value,
      rule: $("#rule-select").value,
      model: $("#model-select").value,
    });
  } catch (e) {
    err.textContent = e.message;
    err.hidden = false;
    button.disabled = false;
    button.textContent = "Read the folder";
    return;
  }
  location.hash = `s=${view.id}`;
  $("#start").hidden = true;
  $("#interview").hidden = false;
  render();
}

// ---------------------------------------------------------------- interview

async function reply(action, value, who) {
  const q = view.question;
  try {
    view = await api(`/api/session/${view.id}/reply`, { item: q.item, action, value, who });
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
  renderQuestion();
  renderProgress();
  renderItems();
  renderBrief();
  const current = document.querySelector(".items-list li.current");
  if (current) current.scrollIntoView({ block: "nearest", behavior: "smooth" });
}

function renderProgress() {
  const counts = {};
  for (const it of view.items) counts[it.state] = (counts[it.state] || 0) + 1;
  const order = ["confirmed", "assumed", "open", "conflict", "cannot be done"];
  $("#progress-pane").replaceChildren(
    el("div", {}, `Questions asked: ${view.question_count} · question cost ${view.running_cost} · ${view.questions_left} waiting`),
    el("div", { class: "legend" }, order.filter((s) => counts[s]).map((s) => el("span", { class: `state ${stateClass(s)}` }, `${counts[s]} ${s}`))),
    el("div", {}, `Read ${view.documents.length} documents: ${view.documents.join(", ")}`),
    view.skipped.length ? el("div", {}, `Not read: ${view.skipped.map((s) => `${s.name} (${s.reason})`).join("; ")}`) : "",
  );
}

function renderQuestion() {
  const pane = $("#question-pane");
  pane.replaceChildren();
  if (view.finished) {
    pane.append(el("h2", {}, "The brief is written"), el("p", { class: "muted" }, `Saved in ${view.run_dir}.`));
    return;
  }
  const q = view.question;
  if (!q) {
    pane.append(
      el("h2", {}, "No more questions"),
      el("p", { class: "muted" }, `Questions asked: ${view.question_count}, question cost ${view.running_cost}.`),
      el("button", { class: "primary", onclick: finish }, "Write the brief"),
    );
    return;
  }
  const item = view.items.find((i) => i.id === q.item);
  const answerBox = el("input", { type: "text", placeholder: "Type your answer" });
  const replies = el("div", { class: "replies" });
  if (q.kind === "confirm") {
    replies.append(el("button", { class: "primary", onclick: () => reply("answer", q.value) }, "Yes, that is right"));
  }
  let clash = null;
  if (q.kind === "choose" && q.sources && q.sources.length) {
    clash = el("div", { class: "clash" }, el("p", { class: "clash-title" }, "The documents disagree. Which is right?"));
    for (const src of q.sources) {
      clash.append(el("button", { class: "clash-option", onclick: () => reply("answer", src.value) },
        el("span", { class: "clash-value" }, src.value),
        el("span", { class: "clash-source" }, `${src.document}: "${src.passage}"`)));
    }
  } else if (q.kind === "choose") {
    for (const c of q.candidates) replies.append(el("button", { onclick: () => reply("answer", c) }, c));
  }
  replies.append(answerBox, el("button", { onclick: () => reply("answer", answerBox.value) }, q.kind === "open" ? "Answer" : "Something else"));
  replies.append(el("button", { class: "quiet", title: "The item stays open. The question still counts.", onclick: () => reply("skip") }, "Skip"));
  const whoBox = el("input", { type: "text", placeholder: "Who could supply it? (optional)" });
  pane.append(...[
    el("p", { class: "cost" }, `Question ${view.question_count + 1} · ${q.kind} question · costs ${q.cost}`),
    el("p", { class: "question-text" }, q.text),
    el("p", { class: "reason" }, q.reason),
    item && item.passage ? el("p", { class: "item-meta" }, `From ${item.document}: "${item.passage}"`) : null,
    clash,
    replies,
    el("div", { class: "nobody" },
      el("button", { onclick: () => reply("nobody can answer", null, whoBox.value) }, "Nobody can answer this"),
      whoBox),
  ].filter(Boolean));
}

function renderItems() {
  const pane = $("#items-pane");
  const currentId = view.question && !view.finished ? view.question.item : null;
  pane.replaceChildren(
    el("h2", {}, "Brief in progress"),
    el("p", { class: "doc-request" }, `Request: ${view.request}`),
  );
  for (const heading of view.headings) {
    const items = view.items.filter((i) => i.heading === heading);
    pane.append(el("h3", {}, heading));
    if (!items.length) {
      pane.append(el("div", { class: "empty" }, "Nothing here yet."));
      continue;
    }
    const list = el("ul", { class: "items-list" });
    for (const it of items) {
      list.append(el("li", { class: it.id === currentId ? "current" : null, id: `item-${it.id}` },
        el("span", { class: `state ${stateClass(it.state)}` }, it.state),
        el("div", { class: "item-body" },
          el("div", {}, el("span", { class: "item-label" }, it.label), it.value && it.state !== "conflict" ? el("span", { class: "item-value" }, `: ${it.value}`) : null),
          el("div", { class: "item-meta" }, `${it.stated_or_inferred} · ${it.must_hold_or_nice} · ${it.way}${it.document ? " · " + it.document : ""}${it.who_can_supply ? " · who can supply it: " + it.who_can_supply : ""}`),
          it.sources && it.sources.length ? el("div", { class: "item-meta clash-note" },
            "Documents disagree: " + it.sources.map((src) => `${src.value} (${src.document})`).join(" vs ")) : null,
        ),
        it.id === currentId ? el("span", { class: "now-tag" }, "this question") : null,
      ));
    }
    pane.append(list);
  }
}

function renderBrief() {
  const pane = $("#brief-pane");
  pane.hidden = !view.brief;
  if (!view.brief) return;
  pane.replaceChildren(el("h2", {}, "Brief"), el("pre", { class: "brief" }, view.brief));
}

init().catch((e) => {
  $("#start-error").textContent = e.message;
  $("#start-error").hidden = false;
});
