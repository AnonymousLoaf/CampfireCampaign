"""DM engines. All share one interface: run(system, user, tools, call_tool) -> EngineResult.

- OfflineEngine: no AI. Scripted narration that still exercises every system (for testing and playing offline).
- ApiKeyEngine: the Claude API with a player's saved key (Anthropic Python SDK, Messages API + tool use).
- ClaudeCodeEngine: Claude Code on the host machine via the Claude Agent SDK, using the host's own login.
"""
from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from typing import Callable

from ..config import DATA_DIR

ToolCaller = Callable[[str, dict], str]

PRICES = {  # USD per million tokens: input, output, cache read, cache write (5-minute)
    "claude-opus-5-5": (4.0, 20.0, 0.20, 5.0),
    "claude-sonnet-5-5": (2.0, 10.0, 0.10, 2.5),
}


@dataclass
class EngineResult:
    text: str
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0
    cost_usd: float | None = None
    duration_ms: int = 0
    model: str | None = None
    tool_calls: list[str] = field(default_factory=list)


class DMError(RuntimeError):
    pass


RECAP_SYSTEM = ("You summarise a D&D campaign's recent events for a player who was away. Write 3-6 short sentences of "
                 "plain prose in past tense: what happened, where the party is now, and what is waiting on them. "
                 "No headings, no lists, no invented details.")


class OfflineEngine:
    name = "offline"

    async def summarize(self, system: str, user: str) -> str:
        items = [re.sub(r"^- \[[^\]]*\]\s*", "• ", l.strip()) for l in user.split("\n") if l.startswith("- ")]
        items = [i if len(i) < 220 else i[:217] + "…" for i in items]
        return "While you were away:\n" + "\n".join(items[-8:]) if items else "Nothing much happened while you were away."

    async def run(self, system: str, user: str, tools: list[dict], call_tool: ToolCaller, reason: str = "") -> EngineResult:
        t0 = time.monotonic()
        body = user.split("# This turn", 1)[-1]
        out: list[str] = []
        if reason == "opening":
            loc = re.search(r"Location: ([^\n—]+)", user)
            place = loc.group(1).strip() if loc else "the town"
            call_tool("upsert_quest", {"title": "Find your first adventure", "status": "active",
                                       "notes": f"Ask around {place} for work."})
            call_tool("upsert_npc", {"name": "Marta Vell", "role": "innkeeper", "attitude": "friendly",
                                     "notes": "Knows every rumour in town."})
            out.append(f"(Offline test DM — no AI is connected, so this story is scripted.) The bell over the inn door "
                       f"of {place} is still ringing when Marta Vell slaps a sealed letter on the bar. \"Came for you lot "
                       f"this morning. The rider didn't wait for coin.\" Outside, a cart rattles past, and somewhere a dog "
                       f"won't stop barking at the road east. What do you do?")
        elif reason in ("round", "rolls"):
            acts = re.findall(r"^- (.+?): (.+)$", body, re.M)
            text = body.lower()
            if any(w in text for w in ("shop", "buy", "market", "store", "sell", "trade")):
                call_tool("open_shop", {"shop_type": "blacksmith" if any(w in text for w in ("weapon", "armor", "armour", "smith"))
                                        else "general", "name": "The Copper Kettle", "keeper": "Oswin, a nervous gnome"})
                out.append("Oswin's shop smells of lamp oil and old leather. \"Browse, browse — just mind the shelves.\"")
            elif any(w in text for w in ("fight", "attack", "ambush", "kill", "charge")) and "Combat in progress" not in user:
                party = len(re.findall(r"\(player: ", user))
                terrain = ("tavern" if any(w in text for w in ("tavern", "inn", "bar")) else
                           "cave" if any(w in text for w in ("cave", "tunnel", "mine")) else
                           "dungeon" if any(w in text for w in ("dungeon", "crypt", "tomb", "vault")) else
                           "ruins" if any(w in text for w in ("ruin", "temple ruins", "old fort")) else
                           "swamp" if any(w in text for w in ("swamp", "bog", "marsh")) else
                           "camp" if any(w in text for w in ("camp", "hideout")) else
                           "forest" if any(w in text for w in ("forest", "woods", "trees")) else "road")
                foe = {"tavern": "Bandit", "cave": "Skeleton", "forest": "Wolf", "dungeon": "Skeleton",
                       "ruins": "Zombie", "swamp": "Giant Frog", "camp": "Bandit"}.get(terrain, "Goblin")
                call_tool("start_combat", {"monsters": [{"name": foe, "count": max(2, party)}], "terrain": terrain})
                out.append(f"Steel flashes — {foe.lower()}s, and they mean business. Fight!")
            elif any(w in text for w in ("rest", "sleep", "camp")):
                call_tool("rest", {"kind": "long"})
                out.append("The night passes quietly. You wake stiff but whole.")
            elif any(w in text for w in ("search", "look", "investigate", "listen", "sneak")):
                who = acts[0][0] if acts else None
                if who and "rolls" not in reason:
                    call_tool("roll_check", {"character": who.split(" (")[0], "check": "Perception", "dc": 12})
                out.append("Something is hidden here. A careful eye might find it.")
            for who, what in acts:
                out.append(f"{who.split(' (')[0]}: {what[:120]} — the world takes note.")
            out.append("The road east waits, and the barking hasn't stopped. What next?")
        elif reason in ("combat_round", "combat_end"):
            lines = [l[2:].strip() for l in body.splitlines() if l.startswith("- ")]
            out.append("Steel rings and boots scrape. " + " ".join(lines[-4:]))
            if reason == "combat_end":
                outcome = re.search(r"Outcome: (\w+)", body)
                out.append({"VICTORY": "The last enemy falls. Catch your breath — what now?",
                            "DEFEAT": "Darkness takes you… and later, you wake, sore and robbed but alive. What now?"}
                           .get(outcome.group(1) if outcome else "", "The fighting is over. What now?"))
        elif reason == "shop_done":
            out.append("Purchases stowed, the party steps back into the street.")
            out.append("What next?")
        else:
            out.append("The world turns. What do you do?")
        return EngineResult(text="\n\n".join(out), duration_ms=int((time.monotonic() - t0) * 1000), model="offline")


