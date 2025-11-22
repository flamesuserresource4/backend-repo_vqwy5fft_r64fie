"""
Database Schemas for Crypto-Reward Puzzle App

Each Pydantic model represents a collection in MongoDB. The collection name
is the lowercase of the class name (e.g., User -> "user").
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Literal
from datetime import datetime

class User(BaseModel):
    username: str = Field(..., description="Unique username")
    ton_address: Optional[str] = Field(None, description="User-provided TON wallet address")
    referred_by: Optional[str] = Field(None, description="Referrer username if any")
    is_banned: bool = Field(False, description="Whether the user is banned")
    balance: int = Field(0, ge=0, description="Reward points balance (not real crypto)")

class Gamesettings(BaseModel):
    key: str
    value: str

class Gamesession(BaseModel):
    username: str
    game: Literal["word", "tiles", "parking"]
    score: int = Field(0, ge=0)
    duration_sec: int = Field(0, ge=0)
    created_at: Optional[datetime] = None

class Reward(BaseModel):
    username: str
    game: Literal["word", "tiles", "parking"]
    score: int = Field(..., ge=0)
    points_awarded: int = Field(..., ge=0)
    reason: str = Field(...)

class Withdrawalrequest(BaseModel):
    username: str
    ton_address: str
    points: int = Field(..., ge=1)
    status: Literal["pending", "approved", "rejected"] = "pending"
    note: Optional[str] = None

# Optional: basic anti-cheat log
class Anticheat(BaseModel):
    username: str
    game: str
    score: int
    flag: str
