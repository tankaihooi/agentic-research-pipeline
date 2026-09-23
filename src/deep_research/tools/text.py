"""Text utilities: token counting, chunking, quote grounding, and citation handling.

All deterministic. The Critic's first check (`quote_grounding_score`) needs no LLM at all.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from functools import lru_cache

import tiktoken
from rapidfuzz import fuzz

# ---------------------------------------------------------------------------- tokens


@lru_cache(maxsize=1)
def _encoder() -> tiktoken.Encoding:
    return tiktoken.get_encoding("o200k_base")


def count_tokens(text: str) -> int:
    return len(_encoder().encode(text, disallowed_special=()))


def truncate_tokens(text: str, max_tokens: int) -> str:
    tokens = _encoder().encode(text, disallowed_special=())
    return text if len(tokens) <= max_tokens else _encoder().decode(tokens[:max_tokens])


# ---------------------------------------------------------------------------- chunking


@dataclass(frozen=True)
class Chunk:
    index: int
    text: str
    token_count: int


_PARAGRAPH_SPLIT = re.compile(r"\n\s*\n")
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9\"'(\[])")


def _pieces(text: str, max_tokens: int) -> list[str]:
    """Split into paragraph-sized pieces, breaking oversize paragraphs by sentence then tokens."""
    pieces: list[str] = []
    for para in _PARAGRAPH_SPLIT.split(text):
        para = para.strip()
        if not para:
            continue
        if count_tokens(para) <= max_tokens:
            pieces.append(para)
            continue
        for sentence in _SENTENCE_SPLIT.split(para):
            if count_tokens(sentence) <= max_tokens:
                pieces.append(sentence)
            else:  # a single huge "sentence" (tables, minified text): hard token windows
                tokens = _encoder().encode(sentence, disallowed_special=())
                for i in range(0, len(tokens), max_tokens):
                    pieces.append(_encoder().decode(tokens[i : i + max_tokens]))
    return pieces


def chunk_text(text: str, max_tokens: int = 400, overlap_tokens: int = 50) -> list[Chunk]:
    """Pack paragraphs into chunks of at most `max_tokens`, carrying a small overlap forward.

    The overlap is the tail of the previous chunk, so facts that straddle a boundary are still
    retrievable from one chunk.
    """
    if overlap_tokens >= max_tokens:
        raise ValueError("overlap_tokens must be smaller than max_tokens")
    chunks: list[Chunk] = []
    current: list[str] = []
    current_tokens = 0

    def flush() -> None:
        body = "\n\n".join(current).strip()
        if body:
            chunks.append(Chunk(index=len(chunks), text=body, token_count=count_tokens(body)))

    for piece in _pieces(text, max_tokens - overlap_tokens):
        piece_tokens = count_tokens(piece)
        if current and current_tokens + piece_tokens > max_tokens:
            flush()
            tail = truncate_tail(current[-1], overlap_tokens)
            current, current_tokens = ([tail], count_tokens(tail)) if tail else ([], 0)
        current.append(piece)
        current_tokens += piece_tokens
    flush()
    return chunks


def truncate_tail(text: str, max_tokens: int) -> str:
    if max_tokens <= 0:
        return ""
    tokens = _encoder().encode(text, disallowed_special=())
    return _encoder().decode(tokens[-max_tokens:]) if len(tokens) > max_tokens else text


# ---------------------------------------------------------------------------- page cleaning

_IMAGE = re.compile(r"!\[[^\]]*\]\([^)]*\)")
_LINK = re.compile(r"\[([^\]]*)\]\([^)]*\)")
_LIST_OR_HEADING = re.compile(r"^\s*(?:[*+-]|\d+\.|#{1,6})\s+")
_BOILERPLATE = re.compile(
    r"^(skip to (main )?content|sign in|log ?in|sign up|create account|contact sales|get started"
    r"|back|menu|close|search|share|accept( all)?( cookies)?|cookie (settings|preferences)"
    r"|previous|next|table of contents|on this page)$",
    re.IGNORECASE,
)
PROSE_MIN_WORDS = 15
_HEADING_LOOKBACK = 15


def _visible(line: str) -> tuple[str, int]:
    """Line text with links flattened to their anchor text, plus how many chars were link text."""
    link_chars = sum(len(m.group(1)) for m in _LINK.finditer(line))
    return _LINK.sub(r"\1", line), link_chars


def _is_prose(line: str) -> bool:
    return len(_LIST_OR_HEADING.sub("", line).split()) >= PROSE_MIN_WORDS


def clean_page_markdown(text: str) -> str:
    """Strip navigation, menus and footers from page markdown, keeping the article body.

    Search APIs return the whole page, and on marketing sites menus are often half of it. That
    noise costs tokens in every later step and pollutes retrieval. Two passes:
    1. Drop images, empty links, and short lines that are mostly link text (menus, breadcrumbs,
       sign-in bars) or known boilerplate. Surviving links are flattened to their anchor text.
    2. Keep the window from the heading before the first prose line to the end of the block
       holding the last prose line, which trims the header and footer around the article.
    Idempotent, so already-clean text (e.g. from trafilatura) passes through unchanged.
    """
    kept: list[str] = []
    for raw in _IMAGE.sub("", text).splitlines():
        visible, link_chars = _visible(raw)
        content = _LIST_OR_HEADING.sub("", visible).strip(" *_|#>")
        if raw.strip() and not content:
            continue  # e.g. "# [](https://stripe.com/)" or a bare bullet
        words = len(content.split())
        if content and link_chars / max(len(content), 1) >= 0.5 and words <= 12:
            continue
        if _BOILERPLATE.match(content):
            continue
        kept.append(visible.rstrip())

    prose = [i for i, line in enumerate(kept) if _is_prose(line)]
    if prose:
        start = prose[0]
        for j in range(prose[0] - 1, max(prose[0] - _HEADING_LOOKBACK, -1), -1):
            if kept[j].lstrip().startswith("#"):
                start = j
                break
        end = prose[-1]
        while end + 1 < len(kept) and kept[end + 1].strip():
            end += 1  # finish the block (paragraph, list or table) holding the last prose line
        kept = kept[start : end + 1]

    out: list[str] = []
    for line in kept:
        if line.strip() and out and line.strip() == out[-1].strip():
            continue  # repeated menu entries
        out.append(line)
    return re.sub(r"\n{3,}", "\n\n", "\n".join(out)).strip()


# ---------------------------------------------------------------------------- grounding

_QUOTE_CHARS = str.maketrans(
    {"\u2018": "'", "\u2019": "'", "\u201c": '"', "\u201d": '"', "\u2013": "-", "\u2014": "-"}
)
_MARKDOWN_NOISE = re.compile(r"[*_`#>|]|\[|\]\([^)]*\)|\]")
_WHITESPACE = re.compile(r"\s+")
SHORT_QUOTE_CHARS = 30


def normalize_for_match(text: str) -> str:
    """Normalise away formatting differences an extractor can legitimately introduce."""
    text = unicodedata.normalize("NFKC", text).translate(_QUOTE_CHARS)
    text = _MARKDOWN_NOISE.sub(" ", text)
    text = text.replace("...", " ").replace("\u2026", " ")
    return _WHITESPACE.sub(" ", text).strip().lower()


def quote_grounding_score(quote: str, source_text: str) -> float:
    """0\u2013100: how well `quote` appears verbatim in `source_text`.

    Short quotes must match exactly (fuzzy matching a 3-word quote against a long page is
    meaningless). Longer quotes use a best-substring fuzzy match, which tolerates the small
    whitespace and punctuation drift that extraction introduces.
    """
    q = normalize_for_match(quote)
    if not q:
        return 0.0
    s = normalize_for_match(source_text)
    if len(q) < SHORT_QUOTE_CHARS:
        return 100.0 if q in s else 0.0
    if q in s:
        return 100.0
    return float(fuzz.partial_ratio(q, s))


def quote_context(quote: str, source_text: str, window_chars: int = 500) -> str:
    """The (normalised) passage around where `quote` best matches, so a judge sees what "it" is."""
    q, s = normalize_for_match(quote), normalize_for_match(source_text)
    if not q or not s:
        return ""
    start = s.find(q)
    if start >= 0:
        end = start + len(q)
    else:
        alignment = fuzz.partial_ratio_alignment(q, s)
        if alignment is None:
            return ""
        start, end = alignment.dest_start, alignment.dest_end
    lo, hi = max(0, start - window_chars), min(len(s), end + window_chars)
    return ("…" if lo > 0 else "") + s[lo:hi] + ("…" if hi < len(s) else "")


_HEADING = re.compile(r"^(#{1,4})\s+(.+?)\s*#*\s*$")


def heading_trail(quote: str, source_text: str) -> list[str]:
    """The markdown headings in force where `quote` appears, outermost first.

    On changelogs and roadmaps the date or product a line belongs to sits in a heading far above
    it, outside any local context window. A judge needs that trail to check dated claims.
    """
    if not quote.strip():
        return []
    lowered = source_text.lower()
    position = lowered.find(quote.lower().strip())
    if position < 0:
        alignment = fuzz.partial_ratio_alignment(quote.lower(), lowered)
        if alignment is None or alignment.score < 60:
            return []
        position = alignment.dest_start
    trail: dict[int, str] = {}
    offset = 0
    for line in source_text.splitlines(keepends=True):
        if offset > position:
            break
        if match := _HEADING.match(line.strip()):
            level = len(match.group(1))
            trail = {lvl: text for lvl, text in trail.items() if lvl < level}
            trail[level] = match.group(2).strip(" *_")
        offset += len(line)
    return [trail[level] for level in sorted(trail)]


# ---------------------------------------------------------------------------- citations

FINDING_ID = r"F-[0-9a-f]{8}"
_CITATION_GROUP = re.compile(rf"\[\s*({FINDING_ID}(?:\s*[,;]\s*{FINDING_ID})*)\s*\]")
_ANY_BRACKET_ID = re.compile(r"\[\s*F-[^\]]*\]")
_NUMERIC_CITATION = re.compile(r"\[(\d+(?:\s*,\s*\d+)*)\]")


@dataclass(frozen=True)
class RenumberResult:
    markdown: str
    references: list[str]  # source ids in citation order: references[0] is [1]
    unknown_ids: list[str]


def cited_finding_ids(markdown: str) -> list[str]:
    ids: list[str] = []
    for group in _CITATION_GROUP.finditer(markdown):
        ids.extend(re.findall(FINDING_ID, group.group(1)))
    return ids


def renumber_citations(markdown: str, finding_to_source: dict[str, str]) -> RenumberResult:
    """Replace `[F-xxxxxxxx, F-yyyyyyyy]` markers with numbered source references `[1, 3]`.

    Numbers follow the order in which sources are first cited. Unknown finding ids are dropped
    and reported rather than silently kept, since an unresolvable citation is a writer error.
    """
    source_numbers: dict[str, int] = {}
    unknown: list[str] = []

    def replace(match: re.Match[str]) -> str:
        numbers: list[int] = []
        for fid in re.findall(FINDING_ID, match.group(1)):
            source_id = finding_to_source.get(fid)
            if source_id is None:
                unknown.append(fid)
                continue
            if source_id not in source_numbers:
                source_numbers[source_id] = len(source_numbers) + 1
            if (n := source_numbers[source_id]) not in numbers:
                numbers.append(n)
        return f"[{', '.join(map(str, sorted(numbers)))}]" if numbers else ""

    out = _CITATION_GROUP.sub(replace, markdown)
    out = _ANY_BRACKET_ID.sub("", out)  # malformed markers the writer invented
    out = re.sub(r"[ \t]+([.,;:])", r"\1", out)  # tidy space left before punctuation
    return RenumberResult(markdown=out, references=list(source_numbers), unknown_ids=unknown)


def lint_citations(markdown: str, n_references: int) -> list[str]:
    """Problems with numbered citations: out-of-range numbers and never-cited references."""
    problems: list[str] = []
    cited: set[int] = set()
    for group in _NUMERIC_CITATION.finditer(markdown):
        for n in (int(x) for x in re.split(r"\s*,\s*", group.group(1))):
            if not 1 <= n <= n_references:
                problems.append(f"citation [{n}] has no matching reference")
            cited.add(n)
    problems.extend(
        f"reference [{n}] is never cited" for n in range(1, n_references + 1) if n not in cited
    )
    return problems
