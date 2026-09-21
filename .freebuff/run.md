# Run doc — Personal starter page (oyedelem.github.io)

Static, dependency-free site: `index.html` + PWA assets (`manifest.json`, `sw.js`, icons).

## 1. Reproduce the artifacts

The only *generated* files are the PWA icons (everything else is committed source):

```bash
python make_icons.py   # writes icon-192.png, icon-512.png, icon-maskable-192.png, icon-maskable-512.png
```

- Requires Python 3 with **numpy** (already available on this machine).
- Only needed if icons are missing or being redesigned; the generated PNGs are committed to the repo.

## 2. Run the server

A real HTTP server is **required** (not the single-file preview and not `file://`):
the manifest, service worker, and icons are sibling files, and service workers
need an http(s) origin.

```bash
python -m http.server 8932 --bind 127.0.0.1
```

- Port: **8932** (project has no default; 8932 is our established port for this site).
- Serve from the repo root so `/index.html`, `/manifest.json`, `/sw.js`, and `/icon-*.png` all resolve.
- Open `http://127.0.0.1:8932/index.html`.
- First load registers the service worker; one extra reload may be needed after a
  `sw.js` version bump before the new shell is served.

Windows detached-start recipe (stdout and stderr must go to different files):

```powershell
powershell -NoProfile -Command "(Start-Process -FilePath 'python.exe' -ArgumentList '-m','http.server','8932','--bind','127.0.0.1' -WorkingDirectory 'C:\Users\moyin\Projects-2026' -RedirectStandardOutput '<log>' -RedirectStandardError '<log>.err' -WindowStyle Hidden -PassThru).Id"
```

Note: the shell wrapper can time out even when the server starts — verify with
`netstat -ano | findstr :8932` and use the reported pid.

Geolocation will fail in sandboxed/headless browsers (graceful "location
unavailable" state by design); real browsers show the permission prompt.
