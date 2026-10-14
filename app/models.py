from typing import Dict, List, Optional

from pydantic import BaseModel


class CompoundSummary(BaseModel):
    chebi_id: str
    wikidata_id: Optional[str] = None
    label: Optional[str] = None
    description: Optional[str] = None


class Compound(CompoundSummary):
    formula: Optional[str] = None
    mass: Optional[float] = None


class CompoundClass(BaseModel):
    wikidata_id: Optional[str] = None
    label: Optional[str] = None
    relation: str


class CrossReferences(BaseModel):
    chebi_id: str
    references: Dict[str, List[str]]


class SearchResult(BaseModel):
    query: str
    count: int
    results: List[CompoundSummary]
