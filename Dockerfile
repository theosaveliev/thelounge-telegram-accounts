# syntax=docker/dockerfile:1
FROM ubuntu:noble

RUN apt-get update -y \
    && apt-get upgrade -y \
    && apt-get install -y --no-install-recommends ca-certificates curl \
    && rm -Rf /var/lib/apt/lists/*

USER ubuntu:ubuntu
WORKDIR /app
ENV HOME="/home/ubuntu"

ADD --chown=ubuntu:ubuntu https://astral.sh/uv/install.sh uv-installer.sh
RUN sh uv-installer.sh && rm uv-installer.sh
ENV PATH="/home/ubuntu/.local/bin/:$PATH"

COPY --chown=ubuntu:ubuntu pyproject.toml .
COPY --chown=ubuntu:ubuntu README.md .
COPY --chown=ubuntu:ubuntu src/ src/
RUN uv tool install .

CMD ["thelounge_telegram_accounts"]