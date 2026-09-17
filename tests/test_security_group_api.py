import unittest
from unittest.mock import MagicMock

from cpkit.jobs.types import JobID
from fastapi import HTTPException

from kloigos.api.security_group import (
    add_security_group_rule,
    allocation_router,
    attach_security_group,
    delete_security_group_rule,
    detach_security_group,
    router,
)
from kloigos.models import (
    ComputeUnitNotFoundError,
    ComputeUnitOperationError,
    SecurityGroupMutationResponse,
    SecurityGroupNotFoundError,
    SecurityGroupRuleCreateRequest,
)


RULE = SecurityGroupRuleCreateRequest(
    direction="ingress",
    protocol="tcp",
    port_from=443,
    port_to=443,
    cidr="10.0.0.0/24",
    ip_version="ipv4",
)


class SecurityGroupMutationApiTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.service = MagicMock()

    def test_all_mutation_routes_declare_the_shared_response_model(self) -> None:
        mutation_routes = [
            route
            for route in (*router.routes, *allocation_router.routes)
            if route.methods & {"POST", "DELETE"}
            and ("/rules" in route.path or "/allocations/" in route.path)
        ]
        self.assertEqual(len(mutation_routes), 4)
        self.assertTrue(
            all(
                route.response_model is SecurityGroupMutationResponse
                for route in mutation_routes
            )
        )

    async def test_mutations_share_the_job_ids_response_contract(self) -> None:
        self.service.add_rule.return_value = [JobID(job_id=201), JobID(job_id=202)]
        response = await add_security_group_rule(
            "sg-1",
            RULE,
            "actor",
            self.service,
        )
        self.assertEqual(response.model_dump(), {"job_ids": [201, 202]})

        self.service.delete_rule.return_value = []
        response = await delete_security_group_rule(
            "sg-1",
            "sgr-1",
            "actor",
            self.service,
        )
        self.assertEqual(response.model_dump(), {"job_ids": []})

        self.service.attach_to_allocation.return_value = [JobID(job_id=203)]
        response = await attach_security_group(
            "alloc-a",
            "sg-1",
            "actor",
            self.service,
        )
        self.assertEqual(response.model_dump(), {"job_ids": [203]})

        self.service.detach_from_allocation.return_value = []
        response = await detach_security_group(
            "alloc-a",
            "sg-1",
            "actor",
            self.service,
        )
        self.assertEqual(response.model_dump(), {"job_ids": []})

    async def test_missing_group_returns_not_found(self) -> None:
        self.service.add_rule.side_effect = SecurityGroupNotFoundError("missing")
        with self.assertRaises(HTTPException) as raised:
            await add_security_group_rule("missing", RULE, "actor", self.service)
        self.assertEqual(raised.exception.status_code, 404)

    async def test_duplicate_rule_remains_a_conflict(self) -> None:
        self.service.add_rule.side_effect = ComputeUnitOperationError("duplicate")
        with self.assertRaises(HTTPException) as raised:
            await add_security_group_rule("sg-1", RULE, "actor", self.service)
        self.assertEqual(raised.exception.status_code, 409)

    async def test_missing_rule_returns_not_found(self) -> None:
        self.service.delete_rule.return_value = None
        with self.assertRaises(HTTPException) as raised:
            await delete_security_group_rule(
                "sg-1",
                "missing",
                "actor",
                self.service,
            )
        self.assertEqual(raised.exception.status_code, 404)

    async def test_missing_allocation_returns_not_found(self) -> None:
        self.service.attach_to_allocation.side_effect = ComputeUnitNotFoundError(
            "missing"
        )
        with self.assertRaises(HTTPException) as raised:
            await attach_security_group("missing", "sg-1", "actor", self.service)
        self.assertEqual(raised.exception.status_code, 404)

    async def test_missing_attachment_returns_not_found(self) -> None:
        self.service.detach_from_allocation.return_value = None
        with self.assertRaises(HTTPException) as raised:
            await detach_security_group("alloc-a", "sg-1", "actor", self.service)
        self.assertEqual(raised.exception.status_code, 404)


if __name__ == "__main__":
    unittest.main()
