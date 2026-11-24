"""Model access behind one small interface, with two implementations.

- AnthropicModel calls the Anthropic API. The key is read only from the
  ANTHROPIC_API_KEY environment variable. The model name is one config value.
- SimulatedModel is a scripted stand-in. It returns fixed, plausible items and
  estimates from a JSON file, so the tool and its tests run with no key. Every
  run made with it is labelled "simulated".

The model does two things only: it lists items under the headings with their
sources, and for each item it estimates the chance a guess is wrong and answers
the two yes-or-no checks. It never chooses what to do; the ask table does.
"""

from __future__ import annotations

import json
import os
from abc import ABC, abstractmethod
from pathlib import Path

from . import ALL_HEADINGS
from .documents import Folder

DEFAULT_MODEL_NAME = os.environ.get("ELICITAGENT_MODEL", "claude-sonnet-5-5")


class ModelError(RuntimeError):
    pass


class Model(ABC):
    name: str  # what the gap trace records in its "model" field
    kind: str  # "real" or "simulated"

    @abstractmethod
    def list_items(self, request: str, folder: Folder) -> list[dict]:
        """Items under the eight headings and "other", with stated or inferred, must hold or nice, and sources."""

    @abstractmethod
    def estimate(self, request: str, folder: Folder, items: list[dict]) -> dict[str, dict]:
        """Per item id: chance_wrong (0 to 1), can_undo, would_notice, model_would_ask."""


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

    def list_items(self, request: str, folder: Folder) -> list[dict]:
        out = []
        for raw in self.script["items"]:
            item = {k: v for k, v in raw.items() if k != "estimate"}
            out.append(item)
        return out

    def estimate(self, request: str, folder: Folder, items: list[dict]) -> dict[str, dict]:
        by_id = {raw["id"]: raw.get("estimate", {}) for raw in self.script["items"]}
        return {item["id"]: by_id.get(item["id"], {}) for item in items}


# ---------------------------------------------------------------- Anthropic API

LIST_SYSTEM = """You help a person hand a task to an AI agent. You read the person's request and the folder of materials they handed over, and you list every item the agent would need to know to do the task well.

Put each item under exactly one of these headings: {headings}. Use "Other" only when no heading fits.

For each item give:
- id: a short unique id such as "i01".
- heading: one of the headings above, spelled exactly.
- key: a short lower-case slug naming what the item is about, such as "hall-empty-time". If two documents talk about the same thing, give both items the same key and the same heading, even when their values differ.
- label: what the agent needs to know, as a short neutral noun phrase of at most ten words. Do not put the value or your reasoning in the label.
- value: the best current value, or null if nothing suggests one.
- candidates: the distinct values that are plausible (empty if none). Include the value itself.
- stated: true only when a document states the value directly; false when you inferred it or it is missing.
- must_hold: true for a hard fact or rule the agent must respect; false for a preference that is nice if possible.
- document: the file name the value came from, exactly as given, or null.
- passage: the exact text copied character for character from that document that supports the value, or null. Never paraphrase a passage. If two documents disagree, list one item per document, each with its own document's value and passage.
- about_named_person: true when the item is a personal fact about a named person (their availability, age, health, relationships, and the like).

List items that are missing from the folder too, with value null and stated false: the gaps are the point. Do not decide whether to ask; only list."""

ESTIMATE_SYSTEM = """You help decide how sure an AI agent can be about each item it needs before doing a task. For each item, answer only these:
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

    def _call(self, system: str, user: str, schema: dict) -> dict:
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
                message = stream.get_final_message()
        except anthropic.APIStatusError as exc:
            # status and the API's own message only: never headers or the request
            raise ModelError(f"The API refused the call ({exc.status_code}): {exc.message}") from None
        except anthropic.APIConnectionError:
            raise ModelError("Could not reach the API.") from None
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

    def list_items(self, request: str, folder: Folder) -> list[dict]:
        system = LIST_SYSTEM.format(headings=", ".join(f'"{h}"' for h in ALL_HEADINGS))
        user = f"The person's request:\n<request>\n{request}\n</request>\n\nThe folder:\n{_folder_as_text(folder)}"
        return self._call(system, user, LIST_SCHEMA)["items"]

    def estimate(self, request: str, folder: Folder, items: list[dict]) -> dict[str, dict]:
        slim = [
            {k: item.get(k) for k in ("id", "heading", "label", "value", "candidates", "stated", "document", "passage", "about_named_person")}
            for item in items
        ]
        user = (
            f"The person's request:\n<request>\n{request}\n</request>\n\nThe folder:\n{_folder_as_text(folder)}\n\n"
            f"The items:\n{json.dumps(slim, indent=1)}"
        )
        data = self._call(ESTIMATE_SYSTEM, user, ESTIMATE_SCHEMA)
        return {e["id"]: e for e in data["estimates"]}


def make_model(choice: str, folder_path: str | Path, model_name: str | None = None) -> Model:
    """choice: "simulated", "anthropic" or "auto" (the API when a key is set, else simulated)."""
    if choice == "auto":
        choice = "anthropic" if os.environ.get("ANTHROPIC_API_KEY") else "simulated"
    if choice == "simulated":
        return SimulatedModel.for_folder(folder_path)
    if choice == "anthropic":
        return AnthropicModel(model_name)
    raise ModelError(f"Unknown model choice: {choice}")
