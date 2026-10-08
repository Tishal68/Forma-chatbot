"""Resolve source references without making old attachments permanently sticky."""
import json
import re

from fastapi import HTTPException

from .routing import is_followup, TOPIC_CHANGE

SOURCE_CUE = re.compile(r'\b(?:(?:the|this|that|uploaded|attached|earlier|previous)\s+'
                        r'(?:file|document|pdf|image|picture|photo|spreadsheet)|'
                        r'top left|top right|bottom left|bottom right|in the (?:picture|document)|'
                        r'what (?:was|were)|which (?:was|were))\b', re.I)


def resolve_attachments(content, history, available, links):
    """Inputs have already been scoped to this visitor, chat and edit boundary."""
    text = content.lower()
    named = [a for a in available if a['filename'].lower() in text]
    if named:
        if len(named) > 4:
            raise HTTPException(422, 'Please choose up to four files for this follow-up.')
        if len({a['filename'] for a in named}) != len(named):
            raise HTTPException(422, 'Several uploads have that filename. Reattach the intended file.')
        return named
    if TOPIC_CHANGE.search(content.strip()):
        return []
    if not (is_followup(content) or SOURCE_CUE.search(content)):
        return []
    by_id = {a['id']: a for a in available}
    group = []
    explicit_source = bool(SOURCE_CUE.search(content))
    for turn in reversed(history):
        if turn['role'] != 'user':
            continue
        ids = links.get(turn['id'], [])
        if ids:
            group = [by_id[aid] for aid in ids if aid in by_id]
            break
        if not explicit_source and not is_followup(turn['content']):
            break
    if not group:
        if re.search(r'\b(?:the|this|that|uploaded|attached|earlier|previous)\s+'
                     r'(?:file|document|pdf|image|picture|photo|spreadsheet)\b', content, re.I):
            raise HTTPException(422, 'The referenced file is not available in this chat. Please attach it again or specify the file.')
        return []
    ordinal = re.search(r'\b(first|second|third|fourth|last)\b', text)
    if ordinal:
        idx = {'first': 0, 'second': 1, 'third': 2, 'fourth': 3, 'last': -1}[ordinal[1]]
        if idx >= len(group):
            raise HTTPException(422, 'That file number is not available. Specify its filename.')
        return [group[idx]]
    if len(group) > 1 and not re.search(r'\b(compare|both|all|files|documents|images|pictures|them|these|those)\b', text):
        names = ', '.join(a['filename'] for a in group[:4])
        raise HTTPException(422, f'Which file do you mean: {names}? Specify its filename or say “both” / “all”.')
    if len(group) > 4:
        raise HTTPException(422, 'Please choose up to four files by filename for this follow-up.')
    return group


def document_excerpt(attachment, query, max_chars=12000):
    """Lexical section retrieval with original citations, no embedding service."""
    text = attachment.get('extracted_text') or ''
    if len(text) <= max_chars:
        return text
    words = set(re.findall(r'\w{4,}', query.lower())) - {'this', 'that', 'what', 'with', 'from', 'document', 'file', 'summarize'}
    pieces = []
    heading = f"--- [File: {attachment['filename']}] ---"
    # Preserve page headings and existing code line numbers on every chunk.
    for section in re.split(r'(?=--- \[File:)', text):
        lines = section.splitlines(keepends=True)
        if lines and lines[0].startswith('--- [File:'):
            heading = lines.pop(0).strip()
        chunk = ''
        for line in lines:
            if chunk and len(chunk) + len(line) > 1800:
                pieces.append(heading + '\n' + chunk)
                chunk = ''
            for offset in range(0, len(line), 1800):
                part = line[offset:offset + 1800]
                if len(chunk) + len(part) > 1800:
                    pieces.append(heading + '\n' + chunk)
                    chunk = ''
                chunk += part
        if chunk:
            pieces.append(heading + '\n' + chunk)
    scored = sorted(enumerate(pieces), key=lambda item: (-len(words & set(re.findall(r'\w{4,}', item[1].lower()))), item[0]))
    chosen, used = [], 0
    for idx, piece in scored:
        if used + len(piece) <= max_chars - 150:
            chosen.append((idx, piece))
            used += len(piece)
    return '[Relevant excerpts; other sections remain saved. Ask for a page or topic for more detail.]\n' + '\n'.join(p for _, p in sorted(chosen))


def previous_search_context(content, history):
    if not (is_followup(content) or re.search(r'\b(?:sources?|citations?|links?|search results)\b', content, re.I)):
        return ''
    for turn in reversed(history[-8:]):
        if turn.get('sources'):
            try:
                sources = json.loads(turn['sources']) if isinstance(turn['sources'], str) else turn['sources']
                return ('Historical web sources from an earlier answer; these have NOT been refreshed:\n' +
                        json.dumps(sources[:5], ensure_ascii=False)[:10000])
            except (ValueError, TypeError):
                return ''
        if turn['role'] == 'user' and not is_followup(turn['content']):
            break
    return ''
