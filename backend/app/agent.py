"""Agentic Workflow Orchestrator for multi-step problem solving.

Plans, selects tools, executes actions sequentially, observes results,
and synthesizes a verified final solution.
Enforces:
- Hard step limit (default 6 steps) to prevent runaway execution.
- Cancellation support through asyncio.CancelledError.
- Real-time step progress streaming via Server-Sent Events.
- Honest error reporting with zero fabricated tool claims.
"""
import asyncio
import json
import logging
import re
from typing import Any, Callable

from .tools import TOOLS_REGISTRY, execute_tool

log = logging.getLogger('forma.agent')

MAX_AGENT_STEPS = 6

AGENT_SYSTEM_PROMPT = (
    "You are Forma Agent, an autonomous problem-solving AI assistant with access to verified tools. "
    "Your goal is to break down the user's objective, invoke necessary tools sequentially, "
    "verify tool outputs, and synthesize a clear, factual final answer.\n\n"
    "Available Tools:\n"
    "{tools_description}\n\n"
    "Instructions:\n"
    "1. When you need to take an action, output ONLY a JSON block with format:\n"
    '```json\n{{"action": "tool", "tool": "<tool_name>", "args": {{...}}, "thought": "<brief reason>"}}\n```\n'
    "2. When you have sufficient information to answer the user completely, output:\n"
    '```json\n{{"action": "finish", "answer": "<your complete, thorough final answer>"}}\n```\n'
    "3. Never guess or hallucinate tool results. Ground your statements solely in tool outputs.\n"
)


def format_tools_description() -> str:
    lines = []
    for name, t in TOOLS_REGISTRY.items():
        params = json.dumps(t['parameters']['properties'])
        lines.append(f"- **{name}**: {t['description']} (Parameters: {params})")
    return '\n'.join(lines)


def parse_agent_action(text: str) -> dict[str, Any]:
    """Parse JSON action block from model response."""
    # Look for code block ```json ... ```
    m = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', text, re.DOTALL)
    candidate = m.group(1) if m else text.strip()

    # Find matching outermost braces
    if not candidate.startswith('{'):
        start = candidate.find('{')
        end = candidate.rfind('}')
        if start != -1 and end != -1 and end > start:
            candidate = candidate[start:end + 1]

    try:
        data = json.loads(candidate)
        if isinstance(data, dict) and 'action' in data:
            return data
    except Exception:
        pass

    # If parsing failed, treat entire response as final answer
    return {'action': 'finish', 'answer': text.strip()}


async def run_agent_workflow(
    client,
    provider: str,
    model: str,
    user_prompt: str,
    visitor_id: str,
    conversation_id: str,
    message_id: int,
    emit_fn: Callable[[str, Any], Any],
    is_openai_format: bool = True,
    max_steps: int = MAX_AGENT_STEPS,
) -> str:
    """Execute multi-step agent workflow with tool dispatch and progress emission."""
    tools_desc = format_tools_description()
    system_msg = AGENT_SYSTEM_PROMPT.format(tools_description=tools_desc)

    steps_taken = 0
    scratchpad: list[dict[str, str]] = []

    await emit_fn('status', message='Forma Agent initialized. Formulating plan…')

    while steps_taken < max_steps:
        # Build prompt messages for current step
        prompt_content = f"User Request: {user_prompt}\n\n"
        if scratchpad:
            prompt_content += "Previous steps and observations:\n"
            for s in scratchpad:
                prompt_content += f"- Step {s['step']}: Tool '{s['tool']}' with args {s['args']}\n"
                prompt_content += f"  Observation: {s['observation'][:1200]}\n"
            prompt_content += "\nBased on the above observations, decide the next action or finish."

        messages = [
            {'role': 'system', 'content': system_msg},
            {'role': 'user', 'content': prompt_content},
        ]

        # Call model for next decision
        payload = {'model': model, 'stream': False, 'temperature': 0.2}
        if is_openai_format:
            payload['messages'] = messages
            payload['max_tokens'] = 1500
            endpoint = '/chat/completions'
        else:
            payload['messages'] = messages
            payload['options'] = {'temperature': 0.2, 'num_predict': 1500}
            endpoint = '/api/chat'

        try:
            resp = await client.post(endpoint, json=payload)
            resp.raise_for_status()
            data = resp.json()
            raw_text = (
                data.get('choices', [{}])[0].get('message', {}).get('content', '')
                if is_openai_format else data.get('message', {}).get('content', '')
            )
        except Exception as exc:
            log.warning('Agent model inference error: %s', exc)
            return f"Agent workflow could not complete due to provider error: {exc}"

        decision = parse_agent_action(raw_text)
        action_type = decision.get('action')

        if action_type == 'finish':
            final_answer = decision.get('answer') or raw_text
            await emit_fn('status', message='Agent workflow complete. Delivering synthesis.')
            return final_answer

        elif action_type == 'tool':
            tool_name = decision.get('tool', '')
            args = decision.get('args', {})
            thought = decision.get('thought', f"Executing {tool_name}…")

            steps_taken += 1
            await emit_fn('agent_step', step=steps_taken, tool=tool_name, thought=thought, args=args)
            await emit_fn('status', message=f"Step {steps_taken}/{max_steps}: {thought}")

            # Execute tool safely
            tool_output = await execute_tool(
                tool_name=tool_name,
                args=args,
                visitor_id=visitor_id,
                conversation_id=conversation_id,
                message_id=message_id,
            )

            obs_str = json.dumps(tool_output, ensure_ascii=False)
            scratchpad.append({
                'step': steps_taken,
                'tool': tool_name,
                'args': json.dumps(args),
                'observation': obs_str,
            })
            await emit_fn('agent_tool_result', step=steps_taken, tool=tool_name, status=tool_output.get('status'))

        else:
            # Fallback if unknown action
            return raw_text

    # If loop exhausted max_steps, synthesize final answer with current observations
    await emit_fn('status', message='Reached step limit. Synthesizing available findings…')
    summary_messages = [
        {'role': 'system', 'content': 'Synthesize a helpful final answer based on the completed steps and observations.'},
        {'role': 'user', 'content': prompt_content + '\nPlease provide your final answer now.'},
    ]
    try:
        resp = await client.post(endpoint, json={'model': model, 'messages': summary_messages, 'stream': False})
        resp.raise_for_status()
        data = resp.json()
        return (
            data.get('choices', [{}])[0].get('message', {}).get('content', '')
            if is_openai_format else data.get('message', {}).get('content', '')
        )
    except Exception:
        return "Completed maximum allowed steps. Here is a summary of the observations gathered:\n" + "\n".join(
            f"Step {s['step']}: {s['observation'][:300]}" for s in scratchpad
        )
