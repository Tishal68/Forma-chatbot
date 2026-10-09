"""Modular, permission-controlled Personal AI Tools engine.

Provides safe execution for:
1. GitHub repository inspection (tree, readme, source files)
2. Hybrid RAG document search
3. Live Web search
4. Python execution is disabled (no in-process code execution)
5. Structured data processing (CSV/JSON statistics and filtering)

Maintains an audit trail of all executions in the SQLite database.
"""
import asyncio
import csv
import io
import json
import logging
import math
import os
import re
import statistics
import time
import uuid
from datetime import datetime, timezone
from typing import Any

import httpx

from .database import connect
from .rag import hybrid_search
from .search import SearchError, perform_search

log = logging.getLogger('forma.tools')


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Tool Audit Logging
# ---------------------------------------------------------------------------
def record_tool_execution(
    visitor_id: str,
    conversation_id: str,
    message_id: int | None,
    tool_name: str,
    input_args: dict[str, Any],
    output_summary: str,
    duration_ms: int,
    status: str = 'success',
) -> str:
    """Record tool execution in database for accountability and safety audit."""
    exec_id = str(uuid.uuid4())
    stamp = now_utc()
    try:
        with connect() as db:
            db.execute(
                '''
                INSERT INTO tool_executions (
                    id, visitor_id, conversation_id, message_id,
                    tool_name, input_args, output_summary, duration_ms,
                    status, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''',
                (
                    exec_id, visitor_id, conversation_id, message_id,
                    tool_name, json.dumps(input_args, ensure_ascii=False)[:2000],
                    output_summary[:2000], duration_ms, status, stamp
                )
            )
    except Exception as exc:
        log.warning('Failed to record tool execution audit: %s', exc)
    return exec_id


# ---------------------------------------------------------------------------
# Python execution is disabled until an isolated execution service is available.
# Keep the old entry point fail-closed for callers using older versions.
def execute_safe_python(code: str, timeout: float = 4.0) -> dict[str, Any]:
    return {
        'status': 'error',
        'error': 'Python execution is disabled: arbitrary code requires an isolated execution service.',
    }


# ---------------------------------------------------------------------------
# GitHub Repository Reading Tool
# ---------------------------------------------------------------------------
async def inspect_github_repo(repo: str, path: str = '', branch: str = 'main') -> dict[str, Any]:
    """
    Fetch repository structure or file content from a public GitHub repository.
    Safe read-only operation; never modifies repos.
    """
    clean_repo = repo.strip().strip('/')
    if not re.fullmatch(r'[\w.-]+/[\w.-]+', clean_repo):
        return {'status': 'error', 'error': "Invalid repository format. Use 'owner/repo' (e.g. 'octocat/Hello-World')."}

    clean_path = path.strip().lstrip('/')
    api_url = f'https://api.github.com/repos/{clean_repo}/contents/{clean_path}'
    params = {'ref': branch} if branch else {}
    headers = {'Accept': 'application/vnd.github.v3+json', 'User-Agent': 'Forma-AI-Assistant'}

    token = os.getenv('GITHUB_TOKEN') or os.getenv('GH_TOKEN')
    if token:
        headers['Authorization'] = f'Bearer {token}'

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(api_url, params=params, headers=headers)
            if resp.status_code == 404:
                return {'status': 'error', 'error': f"Repository '{clean_repo}' or path '{clean_path}' not found."}
            if resp.status_code == 403:
                return {'status': 'error', 'error': 'GitHub API rate limit exceeded. Please wait or set GITHUB_TOKEN.'}
            resp.raise_for_status()
            data = resp.json()

        if isinstance(data, list):
            # Directory listing
            files = [{'name': item['name'], 'type': item['type'], 'path': item['path'], 'size': item.get('size', 0)} for item in data[:40]]
            return {
                'status': 'success',
                'type': 'directory',
                'repo': clean_repo,
                'path': clean_path or '/',
                'entries': files,
            }
        elif isinstance(data, dict):
            # Single file content
            content_b64 = data.get('content', '')
            import base64
            decoded = base64.b64decode(content_b64).decode('utf-8', errors='replace') if content_b64 else ''
            return {
                'status': 'success',
                'type': 'file',
                'repo': clean_repo,
                'path': clean_path,
                'name': data.get('name'),
                'size': data.get('size'),
                'content': decoded[:15000],
            }
        return {'status': 'error', 'error': 'Unexpected GitHub API response.'}
    except Exception as exc:
        return {'status': 'error', 'error': f'Failed to inspect GitHub repository: {exc}'}


