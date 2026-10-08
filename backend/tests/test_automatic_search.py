import pytest
from app.routing import needs_web_search


@pytest.mark.parametrize('question', [
    'Who is the chief minister of Tamil Nadu?', 'who is cmotamilnadu now',
    'Who is the CEO of Microsoft?', 'Latest IPL standings', 'Weather in Chennai',
    'What is the price of this phone?', 'Search the net and give the proper reply',
    'Verify that claim', 'What is the latest Python version?',
    'who is thalapathy vijay', "Who's Thalapathy Vijay?", 'Who is Sundar Pichai?',
])
def test_changing_facts_trigger_search(question):
    assert needs_web_search(question)


@pytest.mark.parametrize('question', [
    'Explain neural networks for 16 marks', 'Write a Python sorting function',
    'Calculate the cost using this equation', 'Write a story about today',
    'Hi', 'Explain it again', '```python\nprint("latest news")\n```',
])
def test_stable_or_creative_requests_do_not_search(question):
    assert not needs_web_search(question)


@pytest.mark.parametrize('question', [
    'Verify my Python code', 'Verify this equation', 'Thanks now', 'Explain it now',
])
def test_verification_of_stable_tasks_does_not_require_web(question):
    assert not needs_web_search(question)


def test_search_followup_keeps_context_without_polluting_new_question():
    from app.routing import build_search_query
    history = [{'role': 'user', 'content': 'Who is the CEO of Example?'},
               {'role': 'assistant', 'content': 'An unverified claim'}]
    assert build_search_query('Search the web for Chennai weather', history) == 'Search the web for Chennai weather'
    assert build_search_query('Verify that', history) == 'Who is the CEO of Example? Verify that'
    assert 'unverified claim' not in build_search_query('Verify that', history)
    assert build_search_query('What about now?', history) == 'Who is the CEO of Example? What about now?'


def test_biography_query_requests_current_role_and_dated_news():
    from datetime import datetime, timezone
    from app.routing import build_search_query
    query = build_search_query('who is thalapathy vijay', [])
    assert query == f"thalapathy vijay current role {datetime.now(timezone.utc).strftime('%B %Y')}"


@pytest.mark.parametrize('question', ['Who is he?', 'Who is this person?', 'Who was Albert Einstein?'])
def test_ambiguous_identity_and_historical_biography_are_not_current_profiles(question):
    from app.routing import biography_subject
    assert biography_subject(question) is None
