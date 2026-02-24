import asyncio
import logging
from app.agents.graph import init_checkpointer, run_workflow, close_checkpointer
from app.agents.state import AgentState

logging.basicConfig(level=logging.DEBUG)

async def test():
    print("Initializing tables...")
    await init_checkpointer()
    
    state: AgentState = {
        "user_id": "test_user",
        "user_request": "hello",
        "status": "analyzing",
        "messages": [],
        "participants": [],
        "retry_count": 0,
        "errors": []
    }
    
    try:
        print("Running workflow...")
        result = await run_workflow(state, "test_thread")
        print(f"Workflow finished. Success status: {result.get('status')}")
    except Exception as e:
        print(f"❌ Workflow failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test())
