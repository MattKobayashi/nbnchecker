FROM python:3.13.3-alpine3.21@sha256:18159b2be11db91f84b8f8f655cd860f805dbd9e49a583ddaac8ab39bf4fe1a7
ENV USERNAME=nbnchecker
ENV GROUPNAME=$USERNAME
ENV UID=911
ENV GID=911
# uv and project
WORKDIR /opt/${USERNAME}
RUN apk --no-cache add uv \
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
ENTRYPOINT ["uv", "run", "main.py"]
LABEL org.opencontainers.image.authors="MattKobayashi <matthew@kobayashi.au>"
