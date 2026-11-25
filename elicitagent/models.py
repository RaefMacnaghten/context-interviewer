"""Model access behind one small interface, with two implementations.

- AnthropicModel calls the Anthropic API. The key is read only from the
  ANTHROPIC_API_KEY environment variable. The model name is one config value.
- SimulatedModel is a scripted stand-in. It returns fixed, plausible items and
  estimates from a JSON file, so the tool and its tests run with no key. Every
  run made with it is labelled "simulated".

Every call receives the person's intent (what they want the agent to do, in
their own words) as the task, or a note that they gave none.

The model does three things only: it lists items under the headings with their
sources, including the folder's own statement of the goal and whether it agrees
with the intent (the first look), looks again in the folder for each item the first
look did not find (one targeted second look), and, for each item still missing
(a gap), estimates the chance a guess is wrong and answers the two yes-or-no
checks. It never chooses what to do; the ask table does.
"""

from __future__ import annotations

import json
import os
import re
from abc import ABC, abstractmethod
from pathlib import Path

from . import ALL_HEADINGS
from .documents import Folder

DEFAULT_MODEL_NAME = os.environ.get("ELICITAGENT_MODEL", "claude-sonnet-5-5")


class ModelError(RuntimeError):
    pass


def scrub(text: str) -> str:
    """Error text shown to the person: never a key, and never a request header."""
    text = str(text)
    for name in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN"):
        secret = os.environ.get(name, "").strip()
        if len(secret) >= 8:
            text = text.replace(secret, "[hidden]")
    text = re.sub(r"sk-[A-Za-z0-9_\-]{6,}", "[hidden]", text)
    return re.sub(r"(?i)([\"']?(?:x-api-key|authorization)[\"']?)\s*[:=]\s*[^\n,;}]+", r"\1: [hidden]", text)


def complete_objects(buf: str, key: str) -> list[dict]:
    """The objects already complete in the JSON array under `key` in a reply that is still arriving.

    The model's reply streams in as text. Each finished object in the array is real progress (an item listed,
    an item looked for again, a gap estimated); an unfinished one is not counted.
    """
    m = re.search(r'"%s"\s*:\s*\[' % re.escape(key), buf)
    if not m:
        return []
    out, depth, start, in_str, esc = [], 0, None, False, False
    for j in range(m.end(), len(buf)):
        c = buf[j]
        if in_str:
            if esc:
                esc = False
            elif c == "\\":
                esc = True
            elif c == '"':
                in_str = False
            continue
        if c == '"':
            in_str = True
        elif c == "{":
            if depth == 0:
                start = j
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0 and start is not None:
                try:
                    out.append(json.loads(buf[start:j + 1]))
                except json.JSONDecodeError:
                    pass
                start = None
        elif c == "]" and depth == 0:
            break
    return out


class Model(ABC):
    name: str  # what the gap trace records in its "model" field
    kind: str  # "real" or "simulated"

    @abstractmethod
    def list_items(self, intent: str, folder: Folder, on_partial=None) -> list[dict]:
        """Items under the eight headings and "other", with stated or inferred, must hold or nice, and sources.

        One of them is the goal (heading "Goal and deliverable", key "goal"), with agrees_with_intent: True or
        False when the person gave an intent, None when they did not. on_partial(items so far) is called as the
        reply arrives, so the page can show items as they come.
        """

    @abstractmethod
    def second_look(self, intent: str, folder: Folder, items: list[dict], on_partial=None) -> dict[str, dict | None]:
        """One targeted second look in the folder for each item the first look did not find.

        Per item id: {"value", "document", "passage"} when the folder states it, else None. on_partial(number of
        items answered so far) is called as the reply arrives.
        """

    @abstractmethod
    def estimate(self, intent: str, folder: Folder, items: list[dict], on_partial=None) -> dict[str, dict]:
        """Per item id: chance_wrong (0 to 1), can_undo, would_notice, model_would_ask. on_partial(number of gaps
        estimated so far) is called as the reply arrives."""

    def word_questions(self, intent: str, folder: Folder, items: list[dict]) -> dict[str, dict]:
        """Per item id: {"question": one plain sentence asking for exactly what is needed, "answer_form": what kind of
        answer is wanted}. Wording only: it is asked after every decision is made and changes none of them. Missing
        entries are worded from a plain template, so an empty reply is always safe."""
        return {}


# ---------------------------------------------------------------- simulated


