# How to Publish AgentGuard to PyPI
## So `pip install agentguard-kernel` works for everyone

---

## Step 1 — Copy these files into your GitHub repo

Add these files to your repo root:

```
agentguard/
  __init__.py       ← provided
  kernel.py         ← your existing kernel.py (upgraded)
pyproject.toml      ← provided
README.md           ← provided (replaces existing)
LICENSE             ← provided
```

---

## Step 2 — Create a PyPI account

1. Go to https://pypi.org/account/register/
2. Register with your email (bkdk62309@gmail.com)
3. Verify your email
4. Go to Account Settings → Add 2FA (required by PyPI)

---

## Step 3 — Create an API Token

1. Go to https://pypi.org/manage/account/token/
2. Click "Add API token"
3. Name it: `agentguard-publish`
4. Scope: "Entire account" (first time), then narrow to project later
5. **Copy the token** — starts with `pypi-` — you only see it once

---

## Step 4 — Install publishing tools (on your machine)

```bash
pip install build twine
```

---

## Step 5 — Build the package

```bash
cd your-repo-root/
python -m build
```

You'll see a `dist/` folder with:
- `agentguard_kernel-0.1.0.tar.gz`
- `agentguard_kernel-0.1.0-py3-none-any.whl`

---

## Step 6 — Test on TestPyPI first (recommended)

```bash
# Upload to test server first
twine upload --repository testpypi dist/*
# Username: __token__
# Password: your pypi- token

# Test install from test server
pip install --index-url https://test.pypi.org/simple/ agentguard-kernel

# Test it works
python -c "from agentguard import TrustEngine; print('works!')"
```

---

## Step 7 — Publish to real PyPI

```bash
twine upload dist/*
# Username: __token__
# Password: your pypi- token
```

Done. Now anyone in the world can run:

```bash
pip install agentguard-kernel
```

---

## Step 8 — Verify it's live

```bash
pip install agentguard-kernel
python -c "from agentguard import TrustEngine; e = TrustEngine(); print(e.get_trust_level('test'))"
# → TRUSTED
```

Check your page at: https://pypi.org/project/agentguard-kernel/

---

## Future releases

When you add features, bump the version in `pyproject.toml`:
```toml
version = "0.1.1"  # or 0.2.0 for bigger changes
```

Then rebuild and re-upload:
```bash
python -m build
twine upload dist/*
```

---

## Optional: GitHub Actions auto-publish

Create `.github/workflows/publish.yml`:

```yaml
name: Publish to PyPI

on:
  push:
    tags:
      - "v*"

jobs:
  publish:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - run: pip install build twine
      - run: python -m build
      - run: twine upload dist/*
        env:
          TWINE_USERNAME: __token__
          TWINE_PASSWORD: ${{ secrets.PYPI_TOKEN }}
```

Then in GitHub → Settings → Secrets → add `PYPI_TOKEN` with your token.

Now every time you push a tag like `v0.2.0`, it auto-publishes. 🚀

---

## Name note

PyPI package name: `agentguard-kernel`  
Import name: `agentguard`

So users do:
```bash
pip install agentguard-kernel   # install command
```
```python
from agentguard import TrustEngine  # import in code
```

This is normal — e.g. `pip install Pillow` → `import PIL`.
