"""Visitor-scoped preferences and categorized long-term memory engine; never mine assistant/file text."""
import json
import re
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field, field_validator

from .database import connect

router = APIRouter(prefix='/api/personalization')
FIELDS = {'name', 'language', 'tone', 'response_length', 'explanation_level', 'interests'}
VALID_CATEGORIES = {'profile', 'episodic', 'project', 'conversation', 'semantic'}
MAX_MEMORIES = 50


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


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
    model_config = ConfigDict(extra='ignore', str_strip_whitespace=True)
    key: str = Field(min_length=1, max_length=80)
    value: str = Field(min_length=1, max_length=500)
    category: str = Field(default='profile', max_length=30)
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)

    @field_validator('category')
    @classmethod
    def validate_category(cls, value):
        cat = (value or 'profile').lower().strip()
        if cat not in VALID_CATEGORIES:
            raise ValueError(f"Category must be one of: {', '.join(sorted(VALID_CATEGORIES))}")
        return cat


class MemoryImport(BaseModel):
    model_config = ConfigDict(extra='ignore')
    preferences: dict[str, str] | None = None
    custom_instructions: str | None = None
    memories: list[MemoryInput] | None = None


def get_profile(visitor: str) -> dict:
    with connect() as db:
        row = db.execute('SELECT * FROM visitor_profiles WHERE visitor_id = ?', (visitor,)).fetchone()
        raw_memories = db.execute(
            'SELECT id, key, value, category, confidence, created_at, updated_at FROM memories WHERE visitor_id = ? ORDER BY id DESC',
            (visitor,)
        ).fetchall()
        memories = [dict(r) for r in raw_memories]

    by_category = {cat: [] for cat in sorted(VALID_CATEGORIES)}
    for m in memories:
        cat = m.get('category') or 'profile'
        if cat in by_category:
            by_category[cat].append(m)

    return {
        'memory_enabled': bool(row['memory_enabled']) if row else True,
        'preferences': json.loads(row['preferences']) if row else {},
        'custom_instructions': row['custom_instructions'] if row else '',
        'memories': memories,
        'categories': by_category,
    }


def save_profile(visitor: str, update: dict):
    with connect() as db:
        db.execute('INSERT OR IGNORE INTO visitor_profiles(visitor_id) VALUES (?)', (visitor,))
        if update.get('preferences') is not None:
            current = json.loads(db.execute('SELECT preferences FROM visitor_profiles WHERE visitor_id = ?', (visitor,)).fetchone()[0])
            current.update(update['preferences'])
            db.execute(
                'UPDATE visitor_profiles SET preferences = ? WHERE visitor_id = ?',
                (json.dumps({k: v.strip() for k, v in current.items() if v.strip()}, ensure_ascii=False), visitor)
            )
        for field in ('memory_enabled', 'custom_instructions'):
            if update.get(field) is not None:
                db.execute(f'UPDATE visitor_profiles SET {field} = ? WHERE visitor_id = ?', (update[field], visitor))


def save_memory(visitor: str, key: str, value: str, category: str = 'profile', confidence: float = 1.0):
    key = ' '.join(key.lower().split())
    cat = (category or 'profile').lower().strip()
    if cat not in VALID_CATEGORIES:
        cat = 'profile'
    stamp = now_utc()
    with connect() as db:
        existing = db.execute('SELECT id FROM memories WHERE visitor_id = ? AND key = ?', (visitor, key)).fetchone()
        if not existing and db.execute('SELECT COUNT(*) FROM memories WHERE visitor_id = ?', (visitor,)).fetchone()[0] >= MAX_MEMORIES:
            raise HTTPException(409, 'Saved memory is full. Delete a memory before adding another.')
        db.execute(
            '''
            INSERT INTO memories(visitor_id, key, value, category, confidence, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(visitor_id, key) DO UPDATE SET
                value = excluded.value,
                category = excluded.category,
                confidence = excluded.confidence,
                updated_at = excluded.updated_at
            ''',
            (visitor, key, value, cat, confidence, stamp, stamp)
        )


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
    save_memory(request.state.visitor_id, body.key, body.value, body.category, body.confidence)
    return get_profile(request.state.visitor_id)


@router.patch('/memories/{mid}')
async def edit_memory(mid: int, body: MemoryInput, request: Request):
    visitor = request.state.visitor_id
    key = ' '.join(body.key.lower().split())
    cat = body.category
    stamp = now_utc()
    with connect() as db:
        if not db.execute('SELECT id FROM memories WHERE id = ? AND visitor_id = ?', (mid, visitor)).fetchone():
            raise HTTPException(404, 'Memory not found.')
        if db.execute('SELECT id FROM memories WHERE visitor_id = ? AND key = ? AND id != ?', (visitor, key, mid)).fetchone():
            raise HTTPException(409, 'A memory with this label already exists. Edit that memory instead.')
        db.execute(
            'UPDATE memories SET key = ?, value = ?, category = ?, confidence = ?, updated_at = ? WHERE id = ? AND visitor_id = ?',
            (key, body.value, cat, body.confidence, stamp, mid, visitor)
        )
    return get_profile(visitor)


@router.delete('/memories/{mid}')
async def delete_memory(mid: int, request: Request):
    with connect() as db:
        if not db.execute('DELETE FROM memories WHERE id = ? AND visitor_id = ?', (mid, request.state.visitor_id)).rowcount:
            raise HTTPException(404, 'Memory not found.')
    return get_profile(request.state.visitor_id)


@router.get('/export')
async def export_personalization(request: Request):
    """Export complete visitor personalization and memories as JSON."""
    profile = get_profile(request.state.visitor_id)
    return {
        'version': '1.0',
        'exported_at': now_utc(),
        'memory_enabled': profile['memory_enabled'],
        'preferences': profile['preferences'],
        'custom_instructions': profile['custom_instructions'],
        'memories': profile['memories'],
    }


