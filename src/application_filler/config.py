from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field

MODEL_ID = "claude-haiku-5-5"  # Canonical immutable snapshot, per Anthropic's versioning policy.


class ConfigurationError(ValueError):
    """User-facing configuration error that never includes candidate values or file contents."""


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class Answers(StrictModel):
    mode: Literal["trusted", "review"] = "trusted"
    protected_category: Literal["negative_or_skip", "ask", "skip"] = "negative_or_skip"
    cookies: Literal["accept_when_needed", "ask"] = "ask"
    topics: dict[
        Literal["work_authorization", "salary", "personal_disclosure", "consent"],
        Literal["infer", "ask", "skip"],
    ] = Field(
        default_factory=lambda: {
            "work_authorization": "infer",
            "salary": "infer",
            "personal_disclosure": "ask",
            "consent": "ask",
        }
    )


class Salary(StrictModel):
    strategy: Literal["low", "market"] = "market"
    minimum: str | None = None
    instructions: str = (
        "Use current comparable gross base pay. Ask if units or evidence are unclear."
    )


class Documents(StrictModel):
    cv: str = "cv.pdf"
    cover_letter: Literal["trusted", "review", "skip"] = "trusted"
    retention: Literal["keep", "delete_after_run"] = "keep"
    background: str = ""
    examples: list[str] = Field(
        default_factory=list,
        description="Private .md/.txt filenames or multiline letter text (YAML block scalar |).",
    )
    instructions: str = "Write a specific, concise cover letter using only my supplied facts."


class Navigation(StrictModel):
    handoffs: Literal["trusted", "ask"] = "trusted"
    allowed_hosts: list[str] = Field(default_factory=list)


class Model(StrictModel):
    id: Literal["claude-haiku-5-5"] = MODEL_ID
    effort: Literal["low", "medium", "high"] = "medium"
    max_output_tokens: int = Field(default=8192, ge=1024, le=12000)
    max_request_chars: int = Field(default=240000, ge=10000, le=350000)
    max_calls_per_application: int = Field(default=40, ge=1, le=100)
    max_calls_per_run: int = Field(default=100, ge=1, le=200)
    estimated_budget_usd: float = Field(default=0.50, gt=0, le=5)
    web_searches_per_application: int = Field(default=6, ge=0, le=20)


class Browser(StrictModel):
    delay_ms: int = Field(default=400, ge=100, le=5000)
    max_actions: int = Field(default=100, ge=1, le=300)
    snapshot_chars: int = Field(default=18000, ge=2000, le=40000)


class Settings(StrictModel):
    version: Literal[2] = 2
    candidate: dict[str, Any] = Field(default_factory=dict)
    instructions: str = (
        "Complete job applications truthfully. Ask when information is insufficient."
    )
    answers: Answers = Field(default_factory=Answers)
    salary: Salary = Field(default_factory=Salary)
    documents: Documents = Field(default_factory=Documents)
    navigation: Navigation = Field(default_factory=Navigation)
    submission: Literal["manual", "auto"] = "manual"
    model: Model = Field(default_factory=Model)
    browser: Browser = Field(default_factory=Browser)


def load_yaml(path: Path):
    if path.stat().st_size > 256000:
        raise ValueError("Instructions exceed 256 KB")

    class UniqueKeys(yaml.SafeLoader):
        def construct_mapping(self, node, deep=False):
            keys = set()
            for key_node, _ in node.value:
                key = self.construct_object(key_node, deep=deep)
                if not isinstance(key, str) or key in keys:
                    raise yaml.constructor.ConstructorError(
                        None, None, "Duplicate or invalid key", key_node.start_mark
                    )
                keys.add(key)
            return super().construct_mapping(node, deep=deep)

    try:
        return yaml.load(path.read_text(encoding="utf-8-sig"), Loader=UniqueKeys)
    except yaml.YAMLError:
        raise ValueError("Invalid YAML. Check indentation, quotes and duplicate keys.") from None


def load_settings(path: Path) -> Settings:
    data = load_yaml(path)
    if isinstance(data, dict) and data.get("version") == 1:
        raise ValueError(
            "Version 1 is retired. Copy the current example to a new file and "
            "transfer your facts/preferences before using it."
        )
    return Settings.model_validate(data)


def private_file(root: Path, relative: str) -> Path:
    path = (root / relative).resolve()
    if not path.is_relative_to(root.resolve()) or not path.is_file():
        raise ValueError("File must exist inside the private directory")
    if path.stat().st_size > 10000000:
        raise ValueError("File exceeds 10 MB")
    return path


def load_cover_letter_examples(root: Path, documents: Documents) -> list[str]:
    examples = []
    for index, entry in enumerate(documents.examples):
        field = f"documents.examples[{index}]"
        try:
            if "\n" in entry or "\r" in entry:
                text = entry
            else:
                path = private_file(root, entry)
                if path.suffix.lower() not in {".md", ".txt"} or path.stat().st_size > 20000:
                    raise ValueError
                text = path.read_text(encoding="utf-8-sig")
            if not text.strip() or len(text.encode("utf-8")) > 20000:
                raise ValueError
        except (OSError, ValueError, UnicodeError):
            # OSError can echo the entire supplied letter as a supposed filename.
            raise ConfigurationError(
                f"{field}: use an existing UTF-8 .md/.txt file inside private/ "
                "or paste multiline text using a YAML '- |' entry. "
                "Each example must contain nonblank text and be at most 20 KB."
            ) from None
        examples.append(text)
    return examples
