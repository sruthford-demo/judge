"""Formatting helpers for logging Claude Agent SDK message streams.

Pure presentation code: no API calls, no state. main.py calls into these
functions as it iterates the async message stream from `query()`, so the
message flow (system init -> assistant/tool_use -> user/tool_result ->
assistant/text -> result) is visible in the terminal output.
"""

import os
import re
import sys
from datetime import datetime

from claude_agent_sdk import (
    AssistantMessage,
    ResultMessage,
    SystemMessage,
    TextBlock,
    ThinkingBlock,
    ToolResultBlock,
    ToolUseBlock,
    UserMessage,
)

RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"

_COLORS = {
    "cyan": "\033[36m",
    "green": "\033[32m",
    "yellow": "\033[33m",
    "magenta": "\033[35m",
    "red": "\033[31m",
}

_ANSI_RE = re.compile(r"\033\[[0-9;]*m")
_log_file = None


def _project_root() -> str:
    """Directory of the running __main__ script, not this lib's location."""
    main_module = sys.modules.get("__main__")
    main_file = getattr(main_module, "__file__", None) or sys.argv[0]
    return os.path.dirname(os.path.abspath(main_file))


def _log_file_handle():
    global _log_file
    if _log_file is None:
        logs_dir = os.path.join(_project_root(), "logs")
        os.makedirs(logs_dir, exist_ok=True)
        timestamp = datetime.now().astimezone().strftime("%Y-%m-%dT%H-%M-%S%z")
        log_path = os.path.join(logs_dir, f"{timestamp}.log")
        _log_file = open(log_path, "a", encoding="utf-8")
    return _log_file


def _emit(text: str) -> None:
    print(text)
    log_file = _log_file_handle()
    log_file.write(_ANSI_RE.sub("", text) + "\n")
    log_file.flush()


def _c(color_name: str, text: str) -> str:
    return f"{_COLORS[color_name]}{text}{RESET}"


def print_header(title: str) -> None:
    line = "=" * max(8, len(title) + 4)
    _emit(f"\n{BOLD}{_c('cyan', line)}")
    _emit(f"  {title}")
    _emit(f"{line}{RESET}")


def print_message(message) -> None:
    """Dispatch a single message from the query() stream to a formatter."""
    if isinstance(message, SystemMessage):
        _print_system_message(message)
    elif isinstance(message, AssistantMessage):
        _print_assistant_message(message)
    elif isinstance(message, UserMessage):
        _print_user_message(message)
    elif isinstance(message, ResultMessage):
        _print_result_message(message)
    else:
        _emit(f"{_c('magenta', f'[{type(message).__name__}]')} {message}")


def _print_system_message(message: SystemMessage) -> None:
    if message.subtype == "init":
        model = message.data.get("model", "?")
        tools = message.data.get("tools", [])
        _emit(f"{BOLD}session init{RESET} {DIM}model={model} tools={tools}{RESET}")
    else:
        _emit(f"{DIM}[system:{message.subtype}] {message.data}{RESET}")


def _print_assistant_message(message: AssistantMessage) -> None:
    for block in message.content:
        if isinstance(block, TextBlock):
            _emit(f"  {_c('green', '[text]')} {block.text}")
        elif isinstance(block, ThinkingBlock):
            if block.thinking:
                _emit(f"  {DIM}[thinking] {block.thinking}{RESET}")
        elif isinstance(block, ToolUseBlock):
            _emit(f"  {_c('yellow', '[tool_use]')} id={block.id} name={block.name} input={block.input}")
        else:
            _emit(f"  {_c('magenta', f'[{type(block).__name__}]')} {block}")


def _print_user_message(message: UserMessage) -> None:
    content = message.content
    if isinstance(content, str):
        _emit(f"  {_c('green', '[user text]')} {content}")
        return
    for block in content:
        if isinstance(block, ToolResultBlock):
            status = _c("red", "error") if block.is_error else _c("green", "ok")
            _emit(
                f"  {_c('green', '<- tool result')} "
                f"tool_use_id={block.tool_use_id} [{status}] {block.content}"
            )
        else:
            _emit(f"  {_c('magenta', f'[{type(block).__name__}]')} {block}")


def _print_result_message(message: ResultMessage) -> None:
    _emit(
        f"\n{BOLD}{_c('green', f'Final result (stop_reason={message.stop_reason}):')}{RESET}"
    )
    _emit(message.result or "")
    _emit(
        f"{DIM}turns={message.num_turns} duration_ms={message.duration_ms} "
        f"cost_usd={message.total_cost_usd} usage={message.usage}{RESET}"
    )
