from typing import Any, Dict, List, Protocol


class SourceProvider(Protocol):
    name: str
    reliability_weight: float
    source_type: str

    def collect(self, query: str, topic: str, limit: int) -> List[Dict[str, Any]]:
        """Collect records from an external source."""
