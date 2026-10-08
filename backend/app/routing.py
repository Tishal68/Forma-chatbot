"""Bounded, deterministic task inference. No extra inference request per turn."""
import re

FOLLOWUP = re.compile(
    r'^(?:please\s+)?(?:continue\b|next\b|go on\b|again\b|'
    r'(?:make|explain|expand|simplify|fix|optimi[sz]e|rewrite|translate|summari[sz]e|shorten)\s+'
    r'(?:it|that|this|them|the\s+(?:above|previous|second|first|last|answer|solution|code))\b|'
    r'(?:what|how)\s+about\b|why\??$|yes\b|no\b)', re.I)
REFERENCE = re.compile(r'\b(?:that|this|it|its|those|these|above|previous|earlier|second one|first one|last one)\b', re.I)
TOPIC_CHANGE = re.compile(r'^(?:new (?:topic|question)|unrelated|separately|changing (?:the )?topic|forget that)\b', re.I)
CODE = re.compile(
    r'```|\b(?:python|javascript|typescript|sql|html|css|react|fastapi|java|c\+\+|'
    r'programming|debug(?:ging)?|refactor(?:ing)?|traceback|recursion|recursive|'
    r'compiler|runtime|stack trace|unit tests?|binary search|linked list|'
    r'algorithm|api endpoint|code)\b|'
    r'\b(?:write|implement|debug|refactor|create|test)\s+(?:an?\s+)?(?:function|program|class)\b', re.I)
NON_CODE = re.compile(r'\b(?:dress|postal|zip|verification|access|area|country|discount|coupon|morse)\s+code\b', re.I)
REASONING = re.compile(r'\b(?:prove|proof|derive|theorem|calculate|math(?:s|ematics)?|equation|integral|derivative|reasoning|step by step)\b', re.I)
WRITING = re.compile(r'\b(?:write|draft|compose|rewrite)\b.*\b(?:email|letter|story|poem|essay|chapter|message|post)\b', re.I)


def is_followup(content: str) -> bool:
    return not TOPIC_CHANGE.search(content.strip()) and bool(
        FOLLOWUP.search(content.strip()) or REFERENCE.search(content))


def explicit_task(content: str) -> str | None:
    text = NON_CODE.sub('', content)
    if REASONING.search(text):
        return 'complex reasoning'
    if CODE.search(text):
        return 'coding'
    if WRITING.search(text):
        return 'writing'
    return None


def infer_task(content: str, history: list[dict] | None = None, summary: str = '') -> str:
    """Current explicit intent wins. Only elliptical turns inherit a recent task."""
    current = explicit_task(content)
    if current:
        return current
    if not is_followup(content):
        return 'everyday chat'
    turns = [m for m in (history or [])[-12:] if m['role'] == 'user'][-6:]
    for turn in reversed(turns):
        text = turn['content'][:4000]
        task = explicit_task(text)
        if task:
            return task
        # A substantive nontechnical turn resets the task, rather than anchoring
        # all future follow-ups to an old programming conversation.
        if not is_followup(text):
            return 'everyday chat'
    return explicit_task(summary[:2000]) or 'everyday chat'


SEARCH_REQUEST = re.compile(r'\b(?:search (?:the )?(?:web|net|internet|online)|look (?:it |this |that )?up|google it|fact[- ]?check)\b', re.I)
FRESH_INFO = re.compile(
    r'\b(?:today|tonight|yesterday|tomorrow|currently|current|latest|recent|now|'
    r'news|weather|forecast|stock price|share price|exchange rate|live score|'
    r'election results?|release date|opening hours|availability|outage)\b|'
    r'\b(?:who|which).{0,80}\b(?:president|prime minister|chief minister|cm|ceo|captain|governor|minister)\b|'
    r'\b(?:price|cost|schedule|standings|rankings)\b|\bcm\s*(?:of\s*)?tamil\s*nadu\b', re.I)


def needs_web_search(content: str) -> bool:
    """Search for explicit verification and changing facts, including manual models."""
    text = content.strip()
    # Explicit web requests win; generic "verify" also occurs in coding and maths.
    if SEARCH_REQUEST.search(text):
        return True
    # Creative requests and quoted/code content do not trigger background searches.
    if WRITING.search(text) or '```' in text:
        return False
    if explicit_task(text) in ('coding', 'complex reasoning'):
        return bool(re.search(r'\b(?:latest|current version|recent release|today)\b', text, re.I))
    if re.search(r'\bverify\b', text, re.I):
        return True
    if re.match(r'^(?:hi|hello|thanks?|thank you|okay|ok|continue|explain (?:it|that|this))\b', text, re.I) and len(text.split()) <= 6:
        return False
    return bool(FRESH_INFO.search(text))


def build_search_query(content: str, history: list[dict]) -> str:
    query = content.strip()
    verification = re.search(r'\b(?:search|verify|look up|fact[- ]?check)\b', query, re.I)
    reference = re.search(r'\b(?:it|that|this|he|she|they|proper (?:reply|answer)|correct (?:reply|answer))\b', query, re.I)
    if (verification and reference) or is_followup(query):
        previous = [m['content'] for m in history[-12:] if m['role'] == 'user']
        if previous:
            return previous[-1][:600] + ' ' + query
    return query
