from abc import ABC, abstractmethod
from typing import List, Dict

class BaseSearchClient(ABC):
    @abstractmethod
    def search(self, query: str, limit: int = 10) -> List[Dict[str, str]]:
        """
        Executes a search and returns a list of result dictionaries.
        Each dictionary should contain 'title', 'text', 'url', and 'source'.
        """
        pass
