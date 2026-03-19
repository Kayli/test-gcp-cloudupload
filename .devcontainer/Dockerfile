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

# NOTE: Docker CLI + daemon are installed by the docker-in-docker devcontainer
# feature declared in devcontainer.json — no manual install needed here.

# Install GitHub CLI (gh)
RUN set -eux; \
  curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg | dd of=/usr/share/keyrings/githubcli-archive-keyring.gpg; \
  chmod go+r /usr/share/keyrings/githubcli-archive-keyring.gpg; \
  echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" \
    > /etc/apt/sources.list.d/github-cli.list; \
  apt-get update; \
  apt-get install -y --no-install-recommends gh; \
  rm -rf /var/lib/apt/lists/*;

# Install Google Cloud SDK (gcloud, gsutil, bq) via tarball.
# The APT package requires python3 >= 3.10 from the Debian repo, but bullseye
# only ships 3.9 there (our Python 3.11 was installed outside APT).
# The tarball bundles its own Python so there is no version conflict.
RUN set -eux; \
  ARCH=$(dpkg --print-architecture); \
  case "$ARCH" in \
    amd64) GC_ARCH="x86_64" ;; \
    arm64) GC_ARCH="arm"    ;; \
    *)     echo "Unsupported arch: $ARCH" >&2; exit 1 ;; \
  esac; \
  curl -fsSL \
    "https://dl.google.com/dl/cloudsdk/channels/rapid/downloads/google-cloud-cli-linux-${GC_ARCH}.tar.gz" \
    -o /tmp/google-cloud-sdk.tar.gz; \
  tar -xzf /tmp/google-cloud-sdk.tar.gz -C /usr/local/; \
  /usr/local/google-cloud-sdk/install.sh --quiet --path-update false --command-completion false; \
  ln -sf /usr/local/google-cloud-sdk/bin/gcloud /usr/local/bin/gcloud; \
  ln -sf /usr/local/google-cloud-sdk/bin/gsutil /usr/local/bin/gsutil; \
  ln -sf /usr/local/google-cloud-sdk/bin/bq     /usr/local/bin/bq; \
  rm /tmp/google-cloud-sdk.tar.gz;

# Install Terraform
RUN set -eux; \
  curl -fsSL https://apt.releases.hashicorp.com/gpg \
    | gpg --dearmor -o /usr/share/keyrings/hashicorp-archive-keyring.gpg; \
  echo "deb [signed-by=/usr/share/keyrings/hashicorp-archive-keyring.gpg] https://apt.releases.hashicorp.com $(lsb_release -cs) main" \
    > /etc/apt/sources.list.d/hashicorp.list; \
  apt-get update; \
  apt-get install -y --no-install-recommends terraform; \
  rm -rf /var/lib/apt/lists/*;

# Install Dev Containers CLI via npm (only distribution channel available)
# Install Node.js LTS from NodeSource, use it to install the CLI globally, then
# expose the devcontainer binary on PATH without keeping a full Node.js environment.
RUN set -eux; \
  curl -fsSL https://deb.nodesource.com/setup_lts.x | bash -; \
  apt-get install -y --no-install-recommends nodejs; \
  npm install -g @devcontainers/cli@latest; \
  rm -rf /var/lib/apt/lists/*


  
# Install Playwright browser binaries as the vscode user so they land in
# /home/vscode/.cache/ms-playwright (where the vscode user will look at runtime).
# Default to non-root 'vscode' user provided by the base image
USER vscode
RUN python -m pip install playwright; \
    python -m playwright install chromium; \
    python -m playwright install-deps chromium

# Copy pyproject.toml last so changes to deps don't bust the apt/tool cache layers above
USER root
COPY pyproject.toml README.md /tmp/app/
RUN set -eux; \
    python -m pip install --upgrade pip setuptools wheel; \
    # Install the project (this will install dependencies declared in pyproject.toml)
    python -m pip install /tmp/app;

EXPOSE 3000