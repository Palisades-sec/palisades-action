from typing import Optional

from pydantic import BaseModel


class GitHubIssue(BaseModel):
    url: str
    repository_url: str
    labels_url: str
    comments_url: str
    events_url: str
    html_url: str
    id: int
    node_id: str
    number: int
    title: str
    user: dict
    labels: list
    state: str
    locked: bool
    assignee: Optional[str] = None
    assignees: list
    milestone: Optional[dict] = None
    comments: int
    created_at: str
    updated_at: str
    closed_at: Optional[str] = None
    author_association: str
    active_lock_reason: Optional[str] = None
    body: str
    reactions: dict
    timeline_url: str
    performed_via_github_app: Optional[str] = None
    state_reason: Optional[str] = None
