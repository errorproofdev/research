from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass

import tiktoken

ENCODING = tiktoken.get_encoding("cl100k_base")
HEADING = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
SENTENCE_END = re.compile(r"(?<=[.!?])\s+")


@dataclass(frozen=True)
class Block:
    kind: str
    text: str
    heading_path: tuple[str, ...]
    start: int
    end: int


@dataclass(frozen=True)
class Chunk:
    chunk_index: int
    heading_path: str
    content: str
    token_count: int
    start_offset: int
    end_offset: int
    content_hash: str
    oversized: bool = False


def token_count(text: str) -> int:
    return len(ENCODING.encode(text))


def parse_markdown(text: str) -> list[Block]:
    blocks: list[Block] = []
    headings: list[str] = []
    lines = text.splitlines(keepends=True)
    offset = 0
    paragraph: list[str] = []
    paragraph_start = 0
    fence: list[str] | None = None
    fence_start = 0

    def flush_paragraph(end: int) -> None:
        nonlocal paragraph
        value = "".join(paragraph).strip()
        if value:
            left_trim = len("".join(paragraph)) - len("".join(paragraph).lstrip())
            blocks.append(Block("paragraph", value, tuple(headings), paragraph_start + left_trim, end))
        paragraph = []

    for line in lines:
        line_start = offset
        offset += len(line)
        stripped = line.strip()
        if fence is not None:
            fence.append(line)
            if stripped.startswith("```") or stripped.startswith("~~~"):
                blocks.append(Block("code", "".join(fence).strip(), tuple(headings), fence_start, offset))
                fence = None
            continue
        if stripped.startswith("```") or stripped.startswith("~~~"):
            flush_paragraph(line_start)
            fence = [line]
            fence_start = line_start
            continue
        match = HEADING.match(line.rstrip("\n"))
        if match:
            flush_paragraph(line_start)
            level, title = len(match.group(1)), match.group(2)
            headings = headings[: level - 1]
            headings.append(title)
            continue
        if not stripped:
            flush_paragraph(line_start)
        else:
            if not paragraph:
                paragraph_start = line_start
            paragraph.append(line)
    flush_paragraph(len(text))
    if fence is not None:
        blocks.append(Block("code", "".join(fence).strip(), tuple(headings), fence_start, len(text)))
    return blocks


def split_oversized_paragraph(block: Block, max_body_tokens: int) -> list[Block]:
    if token_count(block.text) <= max_body_tokens:
        return [block]
    pieces: list[Block] = []
    cursor = 0
    for sentence in SENTENCE_END.split(block.text):
        sentence_start = block.text.find(sentence, cursor)
        cursor = sentence_start + len(sentence)
        if token_count(sentence) <= max_body_tokens:
            pieces.append(Block("paragraph", sentence, block.heading_path, block.start + sentence_start, block.start + cursor))
            continue
        words = list(re.finditer(r"\S+", sentence))
        current: list[re.Match[str]] = []
        for word in words:
            candidate = " ".join(item.group() for item in [*current, word])
            if current and token_count(candidate) > max_body_tokens:
                value = " ".join(item.group() for item in current)
                pieces.append(Block("paragraph", value, block.heading_path, block.start + sentence_start + current[0].start(), block.start + sentence_start + current[-1].end()))
                current = [word]
            else:
                current.append(word)
        if current:
            value = " ".join(item.group() for item in current)
            pieces.append(Block("paragraph", value, block.heading_path, block.start + sentence_start + current[0].start(), block.start + sentence_start + current[-1].end()))
    return pieces


def chunk_markdown(
    text: str,
    target_tokens: int = 600,
    max_tokens: int = 800,
    overlap_tokens: int = 80,
) -> list[Chunk]:
    if not 0 <= overlap_tokens < target_tokens <= max_tokens:
        raise ValueError("Require 0 <= overlap < target <= max")
    blocks = parse_markdown(text)
    chunks: list[Chunk] = []
    current: list[Block] = []

    def render(items: list[Block]) -> tuple[str, str]:
        path = " > ".join(items[0].heading_path) if items else ""
        prefix = f"Context: {path}\n\n" if path else ""
        return path, prefix + "\n\n".join(item.text for item in items)

    def flush(keep_overlap: bool = True) -> None:
        nonlocal current
        if not current:
            return
        path, content = render(current)
        chunks.append(Chunk(len(chunks), path, content, token_count(content), min(x.start for x in current), max(x.end for x in current), hashlib.sha256(content.encode()).hexdigest()))
        overlap: list[Block] = []
        if keep_overlap:
            for item in reversed(current):
                if item.kind != "paragraph":
                    break
                candidate = [item, *overlap]
                if token_count(render(candidate)[1]) > overlap_tokens:
                    break
                overlap = candidate
        current = overlap

    for block in blocks:
        prefix_tokens = token_count(f"Context: {' > '.join(block.heading_path)}\n\n")
        if block.kind == "code":
            flush()
            content = (f"Context: {' > '.join(block.heading_path)}\n\n" if block.heading_path else "") + block.text
            count = token_count(content)
            chunks.append(Chunk(len(chunks), " > ".join(block.heading_path), content, count, block.start, block.end, hashlib.sha256(content.encode()).hexdigest(), count > max_tokens))
            current = []
            continue
        max_body = max(1, max_tokens - prefix_tokens)
        for piece in split_oversized_paragraph(block, max_body):
            if current and current[0].heading_path != piece.heading_path:
                # Heading changes are hard semantic boundaries. Carrying overlap
                # across one would assign the new paragraph to the old section.
                flush(keep_overlap=False)
            candidate = [*current, piece]
            count = token_count(render(candidate)[1])
            if current and (count > target_tokens or count > max_tokens):
                flush()
                candidate = [*current, piece]
                if token_count(render(candidate)[1]) > max_tokens:
                    current = []
                    candidate = [piece]
            current = candidate
    flush(keep_overlap=False)
    return chunks
