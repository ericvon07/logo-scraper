# Contributing to logo-scraper

Thank you for your interest in contributing. This document covers everything you need to get started.

---

## Table of contents

- [Getting started](#getting-started)
- [Development setup](#development-setup)
- [Making changes](#making-changes)
- [Running tests](#running-tests)
- [Linting](#linting)
- [Opening a pull request](#opening-a-pull-request)
- [Adding a new logo source](#adding-a-new-logo-source)

---

## Getting started

1. **Fork** the repository on GitHub.
2. **Clone** your fork locally:

   ```bash
   git clone https://github.com/your-username/logo-scraper.git
   cd logo-scraper
   ```

3. Add the upstream remote so you can pull future changes:

   ```bash
   git remote add upstream https://github.com/original-owner/logo-scraper.git
   ```

---

## Development setup

Install the package and all development dependencies:

```bash
pip install -e ".[dev]"
```

Copy the environment file and add your logo.dev API key:

```bash
cp .env.example .env
# Edit .env:
# LOGODEV_API_KEY=your_key_here
```

---

## Making changes

Always work on a dedicated branch — never commit directly to `main`.

```bash
# Create a branch from the latest upstream main
git fetch upstream
git checkout -b my-feature upstream/main
```

Branch naming conventions:

| Type      | Pattern                  | Example                     |
|-----------|--------------------------|-----------------------------|
| Feature   | `feat/short-description` | `feat/clearbit-source`      |
| Bug fix   | `fix/short-description`  | `fix/linkedin-blocked-403`  |
| Docs      | `docs/short-description` | `docs/update-readme`        |
| Refactor  | `refactor/description`   | `refactor/orchestrator`     |

Keep commits focused. One logical change per commit, with a clear imperative message:

```
Add Clearbit as a fourth logo source
Fix LinkedIn scraper ignoring status 999
Update README with batch mode example
```

---

## Running tests

```bash
pytest
```

To run a specific test file:

```bash
pytest tests/test_logodev.py
```

To run with verbose output:

```bash
pytest -v
```

All tests must pass before opening a PR. If you add a new feature, add tests for it in the `tests/` directory following the existing naming convention (`test_<module>.py`).

---

## Linting

The project uses [ruff](https://docs.astral.sh/ruff/) for linting and import sorting.

```bash
# Check for issues
ruff check .

# Fix auto-fixable issues
ruff check . --fix
```

Fix any reported issues before submitting. The CI will reject PRs with linting errors.

---

## Opening a pull request

1. Push your branch to your fork:

   ```bash
   git push origin my-feature
   ```

2. Open a pull request against the `main` branch of the upstream repository.

3. Fill in the PR description with:
   - **What** changed and **why**
   - Any relevant issue numbers (`Closes #42`)
   - Steps to test the change manually, if applicable

4. Make sure all checks pass (tests + linting).

A maintainer will review your PR and may request changes. Address feedback with new commits on the same branch — do not force-push once a review has started.

---

## Adding a new logo source

The codebase is designed to make adding sources straightforward:

1. Create `logo_scraper/scraper/your_source.py` with a public function:

   ```python
   def scrape_your_source(
       ...,
       output_dir: Path,
   ) -> list[Logo]:
       ...
   ```

   Return a list of `Logo` objects (see `logo_scraper/models.py`). Use `LogoSource` to add a new enum value for your source.

2. Register it in `logo_scraper/orchestrator.py` following the existing priority pattern.

3. Add tests in `tests/test_your_source.py`.

4. Document the source (requirements, limitations) in `README.md`.