class SimulatedModel(Model):
    kind = "simulated"

    def __init__(self, script_path: str | Path):
        self.script_path = Path(script_path)
        if not self.script_path.is_file():
            raise ModelError(
                f"No simulated responses for this folder: expected {self.script_path.name} next to the materials folder."
            )
        with open(self.script_path, encoding="utf-8") as fh:
            self.script = json.load(fh)
        self.name = "simulated"

    @classmethod
    def for_folder(cls, folder_path: str | Path) -> "SimulatedModel":
        """Convention: the script lives next to the materials folder, as simulated-model.json."""
        return cls(Path(folder_path).resolve().parent / "simulated-model.json")

    def list_items(self, intent: str, folder: Folder, on_partial=None) -> list[dict]:
        # The stand-in cannot judge meaning. Its goal item lists the intents it was written for
        # ("goal_agrees_with"); it counts those as agreeing with the folder's goal and any other as differing.
        out = []
        for raw in self.script["items"]:
            item = {k: v for k, v in raw.items() if k not in ("estimate", "goal_agrees_with")}
            agrees = None
            if "goal_agrees_with" in raw and intent.strip():
                agrees = _plain(intent) in {_plain(x) for x in raw["goal_agrees_with"]}
            item["agrees_with_intent"] = agrees
            out.append(item)
        if on_partial:
            on_partial(out)
        return out

    def second_look(self, intent: str, folder: Folder, items: list[dict], on_partial=None) -> dict[str, dict | None]:
        found = self.script.get("second_look", {})
        if on_partial:
            on_partial(len(items))
        return {item["id"]: found.get(item["id"]) for item in items}

    def word_questions(self, intent: str, folder: Folder, items: list[dict]) -> dict[str, dict]:
        # a script may word its questions; one that does not is worded from the plain template
        wording = self.script.get("wording", {})
        return {item["id"]: wording[item["id"]] for item in items if item["id"] in wording}

    def estimate(self, intent: str, folder: Folder, items: list[dict], on_partial=None) -> dict[str, dict]:
        by_id = {raw["id"]: raw.get("estimate", {}) for raw in self.script["items"]}
        if on_partial:
            on_partial(len(items))
        return {item["id"]: by_id.get(item["id"], {}) for item in items}


# ---------------------------------------------------------------- Anthropic API

LIST_SYSTEM = """You help a person hand a task to an AI agent. You read what the person wants the agent to do (their intent, if they gave one) and the folder of materials they handed over, and you list every item the agent would need to know to do the task well.

Put each item under exactly one of these headings: {headings}. Use "Other" only when no heading fits.

For each item give:
- id: a short unique id such as "i01".
- heading: one of the headings above, spelled exactly.
- key: a short lower-case slug naming what the item is about, such as "hall-empty-time". If two documents talk about the same thing, give both items the same key and the same heading, even when their values differ.
- label: what the agent needs to know, as a short neutral noun phrase of at most ten words. Do not put the value or your reasoning in the label.
- value: the best current value, or null if nothing suggests one.
- candidates: the distinct values that are plausible (empty if none). Include the value itself.
- stated: true only when a document states the value directly; false when you inferred it or it is missing. A line that only defers to the person, such as "ask me" or "tbc", is not a stated value: give value null and stated false, with that document and passage.
- must_hold: true for a hard fact or rule the agent must respect; false for a preference that is nice if possible.
- document: the file name the value came from, exactly as given, or null.
- passage: the exact text copied character for character from that document that supports the value, or null. Never paraphrase a passage. If two documents disagree, list one item per document, each with its own document's value and passage.
- about_named_person: true when the item is a personal fact about a named person (their availability, age, health, relationships, and the like).
- agrees_with_intent: null for every item except the goal (below).

Always list the overall goal of the task under "Goal and deliverable" with key "goal" and label "What the agent should do". Its value is the goal as a document in the folder states it (stated true, with that document and passage); if more than one document states a goal, list one goal item per document, each with key "goal". When no document states it, list one goal item with your best reading of the goal from the folder (stated false). If the person gave an intent, set each goal item's agrees_with_intent to true when that goal asks the agent for the same thing as the intent, and to false when it asks for something different that would change what the agent does. If the person gave no intent, set it to null.

List items that are missing from the folder too, with value null and stated false: the gaps are the point. Do not decide whether to ask; only list."""

SECOND_LOOK_SYSTEM = """You help a person hand a task to an AI agent. An earlier reading of their folder did not find a stated value for the items below. For each item, look again through the folder specifically for that item, including tables, CSV rows, notes and email text.

For each item return:
- id: the item's id.
- found: true only if a document in the folder states the value directly. Inferring or guessing does not count, and nor does a line that only defers to the person, such as "ask me" or "tbc".
- value: the value as the document states it, or null.
- document: the file name exactly as given, or null.
- passage: the exact text copied character for character from that document that states the value, or null. Never paraphrase a passage."""

