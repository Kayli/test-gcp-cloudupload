# Devcontainer base with Node.js 18 and common tooling
FROM mcr.microsoft.com/devcontainers/python:1-3.11-bullseye

# Install common packages
## Ensure Yarn APT key exists (some base images include yarn repo)
RUN set -eux; \
  # Attempt to fetch the Yarn APT key and add the repo if successful; ignore if unavailable
  if curl -fsSL https://dl.yarnpkg.com/debian/pubkey.gpg | gpg --dearmor -o /usr/share/keyrings/yarn-archive-keyring.gpg; then \
    echo "deb [signed-by=/usr/share/keyrings/yarn-archive-keyring.gpg] https://dl.yarnpkg.com/debian/ stable main" > /etc/apt/sources.list.d/yarn.list; \
  else \
    echo "Yarn APT key not available; skipping yarn apt source"; \
  fi

## If a Yarn source file exists in the base image, remove it to avoid GPG key issues
RUN rm -f /etc/apt/sources.list.d/yarn.list

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
RUN mkdir -p /workspaces/.secrets && chown vscode:vscode /workspaces/.secrets

# Install Docker CLI (uses host Docker daemon via mounted socket)
RUN set -eux; \
  curl -fsSL https://download.docker.com/linux/debian/gpg | gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg; \
  echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/debian $(lsb_release -cs) stable" \
    > /etc/apt/sources.list.d/docker.list; \
  apt-get update; \
  apt-get install -y --no-install-recommends docker-ce-cli docker-buildx-plugin docker-compose-plugin; \
  rm -rf /var/lib/apt/lists/*;

# Install GitHub CLI (gh)
RUN set -eux; \
  curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg | dd of=/usr/share/keyrings/githubcli-archive-keyring.gpg; \
  chmod go+r /usr/share/keyrings/githubcli-archive-keyring.gpg; \
  echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" \
    > /etc/apt/sources.list.d/github-cli.list; \
  apt-get update; \
  apt-get install -y --no-install-recommends gh; \
  rm -rf /var/lib/apt/lists/*;

# Install Dev Containers CLI via npm (only distribution channel available)
# Install Node.js LTS from NodeSource, use it to install the CLI globally, then
# expose the devcontainer binary on PATH without keeping a full Node.js environment.
RUN set -eux; \
  curl -fsSL https://deb.nodesource.com/setup_lts.x | bash -; \
  apt-get install -y --no-install-recommends nodejs; \
  npm install -g @devcontainers/cli@latest; \
  rm -rf /var/lib/apt/lists/*

# Copy pyproject.toml last so changes to deps don't bust the apt/tool cache layers above
COPY pyproject.toml README.md /tmp/app/

RUN set -eux; \
  python -m pip install --upgrade pip setuptools wheel; \
  # Install the project (this will install dependencies declared in pyproject.toml)
  python -m pip install /tmp/app; \
  # If Playwright is a dependency, install the browser binaries
  if python -c "import importlib,sys; sys.exit(0 if importlib.util.find_spec('playwright') else 1)"; then \
    python -m playwright install --with-deps; \
  else \
    echo "Playwright not installed as a package; skipping browser install"; \
  fi

EXPOSE 3000

# Default to non-root 'vscode' user provided by the base image
USER vscode
