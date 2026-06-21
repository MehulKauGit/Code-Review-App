from enum import Enum
from typing import Optional 
from pydantic import BaseModel,Field, model_validator

class FindingType(str,Enum):
    BUG= "bug"
    SECURITY = "security"
    STYLE = "style"
    SUGGESTION = "suggestion"

class Severity(str,Enum):
    CRITICAL ="critical"
    HIGH ="high"
    MEDIUM ="medium"
    LOW ="low"

class FindingSource(str,Enum):
    RUFF= "ruff"
    BANDIT ="bandit"
    SEMGREP = "semgrep"
    LLM = "llm"

class JobStatus(str ,Enum):
    QUEUED ="queued"
    RUNNING ="running"
    COMPLETE = "complete"
    FAILED = "failed"

#shape produced by every worker
class Finding(BaseModel):
    type :FindingType
    severity:Severity
    file :str
    line: Optional[int]=None
    message :str
    suggestion :Optional[str] =None
    source :FindingSource

#request shape

class ReviewRequest(BaseModel):
    diff:Optional[str]=Field(None,description="Unified diff string")
    content: Optional[str] =Field(None, description ="Full file content")
    filename:Optional[str] =None
    repo :Optional [str] =None        #"owner/repo"
    commit_sha:Optional[str] =None    # for idemptoency later


    @model_validator(mode="after")
    def must_have_diff_or_content(self) -> "ReviewRequest":
        if not self.diff and not self.content:
            raise ValueError("Provide either 'diff' or 'content'.")
        return self


#immediate returned responces after queing
class ReviewResponse(BaseModel):
    job_id :str
    status :JobStatus =JobStatus.QUEUED
    message: str ="Review queued."

#full result returned when polling GET /review / {job_id}

class ReviewResult(BaseModel):
    job_id :str
    status:JobStatus
    findings: list[Finding]=[]
    summary :dict [str,int] ={}     #{"total":5,"high":2, ...}
    error :Optional[str]=None    


#Two separate response models because they serve different purposes. 
# ReviewResponse is lightweight — you return it in milliseconds. 
# ReviewResult carries the full payload and may be empty until the job completes.