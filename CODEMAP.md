# Code Map

<!-- GENERATED FILE: DO NOT EDIT -->

This file is a deterministic map of the Python package surface in this repository.
Regenerate it after structural code changes with:

```bash
python tools/codemap.py --write
```

## Project

- Name: `kloigos`
- Package roots: `kloigos`

## Entry Points

- `kloigos` -> `cpkit.cli:main`

## Packages

| Package | Modules | Classes | Functions | Routes |
| --- | ---: | ---: | ---: | ---: |
| `kloigos` | 16 | 27 | 11 | 7 |

## API Routes

| Method | Path | Handler | Response Model |
| --- | --- | --- | --- |
| `GET` | `/compute_units` | `kloigos.api.compute_unit.list_compute_units` | `list[ComputeUnitOverview]` |
| `POST` | `/compute_units/allocate` | `kloigos.api.compute_unit.allocate` | `str` |
| `DELETE` | `/compute_units/deallocate/{compute_id}` | `kloigos.api.compute_unit.deallocate` | `-` |
| `GET` | `/servers` | `kloigos.api.admin.servers.list_servers` | `list[ServerInDB]` |
| `POST` | `/servers` | `kloigos.api.admin.servers.init_server` | `-` |
| `PUT` | `/servers` | `kloigos.api.admin.servers.decommission_server` | `-` |
| `DELETE` | `/servers/{hostname}` | `kloigos.api.admin.servers.delete_server` | `-` |

## Command Handlers

- none found

## Modules

| File | Public Surface |
| --- | --- |
| `kloigos/__init__.py` | no public surface |
| `kloigos/api/__init__.py` | no public surface |
| `kloigos/api/admin/__init__.py` | no public surface |
| `kloigos/api/admin/servers.py` | functions: list_servers, init_server, decommission_server, delete_server; routes: 4 |
| `kloigos/api/compute_unit.py` | functions: allocate, deallocate, list_compute_units; routes: 3 |
| `kloigos/dep.py` | functions: get_compute_unit_service, get_admin_service |
| `kloigos/main.py` | no public surface |
| `kloigos/models.py` | classes: AutoNameStrEnum, NoFreeComputeUnitError, ComputeUnitNotFoundError, ComputeUnitStateError, ComputeUnitOperationError, ServerNotFoundError, ServerStateError, Event, DeferredTask, Playbook, ComputeUnitStatus, ServerStatus, ComputeUnitInDB, InitComputeUnit, ComputeUnitOverview, ComputeUnitRequest, BaseServer, ServerInDB, ServerComputeUnitInitSpec, ServerInitRequest, ServerDecommRequest |
| `kloigos/repos/__init__.py` | classes: Repo |
| `kloigos/repos/postgres.py` | classes: PostgresRepo |
| `kloigos/services/__init__.py` | no public surface |
| `kloigos/services/admin/__init__.py` | classes: AdminService |
| `kloigos/services/admin/base.py` | classes: AdminServiceBase |
| `kloigos/services/admin/servers.py` | classes: ServersAdminService |
| `kloigos/services/compute_unit.py` | classes: ComputeUnitService |
| `kloigos/util.py` | functions: to_cpu_set, parse_cpu_range |
