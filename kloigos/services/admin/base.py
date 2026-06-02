from ...repos.postgres import PostgresRepo


class AdminServiceBase:
    def __init__(self, repo: PostgresRepo):
        self.repo = repo
