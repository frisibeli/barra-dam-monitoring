from .base import BaseReadingRepo
from models.reading import WaterReading


class WaterReadingRepo(BaseReadingRepo):
    def __init__(self, path: str):
        super().__init__(path, WaterReading)
