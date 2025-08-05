import logging
from abc import ABC, abstractmethod

from pydantic import BaseModel

logger = logging.getLogger(__name__)


class BaseResultModel(ABC, BaseModel):
    @abstractmethod
    def set_id(self, id: str) -> None: ...
