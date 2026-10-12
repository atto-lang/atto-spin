"""Low-overhead Linux process CPU/RSS sampling for repeatable Spin benchmarks."""
from pathlib import Path
import os
import threading
import time

def process_snapshot(pid):
    """One /proc/<pid>/stat sample; None for an exited/inaccessible process."""
    try:
        line = Path(f"/proc/{pid}/stat").read_text()
        rest = line.rsplit(") ", 1)[1].split()
        ticks = os.sysconf("SC_CLK_TCK")
        pagesize = os.sysconf("SC_PAGE_SIZE")
        return {
            "cpu_seconds": (int(rest[11]) + int(rest[12])) / ticks,
            "rss_bytes": int(rest[21]) * pagesize,
            "threads": int(rest[17]),
            "start_ticks": int(rest[19]),
        }
    except (OSError, ValueError, IndexError, KeyError):
        return None

def environment():
    result = {"affinity_cpu_count": len(os.sched_getaffinity(0)) if hasattr(os, "sched_getaffinity") else None}
    for name, path in {
        "cgroup_cpu_max": "/sys/fs/cgroup/cpu.max",
        "cgroup_memory_max": "/sys/fs/cgroup/memory.max",
    }.items():
        try:
            result[name] = Path(path).read_text().strip()
        except OSError:
            result[name] = None
    return result

def _aggregate(observations):
    if len(observations) < 2:
        return {"samples": len(observations), "process_cpu_percent": None,
                "peak_rss_bytes": max((s["rss_bytes"] for s in observations), default=None)}
    begin, end = observations[0], observations[-1]
    duration = end["t_monotonic"] - begin["t_monotonic"]
    if begin["start_ticks"] != end["start_ticks"] or duration <= 0:
        pct = None
    else:
        pct = round(100 * (end["cpu_seconds"] - begin["cpu_seconds"]) / duration, 2)
    return {
        "samples": len(observations),
        "measured_interval_s": round(duration, 3),
        "process_cpu_percent": pct,
        "peak_rss_bytes": max(s["rss_bytes"] for s in observations),
        "peak_threads": max(s["threads"] for s in observations),
    }

class ProcessSampler:
    def __init__(self, server_pid, interval_s=2.0):
        if interval_s <= 0:
            raise ValueError("sampling interval must be positive")
        self.server_pid = server_pid
        self.client_pid = os.getpid()
        self.interval_s = interval_s
        self.samples = {"server": [], "client": []}
        self.stop_event = threading.Event()
        self.thread = threading.Thread(target=self._record, name="spin-resource-sampler", daemon=True)
        self.started = False

    def _record(self):
        while True:
            t = time.monotonic()
            for role, pid in (("server", self.server_pid), ("client", self.client_pid)):
                observed = process_snapshot(pid)
                if observed is not None:
                    observed["t_monotonic"] = t
                    self.samples[role].append(observed)
            if self.stop_event.wait(self.interval_s):
                break

    def start(self):
        if self.started:
            raise RuntimeError("resource sampler already started")
        self.started = True
        self.thread.start()

    def finish(self):
        if not self.started:
            raise RuntimeError("resource sampler never started")
        self.stop_event.set()
        self.thread.join(timeout=5)
        result = {
            "scope": "Linux /proc CPU and resident memory; separate Python load-generator and Java server processes, both on one runner",
            "host": environment(),
            "summary": {role: _aggregate(series) for role, series in self.samples.items()},
        }
        return result
