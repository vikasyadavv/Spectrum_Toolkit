# The toolkit on the website (cheminations.com/tools/spectrum-toolkit)

How the page reaches the toolkit, and how to set it up again from scratch.
Decided 2026-10-23 (roadmap A1).

```
browser  ->  cheminations.com/api/stk/*      Cloudflare Worker (worker/stk-worker.js): only our pages,
                                              only the toolkit's own requests, 95 MB at most,
                                              120 requests a minute per visitor; adds the secret key
         ->  stkapi.cheminations.com          Cloudflare Tunnel "n8n" (one line in /etc/cloudflared/config.yml)
         ->  127.0.0.1:8100                   the stk container on the VM; refuses requests without the key
```

- **Same address as the website**: the page calls `/api/stk/...` on cheminations.com itself, so
  no cross-site setup is needed and the page's security policy only allows `'self'`.
- **Two locks**: a Cloudflare security rule blocks `stkapi.cheminations.com` for requests without
  the `X-STK-Key` header, and the toolkit checks the key itself (`STK_API_KEY_FILE`; the Docker
  image refuses to start without one).
- **Nothing is kept**: answers to a visitor's own files are never cached (`Cache-Control:
  no-store`). Only `options` and `example`, the same for everyone, are kept by Cloudflare for an
  hour, and served for up to 7 days if the VM is down.
- **Sizes**: Cloudflare's free plan accepts at most 100 MB in one request; the Worker and the
  toolkit both stop at 95 MB with a clear message.

## Endpoints the website may use

`GET` health, options, example; `POST` load, process-file (a file, as a form), process,
figure, groups, style-check (JSON). Anything else, `/docs` included, answers 404 from the
Worker. The toolkit's own answers (results, pictures, and its 413 / 422 / 500 messages) are
passed on unchanged, with `Content-Type`, `Content-Disposition` (the file name) and
`X-Warning` (fonts not installed). The Worker's own refusals use the toolkit's form,
`{"detail": "..."}`, so the page reads every message the same way.

## Setting it up (once)

### 1. The key, on the VM

The container runs as user 1000 (`stk`), and `ubuntu` on the VM is 1001, so the key file
belongs to 1000, readable only by it, in a folder only `ubuntu` can open:

```bash
mkdir -p ~/stk-secrets && chmod 700 ~/stk-secrets
openssl rand -hex 32 | sudo tee ~/stk-secrets/api_key.txt > /dev/null
sudo chown 1000:1000 ~/stk-secrets/api_key.txt && sudo chmod 400 ~/stk-secrets/api_key.txt
```

Read it (to paste into the Worker): `sudo cat ~/stk-secrets/api_key.txt`.

### 2. The container

```bash
cd ~/Spectrum_Toolkit && git pull && sudo docker build -t spectrum-toolkit . && sudo docker rm -f stk && sudo docker run -d --name stk -p 127.0.0.1:8100:8000 -v ~/stk-secrets/api_key.txt:/run/secrets/stk_api_key:ro --restart unless-stopped spectrum-toolkit
```

Check: `curl 127.0.0.1:8100/health` answers 200; `curl 127.0.0.1:8100/example` answers 401;
`curl -H "X-STK-Key: $(sudo cat ~/stk-secrets/api_key.txt)" 127.0.0.1:8100/example` answers 200.
On the `/docs` page (ssh tunnel to 8100), "Authorize" at the top right takes the key.

### 3. The tunnel, on the VM

Add above the last line (`- service: http_status:404`) of `/etc/cloudflared/config.yml`:

```yaml
  - hostname: stkapi.cheminations.com
    service: http://localhost:8100
```

Then `cloudflared tunnel route dns n8n stkapi.cheminations.com` (creates the address) and
`sudo systemctl restart cloudflared` (about 30 s; n8n and FreshRSS come back by themselves).

### 4. The Worker, in the Cloudflare dashboard

1. Workers & Pages > Create > Worker, name `cheminations-stk`; paste `worker/stk-worker.js`; Deploy.
2. Settings > Variables and Secrets > Add > Secret: `STK_API_KEY` = the key from step 1.
3. Domains & Routes (the Worker's own tab) > Add > Route: `cheminations.com/api/stk/*`,
   zone cheminations.com, failure mode "fail closed".
4. Turn off the `workers.dev` address and previews (Domains & Routes).

### 5. The security rule

Security > Security rules > Create rule, "stkapi: only the Worker": when hostname equals
`stkapi.cheminations.com` and the request header `x-stk-key` does not exist, Block.

### 6. Check from outside

`https://cheminations.com/api/stk/health` opened in the address bar answers 403 (only pages of
the site may ask); `https://stkapi.cheminations.com/health` answers 403 (the security rule).
The page itself then works.

## Testing the Worker without deploying it

`worker/test/` runs the Worker file, unchanged, in a browser against a local toolkit with a
test key: 31 checks (who may ask, every endpoint and method, wrong body types, missing and
too-large sizes, uploads of text, .wdf and .mat files from data/, pictures and their headers,
the toolkit's own messages, a wrong key, the VM being down, the rate limit). Browsers have the
same `Request`, `Response` and `Headers` as Cloudflare; the page adds stand-ins only for
Cloudflare's cache and for streamed uploads.

```bash
STK_API_KEY=test-key uv run --all-extras uvicorn spectrum_toolkit.api:app --port 8765 &
python3 worker/test/serve.py worker/stk-worker.js data http://127.0.0.1:8765 8766 &
# open http://127.0.0.1:8766/ : the page lists every check as PASS or FAIL
```
