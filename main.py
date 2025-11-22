import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime, timezone

from database import db, create_document, get_documents

app = FastAPI(title="Crypto-Reward Puzzle API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -------------------- Models (request bodies) --------------------
class RegisterBody(BaseModel):
    username: str
    ton_address: Optional[str] = None
    referred_by: Optional[str] = None

class StartSessionBody(BaseModel):
    username: str
    game: str  # "word" | "tiles" | "parking"

class SubmitScoreBody(BaseModel):
    username: str
    game: str
    score: int
    duration_sec: int

class WithdrawalBody(BaseModel):
    username: str
    ton_address: str
    points: int

# -------------------- Helpers --------------------

def collection(name: str):
    return db[name]

def ensure_user(username: str):
    u = collection("user").find_one({"username": username})
    if not u:
        raise HTTPException(status_code=404, detail="User not found")
    return u

# Simple points function: 1 point per 10 score, capped per session
def points_for(game: str, score: int) -> int:
    base = max(0, score // 10)
    cap_map = {"word": 100, "tiles": 100, "parking": 100}
    return min(base, cap_map.get(game, 100))

# -------------------- Routes --------------------

@app.get("/")
def root():
    return {"message": "Crypto-Reward Puzzle API running"}

@app.get("/test")
def test_database():
    response = {
        "backend": "✅ Running",
        "database": "❌ Not Available",
        "database_url": None,
        "database_name": None,
        "connection_status": "Not Connected",
        "collections": []
    }
    try:
        if db is not None:
            response["database"] = "✅ Available"
            response["database_url"] = "✅ Set" if os.getenv("DATABASE_URL") else "❌ Not Set"
            response["database_name"] = db.name
            response["connection_status"] = "Connected"
            try:
                response["collections"] = db.list_collection_names()[:10]
                response["database"] = "✅ Connected & Working"
            except Exception as e:
                response["database"] = f"⚠️  Connected but Error: {str(e)[:50]}"
        else:
            response["database"] = "⚠️  Available but not initialized"
    except Exception as e:
        response["database"] = f"❌ Error: {str(e)[:50]}"
    return response

@app.post("/api/register")
def register(body: RegisterBody):
    if collection("user").find_one({"username": body.username}):
        return {"ok": True, "message": "User exists"}
    doc = {
        "username": body.username,
        "ton_address": body.ton_address,
        "referred_by": body.referred_by,
        "is_banned": False,
        "balance": 0,
        "created_at": datetime.now(timezone.utc),
    }
    collection("user").insert_one(doc)
    return {"ok": True}

@app.post("/api/start-session")
def start_session(body: StartSessionBody):
    user = ensure_user(body.username)
    if user.get("is_banned"):
        raise HTTPException(403, detail="User banned")
    sess = {
        "username": body.username,
        "game": body.game,
        "score": 0,
        "duration_sec": 0,
        "created_at": datetime.now(timezone.utc),
    }
    create_document("gamesession", sess)
    return {"ok": True}

@app.post("/api/submit-score")
def submit_score(body: SubmitScoreBody):
    user = ensure_user(body.username)
    if user.get("is_banned"):
        raise HTTPException(403, detail="User banned")
    pts = points_for(body.game, body.score)
    reward_doc = {
        "username": body.username,
        "game": body.game,
        "score": body.score,
        "points_awarded": pts,
        "reason": "session_completed",
        "created_at": datetime.now(timezone.utc),
    }
    create_document("reward", reward_doc)
    # increment balance
    collection("user").update_one({"username": body.username}, {"$inc": {"balance": pts}})
    return {"ok": True, "awarded": pts}

@app.get("/api/me/{username}")
def me(username: str):
    user = ensure_user(username)
    rewards = get_documents("reward", {"username": username}, limit=50)
    return {
        "username": user["username"],
        "balance": user.get("balance", 0),
        "ton_address": user.get("ton_address"),
        "rewards": rewards
    }

@app.post("/api/withdraw")
def request_withdrawal(body: WithdrawalBody):
    user = ensure_user(body.username)
    if body.points <= 0 or body.points > user.get("balance", 0):
        raise HTTPException(400, detail="Invalid amount")
    req = {
        "username": body.username,
        "ton_address": body.ton_address,
        "points": body.points,
        "status": "pending",
        "created_at": datetime.now(timezone.utc),
    }
    create_document("withdrawalrequest", req)
    # Lock points by deducting immediately
    collection("user").update_one({"username": body.username}, {"$inc": {"balance": -body.points}})
    return {"ok": True, "status": "pending"}

# Simple leaderboard (sum of rewards points)
@app.get("/api/leaderboard")
def leaderboard(limit: int = 20):
    pipeline = [
        {"$group": {"_id": "$username", "total": {"$sum": "$points_awarded"}}},
        {"$sort": {"total": -1}},
        {"$limit": limit},
    ]
    results = list(collection("reward").aggregate(pipeline))
    return [{"username": r["_id"], "points": r["total"]} for r in results]

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
