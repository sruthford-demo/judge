"""Claude-as-judge integration.

Each round, Claude sees the prompt card and an anonymized, numbered list of
response card texts, and picks the worst/funniest-fit one along with a short
roast. This module deals only in anonymous text; it never sees player
identities, so it returns an index into the given list, not a player id.
"""

import json
import random
import re
from dataclasses import dataclass

from claude_agent_sdk import ClaudeAgentOptions, ResultMessage, query

from lib import sdk_parser

JUDGE_MODEL = "claude-sonnet-5"

JUDGE_SYSTEM_PROMPT = """You are the judge for a party game called Judge, modeled on \
Cards Against Humanity. Every round you see one prompt card with a blank and a \
numbered, anonymized list of candidate response cards. Pick the single response that \
is the worst / funniest / most inappropriately perfect fit, and write a short, witty, \
PG-13 roast (1-3 sentences) explaining the pick. Be playful and biting toward the \
*card*, never toward a real person -- the submissions are anonymous to you.

Respond with ONLY a single JSON object and nothing else -- no markdown fences, no \
preamble, no trailing commentary:
{"winner_index": <integer index into the submissions list, 0-based>, "roast": "<string>"}"""

_FALLBACK_ROAST = (
    "The judge got distracted mid-round -- this pick was made at random, "
    "but it's still valid!"
)

_JSON_OBJECT_RE = re.compile(r"\{.*\}", re.DOTALL)


@dataclass
class JudgeResult:
    winner_index: int
    roast: str
    error: str | None = None


async def judge_round(prompt_text: str, submission_texts: list[str]) -> JudgeResult:
    numbered = "\n".join(f"{i}: {text}" for i, text in enumerate(submission_texts))
    user_prompt = (
        f"Prompt card: {prompt_text}\n\n"
        f"Candidate responses:\n{numbered}\n\n"
        "Pick the winner and write your roast."
    )
    options = ClaudeAgentOptions(
        model=JUDGE_MODEL,
        tools=[],
        mcp_servers={},
        allowed_tools=[],
        strict_mcp_config=True,
        permission_mode="bypassPermissions",
        max_turns=1,
        system_prompt=JUDGE_SYSTEM_PROMPT,
    )

    sdk_parser.print_header(f"judge round: {prompt_text}")
    result_text = None
    try:
        async for message in query(prompt=user_prompt, options=options):
            sdk_parser.print_message(message)
            if isinstance(message, ResultMessage):
                result_text = message.result
    except Exception as exc:  # query() failed outright (CLI missing, refusal, etc.)
        return _fallback(submission_texts, error=f"query failed: {exc}")

    return _parse_judge_result(result_text, submission_texts)


def _parse_judge_result(result_text: str | None, submission_texts: list[str]) -> JudgeResult:
    if not result_text:
        return _fallback(submission_texts, error="empty response from judge")

    parsed = _try_json_loads(result_text)
    if parsed is None:
        match = _JSON_OBJECT_RE.search(result_text)
        if match:
            parsed = _try_json_loads(match.group(0))

    if parsed is None:
        return _fallback(submission_texts, error="could not parse judge response as JSON")

    winner_index = parsed.get("winner_index")
    roast = parsed.get("roast")

    if not isinstance(winner_index, int) or not (0 <= winner_index < len(submission_texts)):
        return _fallback(submission_texts, error="judge response had an invalid winner_index")
    if not isinstance(roast, str) or not roast.strip():
        return _fallback(submission_texts, error="judge response had an empty roast")

    return JudgeResult(winner_index=winner_index, roast=roast.strip())


def _try_json_loads(text: str) -> dict | None:
    try:
        value = json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return None
    return value if isinstance(value, dict) else None


def _fallback(submission_texts: list[str], error: str) -> JudgeResult:
    return JudgeResult(
        winner_index=random.randrange(len(submission_texts)),
        roast=_FALLBACK_ROAST,
        error=error,
    )
