"""Shared helpers for the simswitch tests: the shells the scripts run under,
stub commands, and a scratch directory."""
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

TOP = Path(__file__).resolve().parents[1]


def _works(argv):
    try:
        return subprocess.run(argv + ['-c', 'true'], capture_output=True, timeout=10).returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def shells():
    """[argv, ...] of the POSIX shells available here."""
    names = os.environ.get('SIMSWITCH_TEST_SHELLS', 'dash,bash,busybox sh,sh').split(',')
    found, seen = [], set()
    for n in names:
        argv = n.split()
        path = shutil.which(argv[0])
        if not path or not _works(argv):
            continue
        key = (os.path.realpath(path),) + tuple(argv[1:])
        if key not in seen:
            seen.add(key)
            found.append([path] + argv[1:])
    return found


class ShellTest(unittest.TestCase):
    """A scratch directory (self.tmp) with a stub directory first on PATH."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix='simswitch-test-'))
        self.stubs = self.tmp / 'stubs'
        self.stubs.mkdir()
        self.shells = shells()
        if not self.shells:
            self.skipTest('no POSIX shell')

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def stub(self, name, body):
        """A command NAME that runs BODY (sh); $STUBLOG is the scratch directory."""
        p = self.stubs / name
        p.write_text('#!/bin/sh\n' + body + '\n')
        p.chmod(0o755)

    def env(self, **extra):
        e = dict(os.environ)
        e['PATH'] = f'{self.stubs}{os.pathsep}{e.get("PATH", "")}'
        e['STUBLOG'] = str(self.tmp)
        e['LC_ALL'] = 'C'
        e.update({k: str(v) for k, v in extra.items()})
        return e

    def script(self, shell, path, *args, stdin=None, **env):
        return subprocess.run(shell + [str(path)] + [str(a) for a in args], input=stdin,
                              capture_output=True, text=True, env=self.env(**env), timeout=60)

    def each_shell(self):
        for s in self.shells:
            with self.subTest(shell=' '.join(s)):
                yield s
