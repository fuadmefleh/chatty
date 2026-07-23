# Lightweight image for order-explorer-backend - pure Python, reads atlas's
# SQLite files directly via stdlib sqlite3, no compiler toolchain or Node
# needed at all.
FROM python:3.12-slim

WORKDIR /app

COPY order_explorer_site/backend/requirements.txt ./order_explorer_site/backend/requirements.txt
RUN pip install --no-cache-dir -r order_explorer_site/backend/requirements.txt

# No further COPY here - source arrives via a bind mount of the whole repo
# root at runtime (see docker-compose.yml). database.py/exercise_database.py
# resolve data/*.db paths as `Path(__file__).resolve().parent.parent.parent`,
# i.e. three directories up from backend/ - that only lands on the repo's
# real data/ directory if the container's relative layout mirrors the repo
# exactly, which a bind-mounted full tree guarantees and a partial COPY of
# just this directory would break.
