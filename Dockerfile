FROM python:3.13.4-alpine3.22@sha256:b4d299311845147e7e47c970566906caf8378a1f04e5d3de65b5f2e834f8e3bf
ENV USERNAME=nbnchecker
ENV GROUPNAME=$USERNAME
ENV UID=911
ENV GID=911
# uv and project
WORKDIR /opt/${USERNAME}
RUN apk --no-cache add curl uv \
    && addgroup \
      --gid "$GID" \
      "$GROUPNAME" \
    && adduser \
      --disabled-password \
      --gecos "" \
      --home "$(pwd)" \
      --ingroup "$GROUPNAME" \
      --no-create-home \
      --uid "$UID" \
      $USERNAME \
    && chown -R ${UID}:${GID} /opt/${USERNAME}
COPY --chmod=644 --chown=${UID}:${GID} main.py main.py
COPY --chmod=644 --chown=${UID}:${GID} pyproject.toml pyproject.toml
COPY --chmod=644 --chown=${UID}:${GID} templates/ templates/
EXPOSE 8000
USER ${USERNAME}
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD curl --fail http://localhost:8000/health || exit 1
ENTRYPOINT ["uv", "run", "main.py"]
LABEL org.opencontainers.image.authors="MattKobayashi <matthew@kobayashi.au>"
