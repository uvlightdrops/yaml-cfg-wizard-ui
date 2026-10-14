# yaml-cfg-wizard-ui

Dependency-free Python renderer with packaged HTML, CSS and vanilla JavaScript.
Distribution: `yaml-cfg-wizard-ui`; import: `yaml_cfg_wizard_ui`. Python >=3.10.
No framework, configuration loader, application factory or core runtime dependency.

```python
from yaml_cfg_wizard_ui import render_page

html = render_page(
    endpoint="/api/settings/editor",
    csrf_token=session.csrf,
    title="Startup settings",
    description="Only registered fields; changes apply after restart.",
    saved_message="Saved. Restart required; no restart was performed.",
    fields={
        "service.name": {"type": "string", "maxLength": 200},
        "service.enabled": {"type": "boolean"},
        "service.workers": {"type": "integer"},
        "service.ratio": {"type": "number", "nullable": True},
        "service.optional": {"type": ["string", "null"]},
    },
    script_nonce=nonce,
)
```

Serve as `text/html; charset=utf-8` with `Cache-Control: no-store`. Authenticate
the page and endpoint. Use a fresh nonce and CSP, for example `default-src 'none';
script-src 'nonce-<nonce>'; style-src 'nonce-<nonce>'; connect-src 'self';
frame-ancestors 'self'; base-uri 'none'; form-action 'none'`. Same-origin embedding
works; the ready page sends `{type:"config-editor-ready"}` to its same-origin
parent. A host should check the message origin/source and detect load/timeouts.
Without JavaScript an explicit message is shown. No external assets are fetched.

`endpoint` must be a root-relative same-origin path without query/fragment,
backslashes, controls or protocol-relative authority. Tokens must be nonempty
printable ASCII suitable for a header. All configuration JSON escapes `<`, `>`,
`&` and Unicode; labels, values and messages use `textContent`, not HTML.
Metadata is keyed by allowlisted path and never creates extra rows. Supported
types are `string`, `boolean`, `integer`, `number`, `null`; `type` may be a list.
`nullable` adds null. Without explicit types, a non-null scalar supplies its
current type; integer-versus-number intent requires schema metadata. A null
override with a non-null effective value can use that type. Null-only fields
without metadata cannot be set (an existing override can still be removed).
Boolean input accepts exactly `true`/`false`, numbers use finite JSON syntax,
and integer input requires JavaScript-safe integers. Server validation remains
authoritative. Blank strings and null are distinct; inheritance is removal.

## Language-neutral HTTP contract

Any language can implement the endpoint; no Python runtime is required by it.
This renderer consumes the scalar snapshot shape also supplied by
`yaml_cfg_wizard.editor.Editor.snapshot`, but does not import that package.

* **GET**: return HTTP 200 JSON:
  ```json
  {"revision":"opaque-revision","rows":[
    {"path":"service.name","label":"Service name","description":"Startup only",
     "overridden":false,"override":null,"effective":"example"},
    {"path":"service.workers","label":"Workers","description":"",
     "overridden":true,"override":2,"effective":2}
  ]}
  ```
  Rows must have unique nonempty paths and scalar string/bool/finite-number/null
  values. Revision is a nonempty opaque string. An inherited row has
  `overridden:false`; `override:null` alone does not distinguish inheritance.
* **POST**: `Content-Type: application/json`, `X-CSRF-Token` from the page,
  same-origin session cookie, no redirect. Exactly **one field per request**:
  `{"revision":"opaque-revision","changes":{"service.workers":3},"remove":[]}`
  or `{"revision":"opaque-revision","changes":{},"remove":["service.workers"]}`.
  Return the complete new snapshot after successful persistence.
* **409**: revision conflict. Draft and old revision remain; saving is disabled
  until successful explicit GET reload. Failed reload does not clear conflict.
* **400/422**: validation failure; **401/403**: authentication/CSRF failure;
  **503**: busy/runtime unavailable; other non-2xx statuses are explicit errors.
  Errors may use `{"error":{"code":"...","message":"..."}}`; the UI deliberately
  displays stable local messages, not raw server responses or traceback text.
  JSON/shape errors, network failures, redirects and 15-second timeouts are
  visible and do not replace the prior revision/draft.

The gateway must enforce authorization, CSRF, transport, allowlists, scalar
validation, revision conflicts, request limits and safe errors. Never return
arbitrary configuration or secrets. Rendering metadata is not an authorization
boundary. The renderer reads only packaged resources, never YAML/filesystem
configuration, and performs no deployment/restart.

## Development and packaging

```sh
python -m pip install .
python -I -m unittest discover -s tests -v
python -m pip wheel --no-deps . -w dist
```

DOM tests use an existing Chrome/Chromium executable (`CHROME` may select one),
a loopback fixture server and repository-local profiles; no browser package
dependency is needed. They skip if no browser is installed. Python tests cover
rendering validation and resource inclusion. For isolated wheel validation,
install the wheel into a fresh venv and use `python -I` to import/render, then
inspect the wheel for all three assets.

No license was found in the source repositories. No license is assumed or
invented; choose licensing/maintainers before external publication.
