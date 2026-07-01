from __future__ import annotations
import unittest
from jsonl_diagram_core.proposal_template import make_worktree_proposal, validate_worktree_proposal
class WorktreeProposalTemplateTest(unittest.TestCase):
    def test_template_requires_tests_and_evidence(self):
        p=make_worktree_proposal(proposal_id="p",purpose="x",scope="y",tests=["t"],evidence=["e"],risks=["r"])
        self.assertEqual(p["status"],"ready")
        with self.assertRaises(ValueError): validate_worktree_proposal({"id":"bad"})
