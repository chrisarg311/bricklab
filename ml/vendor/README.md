# vendor/

Intentionally near-empty. Two reasons this directory exists:

1. `ml/pyproject.toml` declares `[tool.setuptools.packages.find] where = ["src", "vendor"]`, so the path
   must resolve or the package build fails. Git does not track empty directories, hence this file.

2. It documents an absence. The previous team vendored **DSINE** (surface-normal estimation) here. We
   excluded it from our import because its Imperial College London license states:

   > "You may not use the Software for commercial purposes"

   This project may become commercial, so DSINE cannot ship in it. It is listed in `.gitignore` to prevent
   accidental re-adding.

**Consequence:** `ml/src/ptb_ml/priors/` will not run — it imports DSINE. That module belongs to the
dormant COLMAP photogrammetry path, which we are not using. See `docs/DECISIONS.md` D9 and
`docs/THIRD_PARTY.md`.
