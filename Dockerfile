# Package a published release with the Umbrel GUI proxy and daemon entrypoint.
ARG RAY_REF=v0.5.5

FROM --platform=$BUILDPLATFORM debian:bookworm-slim AS download
ARG RAY_REF
ARG TARGETARCH
RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates curl \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /download
RUN set -eu; \
    case "$TARGETARCH" in \
        amd64) asset=ray-linux-x86_64-musl ;; \
        arm64) asset=ray-linux-aarch64-musl ;; \
        *) echo "Unsupported architecture: $TARGETARCH" >&2; exit 1 ;; \
    esac; \
    base="https://github.com/rayfish/rayfish/releases/download/${RAY_REF}"; \
    curl -fSL --retry 3 "$base/$asset" -o "$asset"; \
    curl -fSL --retry 3 "$base/$asset.sha256" -o "$asset.sha256"; \
    sha256sum -c "$asset.sha256"; \
    mv "$asset" ray; \
    chmod 755 ray
RUN set -eu; \
    mkdir licenses; \
    base="https://raw.githubusercontent.com/rayfish/rayfish/${RAY_REF}"; \
    curl -fSL --retry 3 "$base/LICENSE" -o licenses/rayfish.txt; \
    for font in ChakraPetch IBMPlexMono PressStart2P; do \
        curl -fSL --retry 3 "$base/macos/Rayfish/Fonts/$font-OFL.txt" \
            -o "licenses/$font-OFL.txt"; \
    done

FROM debian:bookworm-slim
RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates iproute2 python3 \
    && rm -rf /var/lib/apt/lists/*
COPY --from=download /download/ray /usr/local/bin/ray
COPY --from=download /download/licenses/ /usr/share/licenses/rayfish/
COPY rayfish-vpn/icon.png /usr/local/lib/rayfish/icon.png
COPY docker/gui-proxy.py /usr/local/lib/rayfish/gui-proxy.py
COPY docker/gui.html /usr/local/lib/rayfish/gui.html
COPY docker/start.sh /usr/local/bin/rayfish-start
RUN chmod +x /usr/local/bin/rayfish-start
CMD ["rayfish-start"]
