"""
Phase 14 — Background Agent Router
"""
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import List, Optional
from backend.auth import get_current_user
from backend.models import User
import backend.services.background_agent as agent_svc

router = APIRouter(prefix="/api/agent", tags=["Background Agent"])


class StartAgentRequest(BaseModel):
    folders: Optional[List[str]] = []


class FolderRequest(BaseModel):
    path: str


@router.get("/status")
def get_agent_status(current_user: User = Depends(get_current_user)):
    return agent_svc.get_status()


@router.post("/start")
def start_agent(req: StartAgentRequest, current_user: User = Depends(get_current_user)):
    return agent_svc.start_agent(req.folders or [])


@router.post("/stop")
def stop_agent(current_user: User = Depends(get_current_user)):
    return agent_svc.stop_agent()


@router.post("/pause")
def pause_agent(current_user: User = Depends(get_current_user)):
    return agent_svc.pause_agent()


@router.delete("/events")
def clear_events(current_user: User = Depends(get_current_user)):
    return agent_svc.clear_events()


@router.get("/folders")
def get_all_folders(current_user: User = Depends(get_current_user)):
    """Return all system folders with watched/exists status."""
    return agent_svc.get_all_candidate_folders()


@router.post("/folders/add")
def add_folder(req: FolderRequest, current_user: User = Depends(get_current_user)):
    """Add a folder to the watch list."""
    return agent_svc.add_folder(req.path)


@router.post("/folders/remove")
def remove_folder(req: FolderRequest, current_user: User = Depends(get_current_user)):
    """Remove a folder from the watch list."""
    return agent_svc.remove_folder(req.path)
