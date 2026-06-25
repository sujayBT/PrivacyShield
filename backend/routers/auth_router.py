from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from fastapi.security import OAuth2PasswordRequestForm
from backend import models, schemas, auth
from backend.database import get_db
from datetime import timedelta
from pydantic import BaseModel

router = APIRouter(prefix="/api/auth", tags=["auth"])

@router.post("/register", response_model=schemas.User)
def register(user: schemas.UserCreate, db: Session = Depends(get_db)):
    db_user = db.query(models.User).filter(models.User.username == user.username).first()
    if db_user:
        raise HTTPException(status_code=400, detail="Username already registered")
    
    hashed_password = auth.get_password_hash(user.password)
    new_user = models.User(username=user.username, hashed_password=hashed_password)
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user

@router.post("/login", response_model=schemas.Token)
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.username == form_data.username).first()
    if not user or not auth.verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    access_token_expires = timedelta(minutes=auth.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = auth.create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}


# ── Change / Reset Password ────────────────────────────────────────────────────
class ChangePasswordRequest(BaseModel):
    username: str
    old_password: str = ""   # optional — empty means Forgot Password flow
    new_password: str

@router.post("/change-password")
def change_password(payload: ChangePasswordRequest, db: Session = Depends(get_db)):
    """
    Reset password.
    - Forgot Password flow: old_password is empty — just verify username exists.
    - Change Password flow: old_password must match current password.
    """
    user = db.query(models.User).filter(models.User.username == payload.username).first()
    if not user:
        raise HTTPException(status_code=404, detail="Username not found. Please check and try again.")

    # Only verify old password when it's provided (Change Password flow)
    if payload.old_password:
        if not auth.verify_password(payload.old_password, user.hashed_password):
            raise HTTPException(status_code=401, detail="Current password is incorrect.")
        if payload.old_password == payload.new_password:
            raise HTTPException(status_code=422, detail="New password must be different from your current password.")

    if len(payload.new_password) < 6:
        raise HTTPException(status_code=422, detail="New password must be at least 6 characters.")

    user.hashed_password = auth.get_password_hash(payload.new_password)
    db.commit()
    return {"message": "Password updated successfully. Please sign in with your new password."}
