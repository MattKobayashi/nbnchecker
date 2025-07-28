FROM alpine:3.22.1@sha256:4bcff63911fcb4448bd4fdacec207030997caf25e9bea4045fa6c8c44de311d1
ENV USERNAME=nbnchecker
ENV GROUPNAME=$USERNAME
ENV UID=911
ENV GID=911

# renovate: datasource=repology depName=alpine_3_22/curl
ENV CURL_VERSION="8.14.1-r1"
# renovate: datasource=repology depName=alpine_3_22/uv
ENV UV_VERSION="0.7.9-r0"

WORKDIR /opt/${USERNAME}
RUN apk --no-cache add \
      curl="${CURL_VERSION}" \
      uv="${UV_VERSION}" \
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
RUN mkdir -p templates
COPY --chmod=644 --chown=${UID}:${GID} templates/index.html templates/
EXPOSE 8000
USER ${USERNAME}
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD curl --fail http://localhost:8000/health || exit 1
ENTRYPOINT ["uv", "run", "main.py"]
LABEL org.opencontainers.image.authors="MattKobayashi <matthew@kobayashi.au>"
