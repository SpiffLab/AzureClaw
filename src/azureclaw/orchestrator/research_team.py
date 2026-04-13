"""MAF-backed research service — Magentic-One multi-agent team.

Production code. NOT exercised by ``pytest -m local`` because it
requires a real ``BaseChatClient`` with provider credentials. Tests
use ``StubResearchService`` instead.

The Magentic-One pattern (from Microsoft Research / AutoGen): a
**manager agent** dynamically picks which worker agent speaks next,
detects stalls, re-plans, and emits a final answer. Workers are:

- **Browser** — fetches web content. In this change the browser is a
  stub (instructions only, no MCP tool). The Playwright MCP integration
  lands in a later change.
- **Summarizer** — condenses content into a concise answer.

The manager orchestrates the conversation: "Browser, fetch this URL"
→ Browser responds → "Summarizer, condense the content" → Summarizer
responds → manager emits the final answer.
"""

from __future__ import annotations

from agent_framework import BaseChatClient, WorkflowAgent
from agent_framework.orchestrations import MagenticBuilder

BROWSER_PROMPT = """\
You are a Browser agent for AzureClaw. Your role is to fetch and read
web content when given a URL or search query.

NOTE: You do not yet have a real browser tool (Playwright MCP will be
added in a future change). For now, answer based on your training data
and clearly state when you cannot actually browse a live page.

When asked to fetch a URL, describe what the page would contain based
on your knowledge. When asked to search, provide relevant information.
"""

SUMMARIZER_PROMPT = """\
You are a Summarizer agent for AzureClaw. Your role is to take content
(fetched by the Browser agent or provided by the user) and produce a
clear, concise summary. Focus on the key points and keep it under 200
words unless asked for more detail.
"""

MANAGER_PROMPT = """\
You are the research team manager for AzureClaw. You coordinate a
Browser agent and a Summarizer agent to research topics and produce
summaries for the user.

Your workflow:
1. Ask the Browser to fetch relevant content for the user's query
2. Once the Browser responds, ask the Summarizer to condense the content
3. Review the summary and emit it as your final answer

Keep the team focused. If an agent stalls or gives an unhelpful answer,
re-direct with a clearer instruction. Aim for 2-4 rounds total.
"""


class MAFResearchService:
    """Wraps a Magentic-One workflow for collaborative research.

    The workflow is built once at construction time. Each ``research()``
    call creates a fresh ``WorkflowAgent`` to run the workflow without
    leaking conversation state between calls.
    """

    def __init__(self, chat_client: BaseChatClient) -> None:
        browser_agent = chat_client.as_agent(name="Browser", instructions=BROWSER_PROMPT)
        summarizer_agent = chat_client.as_agent(name="Summarizer", instructions=SUMMARIZER_PROMPT)
        manager_agent = chat_client.as_agent(name="ResearchManager", instructions=MANAGER_PROMPT)

        self._workflow = MagenticBuilder(
            participants=[browser_agent, summarizer_agent],
            manager_agent=manager_agent,
            max_stall_count=3,
            max_round_count=8,
        ).build()

    async def research(self, query: str, url: str | None) -> str:
        """Run the research team workflow and return the final answer."""
        task_text = f"Research: {query}"
        if url:
            task_text += f"\nURL to browse: {url}"

        agent = WorkflowAgent(workflow=self._workflow, name="ResearchTeam")
        response = await agent.run(task_text)
        return response.text or "No result from the research team."