SECOND_LOOK_SCHEMA = {
    "type": "object",
    "properties": {
        "results": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "found": {"type": "boolean"},
                    "value": {"type": ["string", "null"]},
                    "document": {"type": ["string", "null"]},
                    "passage": {"type": ["string", "null"]},
                },
                "required": ["id", "found", "value", "document", "passage"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["results"],
    "additionalProperties": False,
}

ESTIMATE_SYSTEM = """You help decide how sure an AI agent can be about each item it needs before doing a task. The folder has already been read twice and does not state these items. For each item, answer only these:
- chance_wrong: your estimate, from 0 to 1, of the chance that the agent's best guess for this item would be wrong if nobody asked the person.
- can_undo: if the agent acted on a wrong value for this item, could the mistake be undone afterwards? true or false.
- would_notice: if the agent acted on a wrong value, would the person notice the mistake? true or false.
- model_would_ask: if it were up to you alone, would you ask the person about this item? true or false.
Return one entry per item id. Be calibrated: a value stated plainly in a document is rarely wrong; a missing personal fact is very likely wrong if guessed."""

LIST_SCHEMA = {
    "type": "object",
    "properties": {
        "items": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "heading": {"type": "string", "enum": ALL_HEADINGS},
                    "key": {"type": "string"},
                    "label": {"type": "string"},
                    "value": {"type": ["string", "null"]},
                    "candidates": {"type": "array", "items": {"type": "string"}},
                    "stated": {"type": "boolean"},
                    "must_hold": {"type": "boolean"},
                    "document": {"type": ["string", "null"]},
                    "passage": {"type": ["string", "null"]},
                    "about_named_person": {"type": "boolean"},
                    "agrees_with_intent": {"type": ["boolean", "null"]},
                },
                "required": [
                    "id",
                    "heading",
                    "key",
                    "label",
                    "value",
                    "candidates",
                    "stated",
                    "must_hold",
                    "document",
                    "passage",
                    "about_named_person",
                    "agrees_with_intent",
                ],
                "additionalProperties": False,
            },
        }
    },
    "required": ["items"],
    "additionalProperties": False,
}

