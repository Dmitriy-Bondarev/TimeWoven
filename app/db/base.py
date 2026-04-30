from sqlalchemy.orm import declarative_base

Base = declarative_base()

# Ensure all model modules are imported so Base.metadata is populated for Alembic.
from app import models  # noqa: F401