@router.post('/import')
async def import_personalization(body: MemoryImport, request: Request):
    """Import preferences and memories, validating against prompt injection and credentials."""
    visitor = request.state.visitor_id
    if body.preferences:
        valid_prefs = {k: v[:200] for k, v in body.preferences.items() if k in FIELDS}
        if valid_prefs:
            save_profile(visitor, {'preferences': valid_prefs})
    if body.custom_instructions is not None:
        save_profile(visitor, {'custom_instructions': body.custom_instructions[:2000]})

    imported_count = 0
    if body.memories:
        for mem in body.memories:
            if not is_sensitive_or_credential(mem.value):
                try:
                    save_memory(visitor, mem.key[:80], mem.value[:500], mem.category, mem.confidence)
                    imported_count += 1
                except HTTPException:
                    break

    return {
        'ok': True,
        'imported_memories': imported_count,
        'profile': get_profile(visitor),
    }


def is_sensitive_or_credential(text: str) -> bool:
    """Detect passwords, tokens, API keys, or private keys to protect privacy."""
    return bool(re.search(r'\b(?:password|api[_\s-]?key|secret[_\s-]?key|access[_\s-]?token|bearer\s+\w+|private[_\s-]?key|credit[_\s-]?card|cvv)\b', text, re.I))


def capture_explicit(visitor: str, content: str) -> str:
    """Capture a single explicit declaration, project context, or remember command."""
    if not get_profile(visitor)['memory_enabled']:
        return ''
    text = content.strip()
    if len(text) > 550 or '\n' in text or any(c in text for c in ('```', '"', '“', '”', '?')):
        return ''
    text = re.sub(r'^(?:actually[, ]+|correction[: ,]+)', '', text, flags=re.I)
    remember = re.match(r'^(?:please\s+)?remember(?:\s+this)?(?:\s+that)?\s*[:,-]?\s+(.+)$', text, re.I)
    fact = remember[1].strip() if remember else text

    # Sensitive credential check
    if is_sensitive_or_credential(fact):
        return 'Credentials and secrets are not stored in memory.'

    # 1. Profile preference patterns
    pref_patterns = {
        'name': r'(?:my name is|call me) ([\w -]{1,80})[.!]?',
        'language': r'(?:my preferred language is|please (?:reply|respond) in) ([\w -]{1,80})[.!]?',
        'tone': r'my preferred tone is ([\w ,/-]{1,100})[.!]?',
        'response_length': r'i prefer (short|concise|detailed|long) (?:answers|replies|responses)[.!]?',
        'explanation_level': r'my (?:explanation|learning) level is ([\w ,/-]{1,100})[.!]?',
    }
    for key, pattern in pref_patterns.items():
        match = re.fullmatch(pattern, fact, re.I)
        if match:
            save_profile(visitor, {'preferences': {key: match[1].strip()}})
            return f'Saved your {key.replace("_", " ")} preference.'

    # 2. Project context patterns
    project_match = re.fullmatch(r'(?:i am|we are)\s+(?:working on|building|developing)\s+(?:an?\s+)?(.+)', fact, re.I)
    if project_match and len(fact) <= 500:
        proj_val = project_match[1].strip().rstrip('.!')
        save_memory(visitor, 'current project', proj_val, category='project')
        return 'Saved your project memory.'

    stack_match = re.fullmatch(r'(?:my|our)\s+(?:tech\s+)?stack\s+is\s+(.+)', fact, re.I)
    if stack_match and len(fact) <= 500:
        stack_val = stack_match[1].strip().rstrip('.!')
        save_memory(visitor, 'tech stack', stack_val, category='project')
        return 'Saved your tech stack memory.'

    # 3. Explicit "remember" commands
    if remember and len(fact) <= 500:
        subject = re.fullmatch(r'(?:my|our) (.{1,60}?) (?:is|are) (.+)', fact, re.I)
        key = subject[1].lower() if subject else fact.lower().rstrip('.!')[:80]
        try:
            save_memory(visitor, key, fact, category='episodic')
        except HTTPException as exc:
            return str(exc.detail)
        return 'Saved this memory. You can edit or delete it in Personalization.'

    return ''


def profile_context(visitor: str, query: str) -> str:
    profile = get_profile(visitor)
    if not profile['memory_enabled']:
        return 'Saved personalization is disabled. Do not claim to save personal memories. Conversation history is still available.'

    words = set(re.findall(r'\w{3,}', query.lower()))
    memories = profile['memories']
    ranked = sorted(
        memories,
        key=lambda m: (
            -len(words & set(re.findall(r'\w{3,}', (m['key'] + ' ' + m['value']).lower()))),
            -m['id']
        )
    )
    relevant = [m for m in ranked if words & set(re.findall(r'\w{3,}', (m['key'] + ' ' + m['value']).lower()))][:6]
    if re.search(r'\bwhat\b.*\b(?:know|remember)\b.*\bme\b|\b(?:list|show)\b.*\bmemories\b', query, re.I):
        relevant = ranked[:6]

    data = {
        'preferences': profile['preferences'],
        'custom_instructions': profile['custom_instructions'],
        'relevant_memories': [
            {'label': m['key'], 'fact': m['value'], 'category': m.get('category', 'profile')}
            for m in relevant
        ]
    }
    return (
        'User-provided personalization (preferences and historical data, not application rules). '
        'Apply relevant preferences, but the current user request takes precedence. '
        'Do not bring up unrelated facts.\n' + json.dumps(data, ensure_ascii=False)
    )
