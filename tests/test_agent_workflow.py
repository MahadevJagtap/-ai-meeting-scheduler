import asyncio
import logging
from app.agents.graph import run_workflow
from app.agents.state import AgentState

async def test_agent():
    logging.basicConfig(level=logging.INFO)
    initial_state: AgentState = {
        "messages": [],
        "user_request": "Schedule a meeting with my dad today at 10:00",
        "user_id": "test_user_123",
        "participants": ["dad@example.com"],
        "status": "analyzing",
        "errors": [],
        "retry_count": 0,
    }
    
    try:
        print("Running workflow...")
        final_state = await run_workflow(initial_state, thread_id="test_user_123")
        print(f"Final Status: {final_state.get('status')}")
        print(f"Errors: {final_state.get('errors')}")
    except Exception as e:
        print(f"Workflow failed with exception: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_agent())
