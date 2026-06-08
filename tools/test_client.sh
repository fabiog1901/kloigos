#!/bin/bash

# This script tests the Kloigos API by sending a signed request to the compute_units endpoint.
# cpkit authenticates API keys by verifying this OpenSSL-generated HMAC signature.

export KLOIGOS_ACCESS_KEY="kloigos-tT8r4RgJjT2uyJiC-VdIwA"
export KLOIGOS_SECRET_ACCESS_KEY="6cRlQ2qweazaacZAnKrDRpctiXjQjh_AMXh3A93cwpY"

API_URL="http://localhost:8000/api/compute_units/?deployment_id=crdb"

# --- 1. Extract Path and Query from URL ---
# We use 'cut' to separate the protocol/host from the path/query
PATH_AND_QUERY=$(echo "$API_URL" | cut -d'/' -f4-)
# If the path is empty, default to /
[ -z "$PATH_AND_QUERY" ] && PATH_AND_QUERY="/"

# --- 2. Prepare Request Data ---
METHOD="GET"
TIMESTAMP=$(date -u "+%Y-%m-%dT%H:%M:%SZ")
BODY='{"action": "delete", "target": "database_01"}'
BODY=' '

# --- 3. Create the String-to-Sign ---
# Order: Method + PathAndQuery + Timestamp + Body
# Using printf to avoid unexpected newlines from 'echo'
STRING_TO_SIGN=$(printf "%s\n%s\n%s\n%s" "$METHOD" "/$PATH_AND_QUERY" "$TIMESTAMP" "$BODY")

# --- 4. Generate the HMAC-SHA256 Signature ---
# We use openssl to hash the string using our secret key
SIGNATURE=$(printf "%s" "$STRING_TO_SIGN" | openssl dgst -sha256 -hmac "$KLOIGOS_SECRET_ACCESS_KEY" -hex | sed 's/^.* //')

# echo $STRING_TO_SIGN
# echo $SIGNATURE

# --- 5. Execute the Curl Command ---
curl -sS -X "$METHOD" "$API_URL" \
     -H "Content-Type: application/json" \
     -H "X-CP-Access-Key: $KLOIGOS_ACCESS_KEY" \
     -H "X-Timestamp: $TIMESTAMP" \
     -H "X-CP-Signature: $SIGNATURE" \
     -d "$BODY"
