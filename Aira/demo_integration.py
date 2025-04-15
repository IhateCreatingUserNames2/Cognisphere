import asyncio
from aira_node import AiraNode
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

async def run_agent(hub_url: str, agent_name: str):
    node = AiraNode(hub_url, private_key=f"key-{agent_name}")
    try:
        # 1. Register
        await node.connect()
        logging.info(f"{agent_name}: Registered with hub")

        # 2. Share tools
        tools = [
            ("mcp://tools/memory-query", "Memory operations"),
            ("mcp://tools/emotion-analyzer", "Emotion detection")
        ]
        for uri, desc in tools:
            await node.share_mcp_tool(uri, desc)
            logging.info(f"{agent_name}: Shared {uri}")

        # 3. Continuous discovery
        while True:
            agents = await node.discover_agents()
            logging.info(f"{agent_name}: Found {len(agents)} agents")
            await asyncio.sleep(5)  # Check every 5 seconds

    except Exception as e:
        logging.error(f"{agent_name} failed: {str(e)}")
    finally:
        await node.close()

async def main():
    await asyncio.gather(
        run_agent("http://localhost:8000", "CognitiveAgent1"),
        run_agent("http://localhost:8000", "CognitiveAgent2")
    )

if __name__ == "__main__":
    asyncio.run(main())