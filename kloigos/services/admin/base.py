from ...repos.base import BaseRepo


class AdminServiceBase:
    def __init__(self, repo: BaseRepo):
        self.repo = repo
