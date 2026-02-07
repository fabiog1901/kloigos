import base64
import json
import logging
import os
import shutil
import time
from contextvars import ContextVar

import ansible_runner
import yaml

from kloigos.models import Playbook
from kloigos.repos.base import BaseRepo

from . import BASE_PORT, MAX_CPUS_PER_SERVER, PORTS_PER_CPU


def to_cpu_set(cpu_range: str):
    """
    Returns the cpu set from cpu_range

    Examples:
      "0-3"   -> "0,1,2,3"
      "0-7:2" -> "0,2,4,6"
    """
    start, end, step = parse_cpu_range(cpu_range)
    return ",".join([str(x) for x in list(range(start, end + 1, step))])


def parse_cpu_range(cpu_range: str) -> tuple[int, int, int]:
    """
    Parse start-end[:step] where step defaults to 1.

    Examples:
      "0-3"   -> (0, 3, 1)
      "0-7:2" -> (0, 7, 2)
    """
    s = cpu_range.strip()
    if not s:
        raise ValueError("cpu_range is empty")

    step = 1
    if ":" in s:
        s, step_s = s.split(":", 1)
        step = int(step_s)
        if step <= 0:
            raise ValueError(f"Invalid step: {step} in {cpu_range}")

    if "-" not in s:
        # If you truly only allow start-end[:step], you can remove this branch
        start = end = int(s)
        return start, end, step

    a, b = s.split("-", 1)
    start, end = int(a), int(b)
    if end < start:
        raise ValueError(f"Invalid cpu_range (end < start): {cpu_range}")

    return start, end, step


def ports_for_cpu_range(
    cpu_range: str,
) -> str:
    """
    Returns the PortRange for the given cpu_range.

    Examples:
      "0-3"   -> "1111-3333"
      "0-7:2" -> "45000-45600"
    """
    start, end, step = parse_cpu_range(cpu_range)

    if start < 0 or end >= MAX_CPUS_PER_SERVER:
        raise ValueError(
            f"cpu_range {cpu_range} out of bounds for total_cpus={MAX_CPUS_PER_SERVER}"
        )

    # Number of CPUs in start-end:step (inclusive)
    cpu_count = ((end - start) // step) + 1

    # Pack CPUs so that lane = (cpu % step) blocks are contiguous
    # group_size = ceil(total_cpus / step)
    group_size = (MAX_CPUS_PER_SERVER + step - 1) // step
    packed_start = (start // step) + (start % step) * group_size

    port_start = BASE_PORT + packed_start * PORTS_PER_CPU
    port_end = port_start + cpu_count * PORTS_PER_CPU - 1

    if port_end > 65535:
        raise ValueError(
            f"Port range exceeds 65535: {port_start}-{port_end}. "
            f"Choose a lower base_port, smaller ports_per_cpu, or reduce max units."
        )

    return f"{port_start}-{port_end}"


class MyRunner:
    def __init__(self, repo: BaseRepo, ssh_key: str) -> None:
        self.repo = repo
        self.ssh_key = ssh_key

    data = {}

    def my_status_handler(self, status, runner_config):
        return

    def my_event_handler(self, e):
        task_type = ""
        task_data = ""

        if e["event"] in [
            "verbose",
            "playbook_on_start",
            "playbook_on_no_hosts_matched",
            "runner_on_skipped",
            "runner_item_on_skipped",
            "runner_item_on_ok",
            "runner_on_start",
            "runner_retry",
            "playbook_on_include",
        ]:
            return

        elif e["event"] == "runner_on_ok":
            if e.get("event_data")["task"] == "Data":
                self.data = e["event_data"]["res"]["msg"]
            else:
                return

        elif e["event"] == "warning":
            task_type = "WARNING"
            task_data = e["stdout"]

        elif e["event"] == "error":
            task_type = "ERROR"
            task_data = e["stdout"]

        elif e["event"] == "playbook_on_play_start":
            task_type = f"PLAY [{e['event_data']['play']}]"

        elif e["event"] == "playbook_on_task_start":
            task_type = f"{e['event_data']['task']}"

        elif e["event"] == "runner_on_failed":
            task_data = f"fatal: [{e['event_data']['host']}]\n{json.dumps(e['event_data']['res']['msg'])}"

        elif e["event"] == "runner_item_on_failed":
            task_data = f"fatal: [{e['event_data']['host']}]\n{e['event_data']['res']['stderr']}"

        elif e["event"] == "playbook_on_stats":
            task_type = "PLAY RECAP"
            task_data = (
                f"ok: {e['event_data']['ok']} \nfailures: {e['event_data']['failures']}"
            )

        else:
            # new event not being catched
            task_type = e["event"]
            task_data = json.dumps(e)

        print(
            e["created"],
            task_type,
            task_data,
        )

    def launch_runner(
        self,
        playbook: Playbook,
        extra_vars: dict,
    ) -> bool:

        rs = self.repo.playbook_get_content(playbook)

        # Decode the base64 string back to original YAML
        pb: dict = yaml.safe_load(base64.b64decode(rs))

        # create a new working directory

        job_id = time.time()
        os.mkdir(path=f"/tmp/job-{job_id}")

        # Execute the playbook
        try:
            runner = ansible_runner.run(
                quiet=False,
                verbosity=2,
                playbook=pb,
                private_data_dir=f"/tmp/job-{job_id}",
                extravars=extra_vars,
                event_handler=self.my_event_handler,
                status_handler=self.my_status_handler,
                ssh_key=self.ssh_key,
            )

        except Exception:
            return False

        # rm -rf job-directory
        shutil.rmtree(f"/tmp/job-{job_id}", ignore_errors=True)

        return runner.status == "successful"


class RequestIDFilter(logging.Filter):
    def filter(self, record):
        record.request_id = request_id_ctx.get()
        return True


class ShorthandFormatter(logging.Formatter):
    # Mapping for all standard levels
    LEVEL_MAP = {
        "DEBUG": "D",
        "INFO": "I",
        "WARNING": "W",
        "ERROR": "E",
        "CRITICAL": "C",
    }

    def format(self, record):
        # Substitute the levelname with our shorthand
        original_levelname = record.levelname
        record.levelname = self.LEVEL_MAP.get(original_levelname, original_levelname)

        # Call the original formatter logic
        result = super().format(record)

        # Restore the original levelname in case other handlers use it
        record.levelname = original_levelname
        return result


# Define the variable once here
request_id_ctx: ContextVar[str] = ContextVar("request_id", default="")
