# Reproducible builds

Use Python 3.12 and uv 0.11.32: `uv sync --locked --all-extras && uv build`. CI records wheel/sdist artifacts, a reproducible CycloneDX SBOM, lock digest, and exact Git SHA. Native packaging remains a release-only check. Do not publish or promote.
