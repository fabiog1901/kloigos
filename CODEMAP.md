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
| `kloigos` | 24 | 41 | 24 | 14 |

## API Routes

| Method | Path | Handler | Response Model |
| --- | --- | --- | --- |
| `GET` | `/allocations` | `kloigos.api.allocation.list_allocations` | `list[AllocationInDB]` |
| `POST` | `/allocations` | `kloigos.api.allocation.allocate` | `AllocationCreateResponse` |
| `DELETE` | `/allocations/{allocation_id}` | `kloigos.api.allocation.deallocate_allocation` | `JobID` |
| `GET` | `/allocations/{allocation_id}` | `kloigos.api.allocation.get_allocation` | `AllocationInDB` |
| `POST` | `/allocations/{allocation_id}/scale` | `kloigos.api.allocation.scale_allocation` | `JobID` |
| `GET` | `/compute_units` | `kloigos.api.compute_unit.list_compute_units` | `list[ComputeUnitOverview]` |
| `GET` | `/ip_pool` | `kloigos.api.admin.ip_pool.list_ip_pool_addresses` | `list[IpPoolAddressInDB]` |
| `POST` | `/ip_pool` | `kloigos.api.admin.ip_pool.upsert_ip_pool_addresses` | `list[IpPoolAddressInDB]` |
| `DELETE` | `/ip_pool/{allocation_id}` | `kloigos.api.admin.ip_pool.release_ip_pool_address` | `-` |
| `PUT` | `/ip_pool/{ip_address}` | `kloigos.api.admin.ip_pool.update_ip_pool_address` | `IpPoolAddressInDB` |
| `GET` | `/servers` | `kloigos.api.admin.servers.list_servers` | `list[ServerInDB]` |
| `POST` | `/servers` | `kloigos.api.admin.servers.init_server` | `JobID` |
| `PUT` | `/servers` | `kloigos.api.admin.servers.decommission_server` | `JobID` |
| `DELETE` | `/servers/{hostname}` | `kloigos.api.admin.servers.delete_server` | `-` |

## Command Handlers

- none found

## Modules

| File | Public Surface |
| --- | --- |
| `kloigos/__init__.py` | no public surface |
| `kloigos/api/__init__.py` | no public surface |
| `kloigos/api/admin/__init__.py` | no public surface |
| `kloigos/api/admin/ip_pool.py` | functions: list_ip_pool_addresses, upsert_ip_pool_addresses, update_ip_pool_address, release_ip_pool_address; routes: 4 |
| `kloigos/api/admin/servers.py` | functions: list_servers, init_server, decommission_server, delete_server; routes: 4 |
| `kloigos/api/allocation.py` | functions: list_allocations, allocate, get_allocation, deallocate_allocation, scale_allocation; routes: 5 |
| `kloigos/api/compute_unit.py` | functions: list_compute_units; routes: 1 |
| `kloigos/dep.py` | functions: get_allocation_service, get_compute_unit_service, get_admin_service |
| `kloigos/main.py` | no public surface |
| `kloigos/models.py` | classes: AutoNameStrEnum, NoFreeComputeUnitError, NoFreeIpAddressError, ComputeUnitNotFoundError, ComputeUnitStateError, ComputeUnitOperationError, ServerNotFoundError, ServerStateError, Event, Playbook, QueueCommand, ComputeUnitStatus, AllocationStatus, IpAddressStatus, ServerStatus, ComputeUnitInDB, InitComputeUnit, ComputeUnitOverview, ComputeUnitRequest, AllocationCreateCommand, AllocationCreateResponse, AllocationDeallocateCommand, AllocationScaleRequest, AllocationScaleCommand, AllocationInDB, IpPoolAddressInDB, IpPoolUpsertRequest, IpPoolUpdateRequest, BaseServer, ServerInDB, ServerComputeUnitInitSpec, ServerInitRequest, ServerDecommRequest |
| `kloigos/repos/__init__.py` | classes: Repo |
| `kloigos/repos/postgres.py` | classes: PostgresRepo |
| `kloigos/services/__init__.py` | no public surface |
| `kloigos/services/admin/__init__.py` | classes: AdminService |
| `kloigos/services/admin/base.py` | classes: AdminServiceBase |
| `kloigos/services/admin/ip_pool.py` | classes: IpPoolAdminService |
| `kloigos/services/admin/servers.py` | classes: ServersAdminService |
| `kloigos/services/allocation.py` | classes: AllocationService |
| `kloigos/services/compute_unit.py` | classes: ComputeUnitService |
| `kloigos/util.py` | functions: to_cpu_set, parse_cpu_range |
| `kloigos/workers/__init__.py` | Job worker entry points for Kloigos. |
| `kloigos/workers/remote/__init__.py` | Remote job handlers that execute playbooks on Kloigos-managed servers. |
| `kloigos/workers/remote/allocation.py` | Remote allocation worker handlers.; functions: run_compute_unit_allocate, run_compute_unit_deallocate, run_allocation_scale |
| `kloigos/workers/remote/server.py` | Remote server worker handlers.; functions: run_server_init, run_server_decommission |
