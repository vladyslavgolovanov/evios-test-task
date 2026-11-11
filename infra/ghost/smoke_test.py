"""Exercise the real Ghost stack locally; never targets an existing deployment."""

import http.client
import json
import secrets
import shutil
import subprocess
import tempfile
import uuid
from contextlib import closing
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def check_stack(compose):
    def run(*args):
        return subprocess.check_output(compose + list(args), text=True)

    def port(service, number):
        return int(run("port", service, number).strip().rsplit(":", 1)[1])

    def public(path):
        with closing(
            http.client.HTTPConnection("127.0.0.1", port("caddy", "8080"), timeout=10)
        ) as connection:
            connection.request("GET", path)
            response = connection.getresponse()
            return response.status, response.read()

    def admin(method, body=None):
        with closing(
            http.client.HTTPConnection("127.0.0.1", port("ghost", "2368"), timeout=10)
        ) as connection:
            connection.request(
                method,
                "/ghost/api/admin/authentication/setup/",
                body=json.dumps(body) if body else None,
                headers={
                    "Host": "ghost.test:8443",
                    "X-Forwarded-Proto": "https",
                    "Origin": "https://ghost.test:8443",
                    "Content-Type": "application/json",
                },
            )
            response = connection.getresponse()
            return response.status, json.loads(response.read())

    assert public("/")[0] == 200
    for path in [
        "/ghost",
        "/ghost/",
        "/ghost/api/admin/authentication/setup/",
        "/Ghost/",
        "/%67host/",
        "//ghost/",
        "/ghost/api/content/../../admin/authentication/setup/",
        "/ghost/api/content/%2e%2e/admin/authentication/setup/",
    ]:
        assert public(path)[0] == 403, path
    status, body = public("/ghost/api/content/posts/")
    assert status in (400, 401, 403) and "errors" in json.loads(body)
    status, setup = admin("GET")
    assert status == 200 and setup["setup"][0]["status"] is False
    status, _ = admin(
        "POST",
        {
            "setup": [
                {
                    "name": "Test Owner",
                    "email": "owner@example.com",
                    "password": secrets.token_urlsafe(24),
                    "blogTitle": "Persistence check",
                }
            ]
        },
    )
    assert status == 201
    key = run(
        "exec",
        "-T",
        "db",
        "sh",
        "-c",
        'MYSQL_PWD="$MYSQL_PASSWORD" mysql -u ghost -D ghost -N '
        "-e \"SELECT secret FROM api_keys WHERE type='content' LIMIT 1\"",
    ).strip()
    assert key
    status, body = public("/ghost/api/content/posts/?key=" + key)
    assert status == 200 and "posts" in json.loads(body)
    run(
        "exec",
        "-T",
        "ghost",
        "sh",
        "-c",
        "echo retained > /var/lib/ghost/content/smoke-marker",
    )
    run("down")
    run("up", "-d", "--wait", "--wait-timeout", "240")
    status, setup = admin("GET")
    assert status == 200 and setup["setup"][0]["status"] is True
    assert (
        run("exec", "-T", "ghost", "cat", "/var/lib/ghost/content/smoke-marker").strip()
        == "retained"
    )
    assert public("/")[0] == 200
    assert public("/ghost/")[0] == 403
    print(
        "PASS: HTTP behind Funnel, public admin denial, Content API, owner setup, persistence"
    )


def main():
    project = "evios-ghost-check-" + uuid.uuid4().hex[:10]
    with tempfile.TemporaryDirectory(prefix="evios-ghost-") as directory:
        work = Path(directory)
        for name in ("compose.yml", "Caddyfile"):
            shutil.copyfile(ROOT / name, work / name)
        (work / ".env").write_text(
            "\n".join(
                [
                    "BLOG_DOMAIN=ghost.test",
                    "ADMIN_DOMAIN=ghost.test:8443",
                    "MYSQL_PASSWORD=" + secrets.token_hex(32),
                    "MYSQL_ROOT_PASSWORD=" + secrets.token_hex(32),
                ]
            )
        )
        (work / ".env").chmod(0o600)
        (work / "override.yml").write_text("""services:
  ghost:
    ports: !override
      - "127.0.0.1::2368"
  caddy:
    ports: !override
      - "127.0.0.1::8080"
""")
        compose = [
            "docker",
            "compose",
            "--project-directory",
            directory,
            "-p",
            project,
            "-f",
            str(work / "compose.yml"),
            "-f",
            str(work / "override.yml"),
        ]
        try:
            subprocess.run(compose + ["config", "--quiet"], check=True)
            subprocess.run(
                compose + ["up", "-d", "--wait", "--wait-timeout", "240"], check=True
            )
            check_stack(compose)
        finally:
            subprocess.run(
                compose + ["down", "--volumes", "--remove-orphans"], check=True
            )


if __name__ == "__main__":
    main()
