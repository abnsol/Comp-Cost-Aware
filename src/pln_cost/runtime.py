"""Bounded Python subprocess interface to existing, unmodified PeTTa/PLN.

This is a correctness runner. Its wall timeout is a safety limit, not an
experimental CPU budget. There is no cost estimator or query CPU instrumentation.
"""
import json
import os
from pathlib import Path
import signal
import subprocess


def checked_output(command, **kwargs):
    return subprocess.check_output(command, text=True, timeout=10, **kwargs).strip()


class Runtime:
    def __init__(self, project, config_path):
        self.project = Path(project).resolve()
        self.config = json.loads(Path(config_path).read_text())
        # Paths in config are relative to the project, not the caller's cwd.
        self.context = (self.project / self.config["context_root"]).resolve()
        self.pln = self.context / "repos/PLN"
        self.petta = self.context / "repos/PeTTa"
        self.swipl = self.context / "runtime/swipl/bin/swipl"

    def verify(self):
        """Fail before execution if the external source contract has changed."""
        result = {}
        for name, directory in (("pln", self.pln), ("petta", self.petta)):
            commit = checked_output(["git", "-C", str(directory), "rev-parse", "HEAD"])
            status = checked_output(["git", "-C", str(directory), "status", "--porcelain"])
            if commit != self.config[f"{name}_commit"] or status:
                raise RuntimeError(f"{name} must be at the configured commit and clean")
            result[name] = {"path": str(directory), "commit": commit, "clean": True}
        version = checked_output([str(self.swipl), "--version"])
        if version != self.config["swipl_version"]:
            raise RuntimeError(f"Unexpected SWI runtime: {version}")
        result["swipl"] = version
        return result

    def run(self, fixture, *, preload_pln=False, library_path=None):
        """Optionally load a generated instrumented library instead of the original.

        The caller must establish its source provenance and behavioural parity.
        Merely using library_path does not validate instrumentation.
        """
        if library_path is not None and not preload_pln:
            raise ValueError("library_path requires preload_pln=True")
        env = os.environ.copy()
        site = next((self.context / "runtime/venv/lib").glob("python*/site-packages"))
        env.update(PYTHONDONTWRITEBYTECODE="1", PYTHONPATH=str(site))
        command = [str(self.swipl), "--stack_limit=1g", "-q", "-s",
                   str(self.petta / "src/main.pl")]
        if preload_pln:
            source_file = self.pln / "lib_pln.metta" if library_path is None else Path(library_path).resolve()
            source = str(source_file).replace("\\", "\\\\").replace("'", "\\'")
            command += ["-g", f"load_metta_file('{source}',_)"]
        command += ["--", str(Path(fixture).resolve()), "--silent"]
        # The native example's git-import finds the already verified repos here;
        # it does not fetch when that directory exists. We install nothing.
        child = subprocess.Popen(command, cwd=self.context, env=env, text=True,
                                 stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                 start_new_session=True)
        timed_out = False
        try:
            stdout, stderr = child.communicate(timeout=self.config["timeout_seconds"])
        except subprocess.TimeoutExpired:
            timed_out = True
            os.killpg(child.pid, signal.SIGKILL)
            stdout, stderr = child.communicate()
        return {"command": command, "cwd": str(self.context),
                "returncode": child.returncode, "timed_out": timed_out,
                "stdout": stdout, "stderr": stderr}
