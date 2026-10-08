import asyncio

import httpx
import pytest
from app import search


@pytest.fixture(autouse=True)
def search_config(monkeypatch):
    monkeypatch.setenv('SEARCH_PROVIDER', 'duckduckgo')
    monkeypatch.delenv('TAVILY_API_KEY', raising=False)
    monkeypatch.delenv('BRAVE_API_KEY', raising=False)


def test_timeout_uses_lite_and_parses_results(monkeypatch):
    paths = []
    def handler(request):
        paths.append(request.url.host)
        if request.url.host == 'html.duckduckgo.com':
            raise httpx.ReadTimeout('', request=request)
        return httpx.Response(200, text="<a class='result-link' href='https://example.org/news'>Current <b>news</b></a><td class='result-snippet'>An update.</td>")
    original = httpx.AsyncClient
    monkeypatch.setattr(search.httpx, 'AsyncClient', lambda **kwargs: original(transport=httpx.MockTransport(handler), **kwargs))
    results = asyncio.run(search.perform_search('current news'))
    assert len(paths) == 2
    assert results == [{'title': 'Current news', 'url': 'https://example.org/news', 'snippet': 'An update.'}]


def test_challenge_pages_are_not_results(monkeypatch):
    original = httpx.AsyncClient
    monkeypatch.setattr(search.httpx, 'AsyncClient', lambda **kwargs: original(transport=httpx.MockTransport(lambda req: httpx.Response(202, text='Please prove you are human')), **kwargs))
    with pytest.raises(search.SearchError, match='blocking automated searches'):
        asyncio.run(search.perform_search('news'))


def test_blank_timeout_has_useful_error(monkeypatch):
    def handler(request):
        raise httpx.ReadTimeout('', request=request)
    original = httpx.AsyncClient
    monkeypatch.setattr(search.httpx, 'AsyncClient', lambda **kwargs: original(transport=httpx.MockTransport(handler), **kwargs))
    with pytest.raises(search.SearchError, match='request timed out'):
        asyncio.run(search.perform_search('news'))


def test_api_failure_uses_other_configured_service(monkeypatch):
    monkeypatch.setenv('TAVILY_API_KEY', 'test')
    monkeypatch.setenv('BRAVE_API_KEY', 'test')
    calls = []
    async def failed(*args):
        calls.append('tavily')
        raise search.SearchError('quota exhausted')
    async def working(*args):
        calls.append('brave')
        return [{'title': 'News', 'url': 'https://example.org', 'snippet': 'Update'}]
    monkeypatch.setattr(search, 'search_tavily', failed)
    monkeypatch.setattr(search, 'search_brave', working)
    assert asyncio.run(search.perform_search('news'))[0]['title'] == 'News'
    assert calls == ['tavily', 'brave']


def test_empty_api_results_fall_back_to_duckduckgo(monkeypatch):
    monkeypatch.setenv('TAVILY_API_KEY', 'test')
    async def empty(*args): return []
    async def working(*args): return [{'title': 'News', 'url': 'https://example.org', 'snippet': ''}]
    monkeypatch.setattr(search, 'search_tavily', empty)
    monkeypatch.setattr(search, 'search_duckduckgo', working)
    assert asyncio.run(search.perform_search('news'))[0]['title'] == 'News'


def test_disabled_search_never_uses_a_backup(monkeypatch):
    monkeypatch.setenv('SEARCH_PROVIDER', 'disabled')
    with pytest.raises(search.SearchError, match='disabled'):
        asyncio.run(search.perform_search('news'))


def test_html_redirects_are_decoded_and_unsafe_urls_ignored():
    parser = search.ResultParser()
    parser.feed('<a class="result__a" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fexample.org">News</a><a class="result__snippet">Latest update</a><a class="result__a" href="javascript:alert(1)">Bad</a>')
    assert search.clean_results(parser.results, 5) == [{'title': 'News', 'url': 'https://example.org', 'snippet': 'Latest update'}]
