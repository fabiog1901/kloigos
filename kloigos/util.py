import base64
import gzip
import json
import os
import shutil
import time

import ansible_runner
import psycopg
import yaml
from psycopg.rows import class_row
from psycopg.types.json import Jsonb, JsonbDumper
from psycopg_pool import ConnectionPool

from kloigos.models import Playbook, PortRange

from . import BASE_PORT, DB_URL, MAX_CPUS_PER_SERVER, PORTS_PER_CPU


class Dict2JsonbDumper(JsonbDumper):
    def dump(self, obj):
        return super().dump(Jsonb(obj))


# the pool starts connecting immediately.
psycopg.adapters.register_dumper(dict, Dict2JsonbDumper)
pool = ConnectionPool(DB_URL, kwargs={"autocommit": True})


def cpu_range_to_list_str(cpu_range: str):
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
) -> PortRange:
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

    return PortRange(start=port_start, end=port_end)


class MyRunner:

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

        with pool.connection() as conn:

            cur = conn.cursor()
            rs = cur.execute(
                """
                SELECT content
                FROM playbooks
                WHERE id = %s
                """,
                (playbook,),
            ).fetchone()

        # Decode the base64 string back to original YAML
        gzip.decompress(rs[0]).decode()
        pb: dict = yaml.safe_load(
            base64.b64decode(gzip.decompress(rs[0]).decode()).decode()
        )

        # create a new working directory

        job_id = time.time()
        os.mkdir(path=f"/tmp/job-{job_id}")

        # Execute the playbook
        try:
            runner = ansible_runner.run(
                quiet=False,
                verbosity=1,
                playbook=pb,
                private_data_dir=f"/tmp/job-{job_id}",
                extravars=extra_vars,
                event_handler=self.my_event_handler,
                status_handler=self.my_status_handler,
            )
        except Exception as e:
            print(f"Error running playbook: {e}")

        # rm -rf job-directory
        shutil.rmtree(f"/tmp/job-{job_id}", ignore_errors=True)

        return runner.status == "successful"
