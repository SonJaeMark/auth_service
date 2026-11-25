# Reusable Django Microservice Blueprint (Dev Container, Docker, Supabase & Render)

Use this blueprint as a standardized starter guide and set of configuration templates for any Django microservice repository in your architecture (such as **Auth Service**, **Exam Service**, **Grading Service**, and **Results Service**).

Each microservice runs in its own GitHub repository, uses a **VS Code Dev Container** for local development with Git/SSH support, uses a **multi-stage Dockerfile** for both development and deployment, connects directly to **Supabase PostgreSQL** with schema isolation (`search_path`), and deploys independently as a **Web Service on Render**.

---

## Reusable Service File Layout

Drop this layout into a new microservice repository and customize the service-specific names (`DB_SCHEMA`, `DJANGO_SETTINGS_MODULE`, Gunicorn WSGI module, and app name):

```text
<service-repo>/
├── .devcontainer/
│   └── devcontainer.json
├── docker/
│   ├── Dockerfile
│   └── entrypoint.sh
├── config/
│   ├── __init__.py
│   ├── settings.py
│   ├── urls.py
│   └── wsgi.py
├── <service_app>/
│   ├── __init__.py
│   ├── admin.py
│   ├── apps.py
│   ├── models.py
│   ├── urls.py
│   └── views.py
├── .env.example
├── .dockerignore
├── compose.dev.yml
├── compose.prod.yml
├── manage.py
├── README.md
└── requirements.txt
```

---

## Step-by-Step Blueprint

### Step 1: Configure Git & SSH for Use Inside the Dev Container

To run `git status`, `git add`, `git commit`, `git push`, and `git pull` smoothly inside the container:

1. **On your host machine**, verify your Git user identity:
   ```bash
   git config --global user.name "Your Name"
   git config --global user.email "you@example.com"
   ```
2. **Ensure your SSH key is loaded in your host SSH agent**:
   - **macOS / Linux:**
     ```bash
     eval "$(ssh-agent -s)"
     ssh-add ~/.ssh/id_ed25519
     ```
   - **Windows (PowerShell):**
     ```powershell
     Start-Service ssh-agent
     ssh-add $env:USERPROFILE\.ssh\id_ed25519
     ```
3. The `Dockerfile` (`dev` stage) installs `git` and `openssh-client`. VS Code Dev Containers forwards `SSH_AUTH_SOCK` and copies host Git config automatically.
4. Once inside the Dev Container terminal, test GitHub SSH authentication:
   ```bash
   ssh -T git@github.com
   ```

---

### Step 2: Set Up Dev Container & Local Dev Docker

#### `.devcontainer/devcontainer.json`

```json
{
  "name": "Django Microservice Dev Container",
  "dockerComposeFile": "../compose.dev.yml",
  "service": "app",
  "workspaceFolder": "/workspace",
  "customizations": {
    "vscode": {
      "extensions": [
        "ms-python.python",
        "ms-python.vscode-pylance",
        "ms-python.debugpy",
        "charliermarsh.ruff",
        "batisteo.vscode-django",
        "ms-azuretools.vscode-docker"
      ],
      "settings": {
        "python.defaultInterpreterPath": "/usr/local/bin/python",
        "python.terminal.activateEnvironment": true,
        "[python]": {
          "editor.formatOnSave": true,
          "editor.codeActionsOnSave": {
            "source.fixAll.ruff": "explicit",
            "source.organizeImports.ruff": "explicit"
          }
        }
      }
    }
  },
  "forwardPorts": [8000],
  "postCreateCommand": "pip install --upgrade pip && pip install -r requirements.txt",
  "remoteUser": "vscode"
}
```

#### `compose.dev.yml`

```yaml
services:
  app:
    build:
      context: .
      dockerfile: docker/Dockerfile
      target: dev
    volumes:
      - .:/workspace:cached
    ports:
      - "8000:8000"
    env_file:
      - .env
    environment:
      - DEBUG=1
    command: sleep infinity
```

---

### Step 3: Create Multi-Stage `Dockerfile` and `entrypoint.sh`

#### `docker/Dockerfile`

```dockerfile
# syntax=docker/dockerfile:1

FROM python:3.14-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /workspace

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# --- Development stage (VS Code Dev Container + Git/SSH) ---
FROM base AS dev

ARG USERNAME=vscode
ARG USER_UID=1000
ARG USER_GID=$USER_UID

RUN groupadd --gid $USER_GID $USERNAME \
    && useradd --uid $USER_UID --gid $USER_GID -m $USERNAME \
    && apt-get update && apt-get install -y --no-install-recommends \
        git \
        openssh-client \
        sudo \
    && echo "$USERNAME ALL=(ALL) NOPASSWD:ALL" > /etc/sudoers.d/$USERNAME \
    && chmod 0440 /etc/sudoers.d/$USERNAME \
    && rm -rf /var/lib/apt/lists/* \
    && chown -R $USERNAME:$USERNAME /workspace

USER $USERNAME

# --- Builder stage (Production wheels) ---
FROM base AS builder

COPY requirements.txt .
RUN pip wheel --wheel-dir=/wheels -r requirements.txt

# --- Production runtime stage (Render / Deployment) ---
FROM base AS prod

RUN groupadd -r django && useradd -r -g django django

COPY --from=builder /wheels /wheels
RUN pip install --no-index --find-links=/wheels /wheels/*.whl && rm -rf /wheels

COPY --chown=django:django . /workspace
COPY --chown=django:django docker/entrypoint.sh /entrypoint.sh

RUN mkdir -p /workspace/staticfiles /workspace/media \
    && chown -R django:django /workspace/staticfiles /workspace/media \
    && chmod +x /entrypoint.sh

USER django
EXPOSE 8000

ENTRYPOINT ["/entrypoint.sh"]
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "2", "--timeout", "120"]
```

