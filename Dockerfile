# Builds the ray binary from the rayfish repo at RAY_REF and packages it with
# the Umbrel entrypoint (GUI proxy + daemon).
ARG RAY_REPO=https://github.com/rayfish/rayfish
ARG RAY_REF=master

FROM rust:1-bookworm AS build
ARG RAY_REPO
ARG RAY_REF
RUN git clone --depth 1 --branch "${RAY_REF}" "${RAY_REPO}" /src
WORKDIR /src
RUN cargo build --release --locked

FROM debian:bookworm-slim
RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates iproute2 python3 \
    && rm -rf /var/lib/apt/lists/*
COPY --from=build /src/target/release/ray /usr/local/bin/ray
COPY rayfish-vpn/icon.png /usr/local/lib/rayfish/icon.png
COPY docker/gui-proxy.py /usr/local/lib/rayfish/gui-proxy.py
COPY docker/start.sh /usr/local/bin/rayfish-start
RUN chmod +x /usr/local/bin/rayfish-start
CMD ["rayfish-start"]
