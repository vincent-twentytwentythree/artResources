import json
class Config:
    def __init__(self, config_path):
        with config_path.open(encoding="utf-8") as config_file:
            self.config_data = json.load(config_file)