#### `docker/entrypoint.sh`

```bash
#!/usr/bin/env bash
set -euo pipefail

if [ "${RUN_MIGRATIONS:-0}" = "1" ]; then
  python manage.py migrate --noinput
fi

if [ "${COLLECT_STATIC:-1}" = "1" ]; then
  python manage.py collectstatic --noinput
fi

exec "$@"
```

---

### Step 4: Create Production Docker Compose, Dependencies, Env & Ignore Files

#### `compose.prod.yml`

```yaml
services:
  web:
    build:
      context: .
      dockerfile: docker/Dockerfile
      target: prod
    ports:
      - "8000:8000"
    env_file:
      - .env
    environment:
      - DEBUG=0
      - COLLECT_STATIC=1
      - RUN_MIGRATIONS=0
```

#### `requirements.txt`

```text
Django>=6.1,<6.2
psycopg[binary]>=3.2
dj-database-url>=2.2
PyJWT>=2.9
gunicorn>=23.0
whitenoise>=6.8
python-dotenv>=1.0
ruff>=0.9
```

#### `.env.example`

Copy this file to `.env` locally (never commit `.env` to Git) and configure matching variables on Render:

```env
DEBUG=1
SECRET_KEY=replace-with-strong-secret-key
ALLOWED_HOSTS=localhost,127.0.0.1,[::1],.onrender.com
DJANGO_SETTINGS_MODULE=config.settings

# Supabase connection string (Transaction pooler uses port 6543; Session/Direct uses 5432)
DATABASE_URL=postgresql://postgres.<project-ref>:<password>@aws-0-<region>.pooler.supabase.com:6543/postgres?sslmode=require

# Optional schema isolation per microservice in Supabase
DB_SCHEMA=auth_svc

DISABLE_SERVER_SIDE_CURSORS=True
```

For an Auth Service deployment, keep `DB_SCHEMA=auth_svc` and
`DISABLE_SERVER_SIDE_CURSORS=True` when using the Supabase transaction pooler.
The settings detect the pooler's `6543` port automatically. Never copy a real
database password or signing secret into `.env.example` or commit them to Git.

#### `.dockerignore`

```text
__pycache__/
*.py[cod]
*$py.class
*.egg-info/
.venv/
venv/
.git/
.github/
.vscode/
.env
*.sqlite3
staticfiles/
media/
```

---

### Step 5: Isolate Data in Supabase & Connect Django

1. In the **Supabase SQL Editor**, create a dedicated schema for the microservice so tables and migrations stay isolated:
   ```sql
   create schema if not exists <service_schema>;
   ```
   *(Examples: `auth_svc`, `exam_svc`, `grading_svc`, `results_svc`.)*

2. In `config/settings.py`, load `.env` early, enforce SSL (`sslmode=require`), disable server-side cursors when using Supabase's transaction pooler on port `6543`, and set `search_path` to `<service_schema>,public`:

```python
import os
from pathlib import Path
import dj_database_url
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

SECRET_KEY = os.environ.get("SECRET_KEY", "dev-only-insecure-secret-key")
JWT_SIGNING_SECRET = os.environ.get("JWT_SIGNING_SECRET", SECRET_KEY)
JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_TTL_SECONDS = int(os.environ.get("ACCESS_TOKEN_TTL_SECONDS", "3600"))
REFRESH_TOKEN_TTL_DAYS = int(os.environ.get("REFRESH_TOKEN_TTL_DAYS", "7"))
DEBUG = os.environ.get("DEBUG", "0") == "1"
ALLOWED_HOSTS = [
    h.strip()
    for h in os.environ.get(
        "ALLOWED_HOSTS", "localhost,127.0.0.1,[::1],.onrender.com"
    ).split(",")
    if h.strip()
]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "whitenoise.runserver_nostatic",
    "django.contrib.staticfiles",
    # Add your service app here, e.g. "auth_service"
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"

db_config = dj_database_url.config(
    default=os.environ.get("DATABASE_URL"),
    conn_max_age=60,
    ssl_require=True,
)

if str(db_config.get("PORT")) == "6543":
    db_config["DISABLE_SERVER_SIDE_CURSORS"] = True

schema = os.environ.get("DB_SCHEMA")
if schema:
    db_config.setdefault("OPTIONS", {})
    db_config["OPTIONS"]["options"] = f"-c search_path={schema},public"

DATABASES = {"default": db_config}

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
```

