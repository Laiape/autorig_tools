"""Small, crash-readable build receipts; no geometry evaluation or GPU queries."""
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime, timezone
import json
from pathlib import Path
import time

_ACTIVE = ContextVar('autorig_build_timing', default=None)


def active():
    return _ACTIVE.get()


class BuildTiming:
    def __init__(self, asset, directory):
        stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
        self.path = Path(directory) / (stamp + '.buildtiming.json')
        self.data = dict(version=1, asset=asset, status='building', phases=[], calls=[])
        self.started = time.perf_counter()
        self.phase = None
        self.phase_started = self.started
        self.token = None

    def __enter__(self):
        if active() is not None:
            raise RuntimeError('A rig build is already running. Wait for it to finish.')
        self.token = _ACTIVE.set(self)
        self._save()
        return self

    def _save(self):
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps(self.data, indent=2), encoding='utf-8')
        except OSError:
            # A read-only asset must not turn diagnostic logging into a failure.
            pass

    def mark(self, label):
        now = time.perf_counter()
        if self.phase is not None:
            self.data['phases'].append(dict(name=self.phase, seconds=now-self.phase_started))
        self.phase, self.phase_started = label, now
        self.data['current_phase'] = label
        self.data['elapsed_seconds'] = now-self.started
        self._save()
        print('[AutoRig build] ' + label, flush=True)

    def __exit__(self, kind, error, tb):
        self.mark('Failed' if error else 'Complete')
        self.data.update(status='failed' if error else 'complete',
                         total_seconds=time.perf_counter()-self.started)
        if error:
            self.data['error'] = str(error)
        self._save()
        _ACTIVE.reset(self.token)


@contextmanager
def measure(label):
    recorder = active()
    started = time.perf_counter()
    if recorder:
        recorder.data['current_call'] = label
        recorder._save()
    try:
        yield
    finally:
        if recorder:
            recorder.data['calls'].append(dict(name=label, seconds=time.perf_counter()-started))
            recorder.data.pop('current_call', None)
            recorder._save()
