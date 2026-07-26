# Rayfish Umbrel app

Community Umbrel app store for [rayfish](https://github.com/rayfish/rayfish),
a peer-to-peer mesh VPN over [iroh](https://iroh.computer). Installing the app
puts your Umbrel on your private mesh: services running on it become reachable
from your laptop or phone anywhere, by name (`umbrel.mynet.ray`) or stable
virtual IP.

## Install

1. In umbrelOS, open the App Store, click the three-dot menu, choose
   Community App Stores.
2. Add this repository's URL.
3. Open the Rayfish store and install the app.
4. Click the app to open the dashboard, then create a network or join one
   with an invite code.

## How it runs

One container, modeled on the official Tailscale Umbrel app:

- `network_mode: host` with `NET_ADMIN`/`NET_RAW` and `/dev/net/tun`, so the
  daemon creates the TUN interface on the host and the whole Umbrel joins the
  mesh.
- `ray daemon` runs as PID 1. The dashboard is `ray gui`, exposed on port
  8480 through a small token-injecting proxy (`docker/gui-proxy.py`), since
  the GUI itself only binds localhost with a per-run token.
- Identity and network config persist in `${APP_DATA_DIR}/data`
  (`/etc/rayfish` in the container); logs in `${APP_DATA_DIR}/logs`.
- Updates ship as new image digests via app version bumps. `ray update` and
  auto-update are not used inside the container.

Note: like Tailscale's Umbrel web UI, the dashboard is reachable by anyone on
your LAN without authentication. Don't install on a LAN you don't trust.

## Building the image

```bash
docker build -t rayfish-umbrel --build-arg RAY_REF=master .
```

CI: the `docker` workflow (manual dispatch) builds linux/amd64 + linux/arm64
and pushes `ghcr.io/rayfish/rayfish-umbrel:<ray_ref>`. To pin the compose
file, grab the digest after a push:

```bash
docker buildx imagetools inspect ghcr.io/rayfish/rayfish-umbrel:<version>
```

then set `image: ghcr.io/rayfish/rayfish-umbrel:<version>@sha256:<digest>` in
`rayfish-vpn/docker-compose.yml` and bump `version` in
`rayfish-vpn/umbrel-app.yml`.
