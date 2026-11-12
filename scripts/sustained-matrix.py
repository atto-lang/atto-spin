#!/usr/bin/env python3
"""Execute real sustained HTTP/1.1 pooled-actor trials on one pinned Spin tree.

No generated or untracked Atto source: compile the canonical tracked fixture,
so the source checkout remains clean under Spin's fail-closed pin policy.
"""
import argparse
import asyncio
import hashlib
import json
import os
from pathlib import Path
import queue
import re
import subprocess
import sys
import threading
import time
from importlib.machinery import SourceFileLoader

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/sustained-pool-server.atto"
sys.path.insert(0, str(ROOT / "scripts"))
client = SourceFileLoader("spin_sustained_client", str(ROOT / "scripts/sustained-client.py")).load_module()
from process_resources import ProcessSampler


def declared_limits(source):
    """Read *committed* capacities; reject missing/duplicated markers."""
    pools = re.findall(r"/\* BENCHMARK_POOL \*/\s*(\d+)", source)
    caps = re.findall(r"/\* BENCHMARK_ADMISSION \*/\s*(\d+)", source)
    if len(pools) != 2 or len(caps) != 1 or pools[0] != pools[1]:
        raise ValueError("canonical Atto fixture must contain two equal pools and one admission capacity")
    return int(pools[0]), int(caps[0])


def read_runtime_counters(output):
    """Extract the real guest's final six-line POOL_COUNTERS receipt."""
    markers = [i for i, line in enumerate(output) if line == "POOL_COUNTERS"]
    if len(markers) != 1 or len(output) < markers[0] + 7:
        raise ValueError("missing, duplicated or truncated POOL_COUNTERS")
    values = output[markers[0] + 1:markers[0] + 7]
    if any(not re.fullmatch(r"\d+", x) for x in values):
        raise ValueError("malformed numeric POOL_COUNTERS")
    keys = ("pooled_created", "pooled_reused", "accepted", "completed", "rejected", "active_after_shutdown")
    return dict(zip(keys, map(int, values)))


def violations(result, runtime, pool_size):
    """Fail on actual HTTP errors, dishonest counting, or absent actor reuse."""
    failures = []
    if result.get("attempts", 0) < 2 or result["successes"] != result["attempts"]:
        failures.append("attempts and successes differ or too few requests")
    if result.get("errors") or result.get("status") != {"200": result["successes"]}:
        failures.append("invalid responses or non-200 HTTP status")
    if result.get("reused_connections", 0) <= 0:
        failures.append("no HTTP connection reuse measured")
    if runtime["active_after_shutdown"] != 0:
        failures.append("server retained active HTTP exchanges after shutdown")
    if runtime["rejected"] != 0:
        failures.append("server rejected HTTP admissions")
    # The fixture contains two pool routes: one shared and one isolated.
    if not 1 <= runtime["pooled_created"] <= 2 * pool_size:
        failures.append("pooled actor creation out of bound")
    if runtime["pooled_reused"] <= 0:
        failures.append("no guest pooled actor reuse observed")
    if runtime["accepted"] < result["successes"]:
        failures.append("server accepted fewer requests than client verified")
    return failures


def git(repo, *args):
    return subprocess.check_output(["git", "-C", str(repo), *args], text=True).strip()


def verify_sources():
    """The canonical source and Java/router pin guards must run before output."""
    subprocess.run(["bash", str(ROOT / "scripts/check-pins.sh")], cwd=ROOT, check=True)
    java_dir = Path(os.environ["ORESLANG_SOURCE_DIR"]).resolve(strict=True)
    return {
        "spin_head": git(ROOT, "rev-parse", "HEAD"),
        "spin_tree": git(ROOT, "rev-parse", "HEAD^{tree}"),
        "java_head": git(java_dir, "rev-parse", "HEAD"),
        "router_head": git(ROOT / "dependencies/http-routing", "rev-parse", "HEAD"),
    }


async def stop_server(port):
    reader, writer = await asyncio.wait_for(
        asyncio.open_connection("127.0.0.1", port), timeout=5)
    try:
        writer.write(b"GET /__stop HTTP/1.1\r\nHost: 127.0.0.1\r\nConnection: close\r\n\r\n")
        await asyncio.wait_for(writer.drain(), timeout=5)
        raw = await asyncio.wait_for(reader.read(), timeout=15)
        if not raw.startswith(b"HTTP/1.1 200"):
            raise RuntimeError("server graceful-stop HTTP reply was not 200")
    finally:
        writer.close()
        await writer.wait_closed()


