# app/services/knowledge_retriever.py
#
# Keyword-based knowledge retriever for the JAMM Concierge agent.
# Loads all corpus chunks and procedure playbooks at module import time.
# Returns top matching chunks for a given user query.

import os
import re
import math
import logging
from pathlib import Path
from typing import NamedTuple

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
_REPO_ROOT = Path(__file__).resolve().parents[2]
_KNOWLEDGE_DIR = _REPO_ROOT / "knowledge"
_PROCEDURES_DIR = _KNOWLEDGE_DIR / "procedures"

# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

class Chunk(NamedTuple):
    heading: str        # The ## heading line
    body: str           # Body text under the heading
    source_file: str    # Filename for debugging
    is_procedure: bool  # True for procedure playbooks


# ---------------------------------------------------------------------------
# Loader -- runs once at module import
# ---------------------------------------------------------------------------

def _load_chunks() -> list[Chunk]:
    chunks: list[Chunk] = []

    def _parse_file(path: Path, is_procedure: bool) -> None:
        try:
            text = path.read_text(encoding="utf-8")
        except Exception as e:
            logger.warning("knowledge_retriever: could not read %s: %s", path, e)
            return

        # Split on ## headings (H2 only, not H3+)
        parts = re.split(r'\n(?=## )', text)
        for part in parts:
            part = part.strip()
            if not part:
                continue
            lines = part.split('\n', 1)
            heading = lines[0].lstrip('#').strip()
            body = lines[1].strip() if len(lines) > 1 else ''
            if heading and (body or is_procedure):
                chunks.append(Chunk(
                    heading=heading,
                    body=body,
                    source_file=path.name,
                    is_procedure=is_procedure,
                ))

    # Load content corpus (01_clients.md through 13_reports_analytics.md)
    if _KNOWLEDGE_DIR.exists():
        for md_file in sorted(_KNOWLEDGE_DIR.glob("*.md")):
            _parse_file(md_file, is_procedure=False)

    # Load procedure playbooks
    if _PROCEDURES_DIR.exists():
        for md_file in sorted(_PROCEDURES_DIR.glob("*.md")):
            _parse_file(md_file, is_procedure=True)

    logger.info(
        "knowledge_retriever: loaded %d chunks (%d procedures)",
        len(chunks),
        sum(1 for c in chunks if c.is_procedure),
    )
    return chunks


# Load once at import time
_ALL_CHUNKS: list[Chunk] = _load_chunks()


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------

def _tokenize(text: str) -> set[str]:
    """Lowercase words, strip punctuation, remove stopwords."""
    STOPWORDS = {
        'a', 'an', 'the', 'is', 'are', 'was', 'were', 'be', 'been', 'being',
        'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could',
        'should', 'may', 'might', 'shall', 'can', 'need', 'dare', 'ought',
        'used', 'to', 'of', 'in', 'for', 'on', 'with', 'at', 'by', 'from',
        'up', 'about', 'into', 'through', 'during', 'i', 'my', 'me', 'we',
        'our', 'you', 'your', 'it', 'its', 'this', 'that', 'they', 'them',
        'what', 'which', 'who', 'when', 'where', 'why', 'how', 'and', 'or',
        'but', 'not', 'if', 'then', 'so', 'just', 'also', 'more', 'any',
    }
    words = re.findall(r'[a-z]+', text.lower())
    return {w for w in words if w not in STOPWORDS and len(w) > 2}


def _score(chunk: Chunk, query_tokens: set[str]) -> float:
    """
    Score a chunk against query tokens.
    Heading matches weight 3x, body matches weight 1x.
    Normalised by sqrt of chunk length to avoid length bias.
    Procedures get a 2x multiplier when the query contains a trigger word.
    """
    heading_tokens = _tokenize(chunk.heading)
    body_tokens = _tokenize(chunk.body)

    heading_overlap = len(query_tokens & heading_tokens)
    body_overlap = len(query_tokens & body_tokens)

    raw = (heading_overlap * 3.0) + body_overlap
    length_norm = math.sqrt(max(len(body_tokens), 1))
    score = raw / length_norm

    # Procedure boost
    if chunk.is_procedure:
        PROCEDURE_TRIGGERS = {
            'cannot', 'upload', 'login', 'log', 'invoice', 'invoiced', 'missed',
            'deadline', 'onboard', 'onboarding', 'left', 'quit', 'resign',
            'season', 'kickoff', 'bookkeeping', 'close', 'stalled', 'pending',
            'portal', 'magic', 'link', 'rollout',
        }
        if query_tokens & PROCEDURE_TRIGGERS:
            score *= 2.0

    return score


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def retrieve(query: str, top_k: int = 3) -> list[Chunk]:
    """
    Return the top_k most relevant chunks for the query.
    Procedure playbooks can appear in results when triggered.
    Always includes at most 1 procedure (the top scoring one).
    """
    if not query or not _ALL_CHUNKS:
        return []

    query_tokens = _tokenize(query)
    if not query_tokens:
        return []

    scored = [(chunk, _score(chunk, query_tokens)) for chunk in _ALL_CHUNKS]
    scored.sort(key=lambda x: x[1], reverse=True)

    # Separate procedures from content chunks
    top_procedures = [(c, s) for c, s in scored if c.is_procedure and s > 0]
    top_content = [(c, s) for c, s in scored if not c.is_procedure and s > 0]

    results: list[Chunk] = []

    # Include top procedure if it scored above content threshold
    if top_procedures:
        best_proc_score = top_procedures[0][1]
        best_content_score = top_content[0][1] if top_content else 0
        # Procedure wins if it scored higher than content OR is in trigger zone
        if best_proc_score >= best_content_score or best_proc_score > 1.5:
            results.append(top_procedures[0][0])
            top_k -= 1

    # Fill remaining slots with top content chunks
    for chunk, score in top_content:
        if top_k <= 0:
            break
        if score > 0.5:  # Minimum relevance threshold
            results.append(chunk)
            top_k -= 1

    return results


def format_for_prompt(chunks: list[Chunk]) -> str:
    """
    Format retrieved chunks as a block to inject into the system prompt.
    Returns empty string if no chunks.
    """
    if not chunks:
        return ''

    parts = ['RELEVANT PRODUCT KNOWLEDGE\n']
    for chunk in chunks:
        if chunk.is_procedure:
            parts.append(f'PROCEDURE: {chunk.heading}\n\n{chunk.body}')
        else:
            parts.append(f'{chunk.heading}\n\n{chunk.body}')
        parts.append('---')

    return '\n'.join(parts)
