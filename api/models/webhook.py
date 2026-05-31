from typing import Optional
from pydantic import BaseModel

class GitHubRef(BaseModel):
    sha: str
    ref: str               #branch name     

class GitHubPullRequest (BaseModel):
    number:int
    head:GitHubRef
    base:GitHubRef
    diff_url:str

class GitHubRepository(BaseModel):
    full_name:str                      #"owner/repo"
    default_branch:str

class GitHubInstallation(BaseModel):
    id:int

class PullRequestEvent(BaseModel):
    action:str
    number:int
    pull_request:GitHubPullRequest
    repository:GitHubRepository
    installation:Optional[GitHubInstallation]=None

#used in the webhook route to filter
SUPPORTED_PR_ACTIONS={"opened","synchronize","reopened"}
