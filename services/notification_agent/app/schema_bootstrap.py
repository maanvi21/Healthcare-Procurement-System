"""Bring the database schema up to date on startup.

Replaces a bare `Base.metadata.create_all()`. That call creates whatever tables are
missing but records nothing in `alembic_version`, so Alembic had no idea the schema
existed. The consequence only appears later, the first time a column is added: the
migration cannot be applied, because Alembic sees an unstamped database, assumes it is
empty, and tries to replay the baseline against tables that are already there —

    sqlalchemy.exc.ProgrammingError: type "vendor_type" already exists

— and the only way forward is a hand-run `alembic stamp` inside the container, which has
to be repeated on every environment. Adding a column was therefore a manual operation on
every deployment, which is exactly the situation migrations exist to avoid.

Three cases, all handled here:

* **Fresh database** — no tables at all. Run the migrations; they create everything and
  stamp the revision, so the schema and its version agree from the start.
* **Legacy database** — tables present but no `alembic_version`, i.e. built by the old
  `create_all` path. Adopt it by stamping the baseline (the tables it describes are
  already there), then upgrade to head so any later migration applies normally.
* **Managed database** — already stamped. Just upgrade to head; a no-op when current.

If Alembic cannot run at all, fall back to `create_all` and say so loudly. A service that
starts with a usable schema is better than one that refuses to boot, but this must not be
silent: the fallback leaves the database unstamped, which is how it got here.
"""
import logging
from pathlib import Path

from sqlalchemy import inspect

logger = logging.getLogger(__name__)


def bootstrap_schema(base, engine, baseline_revision: str, service_root: str | Path = ".") -> None:
    """Migrate the schema to head, adopting a pre-Alembic database if it finds one."""
    root = Path(service_root).resolve()
    ini = root / "alembic.ini"

    try:
        from alembic import command
        from alembic.config import Config

        if not ini.exists():
            raise FileNotFoundError(f"no alembic.ini at {ini}")

        inspector = inspect(engine)
        tables = set(inspector.get_table_names())
        stamped = "alembic_version" in tables
        # anything other than Alembic's own bookkeeping table
        has_schema = bool(tables - {"alembic_version"})

        config = Config(str(ini))
        config.set_main_option("script_location", str(root / "alembic"))

        if not stamped and has_schema:
            logger.warning(
                "Database has tables but no alembic_version — adopting it at baseline %s. "
                "This is a database created by the old create_all path.",
                baseline_revision,
            )
            command.stamp(config, baseline_revision)

        command.upgrade(config, "head")
        logger.info("Schema is at head")
    except Exception:
        logger.exception(
            "Alembic bootstrap failed — falling back to create_all. The schema will work "
            "but stays UNSTAMPED, so the next migration will need a manual alembic stamp."
        )
        base.metadata.create_all(bind=engine)
