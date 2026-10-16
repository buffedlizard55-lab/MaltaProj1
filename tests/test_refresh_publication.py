"""Publication-order regressions for concurrently refreshed derived boards.

These are workflow-structure checks, not a claim that live source values were verified.
Real branch/main runs separately exercise collection, rebuild, math, browser and push gates.
"""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parent.parent


class PublicationOrdering(unittest.TestCase):
    def test_executive_commits_only_its_evidence_before_rebasing(self):
        workflow = (ROOT / '.github/workflows/executive-5545dbb8.yml').read_text()
        publish = workflow.split('- name: Commit the validated snapshot', 1)[1]
        publish = publish.split('- name: Request a Pages build', 1)[0]
        before, after = publish.split('git pull --rebase=merges', 1)
        self.assertIn('git add executive/data executive/*.html', before)
        self.assertNotIn('console/data', before)
        self.assertNotIn('livelines/data', before)
        self.assertNotIn('valuepicks/data', before)
        for command in ('python scripts/228bb5bc_build.py', 'python livelines/build.py',
                        'python scripts/7759beef_build.py',
                        'python -m unittest tests.test_228bb5bc tests.test_457629c4 tests.test_7759beef -v'):
            self.assertIn(command, after)
            self.assertLess(after.index(command), after.index('git push origin'))
        self.assertIn('git add console/data', after)

    def test_live_publication_retries_and_regates_without_forcing_conflicts(self):
        workflow = (ROOT / '.github/workflows/livelines-457629c4.yml').read_text()
        publish = workflow.split('- name: Publish only if the invariants passed', 1)[1]
        publish = publish.split('- name: Request Pages rebuild', 1)[0]
        self.assertIn('for attempt in 1 2 3; do', publish)
        self.assertIn('git pull --rebase=merges', publish)
        self.assertIn('python3 livelines/build.py', publish)
        self.assertIn('python3 -m unittest tests.test_457629c4 -v', publish)
        self.assertLess(publish.index('git pull'), publish.index('python3 livelines/build.py'))
        self.assertLess(publish.index('python3 -m unittest'), publish.index('if git push'))
        self.assertIn('if git push origin "HEAD:${GITHUB_REF_NAME}"; then exit 0; fi', publish)
        self.assertIn('Concurrent source/output conflict; no work overwritten.', publish)
        self.assertIn('could not be published after three concurrent-push retries.', publish)
        self.assertNotIn('--force', publish)
        self.assertNotIn('checkout --theirs', publish)
        self.assertIn('exit 1', publish)
        self.assertIn('Request Pages rebuild after successful publication', workflow)


if __name__ == '__main__':
    unittest.main()
