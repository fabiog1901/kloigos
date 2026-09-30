import base64
import hashlib

from cpkit.audit import log_event
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519, rsa

from kloigos.models import (
    ComputeUnitOperationError,
    Event,
    SSHKeyCreate,
    SSHKeyCreateRequest,
    SSHKeyCreateResponse,
    SSHKeyCreationMethod,
    SSHKeyGenerationAlgorithm,
    SSHKeyInDB,
    SSHKeyNotFoundError,
)

from ..repos import Repo

DEFAULT_GENERATED_KEY_ALGORITHM = SSHKeyGenerationAlgorithm.ED25519


def _fingerprint(public_key: str) -> str:
    encoded_key = public_key.split()[1]
    key_blob = base64.b64decode(encoded_key.encode("ascii"), validate=True)
    digest = base64.b64encode(hashlib.sha256(key_blob).digest()).rstrip(b"=")
    return f"SHA256:{digest.decode('ascii')}"


def _generate_private_key(algorithm: SSHKeyGenerationAlgorithm):
    if algorithm is SSHKeyGenerationAlgorithm.ED25519:
        return ed25519.Ed25519PrivateKey.generate()
    if algorithm is SSHKeyGenerationAlgorithm.RSA:
        return rsa.generate_private_key(public_exponent=65537, key_size=4096)
    raise ComputeUnitOperationError(
        f"SSH key generation is not supported for algorithm '{algorithm}'."
    )


def _public_metadata(ssh_key: SSHKeyInDB) -> dict:
    return ssh_key.model_dump(mode="json", exclude={"public_key"})


class SSHKeyService:
    """Manage reusable named SSH public keys."""

    def __init__(self, repo: Repo):
        self.repo = repo

    def create_ssh_key(
        self,
        actor_id: str,
        req: SSHKeyCreateRequest,
    ) -> SSHKeyCreateResponse:
        """Import a public key or generate a key pair and persist its public half."""
        if self.repo.get_ssh_keys(name=req.name):
            raise ComputeUnitOperationError(
                f"SSH key name '{req.name}' already exists."
            )

        private_key_text: str | None = None
        if req.generate:
            algorithm = req.algorithm or DEFAULT_GENERATED_KEY_ALGORITHM
            private_key = _generate_private_key(algorithm)
            public_key = (
                private_key.public_key()
                .public_bytes(
                    serialization.Encoding.OpenSSH,
                    serialization.PublicFormat.OpenSSH,
                )
                .decode("ascii")
            )
            private_key_text = private_key.private_bytes(
                serialization.Encoding.PEM,
                serialization.PrivateFormat.OpenSSH,
                serialization.NoEncryption(),
            ).decode("ascii")
            creation_method = SSHKeyCreationMethod.GENERATED
        else:
            public_key = req.public_key
            algorithm = public_key.split(maxsplit=1)[0]
            creation_method = SSHKeyCreationMethod.IMPORTED

        record = self.repo.create_ssh_key(
            SSHKeyCreate(
                name=req.name,
                algorithm=algorithm,
                public_key=public_key,
                fingerprint=_fingerprint(public_key),
                creation_method=creation_method,
            )
        )
        log_event(
            self.repo,
            actor_id,
            Event.SSH_KEY_CREATED,
            _public_metadata(record),
        )
        return SSHKeyCreateResponse(
            **record.model_dump(),
            private_key=private_key_text,
        )

    def list_ssh_keys(self) -> list[SSHKeyInDB]:
        """Return all stored public SSH keys."""
        return self.repo.get_ssh_keys()

    def get_ssh_key(self, name: str) -> SSHKeyInDB:
        """Return one stored public SSH key by name."""
        matches = self.repo.get_ssh_keys(name=name)
        if not matches:
            raise SSHKeyNotFoundError(f"SSH key '{name}' was not found.")
        return matches[0]

    def delete_ssh_key(self, actor_id: str, name: str) -> bool:
        """Delete one stored SSH key definition."""
        ssh_key = self.get_ssh_key(name)
        deleted = self.repo.delete_ssh_key(name)
        if deleted:
            log_event(
                self.repo,
                actor_id,
                Event.SSH_KEY_DELETED,
                _public_metadata(ssh_key),
            )
        return deleted
