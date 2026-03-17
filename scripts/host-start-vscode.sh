#!/usr/bin/env bash

set -eu

# Export required environment variables
export NODE_EXTRA_CA_CERTS="/etc/ssl/cert.pem"
export PATH="/Users/prog/projects/homebrew/bin:$PATH"

code "$@"
