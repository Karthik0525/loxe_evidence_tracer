from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

class FreshnessStatus(Enum):
    FRESH = "✅ Fresh"
    STALE = "⚠️ Stale"
    EXPIRED = "🚨 Expired"

@dataclass
class EvidenceFinding:
    """A structured dataclass for a single piece of evidence."""
    control_id: str
    resource: str
    status: str
    description: str
    evidence: dict
    timestamp: datetime = field(default_factory=datetime.utcnow)
    freshness: FreshnessStatus = FreshnessStatus.FRESH

    def __post_init__(self):
        """Calculate freshness after the object is created."""
        days_old = (datetime.utcnow() - self.timestamp).days
        if days_old > 90:
            self.freshness = FreshnessStatus.EXPIRED
        elif days_old > 30:
            self.freshness = FreshnessStatus.STALE