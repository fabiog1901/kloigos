import json
import os
import shutil
import time

import ansible_runner
import yaml


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

    def launch_runner(self, playbook_name: str, extra_vars: dict):

        with open(playbook_name, "r") as f:
            playbook = yaml.safe_load(f.read())

        # create a new working directory

        job_id = time.time()
        os.mkdir(path=f"/tmp/job-{job_id}")

        # Execute the playbook
        try:
            runner = ansible_runner.run(
                quiet=False,
                verbosity=1,
                playbook=playbook,
                private_data_dir=f"/tmp/job-{job_id}",
                extravars=extra_vars,
                event_handler=self.my_event_handler,
                status_handler=self.my_status_handler,
            )
        except Exception as e:
            print(f"Error running playbook: {e}")

        # rm -rf job-directory
        shutil.rmtree(f"/tmp/job-{job_id}", ignore_errors=True)

        return runner.status
