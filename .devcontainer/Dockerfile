# Devcontainer base with Node.js 18 and common tooling
FROM mcr.microsoft.com/devcontainers/javascript-node:1-18-bullseye

# Install common packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    apt-transport-https \
    ca-certificates \
    gnupg \
    curl \
    lsb-release \
    git \
    unzip \
  && apt-get clean && rm -rf /var/lib/apt/lists/*

# Create a directory for mounting secrets (service account key)
RUN mkdir -p /workspaces/.secrets && chown node:node /workspaces/.secrets

EXPOSE 3000

# Default to non-root 'node' user provided by the base image
USER node
