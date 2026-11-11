# TLS and reverse proxies

keyup ships serving **plain HTTP**. There are two ways to put it on HTTPS, and they are
alternatives, not layers:

* **keyup's own edge.** The `edge` container (Caddy) obtains and renews free
  [Let's Encrypt](https://letsencrypt.org/) certificates itself. Nothing else to run.
* **Your own reverse proxy or tunnel** in front of keyup's plain-HTTP port: nginx, Caddy,
  Cloudflare Tunnel and the like. The edge then stays a plain pass-through.

The deep references are keyup's
[HTTPS.md](reference/keyup/HTTPS.md) and
[REVERSE-PROXY.md](reference/keyup/REVERSE-PROXY.md).

**Ports.** The edge publishes `WEB_PORT` (plain HTTP, default `8095`) and `WEB_TLS_PORT`
(HTTPS, default `8443`) on the host. Addresses below like `http://192.0.2.10/` mean
`http://192.0.2.10:8095/` on a stock install.

## keyup's edge: Let's Encrypt

Let's Encrypt has to check that you control each name before it issues a certificate. That
check is the **challenge**, and the edge supports two:

| | HTTP-01 | DNS-01 through Cloudflare |
| --- | --- | --- |
| Names resolve | publicly, to this box | anywhere; a LAN-only address is fine |
| Inbound ports | 80 and 443 from the internet | none |
| Credential | none | a Cloudflare API token with DNS edit on the zone |
| `KEYUP_TLS_CHALLENGE` | `http` (or `auto` with no token) | `dns` (or `auto` with a token) |
| Status | **beta** | supported |

!!! warning "HTTP-01 is beta"
    The HTTP-01 path has been tested end to end against a local ACME test server, but not yet
    against Let's Encrypt itself. Do the [staging rehearsal](#rehearse-against-staging-first)
    before you switch to real certificates, and please report how it went.

You can configure it two ways: fill the fields in **Admin → HTTPS** and press Save (applied to
the running proxy with no restart), or set the variables in `.env` and run
`docker compose up -d`. A value saved in Admin → HTTPS wins over `.env`; clearing it there
brings the `.env` value back.

=== "HTTP-01 (public names)"

    1. **DNS.** An A (and/or AAAA) record for each name, pointing at the box's **public**
       address, or at your router with ports 80 and 443 forwarded to the box.
    2. **Ports.** Let's Encrypt only connects to ports 80 and 443, so publish the edge there:

        ```sh
        WEB_PORT=80
        WEB_TLS_PORT=443
        ```

        This moves keyup's plain-HTTP port from 8095 to 80. A recorder whose `[uplink] url`
        still says `:8095` can no longer reach keyup: change it to
        `https://<your keyup name>/api/call-upload` (or `http://<keyup address>/api/call-upload`
        on port 80) and restart the recorder. See [Connect trunkd to keyup](connect.md#2-put-it-in-uplink).

    3. **`.env`:**

        ```sh
        KEYUP_TLS_DOMAINS=keyup.example.org
        KEYUP_TLS_CHALLENGE=http
        ACME_EMAIL=you@example.org
        ACME_CA=
        KEYUP_TLS_REDIRECT_HTTP=true
        PUBLIC_URL=https://keyup.example.org
        PUBLIC_BASE_URL=https://keyup.example.org
        ```

=== "DNS-01 (Cloudflare)"

    1. **Token.** In the Cloudflare dashboard: My Profile → **API Tokens** → *Create Token* →
       *Create Custom Token*, with permission **Zone → DNS → Edit** and zone resources limited
       to the one zone holding your names. Not the Global API Key.
    2. **DNS.** A records in that zone pointing at the box. A private address is fine, since
       the challenge never connects to the box. Set the record to **DNS only** (grey cloud):
       Cloudflare's proxy must be off.

        | Name | Type | Value | Proxy |
        | --- | --- | --- | --- |
        | `keyup.example.org` | A | `192.0.2.10` | DNS only |

    3. **`.env`:**

        ```sh
        KEYUP_TLS_DOMAINS=keyup.example.org
        KEYUP_TLS_CHALLENGE=dns
        WEB_TLS_PORT=443
        CLOUDFLARE_API_TOKEN=<the token from step 1>
        ACME_EMAIL=you@example.org
        ACME_CA=
        KEYUP_TLS_REDIRECT_HTTP=true
        PUBLIC_URL=https://keyup.example.org
        PUBLIC_BASE_URL=https://keyup.example.org
        ```

    `.env` then holds the token in the clear: keep it out of version control. Alternatively
    leave `CLOUDFLARE_API_TOKEN` blank and paste the token into Admin → HTTPS, where it is
    stored write-only (then keep `KEYUP_TLS_CHALLENGE=dns` explicit). **Test Cloudflare token**
    on that page checks the token is live and can see each domain's zone, without issuing
    anything.

`KEYUP_TLS_DOMAINS` takes several space-separated names. **Blank is the off switch**, and is
how keyup ships. `PUBLIC_URL` and `PUBLIC_BASE_URL` are changed **by hand**: nothing derives
them from the domain list, and the session cookie only gets its `Secure` flag when
`PUBLIC_URL` is `https://`.

### Rehearse against staging first

Let's Encrypt's production rate limits are weekly and unforgiving. Point at the staging CA
first:

```sh
ACME_CA=https://acme-staging-v02.api.letsencrypt.org/directory
```

(or *Certificate authority* → `staging` in Admin → HTTPS), start, and confirm a certificate is
issued. Staging certificates are not trusted, so browsers and `curl` complain; that is the
expected result. Then blank `ACME_CA` and restart for the real one.

### Start and watch

```sh
docker compose up -d
docker compose logs -f edge
```

Success looks like `certificate obtained successfully`: seconds for HTTP-01, tens of seconds
for DNS-01 (it waits for the TXT record). Then:

```sh
curl -vk https://keyup.example.org/health      # ok, and the certificate chain
curl -sI http://keyup.example.org/             # 308 redirect to https://
curl -s  http://192.0.2.10/api/status          # the API over plain http, NOT a redirect
```

If nothing happens, the usual causes are a wrongly scoped Cloudflare token (DNS-01), or for
HTTP-01 a name that does not resolve publicly to the box, ports not forwarded, or
`WEB_PORT`/`WEB_TLS_PORT` not 80/443. The edge keeps serving plain HTTP in all of these
cases, so the symptom is "nothing happened". `docker compose logs edge` names the failing
challenge, and the status card in Admin → HTTPS shows **wanted** beside **serving**.

### Recorders keep working

`/health` and `/api/...` are **never redirected**: they answer over plain HTTP on the edge's
HTTP port whichever way `KEYUP_TLS_REDIRECT_HTTP` is set. Recorders often upload by IP
address, and no certificate can cover an IP, so a redirect would break their uploads. Switch
trunkd's `[uplink] url` to `https://keyup.example.org/api/call-upload` when convenient; until
then the upload token crosses your LAN unencrypted, as it did before.

`KEYUP_TLS_REDIRECT_HTTP=false` serves the whole site over plain HTTP **as well as** HTTPS, for
a LAN client that cannot follow a redirect.

### Renewal and storage

Caddy renews each certificate about 30 days before expiry, on its own. Certificates and the
ACME account key live in the `keyup_caddy_data` Docker volume (named after the Compose
project), which survives redeploys, `docker compose down` and rebuilds. Do not prune it:
losing it costs a fresh issuance and spends rate limit.

To turn HTTPS off: switch **Serve HTTPS** off in Admin → HTTPS (or blank `KEYUP_TLS_DOMAINS`
and `docker compose up -d`), then set `PUBLIC_URL`/`PUBLIC_BASE_URL` back to `http://`.

## Your own reverse proxy

Point your proxy at the box's `WEB_PORT` (`http://192.0.2.10:8095`) and leave
`KEYUP_TLS_DOMAINS` blank. keyup's own nginx has the WebSocket and server-sent-events
handling its live routes need, but **a proxy in front does not inherit it**. If the outer
proxy gets these wrong, the pages and call lists load fine while the header badge says
**Offline** or the live page says **Reconnecting** for ever.

What the outer hop must do:

| Route | Type | Needs |
| --- | --- | --- |
| `/api/live` | WebSocket | HTTP/1.1, `Upgrade`/`Connection` headers, no buffering, 3600 s timeouts |
| `/api/recorder/stream` | WebSocket | the same upgrade headers, 300 s timeouts (trunkd's push channel) |
| `/api/live/sse`, `/api/activity/stream`, `/api/admin/recorders/stream`, `/api/admin/recorders/spectrum/stream` | server-sent events | buffering off, cache off, long read timeout |
| everything under `/api/` | HTTP | no body-size limit (recorder uploads, streamed exports), buffering off (ranged audio) |
| all | | `X-Forwarded-Proto` and `X-Forwarded-Host` set: the API's cookie and same-origin checks read them, and without them every change you make answers 403 |

Also enable HTTP/2 (`http2 on` in nginx): phones on plain HTTP/1.1 run out of connections
while a call is playing.

=== "Caddy"

    Caddy handles WebSockets and SSE without help; only the timeouts, the body limit and the
    flushing need saying:

    ```caddyfile
    keyup.example.org {
    	encode zstd gzip

    	request_body {
    		max_size 0
    	}

    	reverse_proxy 192.0.2.10:8095 {
    		flush_interval -1
    		transport http {
    			read_timeout  3600s
    			write_timeout 3600s
    		}
    		header_up X-Forwarded-Proto {scheme}
    		header_up X-Forwarded-Host  {host}
    	}
    }
    ```

    `flush_interval -1` is the line people miss: without it the event streams look dead.

=== "nginx"

    The complete server block, with the `map` for the `Connection` header, a `location` per
    streaming route and the SSE snippet, is in
    [REVERSE-PROXY.md section 2](reference/keyup/REVERSE-PROXY.md#2-nginx-complete).
    The essentials:

    ```nginx
    client_max_body_size 0;
    large_client_header_buffers 4 32k;
    proxy_http_version 1.1;
    proxy_set_header Host              $host;
    proxy_set_header X-Forwarded-For   $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_set_header X-Forwarded-Host  $host;

    location = /api/live {
        proxy_pass http://192.0.2.10:8095;
        proxy_set_header Upgrade    $http_upgrade;
        proxy_set_header Connection $keyup_connection_upgrade;   # from the map block
        proxy_read_timeout 3600s;
        proxy_send_timeout 3600s;
        proxy_buffering off;
    }
    ```

    Test the upgrade; `101` is the whole test:

    ```sh
    curl -is -o /dev/null -w '%{http_code}\n' \
      -H 'Connection: Upgrade' -H 'Upgrade: websocket' \
      -H 'Sec-WebSocket-Version: 13' -H "Sec-WebSocket-Key: $(openssl rand -base64 16)" \
      https://keyup.example.org/api/live
    ```

=== "Cloudflare Tunnel"

    Point the tunnel's public hostname at the box's `WEB_PORT`, the same target an outer proxy
    would use, and set `EDGE_TRUSTED_PROXIES` in `.env` to the tunnel connector's address.
    The edge then takes the visitor's address from `Cf-Connecting-Ip` for requests from that
    address only. Without it, every visitor shares the connector's address for rate limits
    and login lockouts. Recorders on the LAN can keep uploading to the box's own address and
    never pass through the tunnel.

If you ever run both (an outer proxy in front of an edge that is also doing TLS), the outer
hop must talk HTTPS to `WEB_TLS_PORT` and forward the original `Host`, or Caddy cannot pick
the right certificate.

### Troubleshooting a proxy

| Symptom | Cause |
| --- | --- |
| Header badge reads **Offline**, calls list is fine | `/api/live` upgrade not forwarded: missing `proxy_http_version 1.1` or the upgrade headers |
| The live feed drops every 60 s | The proxy's read timeout is at its default; raise it to 3600 s |
| A recorder says it is connected, keyup shows it offline | `/api/recorder/stream` upgrade or timeout |
| Activity log does not tail, spectrum stays blank | An SSE route is buffered |
| Recorder uploads fail with **413** | Body-size limit on the proxy; set it to unlimited |
| A large selection answers **414** | `large_client_header_buffers 4 32k` missing |
| Signed in, but every change answers **403** | `X-Forwarded-Proto`/`X-Forwarded-Host` not set |

When the WebSocket handshake fails twice in 30 s, the web app falls back to server-sent
events for the rest of the session and says so in the badge's tooltip. That keeps the site
usable; it is not a reason to leave the proxy misconfigured.
