import logging
from abc import ABC, abstractmethod

from pydantic import BaseModel

logger = logging.getLogger(__name__)


class BaseResultModel(ABC, BaseModel):
    @abstractmethod
    def set_key(self, key: str) -> None: ...