def run_trial(args, concurrency, mode, env, output):
    tag = f"c{concurrency}-{mode}-pool{args.pool_size}"
    process = None
    lines = queue.Queue()
    stdout = []
    with (output / (tag + ".stderr.log")).open("w") as stderr:
        try:
            process = subprocess.Popen(
                [str(ROOT / "scripts/compiler.sh"), "--platform=server",
                 "--allow-net=127.0.0.1:0", str(FIXTURE)],
                cwd=ROOT, env=env, text=True, bufsize=1,
                stdout=subprocess.PIPE, stderr=stderr)
            def capture_stdout():
                for line in process.stdout:
                    item = line.strip()
                    stdout.append(item)
                    lines.put(item)
            thread = threading.Thread(target=capture_stdout, daemon=True)
            thread.start()
            deadline = time.monotonic() + 45
            while True:
                try:
                    msg = lines.get(timeout=.5)
                    if re.fullmatch(r"\d+", msg):
                        port = int(msg)
                        if not 1 <= port <= 65535:
                            raise RuntimeError("guest advertised invalid TCP port")
                        break
                except queue.Empty:
                    if process.poll() is not None:
                        raise RuntimeError("guest exited before port announcement")
                    if time.monotonic() >= deadline:
                        raise TimeoutError("guest did not advertise port within 45s")
            async def measure():
                sampler = ProcessSampler(process.pid, interval_s=2.0)
                sampler.start()
                try:
                    options = argparse.Namespace(
                        host="127.0.0.1", port=port, path="/pooled/" + mode,
                        mode=mode, concurrency=concurrency,
                        duration=args.duration, timeout=30)
                    result = await client.benchmark(options)
                finally:
                    resources = sampler.finish()
                    (output / (tag + ".resources.json")).write_text(json.dumps(resources, indent=2) + "\n")
                (output / (tag + ".json")).write_text(json.dumps(result, indent=2) + "\n")
                await stop_server(port)
                return result
            result = asyncio.run(measure())
            process.wait(timeout=30)
            thread.join(timeout=3)
            if process.returncode != 0:
                raise RuntimeError(f"guest exited {process.returncode}")
            runtime = read_runtime_counters(stdout)
            (output / (tag + ".runtime.json")).write_text(json.dumps(runtime, indent=2) + "\n")
            failed = violations(result, runtime, args.pool_size)
            if failed:
                raise AssertionError("; ".join(failed))
            print(json.dumps({"tag": tag, "result": "PASS", "attempts": result["attempts"],
                              "successes": result["successes"], "runtime": runtime}), flush=True)
        finally:
            (output / (tag + ".stdout.log")).write_text("\n".join(stdout) + "\n")
            if process and process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--concurrency", default="100,1000,10000")
    parser.add_argument("--modes", nargs="+", choices=("shared", "isolated"), default=["shared", "isolated"])
    parser.add_argument("--duration", type=float, default=180.0)
    parser.add_argument("--pool-size", type=int, default=100)
    parser.add_argument("--capacity", type=int, default=10000)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    try:
        concurrencies = [int(x) for x in args.concurrency.split(",")]
    except ValueError:
        parser.error("concurrency must be a comma-separated list of integers")
    if args.duration <= 0 or not concurrencies or len(set(concurrencies)) != len(concurrencies):
        parser.error("duration and unique concurrency values are required")
    if any(n < 1 or n > 10000 or n > args.capacity for n in concurrencies):
        parser.error("concurrency must be 1..10000 and no greater than admission capacity")
    if args.out.resolve().is_relative_to(ROOT.resolve()):
        parser.error("outputs must be outside source Git checkout")
    pool, capacity = declared_limits(FIXTURE.read_text())
    if args.pool_size != pool or args.capacity != capacity:
        parser.error("options must match tracked Atto fixture; edit/commit fixture and rerun exact-head CI to change limits")
    pins = verify_sources()
    args.out.mkdir(parents=True, exist_ok=False)
    env = os.environ.copy()
    env["JAVA_TOOL_OPTIONS"] = env.get("JAVA_TOOL_OPTIONS", "") + \
        " -Xms256m -Xmx3g -Djdk.httpserver.maxConnections=20000 -Dsun.net.httpserver.maxIdleConnections=20000"
    metadata = {
        **pins,
        "fixture_sha256": hashlib.sha256(FIXTURE.read_bytes()).hexdigest(),
        "client_sha256": hashlib.sha256((ROOT / "scripts/sustained-client.py").read_bytes()).hexdigest(),
        "config": {"duration_s": args.duration, "concurrencies": concurrencies,
                   "modes": args.modes, "pool_size": pool, "capacity": capacity},
        "java_options": env["JAVA_TOOL_OPTIONS"],
        "scope": "real Java interpreter guest on one Linux runner; no retries; no native-image/LLVM parity"
    }
    (args.out / "metadata.json").write_text(json.dumps(metadata, indent=2) + "\n")
    failed = []
    for concurrency in concurrencies:
        for mode in args.modes:
            try:
                run_trial(args, concurrency, mode, env, args.out)
            except Exception as exc:
                failed.append(f"c{concurrency}-{mode}: {type(exc).__name__}: {exc}")
                print(failed[-1], file=sys.stderr, flush=True)
    (args.out / "validation.json").write_text(json.dumps({"pass": not failed, "violations": failed}, indent=2) + "\n")
    if failed:
        raise SystemExit(1)
    print("SPIN_SUSTAINED_REAL_GUEST_PASS", flush=True)


if __name__ == "__main__":
    main()
