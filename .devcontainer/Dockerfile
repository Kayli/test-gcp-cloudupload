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

# Install Docker CLI (uses host Docker daemon via mounted socket)
RUN set -eux; \
  curl -fsSL https://download.docker.com/linux/debian/gpg | gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg; \
  echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/debian $(lsb_release -cs) stable" \
    > /etc/apt/sources.list.d/docker.list; \
  apt-get update; \
  apt-get install -y --no-install-recommends docker-ce-cli docker-buildx-plugin docker-compose-plugin; \
  rm -rf /var/lib/apt/lists/*;

# Install GitHub CLI (gh) and Dev Containers CLI
RUN set -eux; \
  curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg | dd of=/usr/share/keyrings/githubcli-archive-keyring.gpg; \
  chmod go+r /usr/share/keyrings/githubcli-archive-keyring.gpg; \
  echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" \
    > /etc/apt/sources.list.d/github-cli.list; \
  apt-get update; \
  apt-get install -y --no-install-recommends gh; \
  rm -rf /var/lib/apt/lists/*; \
  # Install Dev Containers CLI as root and ensure binary is available
  npm install -g --unsafe-perm @devcontainers/cli@latest; \
  if [ -x "/usr/local/bin/devcontainer" ]; then \
    echo "devcontainer installed at /usr/local/bin/devcontainer"; \
  elif command -v devcontainer >/dev/null 2>&1; then \
    ln -s "$(command -v devcontainer)" /usr/local/bin/devcontainer || true; \
  fi; \
  chmod a+rx /usr/local/bin/devcontainer || true; \
  npm cache clean --force || true

EXPOSE 3000

# Default to non-root 'node' user provided by the base image
USER node
