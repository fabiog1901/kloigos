import datetime as dt
import json
import unittest
from unittest.mock import MagicMock

from fastapi import HTTPException, Response, status
from fastapi.routing import serialize_response

from kloigos.api.ssh_key import (
    create_ssh_key,
    delete_ssh_key,
    get_ssh_key,
    list_ssh_keys,
    router,
)
from kloigos.models import (
    ComputeUnitOperationError,
    SSHKeyCreateRequest,
    SSHKeyCreateResponse,
    SSHKeyNotFoundError,
)

PRIVATE_KEY_SENTINEL = "KLOIGOS-PRIVATE-KEY-SENTINEL"
PUBLIC_KEY = (
    "ssh-ed25519 "
    "AAAAC3NzaC1lZDI1NTE5AAAAIDk65l+4HPbBZRt6mV7tHcvap3PrhCUo79iaCEdE1exx"
)


class SSHKeyApiTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.service = MagicMock()

    def test_routes_expose_expected_methods_and_create_status(self) -> None:
        methods_by_path = {
            (route.path, next(iter(route.methods))): route for route in router.routes
        }
        create_route = methods_by_path[("/ssh-keys/", "POST")]
        self.assertEqual(create_route.status_code, status.HTTP_201_CREATED)
        self.assertIn("non-idempotent", create_route.description)
        self.assertIn("must not retry", create_route.description)
        self.assertIn("delete it if present", create_route.description)
        documented_headers = create_route.responses[status.HTTP_201_CREATED]["headers"]
        self.assertEqual(
            set(documented_headers),
            {"Cache-Control", "Pragma", "Expires"},
        )
        self.assertIn(status.HTTP_409_CONFLICT, create_route.responses)
        self.assertIn(("/ssh-keys/", "GET"), methods_by_path)
        self.assertIn(("/ssh-keys/{name}", "GET"), methods_by_path)
        self.assertIn(("/ssh-keys/{name}", "DELETE"), methods_by_path)

    async def test_create_returns_service_response(self) -> None:
        expected = MagicMock()
        self.service.create_ssh_key.return_value = expected
        request = SSHKeyCreateRequest(name="generated", generate=True)
        response = Response()

        result = await create_ssh_key(request, response, "actor", self.service)

        self.assertIs(result, expected)
        self.service.create_ssh_key.assert_called_once_with("actor", request)

    async def test_create_response_disables_caching_for_all_creation_modes(
        self,
    ) -> None:
        requests = (
            SSHKeyCreateRequest(name="generated", generate=True),
            SSHKeyCreateRequest(
                name="imported",
                public_key=(
                    "ssh-ed25519 "
                    "AAAAC3NzaC1lZDI1NTE5AAAAIDk65l+4HPbBZRt6mV7tHcvap3PrhCUo79iaCEdE1exx"
                ),
            ),
        )

        for request in requests:
            with self.subTest(name=request.name):
                response = Response()
                await create_ssh_key(request, response, "actor", self.service)

                self.assertEqual(response.headers["cache-control"], "no-store")
                self.assertEqual(response.headers["pragma"], "no-cache")
                self.assertEqual(response.headers["expires"], "0")

    async def test_duplicate_name_returns_conflict(self) -> None:
        self.service.create_ssh_key.side_effect = ComputeUnitOperationError(
            "already exists"
        )
        with self.assertRaises(HTTPException) as raised:
            await create_ssh_key(
                SSHKeyCreateRequest(name="duplicate", generate=True),
                Response(),
                "actor",
                self.service,
            )
        self.assertEqual(raised.exception.status_code, status.HTTP_409_CONFLICT)

    async def test_list_and_get_return_service_records(self) -> None:
        records = [MagicMock()]
        self.service.list_ssh_keys.return_value = records
        self.service.get_ssh_key.return_value = records[0]

        self.assertIs(await list_ssh_keys(self.service), records)
        self.assertIs(await get_ssh_key("workstation", self.service), records[0])

    async def test_get_and_list_response_models_strip_private_key_material(
        self,
    ) -> None:
        record = SSHKeyCreateResponse(
            name="generated",
            algorithm="ssh-ed25519",
            public_key=PUBLIC_KEY,
            fingerprint="SHA256:example",
            creation_method="generated",
            created_at=dt.datetime(2026, 1, 1, tzinfo=dt.UTC),
            updated_at=dt.datetime(2026, 1, 1, tzinfo=dt.UTC),
            private_key=PRIVATE_KEY_SENTINEL,
        )
        routes = {
            (route.path, next(iter(route.methods))): route for route in router.routes
        }

        cases = (
            (routes[("/ssh-keys/", "GET")], [record]),
            (routes[("/ssh-keys/{name}", "GET")], record),
        )
        for route, content in cases:
            with self.subTest(path=route.path):
                serialized = await serialize_response(
                    field=route.response_field,
                    response_content=content,
                )
                encoded = json.dumps(serialized)
                self.assertNotIn("private_key", encoded)
                self.assertNotIn(PRIVATE_KEY_SENTINEL, encoded)

    async def test_missing_get_and_delete_return_not_found(self) -> None:
        self.service.get_ssh_key.side_effect = SSHKeyNotFoundError("missing")
        with self.assertRaises(HTTPException) as raised:
            await get_ssh_key("missing", self.service)
        self.assertEqual(raised.exception.status_code, status.HTTP_404_NOT_FOUND)

        self.service.delete_ssh_key.side_effect = SSHKeyNotFoundError("missing")
        with self.assertRaises(HTTPException) as raised:
            await delete_ssh_key("missing", "actor", self.service)
        self.assertEqual(raised.exception.status_code, status.HTTP_404_NOT_FOUND)

    async def test_delete_returns_no_content(self) -> None:
        self.service.delete_ssh_key.return_value = True

        response = await delete_ssh_key("workstation", "actor", self.service)

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)


if __name__ == "__main__":
    unittest.main()
