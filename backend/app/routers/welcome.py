"""Welcome banner endpoints: public feed + the member's own banner choice."""
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field

from .. import welcome
from ..deps import get_current_user

router = APIRouter(prefix="/api/welcome", tags=["welcome"])


class ChoiceIn(BaseModel):
    # "named" | "anonymous" | "optout" | "none" (no announcement). The choice
    # itself is onboarding's first question; unset means the member has not
    # chosen yet, which defaults to no announcement.
    choice: str
    display_name: str | None = Field(default=None, max_length=80)


@router.get("/feed")
async def get_feed(request: Request, response: Response):
    """Recent welcome announcements, newest first, capped and cacheable.

    Public by design: it only ever returns the sanitized public shape from
    welcome.public_announcement(). An empty list is honest — the banner then
    shows the parade plus a general "we're happy you're here".
    """
    response.headers["Cache-Control"] = f"public, max-age={welcome.CACHE_MAX_AGE_SECONDS}"
    return {"announcements": await welcome.feed(request.app.state.db)}


@router.get("/me")
async def my_choice(user=Depends(get_current_user)):
    # Own record only: the stored choice and the sanitized display name.
    return {"welcome_choice": user.get("welcome_choice"),
            "welcome_display_name": user.get("welcome_display_name")}


@router.put("/choice")
async def put_choice(body: ChoiceIn, request: Request, user=Depends(get_current_user)):
    """Set or change the banner choice; later opt-outs apply immediately."""
    if body.choice not in (*welcome.CHOICES, "none"):
        raise HTTPException(422, "invalid welcome choice")
    choice = None if body.choice == "none" else body.choice
    db = request.app.state.db
    display = welcome.sanitize_display_name(body.display_name)
    await db.users.update_one({"_id": user["_id"]},
                              {"$set": {"welcome_choice": choice, "welcome_display_name": display}})
    fresh = await db.users.find_one({"_id": user["_id"]})
    doc = await welcome.set_welcome_choice(db, fresh, choice, body.display_name)
    return {"welcome_choice": choice,
            "announcement": welcome.public_announcement(doc) if doc else None}
