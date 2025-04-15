from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import Dict, List, Optional
import uvicorn
import asyncio
import time
import pickle
from pathlib import Path

# Data Models
class Resource(BaseModel):
    uri: str
    description: str
    type: str
    version: str = "1.0.0"
    timestamp: float = time.time()

class AgentRegistration(BaseModel):
    url: str
    name: str
    skills: List[Dict]
    shared_resources: List[Resource] = []
    aira_capabilities: List[str] = []
    auth: Dict = {}
    last_seen: float = time.time()

# Hub Core
app = FastAPI(title="Aira Hub")
DB_FILE = "aira_db.pkl"

def load_db() -> Dict[str, AgentRegistration]:
    try:
        return pickle.load(open(DB_FILE, "rb"))
    except (FileNotFoundError, EOFError):
        return {}

def save_db(db: Dict[str, AgentRegistration]):
    pickle.dump(db, open(DB_FILE, "wb"))

db = load_db()

# Background Tasks
async def cleanup_task():
    while True:
        await asyncio.sleep(60)
        now = time.time()
        db = {k:v for k,v in db.items() if now - v.last_seen < 300}
        save_db(db)

@app.on_event("startup")
async def startup_event():
    BackgroundTasks().add_task(cleanup_task)

# API Endpoints
@app.post("/register")
async def register_agent(agent: AgentRegistration):
    agent.last_seen = time.time()
    db[agent.url] = agent
    save_db(db)
    return {"status": "registered", "agent_url": agent.url}

@app.post("/heartbeat/{agent_url}")
async def heartbeat(agent_url: str):
    if agent_url in db:
        db[agent_url].last_seen = time.time()
        save_db(db)
    return {"status": "ok"}

@app.get("/agents")
async def list_agents():
    return list(db.values())

@app.get("/discover")
async def discover_agents(skill: Optional[str] = None):
    agents = list(db.values())
    if skill:
        return [a for a in agents if skill in [s["id"] for s in a.skills]]
    return agents

@app.get("/status")
async def system_status():
    return {
        "agents": len(db),
        "resources": sum(len(a.shared_resources) for a in db.values())
    }

def run(port=8000):
    uvicorn.run(app, host="0.0.0.0", port=port)

if __name__ == "__main__":
    run()