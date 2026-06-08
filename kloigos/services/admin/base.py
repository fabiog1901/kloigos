from ...repos import Repo


class AdminServiceBase:
    def __init__(self, repo: Repo):
        self.repo = repo
