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

function stateClass(state) {
  return state === "not available here" ? "unavailable" : state;
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
  if (!documentName || !passage) return null;
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
    container.replaceChildren(el("p", { class: "error" }, e.message));
    return;
  }
  const d = data.decided;
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
  container.replaceChildren(
    el("p", { class: "why-title" }, "Why this question (read-only, from the gap trace)"),
    el("dl", { class: "why-list" }, rows.flatMap(([k, v]) => [el("dt", {}, k), el("dd", {}, v)])),
    working ? el("p", { class: "why-working" }, working) : null,
    el("p", { class: "why-reason" }, d.reason),
    el("p", { class: "muted small-note" }, `Order of value: (chance wrong x harm) / cost = ${num(d.chance_wrong * d.harm / d.question_cost)}. Higher comes first.`),
  );
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
  const unavailable = live.filter((i) => i.state === "not available here");
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
    section("Not available here", "You could not answer these, and the folder does not hold them. Say who could, if you know.", unavailable, (it) => {
      const box = el("input", { type: "text", value: it.who_could || "", placeholder: "Who could?", "aria-label": `Who could answer: ${it.label}` });
      box.addEventListener("change", () => control(it.id, "who could", box.value));
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
  const order = ["confirmed", "assumed", "open", "conflict", "not available here"];
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
        el("span", { class: "clash-source" }, `from ${src.document}`)));
    }
  } else if (q.kind === "choose") {
    for (const c of q.candidates) replies.append(el("button", { onclick: () => reply("answer", c) }, c));
  }
  replies.append(answerBox, el("button", { onclick: () => reply("answer", answerBox.value) }, q.kind === "open" ? "Answer" : "Something else"));
  replies.append(el("button", { class: "quiet", title: "The item stays open. The question still counts.", onclick: () => reply("skip") }, "Skip"));
  const whoBox = el("input", { type: "text", placeholder: "Who could? (optional)", "aria-label": "Who could answer this? (optional)" });
  pane.append(...[
    el("p", { class: "cost" }, `Question ${view.question_count + 1} · ${q.kind} question · costs ${q.cost}`),
    el("p", { class: "question-text" }, q.text),
    el("p", { class: "reason" }, q.reason),
    el("button", { class: "why-toggle", "aria-expanded": whyOpen ? "true" : "false", onclick: () => { whyOpen = !whyOpen; render(); } },
      whyOpen ? "Hide why" : "Why this question?"),
    whyOpen ? (() => { const box = el("div", { class: "why" }, el("p", { class: "muted" }, "Loading...")); renderWhy(box, q.item); return box; })() : null,
    item ? sourceView(`q-${item.id}`, item.document, item.passage, item.context) : null,
    clash,
    clash && item ? el("div", { class: "clash-sources" }, item.sources.map((src, i) => sourceView(`q-${item.id}-${i}`, src.document, src.passage, src.context))) : null,
    replies,
    el("div", { class: "cant-answer" },
      el("button", { title: "Asking you again will not help. The tool stops asking and records who to go to.", onclick: () => reply("I can't answer this", null, whoBox.value) }, "I can't answer this"),
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
          el("div", { class: "item-meta" }, `${it.stated_or_inferred} · ${it.must_hold_or_nice} · ${it.way}${it.document ? " · " + it.document : ""}${it.who_could ? " · who could: " + it.who_could : ""}${it.source === "person" ? " · settled by you" : ""}`),
          it.sources && it.sources.length ? el("div", { class: "item-meta clash-note" },
            "Documents disagree: " + it.sources.map((src) => `${src.value} (${src.document})`).join(" vs ")) : null,
          it.passage ? sourceView(`i-${it.id}`, it.document, it.passage, it.context, true) : null,
          ...(it.sources || []).map((src, n) => sourceView(`i-${it.id}-${n}`, src.document, src.passage, src.context, true)),
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
