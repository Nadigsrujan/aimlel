"""Version-one API responses shared by OpenAPI and runtime validation."""

from typing import Any, Dict, List, Literal
from pydantic import BaseModel, ConfigDict, Field


class ExtensibleModel(BaseModel):
    model_config = ConfigDict(extra="allow")


class Evidence(ExtensibleModel):
    import_path: List[str] = Field(default_factory=list)
    past_commits: List[str] = Field(default_factory=list)


class Candidate(ExtensibleModel):
    path: str
    score: float
    channels: List[str] = Field(default_factory=list)
    features: Dict[str, Any] = Field(default_factory=dict)
    evidence: Evidence = Field(default_factory=Evidence)


class Graph(ExtensibleModel):
    nodes: List[Dict[str, Any]]
    edges: List[Dict[str, Any]]


class AnalysisResponse(ExtensibleModel):
    schema_version: Literal[1]
    repo: str
    graph_revision: str = Field(pattern="^[0-9a-f]{40}$")
    seed: str
    ranker: str
    score_is_probability: Literal[False]
    candidate_count: int = Field(ge=0)
    candidates: List[Candidate]
    recommended_tests: List[Candidate] = Field(default_factory=list)
    graph: Graph
    parse_failures: List[Dict[str, Any]]
    provenance: Dict[str, Any]


class CatalogEntry(ExtensibleModel):
    repo: str
    revision: str
    split: Literal["train", "validation", "test", "submitted"]
    source_url: str
    deletable: bool
    available: bool
    summary: Dict[str, Any]


class SourceResponse(BaseModel):
    repo: str
    revision: str
    path: str
    start: int = Field(ge=1)
    total_lines: int = Field(ge=0)
    lines: List[str]


class JobStatus(ExtensibleModel):
    job: str
    repo: str
    status: Literal["running", "cancelling", "processed", "failed", "cancelled"]
    progress: Dict[str, Any] = Field(default_factory=dict)
