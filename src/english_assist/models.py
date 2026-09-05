from dataclasses import dataclass


@dataclass(frozen=True)
class TranslationResult:
    source: str
    replacement: str
    learning_phrase: str
    model: str


@dataclass(frozen=True)
class PhraseRecord:
    timestamp: str
    source: str
    translation: str
    model: str
