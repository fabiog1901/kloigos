from .postgres import PostgresRepo


class Repo(PostgresRepo):
    pass


__all__ = ["Repo"]
