from __future__ import annotations

import hashlib
import re

from packages.rag_policy.schemas import PolicyChunkRecord, PolicyDocument


def _split_sections(markdown: str) -> list[tuple[str, str]]:
    sections: list[tuple[str, str]] = []
    title = ""
    lines: list[str] = []
    for line in markdown.splitlines():
        heading = re.match(r"^(#{1,6})\s+(.+)$", line)
        if heading:
            if lines and "\n".join(lines).strip():
                sections.append((title, "\n".join(lines).strip()))
            title = heading.group(2).strip()
            lines = [line]
        else:
            lines.append(line)
    if lines and "\n".join(lines).strip():
        sections.append((title, "\n".join(lines).strip()))
    return sections or [("", markdown.strip())]


def chunk_policy_document(document: PolicyDocument) -> list[PolicyChunkRecord]:
    chunks: list[PolicyChunkRecord] = []
    for index, (title, text) in enumerate(_split_sections(document.text)):
        digest = hashlib.sha256(
            f"{document.doc_id}:{index}:{title}:{text[:200]}".encode("utf-8")
        ).hexdigest()[:16]
        metadata = dict(document.metadata)
        metadata["section"] = title
        chunks.append(
            PolicyChunkRecord(
                doc_id=document.doc_id,
                chunk_id=f"{document.doc_id}:{digest}",
                text=text,
                title=title or document.doc_id.replace("_", " "),
                metadata=metadata,
            )
        )
    return chunks
