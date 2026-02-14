class EntryModel:
    def __init__(self, data: dict):
        self.data = data

    @property
    def original(self):
        return self.data["original"]

    @property
    def translation(self):
        return self.data["translation"]

    @translation.setter
    def translation(self, value: str):
        self.data["translation"] = value

    @property
    def speaker(self):
        return self.data.get("speaker")

    @property
    def status(self):
        return self.data["status"]
