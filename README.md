# kloigos | κλοηγός

Ultrasimple micro CMDB for managing local servers

![dashboard](resources/dashboard.png)

## Setup

This is a very simple [FastAPI](https://fastapi.tiangolo.com/) app.

For local testing:

- clone the repo,
- install requirements using `poetry install`
- run the FastAPI server in dev mode using

    ```bash
    fastapi dev kloigos/main.py 
    ```

Consult the FastAPI docs for the production deployment guide.

## API endpoints

This API manages a pool of servers that can be provisioned, deprovisioned, and listed.  
It also exposes an HTML dashboard at the root path.

The full API docs are available at `/docs`

---

## Data Models

### HostDetails

Returned by several endpoints to describe a server:

```json
{
  "hostname": "host-001",
  "ansible_host": "10.0.0.1",
  "numa_node": 0,
  "service_name": "peru",
  "started_at": "2025-01-01T00:00:00Z",
  "owner": "anastasia",
  "status": "running"
}
```

Fields:

* `hostname` *(string, required)* – Unique name of the host.
* `ansible_host` *(string, required)* – IP or address used by Ansible.
* `numa_node` *(integer, required)* – NUMA node index the host belongs to.
* `service_name` *(string | null, required)* – Name of the service currently running on the host, or `null` if unused.
* `started_at` *(ISO 8601 | null, required)* – When the service was started on this host, or `null` if not applicable.
* `owner` *(string | null, required)* – Logical owner of the host (e.g. user or team), or `null`.
* `status` *(string, required)* – Current status (e.g. `running`, `free`, `stopped`).

---

## POST `/provision`

Provision (allocate) a new host for a given requester/name.

**Summary:** Provision resources.
**Method:** `POST`
**Content-Type:** `application/json`

### Request Body

Schema: `ProvisionRequest`

```json
{
  "name": "my-service"
}
```

* `name` *(string, required)* - your unique deployment ID.

### Responses

#### `200 OK`

Returns `HostDetails` for the newly provisioned host.

```json
{
  "hostname": "host-001",
  "ansible_host": "10.0.0.1",
  "numa_node": 0,
  "service_name": "peru",
  "started_at": "2025-01-01T00:00:00Z",
  "owner": "anastasia",
  "status": "running"
}
```

---

## POST `/deprovision`

Deprovision (release) a specific host.

**Summary:** Deprovision resources.
**Method:** `POST`
**Content-Type:** `application/json`

### Request Body

Schema: `DeprovisionRequest`

```json
{
  "hostname": "host-001"
}
```

* `hostname` *(string, required)* – Hostname to deprovision.

### Responses

#### `200 OK`

Empty JSON object on success:

```json
{}
```

---

## GET `/servers`

List all servers, optionally filtered by service or status.

**Summary:** List servers.
**Method:** `GET`

### Query Parameters (optional)

* `service_name` *(string, optional)* – Filter servers by `service_name`.
* `status` *(string, optional)* – Filter servers by `status`.

Examples:

* `GET /servers`
* `GET /servers?service_name=peru`
* `GET /servers?status=free`
* `GET /servers?service_name=peru&status=running`

### Responses

#### `200 OK`

Returns an array of `HostDetails`:

```json
[
  {
    "hostname": "host-001",
    "ansible_host": "10.0.0.1",
    "numa_node": 0,
    "service_name": "peru",
    "started_at": "2025-01-01T00:00:00Z",
    "owner": "anastasia",
    "status": "free"
  },
  {
    "hostname": "host-002",
    "ansible_host": "10.0.0.2",
    "numa_node": 1,
    "service_name": "peru",
    "started_at": null,
    "owner": null,
    "status": "free"
  }
]
```

---

## Example usage with Ansible

This is a simple Ansible Playbook to show how to
provision local servers from `kloigos` and
to dynamically add them to the Ansible inventory.

Once they are in the Ansible inventory, you can use in the same way
as you use server instances returned by the AWS EC2 service.

```yaml
---
- name: PROVISION VMS
  hosts: localhost
  connection: local
  gather_facts: no
  become: no
  vars:
    deployment_id: "c555"
    kloigos_server: "http://127.0.0.1:8000"
  tasks:
    - name: provision local instance
      ansible.builtin.uri:
        url: "{{ kloigos_server }}/provision"
        method: POST
        body_format: json
        body:
          name: "{{ deployment_id }}"
        status_code: 200
        headers:
          Content-Type: application/json
          accept: application/json
      loop: "{{ range(3) }}"
      register: instances

    - name: Build ansible inventory dynamically
      add_host:
        name: "{{ item.json.hostname }}"
        ansible_user: ubuntu
        ansible_host: "{{ item.json.ansible_host }}"
        numa_node: "{{ item.json.numa_node }}"

        groups: crdb

      loop: "{{ instances.results }}"

    - name: save simplified list of hosts
      copy:
        content: |
          {% for item in groups %}
          [{{item}}]
          {% for entry in groups[item] %}
          {{ entry }}   {{ "{:18}".format(hostvars[entry].ansible_host) }} {{ hostvars[entry].numa_node }}
          {% endfor %}

          {% endfor %}
        dest: "{{ deployment_id }}.simple.ini"
```

Here, I save the content to a file `c555.simple.ini`

```text
[all]
srv3_n1   10.0.0.3           1
srv3_n2   10.0.0.3           2
srv3_n3   10.0.0.3           3

[ungrouped]

[crdb]
srv3_n1   10.0.0.3           1
srv3_n2   10.0.0.3           2
srv3_n3   10.0.0.3           3

```

From now on, I can use ansible to access those servers.