class ApiKeyEngine:
    name = "api_key"

    def __init__(self, api_key: str, model: str):
        self.api_key = api_key
        self.model = model

    async def summarize(self, system: str, user: str) -> str:
        import anthropic
        client = anthropic.AsyncAnthropic(api_key=self.api_key, max_retries=2, timeout=300)
        try:
            resp = await client.messages.create(model=self.model, max_tokens=2000, system=system,
                                                output_config={"effort": "low"},
                                                messages=[{"role": "user", "content": user}])
        except anthropic.APIStatusError as e:
            raise DMError(f"Claude API error {e.status_code}") from e
        except anthropic.APIConnectionError as e:
            raise DMError("couldn't reach the Claude API") from e
        if resp.stop_reason == "refusal":
            raise DMError("the model declined to summarise")
        return "\n\n".join(b.text for b in resp.content if b.type == "text").strip()

    async def run(self, system: str, user: str, tools: list[dict], call_tool: ToolCaller, reason: str = "") -> EngineResult:
        import anthropic

        t0 = time.monotonic()
        client = anthropic.AsyncAnthropic(api_key=self.api_key, max_retries=3, timeout=600)
        messages: list[dict] = [{"role": "user", "content": user}]
        res = EngineResult(text="", model=self.model)
        texts: list[str] = []
        for _ in range(16):
            try:
                resp = await client.beta.messages.create(
                    model=self.model,
                    max_tokens=16000,
                    system=[{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
                    tools=tools,
                    messages=messages,
                    output_config={"effort": "medium"},
                    betas=["server-side-fallback-2026-07-01"],
                    fallbacks="default",
                )
            except anthropic.AuthenticationError as e:
                raise DMError("the saved Claude API key was rejected — check it in Settings") from e
            except anthropic.PermissionDeniedError as e:
                raise DMError(f"the API key isn't allowed to use {self.model}") from e
            except anthropic.RateLimitError as e:
                raise DMError("Claude API rate limit reached — try again in a minute") from e
            except anthropic.APIStatusError as e:
                raise DMError(f"Claude API error {e.status_code}: {getattr(e, 'message', e)}") from e
            except anthropic.APIConnectionError as e:
                raise DMError("couldn't reach the Claude API — check the internet connection") from e
            u = resp.usage
            res.input_tokens += u.input_tokens or 0
            res.output_tokens += u.output_tokens or 0
            res.cache_read_tokens += getattr(u, "cache_read_input_tokens", 0) or 0
            res.cache_write_tokens += getattr(u, "cache_creation_input_tokens", 0) or 0
            if resp.stop_reason == "refusal":
                raise DMError("the model declined to continue this scene — try rephrasing the actions")
            step_text = [b.text for b in resp.content if b.type == "text" and b.text.strip()]
            tool_uses = [b for b in resp.content if b.type == "tool_use"]
            messages.append({"role": "assistant", "content": [b.model_dump(exclude_none=True) for b in resp.content]})
            if resp.stop_reason == "tool_use" and tool_uses:
                results = []
                for b in tool_uses:
                    out = call_tool(b.name, b.input if isinstance(b.input, dict) else {})
                    res.tool_calls.append(b.name)
                    results.append({"type": "tool_result", "tool_use_id": b.id, "content": out,
                                    **({"is_error": True} if out.startswith("Error:") else {})})
                messages.append({"role": "user", "content": results})
                if step_text:
                    texts = step_text  # keep the latest prose in case the model ends right after tools
                continue
            if resp.stop_reason == "pause_turn":
                continue
            if step_text:
                texts = step_text
            break
        res.text = "\n\n".join(texts).strip()
        if not res.text:
            raise DMError("the DM returned no narration")
        p = PRICES.get(self.model)
        if p:
            res.cost_usd = round((res.input_tokens * p[0] + res.output_tokens * p[1] + res.cache_read_tokens * p[2]
                                  + res.cache_write_tokens * p[3]) / 1_000_000, 5)
        res.duration_ms = int((time.monotonic() - t0) * 1000)
        return res


class ClaudeCodeEngine:
    name = "claude_code"

    def __init__(self, model: str):
        self.model = model

    async def summarize(self, system: str, user: str) -> str:
        from claude_agent_sdk import ClaudeAgentOptions, ResultMessage, query
        cwd = DATA_DIR / "claude_code_dm"
        cwd.mkdir(parents=True, exist_ok=True)
        opts = ClaudeAgentOptions(system_prompt=system, tools=[], allowed_tools=[], model=self.model, max_turns=1,
                                  setting_sources=[], cwd=str(cwd), effort="low")
        text = ""
        try:
            async for msg in query(prompt=user, options=opts):
                if isinstance(msg, ResultMessage):
                    if msg.is_error:
                        raise DMError(f"Claude Code reported an error: {msg.result or msg.subtype}")
                    text = (msg.result or "").strip()
        except DMError:
            raise
        except Exception as e:
            raise DMError(f"Claude Code failed: {e}") from e
        return text

    async def run(self, system: str, user: str, tools: list[dict], call_tool: ToolCaller, reason: str = "") -> EngineResult:
        try:
            from claude_agent_sdk import (AssistantMessage, ClaudeAgentOptions, CLINotFoundError, ResultMessage,
                                          TextBlock, create_sdk_mcp_server, query, tool)
        except ImportError as e:  # pragma: no cover
            raise DMError("the claude-agent-sdk package isn't installed") from e

        t0 = time.monotonic()
        sdk_tools = []
        names = []
        for spec in tools:
            def make(n):
                async def handler(args):
                    return {"content": [{"type": "text", "text": call_tool(n, args or {})}]}
                return handler
            sdk_tools.append(tool(spec["name"], spec["description"], spec["input_schema"])(make(spec["name"])))
            names.append(f"mcp__dm__{spec['name']}")
        server = create_sdk_mcp_server("dm", tools=sdk_tools)
        cwd = DATA_DIR / "claude_code_dm"
        cwd.mkdir(parents=True, exist_ok=True)
        options = ClaudeAgentOptions(
            system_prompt=system, mcp_servers={"dm": server}, allowed_tools=names, tools=[],
            model=self.model, max_turns=24, setting_sources=[], cwd=str(cwd), effort="medium",
        )
        res = EngineResult(text="", model=self.model)
        last_text = ""
        try:
            async for msg in query(prompt=user, options=options):
                if isinstance(msg, AssistantMessage):
                    t = "\n\n".join(b.text for b in msg.content if isinstance(b, TextBlock) and b.text.strip())
                    if t:
                        last_text = t
                elif isinstance(msg, ResultMessage):
                    if msg.is_error:
                        detail = str(msg.result or msg.subtype)
                        if "authenticat" in detail.lower() or "oauth" in detail.lower() or "log in" in detail.lower():
                            raise DMError("Claude Code on the host PC isn't signed in. On that PC, open a terminal, "
                                          "run `claude`, sign in, then press Retry DM")
                        raise DMError(f"Claude Code reported an error: {detail}")
                    res.text = (msg.result or last_text or "").strip()
                    res.cost_usd = msg.total_cost_usd
                    u = msg.usage or {}
                    res.input_tokens = int(u.get("input_tokens", 0) or 0)
                    res.output_tokens = int(u.get("output_tokens", 0) or 0)
                    res.cache_read_tokens = int(u.get("cache_read_input_tokens", 0) or 0)
                    res.cache_write_tokens = int(u.get("cache_creation_input_tokens", 0) or 0)
        except CLINotFoundError as e:
            raise DMError("Claude Code isn't installed on the host computer") from e
        except DMError:
            raise
        except Exception as e:  # the SDK raises several process/JSON errors
            raise DMError(f"Claude Code failed: {e}") from e
        if not res.text:
            res.text = last_text
        if not res.text:
            raise DMError("Claude Code returned no narration")
        res.duration_ms = int((time.monotonic() - t0) * 1000)
        return res
