from __future__ import annotations
from typing import Any
JsonObj=dict[str,Any]; REQUIRED={"id","purpose","scope","tests","evidence","risks","status"}
def make_worktree_proposal(*,proposal_id:str,purpose:str,scope:str,tests:list[str],evidence:list[str],risks:list[str],status:str="ready") -> JsonObj:
    p={"id":proposal_id,"purpose":purpose,"scope":scope,"tests":tests,"evidence":evidence,"risks":risks,"status":status}; validate_worktree_proposal(p); return p
def validate_worktree_proposal(proposal: JsonObj) -> None:
    missing=sorted(REQUIRED-set(proposal))
    if missing: raise ValueError("proposal missing: "+", ".join(missing))
    if not proposal["tests"] or not proposal["evidence"]: raise ValueError("proposal requires tests and evidence")
