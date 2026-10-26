#!/usr/bin/env python3
"""Synthetic task-B applicability entrypoint tests; no real queue mutations."""
import csv
import importlib.util
import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

HERE = Path(__file__).resolve().parent


def module(name):
    spec = importlib.util.spec_from_file_location(name.replace('-', '_'), HERE/f'{name}.py')
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


class TaskBSessionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.queue = self.root/'queue.csv'
        self.fields = ['building_id', 'notice_excerpt', 'suggested_era', 'construction_era',
                       'phase_years', 'evidence', 'reviewer', 'reviewed_at', 'confidence']
        self.row = dict.fromkeys(self.fields, '')
        self.row.update(building_id='7', notice_excerpt='constructed in 1900', suggested_era='1893-1914')
        self.write_queue()

    def write_queue(self):
        with self.queue.open('w', newline='') as handle:
            writer = csv.DictWriter(handle, fieldnames=self.fields)
            writer.writeheader()
            writer.writerow(self.row)

    def test_legacy_session_unknown_and_explicit_positive_are_preserved(self):
        applier = module('apply-taskb-session')
        applier.QUEUE = self.queue
        for status in (None, '', 'yes'):
            self.write_queue()
            record = dict(building_id='7', construction_era='1893-1914',
                          fingerprint=applier.fingerprint(self.row))
            if status is not None:
                record['depicts_building'] = status
            session = self.root/'session.json'
            session.write_text(json.dumps({'schema': 'taskb-session/1', 'records': [record]}))
            with patch.object(sys, 'argv', ['apply-taskb-session.py', str(session)]), redirect_stdout(io.StringIO()):
                applier.main()
            with self.queue.open() as handle:
                row = next(csv.DictReader(handle))
            self.assertEqual(row['depicts_building'], status or '')

    def test_terminal_default_is_unknown_not_yes(self):
        cli = module('review-taskb-cli')
        cli.QUEUE = self.queue
        cli.INBOX = self.root/'no-images'
        out = self.root/'review.json'
        # reviewer, era, phase, unknown applicability, confidence, evidence
        replies = ['Reviewer', '3', '1900', '', '', '']
        with patch.object(sys, 'argv', ['review-taskb-cli.py', '--out', str(out)]), \
                patch('builtins.input', side_effect=replies), redirect_stdout(io.StringIO()):
            cli.main()
        record = json.loads(out.read_text())['records'][0]
        self.assertEqual(record['depicts_building'], '')
        self.assertEqual(record['construction_era'], '1893-1914')


if __name__ == '__main__':
    unittest.main()
