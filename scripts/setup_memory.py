"""One-time setup: create LangGraph's checkpoint tables in the agent_memory schema."""

from tourquery.memory import get_checkpointer

if __name__ == "__main__":
    get_checkpointer().setup()
    print("Checkpoint tables ready in agent_memory.")
