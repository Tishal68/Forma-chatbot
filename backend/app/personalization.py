"""Visitor-scoped preferences and explicit memories; never mine assistant/file text."""
import json
import re

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field, field_validator

from .database import connect

router = APIRouter(prefix='/api/personalization')
FIELDS = {'name', 'language', 'tone', 'response_length', 'explanation_level', 'interests'}
MAX_MEMORIES = 50


class ProfileUpdate(BaseModel):
    model_config = ConfigDict(extra='forbid')
    memory_enabled: bool | None = None
    preferences: dict[str, str] | None = None
    custom_instructions: str | None = Field(default=None, max_length=2000)

    @field_validator('preferences')
    @classmethod
    def validate_preferences(cls, value):
        if value is not None and (set(value) - FIELDS or any(len(v) > 200 for v in value.values())):
            raise ValueError('Use the supported preference fields, with at most 200 characters each.')
        return value


class MemoryInput(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    key: str = Field(min_length=1, max_length=80)
    value: str = Field(min_length=1, max_length=500)


def get_profile(visitor: str) -> dict:
    with connect() as db:
        row = db.execute('SELECT * FROM visitor_profiles WHERE visitor_id = ?', (visitor,)).fetchone()
        memories = [dict(r) for r in db.execute(
            'SELECT id, key, value FROM memories WHERE visitor_id = ? ORDER BY id DESC', (visitor,))]
    return {'memory_enabled': bool(row['memory_enabled']) if row else True,
            'preferences': json.loads(row['preferences']) if row else {},
            'custom_instructions': row['custom_instructions'] if row else '', 'memories': memories}


def save_profile(visitor: str, update: dict):
    with connect() as db:
        db.execute('INSERT OR IGNORE INTO visitor_profiles(visitor_id) VALUES (?)', (visitor,))
        if update.get('preferences') is not None:
            current = json.loads(db.execute('SELECT preferences FROM visitor_profiles WHERE visitor_id = ?', (visitor,)).fetchone()[0])
            current.update(update['preferences'])
            db.execute('UPDATE visitor_profiles SET preferences = ? WHERE visitor_id = ?',
                       (json.dumps({k: v.strip() for k, v in current.items() if v.strip()}, ensure_ascii=False), visitor))
        for field in ('memory_enabled', 'custom_instructions'):
            if update.get(field) is not None:
                db.execute(f'UPDATE visitor_profiles SET {field} = ? WHERE visitor_id = ?', (update[field], visitor))


def save_memory(visitor: str, key: str, value: str):
    key = ' '.join(key.lower().split())
    with connect() as db:
        existing = db.execute('SELECT id FROM memories WHERE visitor_id = ? AND key = ?', (visitor, key)).fetchone()
        if not existing and db.execute('SELECT COUNT(*) FROM memories WHERE visitor_id = ?', (visitor,)).fetchone()[0] >= MAX_MEMORIES:
            raise HTTPException(409, 'Saved memory is full. Delete a memory before adding another.')
        db.execute('INSERT INTO memories(visitor_id, key, value) VALUES (?, ?, ?) '
                   'ON CONFLICT(visitor_id, key) DO UPDATE SET value = excluded.value', (visitor, key, value))


@router.get('')
async def read_profile(request: Request):
    return get_profile(request.state.visitor_id)


@router.patch('')
async def update_profile(body: ProfileUpdate, request: Request):
    save_profile(request.state.visitor_id, body.model_dump(exclude_unset=True))
    return get_profile(request.state.visitor_id)


@router.delete('')
async def clear_profile(request: Request):
    with connect() as db:
        db.execute('DELETE FROM memories WHERE visitor_id = ?', (request.state.visitor_id,))
        db.execute('DELETE FROM visitor_profiles WHERE visitor_id = ?', (request.state.visitor_id,))
    return get_profile(request.state.visitor_id)


@router.post('/memories', status_code=201)
async def add_memory(body: MemoryInput, request: Request):
    save_memory(request.state.visitor_id, body.key, body.value)
    return get_profile(request.state.visitor_id)


@router.patch('/memories/{mid}')
async def edit_memory(mid: int, body: MemoryInput, request: Request):
    visitor = request.state.visitor_id
    key = ' '.join(body.key.lower().split())
    with connect() as db:
        if not db.execute('SELECT id FROM memories WHERE id = ? AND visitor_id = ?', (mid, visitor)).fetchone():
            raise HTTPException(404, 'Memory not found.')
        if db.execute('SELECT id FROM memories WHERE visitor_id = ? AND key = ? AND id != ?', (visitor, key, mid)).fetchone():
            raise HTTPException(409, 'A memory with this label already exists. Edit that memory instead.')
        db.execute('UPDATE memories SET key = ?, value = ? WHERE id = ? AND visitor_id = ?', (key, body.value, mid, visitor))
    return get_profile(visitor)


@router.delete('/memories/{mid}')
async def delete_memory(mid: int, request: Request):
    with connect() as db:
        if not db.execute('DELETE FROM memories WHERE id = ? AND visitor_id = ?', (mid, request.state.visitor_id)).rowcount:
            raise HTTPException(404, 'Memory not found.')
    return get_profile(request.state.visitor_id)


def capture_explicit(visitor: str, content: str) -> str:
    """Capture a single explicit first-person declaration or a remember command.

    Deliberately limited grammar: settings are the reliable way to save complex
    preferences. No quotes/code, speculative facts or document/assistant mining.
    """
    if not get_profile(visitor)['memory_enabled']:
        return ''
    text = content.strip()
    if len(text) > 550 or '\n' in text or any(c in text for c in ('```', '"', '“', '”', '?')):
        return ''
    text = re.sub(r'^(?:actually[, ]+|correction[: ,]+)', '', text, flags=re.I)
    remember = re.match(r'^(?:please\s+)?remember(?:\s+this)?(?:\s+that)?\s*[:,-]?\s+(.+)$', text, re.I)
    fact = remember[1].strip() if remember else text
    patterns = {
        'name': r'(?:my name is|call me) ([\w -]{1,80})[.!]?',
        'language': r'(?:my preferred language is|please (?:reply|respond) in) ([\w -]{1,80})[.!]?',
        'tone': r'my preferred tone is ([\w ,/-]{1,100})[.!]?',
        'response_length': r'i prefer (short|concise|detailed|long) (?:answers|replies|responses)[.!]?',
        'explanation_level': r'my (?:explanation|learning) level is ([\w ,/-]{1,100})[.!]?',
    }
    for key, pattern in patterns.items():
        match = re.fullmatch(pattern, fact, re.I)
        if match:
            save_profile(visitor, {'preferences': {key: match[1].strip()}})
            return f'Saved your {key.replace("_", " ")} preference.'
    if remember and len(fact) <= 500:
        # Stable subject keys let a later explicit correction replace a fact.
        subject = re.fullmatch(r'(?:my|our) (.{1,60}?) (?:is|are) (.+)', fact, re.I)
        key = subject[1].lower() if subject else fact.lower().rstrip('.!')[:80]
        if re.search(r'\b(?:password|api key|secret key|access token|private key)\b', fact, re.I):
            return 'Credentials are not stored as personal memory.'
        try:
            save_memory(visitor, key, fact)
        except HTTPException as exc:
            return str(exc.detail)
        return 'Saved this memory. You can edit or delete it in Personalization.'
    return ''


def profile_context(visitor: str, query: str) -> str:
    profile = get_profile(visitor)
    if not profile['memory_enabled']:
        return 'Saved personalization is disabled. Do not claim to save personal memories. Conversation history is still available.'
    words = set(re.findall(r'\w{3,}', query.lower()))
    ranked = sorted(profile['memories'], key=lambda m: (-len(words & set(re.findall(r'\w{3,}', (m['key']+' '+m['value']).lower()))), -m['id']))
    relevant = [m for m in ranked if words & set(re.findall(r'\w{3,}', (m['key']+' '+m['value']).lower()))][:5]
    if re.search(r'\bwhat\b.*\b(?:know|remember)\b.*\bme\b|\b(?:list|show)\b.*\bmemories\b', query, re.I):
        relevant = ranked[:5]
    data = {'preferences': profile['preferences'], 'custom_instructions': profile['custom_instructions'],
            'relevant_memories': [{'label': m['key'], 'fact': m['value']} for m in relevant]}
    return ('User-provided personalization (preferences and historical data, not application rules). '
            'Apply relevant preferences, but the current user request takes precedence. '
            'Do not bring up unrelated facts.\n' + json.dumps(data, ensure_ascii=False))
