from fastapi import APIRouter
from pydantic import BaseModel

from tools._shared.errors import make_error

router = APIRouter()


class Input(BaseModel):
    text: str
    mode: str = "basic"


def _collapse_blank_lines(lines: list[str]) -> list[str]:
    collapsed = []
    blank_run = 0
    for line in lines:
        if line == "":
            blank_run += 1
        else:
            blank_run = 0
        if blank_run <= 2:
            collapsed.append(line)
    return collapsed


@router.post("/tools/text_normalize")
def text_normalize(data: Input):
    text = data.text
    if len(text) == 0:
        return make_error("TEXT_EMPTY", "Text is empty.")
    if len(text) > 20000:
        return make_error("TEXT_TOO_LONG", "Text exceeds 20000 characters.")
    if data.mode not in {"basic", "strict"}:
        return make_error("MODE_INVALID", "Mode must be basic or strict.")

    changes = []
    original_length = len(text)

    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    if normalized != text:
        changes.append("normalized_newlines")

    lines = [line.rstrip(" ") for line in normalized.split("\n")]
    trimmed_lines_text = "\n".join(lines)
    if trimmed_lines_text != normalized:
        changes.append("trimmed_line_trailing_spaces")

    collapsed_lines = _collapse_blank_lines(trimmed_lines_text.split("\n"))
    collapsed_text = "\n".join(collapsed_lines)
    if collapsed_text != trimmed_lines_text:
        changes.append("collapsed_blank_lines")

    replaced_tabs = collapsed_text.replace("\t", "  ")
    if replaced_tabs != collapsed_text:
        changes.append("replaced_tabs")

    if data.mode == "strict":
        strict_text = replaced_tabs.strip()
        if strict_text != replaced_tabs:
            changes.append("trimmed_text")
        normalized_text = strict_text
    else:
        normalized_text = replaced_tabs

    return {
        "text": normalized_text,
        "meta": {
            "original_length": original_length,
            "normalized_length": len(normalized_text),
            "changes": changes,
        },
    }
