import base64
import json
import os
import shutil
import sqlite3
import time

import ansible_runner
import yaml

from kloigos.models import Playbook

from . import SQLITE_DB


def cpu_range_to_list(s: str):
    """
    Convert from cpu_short syntax to a comma separated list

    Examples:

    "0-7:2" -> "0,2,4,6"

    "1-7:2" -> "1,3,5,7"

    "0-7"   -> "0,1,2,3,4,5,6,7"
    """

    # check whether the string is already a comma separated list
    if s.find(",") > 0:
        return s

    # check to see if the step syntax is used:
    if s.find(":") < 0:
        step = 1
        rng = s
    else:
        rng, step = s.split(":")
        step = int(step)

    start, end = rng.split("-")
    start = int(start)
    end = int(end)

    return ",".join([str(x) for x in list(range(start, end + 1, step))])


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

        with sqlite3.connect(SQLITE_DB) as conn:

            cur = conn.cursor()
            rs = cur.execute(
                """
                SELECT content
                FROM playbooks
                WHERE id = ?
                """,
                (playbook,),
            ).fetchone()

        # Decode the base64 string back to original YAML
        pb: dict = yaml.safe_load(base64.b64decode(rs[0]).decode())

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
