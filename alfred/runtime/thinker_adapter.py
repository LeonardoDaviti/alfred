"""ThinkerAdapter: wraps `pi` so the Dispatcher can fall back to the big model.

Default mode `per_call` spawns `pi -p "<message>"` per call. Slow (model
reload each invocation) but robust and trivial to test. An optional
persistent `rpc` mode keeps a long-lived Popen and exchanges JSON over
stdin/stdout; left in place but disabled by default until the Pi RPC
contract stabilises.
"""
from __future__ import annotations

import json
import subprocess
import time
from typing import Optional

from .types import DispatchResult


class ThinkerAdapter:
    def __init__(
        self,
        command: list[str],
        timeout_s: int,
        mode: str = "per_call",
    ) -> None:
        self.command = list(command)
        self.timeout_s = timeout_s
        self.mode = mode
        self.proc: Optional[subprocess.Popen] = None

    def start(self) -> None:
        if self.mode != "rpc":
            return
        # TODO: enable when Pi RPC contract stable
        self.proc = subprocess.Popen(
            self.command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        )

    def run(self, message: str) -> DispatchResult:
        if self.mode == "rpc":
            return self._run_rpc(message)
        return self._run_per_call(message)

    def _run_per_call(self, message: str) -> DispatchResult:
        # Use the first command token as the binary; ignore RPC flags from default.
        binary = self.command[0] if self.command else "pi"
        argv = [binary, "-p", message]
        t0 = time.perf_counter()
        try:
            cp = subprocess.run(
                argv,
                capture_output=True,
                text=True,
                timeout=self.timeout_s,
            )
        except FileNotFoundError:
            return DispatchResult(
                status="error",
                route_taken="thinker",
                pattern_id=None,
                output="",
                latency_ms=int((time.perf_counter() - t0) * 1000),
                reason="pi_not_available",
            )
        except subprocess.TimeoutExpired:
            return DispatchResult(
                status="failure",
                route_taken="thinker",
                pattern_id=None,
                output="",
                latency_ms=int((time.perf_counter() - t0) * 1000),
                reason=f"timeout_after_{self.timeout_s}s",
            )
        latency_ms = int((time.perf_counter() - t0) * 1000)
        if cp.returncode == 0:
            return DispatchResult(
                status="success",
                route_taken="thinker",
                pattern_id=None,
                output=cp.stdout,
                latency_ms=latency_ms,
                reason="",
            )
        return DispatchResult(
            status="failure",
            route_taken="thinker",
            pattern_id=None,
            output=cp.stdout,
            latency_ms=latency_ms,
            reason=(cp.stderr or "").strip()[:500],
        )

    # TODO: enable when Pi RPC contract stable
    def _run_rpc(self, message: str) -> DispatchResult:
        if self.proc is None:
            self.start()
        assert self.proc is not None and self.proc.stdin is not None and self.proc.stdout is not None
        t0 = time.perf_counter()
        try:
            self.proc.stdin.write(json.dumps({"message": message}) + "\n")
            self.proc.stdin.flush()
            line = self.proc.stdout.readline()
            resp = json.loads(line)
        except Exception as e:
            return DispatchResult(
                status="error",
                route_taken="thinker",
                pattern_id=None,
                output="",
                latency_ms=int((time.perf_counter() - t0) * 1000),
                reason=f"rpc_error: {e}",
            )
        latency_ms = int((time.perf_counter() - t0) * 1000)
        ok = bool(resp.get("ok"))
        return DispatchResult(
            status="success" if ok else "failure",
            route_taken="thinker",
            pattern_id=None,
            output=str(resp.get("output", "")),
            latency_ms=latency_ms,
            reason="" if ok else str(resp.get("error", ""))[:500],
        )

    def shutdown(self) -> None:
        if self.mode != "rpc" or self.proc is None:
            return
        try:
            self.proc.terminate()
            self.proc.wait(timeout=2)
        except Exception:
            try:
                self.proc.kill()
            except Exception:
                pass
        self.proc = None
