"""Pull slide text out of ProPresenter 7 `.pro` files.

A `.pro` file is a protobuf document, but every slide's text is carried inside
it as an RTF blob. Reading the RTF blobs directly avoids compiling the
ProPresenter schema, which Renewed Vision does not publish.
"""

import re

# Bumped whenever extraction changes, so a sync re-reads files it already stored.
PARSER_VERSION = 2

_RTF_START = b"{\\rtf"
_SKIPPED_GROUP = re.compile(
    r"\\(?:\*|fonttbl|colortbl|stylesheet|listtable|listoverridetable|info|pntext)"
)
_UNICODE_ESCAPE = re.compile(r"\\u(-?\d+)\s?\??")
_HEX_ESCAPE = re.compile(r"\\'([0-9a-fA-F]{2})")
_LINE_BREAK = re.compile(r"\\(?:par|line)(?![a-zA-Z])")
_CONTROL_WORD = re.compile(r"\\[a-zA-Z]+-?\d*\s?")


def _rtf_blocks(data: bytes) -> list[bytes]:
    blocks, i = [], 0
    while True:
        i = data.find(_RTF_START, i)
        if i < 0:
            return blocks
        depth, j = 0, i
        while j < len(data):
            char = data[j:j + 1]
            if char == b"\\":
                j += 2
                continue
            if char == b"{":
                depth += 1
            elif char == b"}":
                depth -= 1
                if depth == 0:
                    blocks.append(data[i:j + 1])
                    break
            j += 1
        i = j + 1


def _drop_groups(text: str) -> str:
    """Remove font, colour and list tables, and every other `{\\*...}` destination.

    These nest — `{\\*\\listtable{\\list{\\listlevel...}}}` — so they are matched
    by counting braces rather than with a regex.
    """
    out, i = [], 0
    while i < len(text):
        char = text[i]
        if char == "\\" and i + 1 < len(text):
            out.append(text[i:i + 2])
            i += 2
            continue
        if char == "{" and _SKIPPED_GROUP.match(text, i + 1):
            depth, j = 0, i
            while j < len(text):
                if text[j] == "\\":
                    j += 2
                    continue
                if text[j] == "{":
                    depth += 1
                elif text[j] == "}":
                    depth -= 1
                    if depth == 0:
                        break
                j += 1
            i = j + 1
            continue
        out.append(char)
        i += 1
    return "".join(out)


def _rtf_to_text(rtf: bytes) -> str:
    text = rtf.decode("latin-1")
    text = _drop_groups(text)
    text = _UNICODE_ESCAPE.sub(lambda m: chr(int(m.group(1)) % 65536), text)
    text = _LINE_BREAK.sub("\n", text)
    text = _HEX_ESCAPE.sub(
        lambda m: bytes.fromhex(m.group(1)).decode("cp1252", "ignore"), text
    )
    text = _CONTROL_WORD.sub("", text)
    text = text.replace("{", "").replace("}", "")
    return "\n".join(line.strip() for line in text.splitlines() if line.strip())


def lyrics_from_pro(data: bytes) -> str:
    """Slide text from a `.pro` file, one blank line between slides.

    Returns "" for a file with no text, such as an empty template.
    """
    seen, slides = set(), []
    for block in _rtf_blocks(data):
        text = _rtf_to_text(block)
        if text and text not in seen:
            seen.add(text)
            slides.append(text)
    return "\n\n".join(slides)
