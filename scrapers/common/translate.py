"""Japanese title translation, per PRD 4.2.

DeepL free API first (DEEPL_API_KEY secret), deep-translator's Google backend
as unofficial fallback. Never raises: any failure returns None and the caller
shows the original text. Translation must never fail the run.
"""

from __future__ import annotations

import os
import re

import httpx

DEEPL_URL = "https://api-free.deepl.com/v2/translate"

_CJK = re.compile(r"[぀-ヿ㐀-鿿]")  # kana + common kanji


def needs_translation(text: str | None) -> bool:
    return bool(text and _CJK.search(text))


def _deepl(text: str, api_key: str) -> str | None:
    resp = httpx.post(
        DEEPL_URL,
        headers={"Authorization": f"DeepL-Auth-Key {api_key}"},
        data={"text": text, "target_lang": "EN-GB", "source_lang": "JA"},
        timeout=15,
    )
    if resp.status_code != 200:
        return None
    translations = resp.json().get("translations", [])
    return translations[0]["text"] if translations else None


def _fallback(text: str) -> str | None:
    try:
        from deep_translator import GoogleTranslator
        return GoogleTranslator(source="ja", target="en").translate(text)
    except Exception:
        return None


def translate(text: str | None) -> str | None:
    """Best-effort Japanese-to-English. None means 'show the original'."""
    if not needs_translation(text):
        return None
    api_key = os.environ.get("DEEPL_API_KEY", "")
    if api_key:
        try:
            result = _deepl(text, api_key)
            if result:
                return result
        except Exception:
            pass
    return _fallback(text)
