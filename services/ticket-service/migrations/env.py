"""Alembic environment: DATABASE_URL wins over alembic.ini (compose sets it)."""

from __future__ import annotations

import os

from alembic import context
from sqlalchemy import create_engine
from ticket_service.db import metadata, normalise_url

config = context.config
url = normalise_url(os.getenv("DATABASE_URL") or config.get_main_option("sqlalchemy.url"))


def run() -> None:
    if context.is_offline_mode():
        context.configure(url=url, target_metadata=metadata, literal_binds=True)
        with context.begin_transaction():
            context.run_migrations()
        return
    conn = config.attributes.get("connection")
    if conn is not None:  # programmatic upgrade on startup / in tests
        context.configure(connection=conn, target_metadata=metadata)
        with context.begin_transaction():
            context.run_migrations()
        return
    with create_engine(url).connect() as connection:
        context.configure(connection=connection, target_metadata=metadata)
        with context.begin_transaction():
            context.run_migrations()


run()
