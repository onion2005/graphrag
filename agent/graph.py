from typing import Annotated, TypedDict

from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode

import config
from agent.tools import search_code, search_code_with_graph, read_symbol_source
from agent.prompts import SYSTEM_PROMPT

MAX_RETRIEVAL_PASSES = 3

tools = [search_code, search_code_with_graph, read_symbol_source]


class AgentState(TypedDict):
    messages: Annotated[list, add_messages]
    retrieval_count: int


def build_graph():
    llm = ChatOpenAI(
        model=config.LLM_MODEL,
        temperature=config.LLM_TEMPERATURE,
        max_tokens=4096,
        base_url=config.LLM_BASE_URL,
        api_key=config.LLM_API_KEY,
    )
    llm_with_tools = llm.bind_tools(tools)

    def agent_node(state: AgentState) -> dict:
        messages = [SystemMessage(content=SYSTEM_PROMPT)] + state["messages"]
        response = llm_with_tools.invoke(messages)
        return {"messages": [response]}

    tool_node = ToolNode(tools)

    def tools_node(state: AgentState) -> dict:
        result = tool_node.invoke(state)
        result["retrieval_count"] = state.get("retrieval_count", 0) + 1
        return result

    def summarize_node(state: AgentState) -> dict:
        """Force a text answer when loop cap is reached."""
        from langchain_core.messages import AIMessage, ToolMessage
        # Build clean message list: drop all tool_use and tool_result messages
        # so the unbound LLM doesn't hit the tool_use/tool_result pairing error.
        clean = [SystemMessage(content=SYSTEM_PROMPT)]
        for msg in state["messages"]:
            if isinstance(msg, ToolMessage):
                continue
            if hasattr(msg, "tool_calls") and msg.tool_calls:
                # Extract only text from content (strip tool_use blocks)
                content = msg.content
                if isinstance(content, list):
                    text_parts = [
                        b["text"] for b in content
                        if isinstance(b, dict) and b.get("type") == "text"
                    ]
                    content = "\n".join(text_parts) if text_parts else ""
                clean.append(AIMessage(content=content or ""))
            else:
                clean.append(msg)
        clean.append(HumanMessage(
            content="You've reached the maximum number of retrieval passes. "
                    "Please answer the question now with the information you have."
        ))
        response = llm.invoke(clean)  # no tools bound
        return {"messages": [response]}

    def should_continue(state: AgentState) -> str:
        last = state["messages"][-1]
        if hasattr(last, "tool_calls") and last.tool_calls:
            if state.get("retrieval_count", 0) < MAX_RETRIEVAL_PASSES:
                return "tools"
            return "summarize"
        return END

    graph = StateGraph(AgentState)
    graph.add_node("agent", agent_node)
    graph.add_node("tools", tools_node)
    graph.add_node("summarize", summarize_node)
    graph.set_entry_point("agent")
    graph.add_conditional_edges("agent", should_continue, {
        "tools": "tools",
        "summarize": "summarize",
        END: END,
    })
    graph.add_edge("tools", "agent")
    graph.add_edge("summarize", END)

    return graph.compile()
