"""Languages HAQ supports.

UI_LANGUAGES: languages the app screens and complaint-letter headings are available in.
A claim may also use "other": the worker writes or speaks in any language at all, their
words are kept exactly as given, and the letter headings fall back to English.
"""
from typing import Literal

LANGUAGE_NAMES = {
    "en": "English", "hi": "Hindi", "bn": "Bengali", "te": "Telugu", "mr": "Marathi",
    "ta": "Tamil", "ur": "Urdu", "gu": "Gujarati", "kn": "Kannada", "ml": "Malayalam",
    "or": "Odia", "pa": "Punjabi", "as": "Assamese",
}
UI_LANGUAGES = tuple(LANGUAGE_NAMES)
CLAIM_LANGUAGES = UI_LANGUAGES + ("other",)

UiLang = Literal[UI_LANGUAGES]  # type: ignore[valid-type]
ClaimLang = Literal[CLAIM_LANGUAGES]  # type: ignore[valid-type]
