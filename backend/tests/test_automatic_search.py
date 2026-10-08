import pytest
from app.routing import needs_web_search


@pytest.mark.parametrize('question', [
    'Who is the chief minister of Tamil Nadu?', 'who is cmotamilnadu now',
    'Who is the CEO of Microsoft?', 'Latest IPL standings', 'Weather in Chennai',
    'What is the price of this phone?', 'Search the net and give the proper reply',
    'Verify that claim', 'What is the latest Python version?',
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
