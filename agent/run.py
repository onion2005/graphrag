"""CLI entry point: python -m agent.run "How does httpx handle authentication?" """
import sys

from langchain_core.messages import HumanMessage

from agent.graph import build_graph


def main():
    if len(sys.argv) > 1:
        question = " ".join(sys.argv[1:])
    else:
        question = input("Question: ")

    print(f"\n> {question}\n")
    print("Thinking...\n")

    graph = build_graph()
    result = graph.invoke({
        "messages": [HumanMessage(content=question)],
        "retrieval_count": 0,
    })

    # Print tool calls made
    tool_calls_made = 0
    for msg in result["messages"]:
        if hasattr(msg, "tool_calls") and msg.tool_calls:
            for tc in msg.tool_calls:
                tool_calls_made += 1
                print(f"  [{tool_calls_made}] Called {tc['name']}({tc['args']})")

    print(f"\n{'='*70}")
    print(f"  Retrieval passes: {result['retrieval_count']}")
    print(f"{'='*70}\n")

    # Print final answer
    final = result["messages"][-1]
    print(final.content)


if __name__ == "__main__":
    main()