ESTIMATE_SCHEMA = {
    "type": "object",
    "properties": {
        "estimates": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "chance_wrong": {"type": "number"},
                    "can_undo": {"type": "boolean"},
                    "would_notice": {"type": "boolean"},
                    "model_would_ask": {"type": "boolean"},
                },
                "required": ["id", "chance_wrong", "can_undo", "would_notice", "model_would_ask"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["estimates"],
    "additionalProperties": False,
}


WORDING_SYSTEM = """You write the questions a person is asked about a task they are handing to an AI agent. Everything has already been decided: these items will be asked. Your only job is the wording.

For each item write:
- question: one full, plain sentence ending with a question mark that says exactly what is needed, naming the person, thing or date it is about. Ask about the real-world fact, not about a label: "When can Kit Inventa work on the day?", not "Kit Inventa's availability?". For a confirm item, ask whether the given value is right ("Is the hall free from 11:00?"). For a choose item, ask which of the given values is right, without listing them. For an open item, ask for the value.
- answer_form: one short sentence saying what form of answer is wanted, such as "Give times, or \"all day\"." or "Give a number of pints a day." or "Answer yes or no."

Do not say why the question is asked: that is added separately from the files. Do not add facts that are not in the item or the folder. Use plain words and the names as they appear. Return one entry per item id."""

WORDING_SCHEMA = {
    "type": "object",
    "properties": {
        "questions": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"id": {"type": "string"}, "question": {"type": "string"}, "answer_form": {"type": "string"}},
                "required": ["id", "question", "answer_form"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["questions"],
    "additionalProperties": False,
}


def _plain(text: str) -> str:
    return " ".join("".join(c.lower() if c.isalnum() else " " for c in text).split())


def _intent_block(intent: str) -> str:
    if intent.strip():
        return f"What the person wants the agent to do, in their own words:\n<intent>\n{intent.strip()}\n</intent>"
    return "The person did not say what they want the agent to do. Work out the goal from the folder."


def _folder_as_text(folder: Folder) -> str:
    parts = []
    for doc in folder.documents:
        parts.append(f'<document name="{doc.name}">\n{doc.text}\n</document>')
    return "\n\n".join(parts)


class AnthropicModel(Model):
    kind = "real"

    def __init__(self, model_name: str | None = None, client=None):
        self.name = model_name or DEFAULT_MODEL_NAME
        if client is None:
            if not os.environ.get("ANTHROPIC_API_KEY"):
                raise ModelError("ANTHROPIC_API_KEY is not set. Set it, or run with the simulated model.")
            import anthropic

            client = anthropic.Anthropic()
        self.client = client

    def _call(self, system: str, user: str, schema: dict, on_text=None) -> dict:
        kwargs = dict(
            model=self.name,
            max_tokens=64000,
            system=system,
            messages=[{"role": "user", "content": user}],
            output_config={"format": {"type": "json_schema", "schema": schema}},
        )
        if self.name == "claude-sonnet-5-5":
            # Server-side fallback on a policy decline, routed by category.
            kwargs.update(betas=["server-side-fallback-2026-07-01"], fallbacks="default")
            stream_ctx = self.client.beta.messages.stream(**kwargs)
        else:
            stream_ctx = self.client.messages.stream(**kwargs)
        import anthropic

        try:
            with stream_ctx as stream:
                if on_text is not None:
                    buf = ""
                    for text in stream.text_stream:
                        buf += text
                        if "}" in text:
                            on_text(buf)
                message = stream.get_final_message()
        except anthropic.APIStatusError as exc:
            # status and the API's own message only: never headers or the request
            raise ModelError(scrub(f"The model service refused the call (status {exc.status_code}): {exc.message}")) from None
        except anthropic.APIConnectionError:
            raise ModelError("Could not reach the model service. Check the connection and try again.") from None
        if message.stop_reason == "refusal":
            raise ModelError("The model declined this request.")
        if message.stop_reason == "max_tokens":
            raise ModelError("The model ran out of output space before finishing.")
        text = next((b.text for b in message.content if b.type == "text"), None)
        if text is None:
            raise ModelError("The model returned no text.")
        try:
            return json.loads(text)
        except json.JSONDecodeError as exc:
            raise ModelError(f"The model returned invalid JSON: {exc}") from exc

    def list_items(self, intent: str, folder: Folder, on_partial=None) -> list[dict]:
        system = LIST_SYSTEM.format(headings=", ".join(f'"{h}"' for h in ALL_HEADINGS))
        user = f"{_intent_block(intent)}\n\nThe folder:\n{_folder_as_text(folder)}"
        on_text = (lambda buf: on_partial(complete_objects(buf, "items"))) if on_partial else None
        return self._call(system, user, LIST_SCHEMA, on_text)["items"]

    def second_look(self, intent: str, folder: Folder, items: list[dict], on_partial=None) -> dict[str, dict | None]:
        if not items:
            return {}
        slim = [{k: item.get(k) for k in ("id", "heading", "label")} for item in items]
        user = (
            f"{_intent_block(intent)}\n\nThe folder:\n{_folder_as_text(folder)}\n\n"
            f"Look again for each of these items:\n{json.dumps(slim, indent=1)}"
        )
        on_text = (lambda buf: on_partial(len(complete_objects(buf, "results")))) if on_partial else None
        data = self._call(SECOND_LOOK_SYSTEM, user, SECOND_LOOK_SCHEMA, on_text)
        out: dict[str, dict | None] = {item["id"]: None for item in items}
        for r in data["results"]:
            if r.get("id") in out and r.get("found") and r.get("value") and r.get("document") and r.get("passage"):
                out[r["id"]] = {"value": r["value"], "document": r["document"], "passage": r["passage"]}
        return out

    def estimate(self, intent: str, folder: Folder, items: list[dict], on_partial=None) -> dict[str, dict]:
        slim = [
            {k: item.get(k) for k in ("id", "heading", "label", "value", "candidates", "stated", "document", "passage", "about_named_person")}
            for item in items
        ]
        user = (
            f"{_intent_block(intent)}\n\nThe folder:\n{_folder_as_text(folder)}\n\n"
            f"The items:\n{json.dumps(slim, indent=1)}"
        )
        on_text = (lambda buf: on_partial(len(complete_objects(buf, "estimates")))) if on_partial else None
        data = self._call(ESTIMATE_SYSTEM, user, ESTIMATE_SCHEMA, on_text)
        return {e["id"]: e for e in data["estimates"]}

    def word_questions(self, intent: str, folder: Folder, items: list[dict]) -> dict[str, dict]:
        if not items:
            return {}
        user = (f"{_intent_block(intent)}\n\nThe folder:\n{_folder_as_text(folder)}\n\n"
                f"The questions to word:\n{json.dumps(items, indent=1)}")
        data = self._call(WORDING_SYSTEM, user, WORDING_SCHEMA)
        wanted = {item["id"] for item in items}
        return {q["id"]: {"question": q["question"].strip(), "answer_form": q["answer_form"].strip()}
                for q in data["questions"] if q.get("id") in wanted and q.get("question", "").strip()}


def make_model(choice: str, folder_path: str | Path, model_name: str | None = None) -> Model:
    """choice: "simulated", "anthropic" or "auto" (the API when a key is set, else simulated)."""
    if choice == "auto":
        choice = "anthropic" if os.environ.get("ANTHROPIC_API_KEY") else "simulated"
    if choice == "simulated":
        return SimulatedModel.for_folder(folder_path)
    if choice == "anthropic":
        return AnthropicModel(model_name)
    raise ModelError(f"Unknown model choice: {choice}")
