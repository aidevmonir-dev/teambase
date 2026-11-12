"""Server setup for shared hosting without Node (cPanel "Setup Python App" > Execute python script).

1. Applies database migrations and collects Django's static files.
2. Downloads the frontend build that CI publishes to the frontend-dist branch and unpacks it into
   FRONTEND_DIR (set it to the subdomain's web folder so the web server serves it directly).
3. Links /static/ into that folder, then asks Passenger to restart the app.

Run it again after every deploy. It never deletes files it did not write.
"""
import io
import os
import sys
import urllib.request
import zipfile
from pathlib import Path

APP = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(APP))
os.chdir(APP)
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django  # noqa: E402

django.setup()

from django.conf import settings  # noqa: E402
from django.core.management import call_command  # noqa: E402

REPO = os.environ.get("FRONTEND_REPO", "aidevmonir-dev/teambase")
BRANCH = os.environ.get("FRONTEND_BRANCH", "frontend-dist")

call_command("migrate", interactive=False)
call_command("collectstatic", interactive=False, verbosity=0)
print("migrations and static files: done")

target = Path(settings.FRONTEND_DIR)
url = f"https://codeload.github.com/{REPO}/zip/refs/heads/{BRANCH}"
request = urllib.request.Request(url, headers={"User-Agent": "teambase-setup"})
with urllib.request.urlopen(request, timeout=60) as response:
    archive = zipfile.ZipFile(io.BytesIO(response.read()))
root = archive.namelist()[0].split("/")[0] + "/"
written = 0
for name in archive.namelist():
    relative = name[len(root):]
    if not relative or name.endswith("/"):
        continue
    destination = (target / relative).resolve()
    if target.resolve() not in destination.parents:
        raise SystemExit(f"refusing to write outside {target}: {relative}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(archive.read(name))
    written += 1
print(f"frontend: {written} files from {REPO}@{BRANCH} into {target}")

static_link = target / "static"
if not static_link.exists():
    os.symlink(settings.STATIC_ROOT, static_link)
    print("linked", static_link, "->", settings.STATIC_ROOT)

restart = APP / "tmp" / "restart.txt"
restart.parent.mkdir(exist_ok=True)
restart.touch()
os.utime(restart)
print("restart requested")
