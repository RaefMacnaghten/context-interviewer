"use strict";

const $ = (sel) => document.querySelector(sel);
let config = null;
let view = null;
let editing = null; // id of the item being edited

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
  $("#limit-input").value = config.limit_start;
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
      limit: $("#limit-input").value.trim() || "none",
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
    return el("div", { class: "controls" }, el("button", { class: "mini", onclick: () => control(it.id, "restore") }, "Restore"));
  }
  const canConfirm = it.value && it.state !== "conflict" && !(it.state === "confirmed" && it.source === "person");
  return el("div", { class: "controls" },
    canConfirm ? el("button", { class: "mini", title: "The value is right", onclick: () => control(it.id, "confirm") }, "Confirm") : null,
    el("button", { class: "mini", title: "Change the value", onclick: () => { editing = it.id; renderItems(); } }, "Edit"),
    el("button", { class: "mini", title: "This does not belong in the brief", onclick: () => control(it.id, "reject") }, "Reject"),
  );
}

function editBox(it) {
  const input = el("input", { type: "text", value: it.value || "", "aria-label": `New value for ${it.label}` });
  const save = () => control(it.id, "edit", input.value);
  input.addEventListener("keydown", (ev) => { if (ev.key === "Enter") save(); if (ev.key === "Escape") { editing = null; renderItems(); } });
  setTimeout(() => input.focus(), 0);
  return el("div", { class: "edit-box" }, input,
    el("button", { class: "mini primary", onclick: save }, "Save"),
    el("button", { class: "mini", onclick: () => { editing = null; renderItems(); } }, "Cancel"));
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

// P7 and P8: at the limit, say how much more seems needed, and let the person continue or stop.
function renderLimit(pane) {
  const need = view.at_limit;
  const plural = need.questions === 1 ? "question" : "questions";
  pane.append(
    el("h2", {}, "You have reached your question limit"),
    el("p", {}, `Your limit is ${view.limit} in question cost, and you have used ${view.running_cost}. ` +
      `I think I need at least ${need.questions} more ${plural}, with a question cost of ${need.cost}.`),
    el("p", { class: "muted small-note" }, "This is a lower bound: an answer can reveal a new gap. The most important questions came first."),
    el("div", { class: "replies" },
      el("button", { class: "primary", onclick: () => limitChoice("continue") }, `Continue (${config.limit_start} more)`),
      el("button", { onclick: () => limitChoice("stop") }, "Stop here")),
    el("p", { class: "muted small-note" }, "If you stop: anything that cannot be undone, and any fact about a named person, is left open for the agent to ask; the rest is guessed and marked assumed."),
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
  const cannot = live.filter((i) => i.state === "cannot be done");
  const section = (title, note, items, extra) => items.length ? el("div", { class: "review-section" },
    el("h3", {}, `${title} (${items.length})`),
    el("p", { class: "muted small-note" }, note),
    el("ul", { class: "review-list" }, items.map((it) => el("li", {},
      el("a", { href: `#item-${it.id}`, onclick: (ev) => { ev.preventDefault(); document.getElementById(`item-${it.id}`).scrollIntoView({ block: "center", behavior: "smooth" }); } }, it.label),
      it.value && it.state === "assumed" ? el("span", { class: "muted" }, `: ${it.value}`) : null,
      extra ? extra(it) : null)))) : null;
  pane.append(...[
    el("h2", {}, "Review before the brief is written"),
    el("p", { class: "muted" }, `No more questions. Asked ${view.question_count}, question cost ${view.running_cost}. Check the brief on the right once: confirm, edit or reject anything. Then write it.`),
    section("Waiting", "Not settled. The brief passes these to the agent as \"ask before you do this\".", waiting),
    section("Guessed and marked", "The tool guessed these. Confirm or edit any you can.", assumed),
    section("Cannot be done", "Nobody here can supply these. Say who needs to.", cannot, (it) => {
      const box = el("input", { type: "text", value: it.who_can_supply || "", placeholder: "Who needs to supply it?", "aria-label": `Who needs to supply ${it.label}` });
      box.addEventListener("change", () => control(it.id, "who can supply", box.value));
      return box;
    }),
    el("button", { class: "primary", onclick: finish }, "Write the brief"),
  ].filter(Boolean));
}

// A very small Markdown view for the brief: headings, lists, bold, italics, quotes. Text is escaped first.
function briefHtml(md) {
  const esc = (t) => t.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  const inline = (t) => esc(t).replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>").replace(/(^|\s)_(.+?)_(?=\s|$|[.,;])/g, "$1<em>$2</em>");
  const out = [];
  let inList = false;
  for (const line of md.split("\n")) {
    const li = line.match(/^- (.*)$/);
    if (li) { if (!inList) { out.push("<ul>"); inList = true; } out.push(`<li>${inline(li[1])}</li>`); continue; }
    if (inList) { out.push("</ul>"); inList = false; }
    if (line.startsWith("# ")) out.push(`<h2>${inline(line.slice(2))}</h2>`);
    else if (line.startsWith("## ")) out.push(`<h3>${inline(line.slice(3))}</h3>`);
    else if (line.startsWith("> ")) out.push(`<blockquote>${inline(line.slice(2))}</blockquote>`);
    else if (line.trim()) out.push(`<p>${inline(line)}</p>`);
  }
  if (inList) out.push("</ul>");
  return out.join("\n");
}

function renderProgress() {
  const counts = {};
  for (const it of view.items) counts[it.state] = (counts[it.state] || 0) + 1;
  const order = ["confirmed", "assumed", "open", "conflict", "cannot be done"];
  $("#progress-pane").replaceChildren(
    el("div", {}, `Questions asked: ${view.question_count} · question cost ${view.running_cost}${view.limit !== null ? ` of ${view.limit}` : ""} · ${view.questions_left} waiting`),
    el("div", { class: "legend" }, order.filter((s) => counts[s]).map((s) => el("span", { class: `state ${stateClass(s)}` }, `${counts[s]} ${s}`))),
    el("div", {}, `Read ${view.documents.length} documents: ${view.documents.join(", ")}`),
    view.skipped.length ? el("div", {}, `Not read: ${view.skipped.map((s) => `${s.name} (${s.reason})`).join("; ")}`) : "",
  );
}

function renderQuestion() {
  const pane = $("#question-pane");
  pane.replaceChildren();
  if (view.finished) {
    pane.append(
      el("h2", {}, "The brief is written"),
      el("p", { class: "muted" }, `Saved in ${view.run_dir}.`),
      el("div", { class: "downloads" },
        el("a", { class: "button", href: `/api/session/${view.id}/brief.md` }, "Download the brief"),
        el("a", { class: "button", href: `/api/session/${view.id}/gap-trace.jsonl` }, "Download the gap trace")),
      el("p", {}, el("a", { href: "/" , onclick: () => { location.hash = ""; } }, "Start another")),
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
      const classes = [it.id === currentId ? "current" : "", it.rejected ? "rejected" : ""].join(" ").trim() || null;
      list.append(el("li", { class: classes, id: `item-${it.id}` },
        el("span", { class: `state ${stateClass(it.state)}` }, it.rejected ? "rejected" : it.state),
        el("div", { class: "item-body" },
          el("div", {}, el("span", { class: "item-label" }, it.label), it.value && it.state !== "conflict" ? el("span", { class: "item-value" }, `: ${it.value}`) : null),
          el("div", { class: "item-meta" }, `${it.stated_or_inferred} · ${it.must_hold_or_nice} · ${it.way}${it.document ? " · " + it.document : ""}${it.who_can_supply ? " · who can supply it: " + it.who_can_supply : ""}${it.source === "person" ? " · settled by you" : ""}`),
          it.sources && it.sources.length ? el("div", { class: "item-meta clash-note" },
            "Documents disagree: " + it.sources.map((src) => `${src.value} (${src.document})`).join(" vs ")) : null,
          editing === it.id ? editBox(it) : null,
        ),
        editing === it.id ? null : itemControls(it),
        it.id === currentId ? el("span", { class: "now-tag" }, "this question") : null,
      ));
    }
    pane.append(list);
  }
}

function renderBrief() {
  const pane = $("#brief-pane");
  pane.hidden = !view.brief;
  $("#items-pane").hidden = Boolean(view.brief);
  if (!view.brief) return;
  const body = el("div", { class: "brief-view" });
  body.innerHTML = briefHtml(view.brief); // escaped in briefHtml
  pane.replaceChildren(body);
}

init().catch((e) => {
  $("#start-error").textContent = e.message;
  $("#start-error").hidden = false;
});
