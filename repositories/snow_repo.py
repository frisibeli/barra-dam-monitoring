from .base import BaseReadingRepo
from models.reading import SnowReading


class SnowReadingRepo(BaseReadingRepo):
    def __init__(self, path: str):
        super().__init__(path, SnowReading)
