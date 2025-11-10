from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi import FastAPI, HTTPException,Depends, status
from app.database import sessions_db

security = HTTPBearer()

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    token = credentials.credentials
    if token not in sessions_db:
        raise HTTPException(status_code=401, detail="Invalid token")
    return sessions_db[token]