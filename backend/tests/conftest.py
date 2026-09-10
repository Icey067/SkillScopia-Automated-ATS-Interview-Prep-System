import os

# Unit tests do not need Postgres or a running Docker stack.
os.environ.setdefault("DATABASE_URL", "sqlite://")
