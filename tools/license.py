#!/usr/bin/env python3
"""Sign or decode Kloigos enterprise license JWTs."""

import argparse
import datetime as dt
import json
import sys
from pathlib import Path
from typing import Any

import jwt
import yaml
from jwt import DecodeError
from jwt import InvalidSignatureError as JwtInvalidSignatureError

REQUIRED_FIELDS = {
    "license_id",
    "customer",
    "issued_at",
    "expires_at",
    "features",
    "limits",
}


class LicenseValidationError(Exception):
    pass


def main() -> int:
    parser = argparse.ArgumentParser(description="Sign or decode Kloigos license JWTs.")
    subcommands = parser.add_subparsers(dest="command", required=True)

    sign = subcommands.add_parser(
        "sign",
        help="Sign a license payload YAML as a JWT.",
    )
    sign.add_argument("payload", help="Path to the license payload YAML file.")
    sign.add_argument("private_key", help="Path to the Ed25519 private key PEM file.")
    sign.add_argument(
        "--kid",
        required=True,
        help="Signing key id to place in the JWT header.",
    )
    sign.add_argument(
        "-o",
        "--output",
        help="Optional output file. Defaults to stdout.",
    )

    decode = subcommands.add_parser(
        "decode",
        help="Decode a license JWT without verifying its signature.",
    )
    decode.add_argument("jwt_file", help="Path to the JWT file.")

    validate = subcommands.add_parser(
        "validate",
        help="Validate a license JWT with an Ed25519 public key.",
    )
    validate.add_argument("jwt_file", help="Path to the JWT file.")
    validate.add_argument("public_key", help="Path to the Ed25519 public key PEM file.")
    args = parser.parse_args()

    if args.command == "decode":
        decode_token(Path(args.jwt_file))
        return 0
    if args.command == "validate":
        decode_token(Path(args.jwt_file))
        return validate_token(Path(args.jwt_file), Path(args.public_key))

    return sign_token(args)


def sign_token(args: argparse.Namespace) -> int:
    payload = load_payload(Path(args.payload))
    private_key = Path(args.private_key).read_text()

    token = jwt.encode(
        payload,
        private_key,
        algorithm="EdDSA",
        headers={"kid": args.kid},
    )

    if args.output:
        Path(args.output).write_text(f"{token}\n")
    else:
        print(token)

    return 0


def decode_token(path: Path) -> None:
    token = path.read_text().strip()
    header = jwt.get_unverified_header(token)
    payload = jwt.decode(token, options={"verify_signature": False})
    print(
        yaml.safe_dump(
            {
                "header": header,
                "payload": payload,
            },
            indent=2,
            sort_keys=True,
        )
    )


def validate_token(jwt_path: Path, public_key_path: Path) -> int:
    token = jwt_path.read_text().strip()
    public_key = public_key_path.read_text()

    try:
        validate_license(token, public_key)
    except LicenseValidationError as exc:
        print(f"invalid: {exc}", file=sys.stderr)
        return 1

    print("License is valid")
    return 0


def validate_license(token: str, public_key: str) -> None:
    if not token:
        raise LicenseValidationError("Enterprise license is empty.")

    try:
        header = jwt.get_unverified_header(token)
    except DecodeError as exc:
        raise LicenseValidationError("Enterprise license is not a valid JWT.") from exc

    key_id = header.get("kid")
    if not key_id:
        raise LicenseValidationError("Enterprise license signing key is missing.")

    try:
        payload = jwt.decode(
            token,
            public_key,
            algorithms=["EdDSA"],
            options={
                "verify_aud": False,
                "verify_exp": False,
                "verify_iat": False,
                "verify_nbf": False,
            },
        )
    except JwtInvalidSignatureError as exc:
        raise LicenseValidationError(
            "Enterprise license signature is invalid."
        ) from exc
    except Exception as exc:
        raise LicenseValidationError(
            "Enterprise license could not be decoded."
        ) from exc

    missing = sorted(REQUIRED_FIELDS - set(payload))
    if missing:
        raise LicenseValidationError(
            f"Enterprise license payload is missing required fields: {missing}"
        )

    parse_license_date(payload["issued_at"], "issued_at")
    expires_at = parse_license_date(payload["expires_at"], "expires_at")
    if expires_at <= dt.datetime.now(dt.UTC):
        raise LicenseValidationError("Enterprise license has expired.")

    if not isinstance(payload["features"], list):
        raise LicenseValidationError(
            "Enterprise license payload field 'features' must be a list."
        )

    if not isinstance(payload["limits"], dict):
        raise LicenseValidationError(
            "Enterprise license payload field 'limits' must be a mapping/object."
        )


def load_payload(path: Path) -> dict[str, Any]:
    payload = yaml.safe_load(path.read_text())
    if not isinstance(payload, dict):
        raise SystemExit("License payload YAML must contain a mapping/object.")

    missing = sorted(REQUIRED_FIELDS - set(payload))
    if missing:
        raise SystemExit(f"License payload is missing required fields: {missing}")

    try:
        issued_at = parse_license_date(payload["issued_at"], "issued_at")
        expires_at = parse_license_date(payload["expires_at"], "expires_at")
    except LicenseValidationError as exc:
        raise SystemExit(str(exc)) from exc
    if expires_at <= issued_at:
        raise SystemExit(
            "License payload field 'expires_at' must be after 'issued_at'."
        )

    if not isinstance(payload["features"], list):
        raise SystemExit("License payload field 'features' must be a list.")

    if not isinstance(payload["limits"], dict):
        raise SystemExit("License payload field 'limits' must be a mapping/object.")

    return payload


def parse_license_date(value: Any, field: str) -> dt.datetime:
    if not isinstance(value, str):
        raise LicenseValidationError(
            f"License payload field '{field}' must be a yyyy-mm-dd string."
        )

    try:
        license_date = dt.date.fromisoformat(value)
    except ValueError as exc:
        raise LicenseValidationError(
            f"License payload field '{field}' must be a yyyy-mm-dd string."
        ) from exc

    return dt.datetime.combine(license_date, dt.time.min, tzinfo=dt.UTC)


if __name__ == "__main__":
    sys.exit(main())