---

### Step 6: Initialize Django Project, Service App & `/health` Endpoint

Run inside your Dev Container:

```bash
pip install -r requirements.txt
django-admin startproject config .
python manage.py startapp <service_app>
```

#### Health Check View & URLs

Add a `/health` endpoint so local checks, Docker health checks, and Render health checks can verify the service is up:

```python
# <service_app>/views.py
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_GET


@require_GET
def health_check(request):
    return JsonResponse(
        {
            "status": "UP",
            "service": "<service-name>",
            "timestamp": timezone.now().strftime("%Y-%m-%dT%H:%M:%SZ"),
        },
        status=200,
    )
```

```python
# config/urls.py
from django.contrib import admin
from django.urls import include, path
from <service_app>.views import health_check

urlpatterns = [
    path("admin/", admin.site.urls),
    path("health", health_check, name="health"),
    path("api/v1/health", health_check, name="api-v1-health"),
    path("api/v1/<resource>/", include("<service_app>.urls")),
]
```

#### Database Migrations & Verification

```bash
# Create and apply migrations for your service app
python manage.py makemigrations <service_app>
python manage.py migrate

# Start the development server
python manage.py runserver 0.0.0.0:8000
```

Test `/health` in a second terminal:

```bash
curl http://localhost:8000/health
```

---

### Step 7: Optional JWT User Context Middleware (Downstream Services)

For downstream services such as **Exam**, **Grading**, and **Results**, validate the auth service's signed access token in each service. Have the API Gateway forward the original `Authorization: Bearer <access-token>` header; do not trust user ID or role headers supplied by clients.

Copy this middleware into each service as `<service_app>/middleware.py`. It rejects missing, invalid, or expired tokens and attaches the verified identity metadata to the Django request. The auth service's access token contains `uid` (the user's UUID), `sub` (the user code), `role`, and `email`.

```python
# <service_app>/middleware.py
import jwt
from django.conf import settings
from django.http import JsonResponse


class UserContextMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
        self.exempt_paths = set(
            getattr(
                settings,
                "JWT_AUTH_EXEMPT_PATHS",
                ("/health", "/api/v1/health"),
            )
        )

    def __call__(self, request):
        if request.path in self.exempt_paths:
            return self.get_response(request)

        auth_header = request.headers.get("Authorization", "")
        scheme, separator, token = auth_header.partition(" ")
        if not separator or scheme.lower() != "bearer" or not token.strip():
            return JsonResponse({"error": "Unauthorized"}, status=401)

        try:
            claims = jwt.decode(
                token.strip(),
                settings.JWT_SIGNING_SECRET,
                algorithms=[settings.JWT_ALGORITHM],
                options={"require": ["exp", "iat", "sub", "uid", "role"]},
            )
        except jwt.PyJWTError:
            return JsonResponse({"error": "Unauthorized"}, status=401)

        if not all(
            isinstance(claims.get(key), str) and claims[key]
            for key in ("sub", "uid", "role")
        ):
            return JsonResponse({"error": "Unauthorized"}, status=401)

        request.user_id = claims["uid"]
        request.user_code = claims["sub"]
        request.user_role = claims["role"]
        request.user_email = claims.get("email")
        request.auth_claims = claims

        return self.get_response(request)

```

Add the middleware path to the service's existing `MIDDLEWARE` list:

```python
"<service_app>.middleware.UserContextMiddleware",
```

Configure each downstream service with the same `JWT_SIGNING_SECRET` and `JWT_ALGORITHM` as the auth service. Set `JWT_SIGNING_SECRET` explicitly in each deployment rather than relying on a service-specific `SECRET_KEY` fallback. With the current `HS256` algorithm, every service holding this shared secret can also create tokens; use an asymmetric signing algorithm if downstream services should verify tokens without being able to mint them.

Authenticated views can read `request.user_id`, `request.user_code`, `request.user_role`, `request.user_email`, and the complete verified payload from `request.auth_claims`. Health paths `/health` and `/api/v1/health` are exempt by default; override `JWT_AUTH_EXEMPT_PATHS` in settings if needed.

---

### Step 8: Local Prod Test & Deploy to Render

1. **Test the production image locally**:
   ```bash
   docker compose -f compose.prod.yml up --build
   ```
2. **Push to GitHub** using Git inside your Dev Container:
   ```bash
   git status
   git add .
   git commit -m "Initialize microservice with Docker, devcontainer, and Supabase config"
   git push -u origin main
   ```
3. **Deploy on Render**:
   - Create a new **Web Service** linked to the microservice's GitHub repository.
   - Choose **Docker** as the runtime and set the Dockerfile path to `docker/Dockerfile` (target `prod` if configuring build target).
   - Set **Health Check Path** to `/health`.
   - Configure environment variables in Render (**Environment** tab): `SECRET_KEY`, `DEBUG=0`, `DJANGO_SETTINGS_MODULE`, `ALLOWED_HOSTS`, `DATABASE_URL`, `DB_SCHEMA`, and `DISABLE_SERVER_SIDE_CURSORS=True`.