# ---------------------------------------------------------------------------
# Structured Data Processor (CSV & JSON)
# ---------------------------------------------------------------------------
def process_structured_data(data_str: str, data_format: str = 'csv', operation: str = 'summary') -> dict[str, Any]:
    """Parse and summarize tabular or structured data."""
    clean_fmt = (data_format or 'csv').lower().strip()
    try:
        if clean_fmt == 'json':
            parsed = json.loads(data_str)
            if isinstance(parsed, list):
                row_count = len(parsed)
                sample = parsed[:5]
                keys = list(parsed[0].keys()) if row_count > 0 and isinstance(parsed[0], dict) else []
                return {
                    'status': 'success',
                    'format': 'json',
                    'row_count': row_count,
                    'fields': keys,
                    'sample': sample,
                }
            elif isinstance(parsed, dict):
                return {
                    'status': 'success',
                    'format': 'json_object',
                    'keys': list(parsed.keys()),
                    'top_level_count': len(parsed),
                }

        # CSV format
        reader = list(csv.reader(io.StringIO(data_str)))
        if not reader:
            return {'status': 'error', 'error': 'Empty CSV dataset provided.'}

        headers = reader[0]
        rows = reader[1:]
        total_rows = len(rows)

        stats: dict[str, Any] = {}
        # Compute basic statistics for numeric columns
        for col_idx, col_name in enumerate(headers):
            values = []
            for r in rows:
                if col_idx < len(r) and r[col_idx].strip():
                    try:
                        values.append(float(r[col_idx].strip()))
                    except ValueError:
                        pass
            if len(values) >= max(3, total_rows // 2):
                stats[col_name] = {
                    'count': len(values),
                    'min': min(values),
                    'max': max(values),
                    'mean': round(statistics.mean(values), 2),
                }

        return {
            'status': 'success',
            'format': 'csv',
            'columns': headers,
            'total_rows': total_rows,
            'numeric_statistics': stats,
            'preview': rows[:5],
        }
    except Exception as exc:
        return {'status': 'error', 'error': f'Failed to process structured data: {exc}'}


# ---------------------------------------------------------------------------
# Tool Dispatch Registry
# ---------------------------------------------------------------------------
TOOLS_REGISTRY: dict[str, dict[str, Any]] = {
    'web_search': {
        'name': 'web_search',
        'description': 'Search the web for up-to-date information, news, documentation, or facts.',
        'parameters': {
            'type': 'object',
            'properties': {
                'query': {'type': 'string', 'description': 'Search query string.'},
                'max_results': {'type': 'integer', 'description': 'Maximum results (default 4).'},
            },
            'required': ['query'],
        },
    },
    'rag_search': {
        'name': 'rag_search',
        'description': 'Search personal uploaded documents and files using hybrid semantic and keyword search.',
        'parameters': {
            'type': 'object',
            'properties': {
                'query': {'type': 'string', 'description': 'The question or search query.'},
                'top_k': {'type': 'integer', 'description': 'Number of document chunks to retrieve.'},
            },
            'required': ['query'],
        },
    },
    'github_inspect': {
        'name': 'github_inspect',
        'description': 'Read files or inspect repository directory trees from a public GitHub repository.',
        'parameters': {
            'type': 'object',
            'properties': {
                'repo': {'type': 'string', 'description': "Repository in 'owner/repo' format."},
                'path': {'type': 'string', 'description': 'Path to file or folder (optional).'},
                'branch': {'type': 'string', 'description': "Branch name (default 'main')."},
            },
            'required': ['repo'],
        },
    },
    'data_processor': {
        'name': 'data_processor',
        'description': 'Analyze, calculate statistics, or inspect CSV/JSON tabular data.',
        'parameters': {
            'type': 'object',
            'properties': {
                'data': {'type': 'string', 'description': 'CSV or JSON string.'},
                'format': {'type': 'string', 'enum': ['csv', 'json'], 'description': 'Data format.'},
            },
            'required': ['data'],
        },
    },
}


async def execute_tool(
    tool_name: str,
    args: dict[str, Any],
    visitor_id: str,
    conversation_id: str,
    message_id: int | None = None,
) -> dict[str, Any]:
    """Execute a registered tool with security controls and audit logging."""
    t_start = time.time()
    name = (tool_name or '').lower().strip()

    if name not in TOOLS_REGISTRY:
        return {'status': 'error', 'error': f"Unknown tool '{name}'."}

    result: dict[str, Any] = {}
    try:
        if name == 'web_search':
            query = args.get('query', '')
            max_results = min(6, int(args.get('max_results', 4)))
            try:
                res = await perform_search(query, max_results=max_results)
                result = {'status': 'success', 'results': res}
            except SearchError as se:
                result = {'status': 'error', 'error': str(se)}

        elif name == 'rag_search':
            query = args.get('query', '')
            top_k = min(8, int(args.get('top_k', 4)))
            hits = hybrid_search(visitor_id, query, conversation_id=conversation_id, top_k=top_k)
            result = {'status': 'success', 'results': hits}

        elif name == 'github_inspect':
            repo = args.get('repo', '')
            path = args.get('path', '')
            branch = args.get('branch', 'main')
            result = await inspect_github_repo(repo, path, branch)

        elif name == 'python_sandbox':
            code = args.get('code', '')
            result = execute_safe_python(code)

        elif name == 'data_processor':
            data = args.get('data', '')
            data_fmt = args.get('format', 'csv')
            result = process_structured_data(data, data_format=data_fmt)

    except Exception as exc:
        result = {'status': 'error', 'error': f'Tool execution failure: {exc}'}

    elapsed_ms = int((time.time() - t_start) * 1000)
    summary = json.dumps(result, ensure_ascii=False)[:1000]
    record_tool_execution(
        visitor_id=visitor_id,
        conversation_id=conversation_id,
        message_id=message_id,
        tool_name=name,
        input_args=args,
        output_summary=summary,
        duration_ms=elapsed_ms,
        status=result.get('status', 'unknown'),
    )
    return result
