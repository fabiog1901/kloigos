import unittest
from unittest.mock import MagicMock

from fastapi import HTTPException, status

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
    SSHKeyNotFoundError,
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
        self.assertIn(("/ssh-keys/", "GET"), methods_by_path)
        self.assertIn(("/ssh-keys/{name}", "GET"), methods_by_path)
        self.assertIn(("/ssh-keys/{name}", "DELETE"), methods_by_path)

    async def test_create_returns_service_response(self) -> None:
        expected = MagicMock()
        self.service.create_ssh_key.return_value = expected
        request = SSHKeyCreateRequest(name="generated", generate=True)

        result = await create_ssh_key(request, "actor", self.service)

        self.assertIs(result, expected)
        self.service.create_ssh_key.assert_called_once_with("actor", request)

    async def test_duplicate_name_returns_conflict(self) -> None:
        self.service.create_ssh_key.side_effect = ComputeUnitOperationError(
            "already exists"
        )
        with self.assertRaises(HTTPException) as raised:
            await create_ssh_key(
                SSHKeyCreateRequest(name="duplicate", generate=True),
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
