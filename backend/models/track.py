import dataclasses
from typing import Any, Dict

@dataclasses.dataclass
class Track:
    path: str
    title: str = 'Unknown'
    artist: str = 'Unknown'
    album: str = 'Unknown'
    track_number: int = 0
    duration: float = 0.0
    sample_rate: int = 44100
    bit_depth: int = 16
    channels: int = 2
    cover_hash: str = ''
    mtime: float = 0.0
    size: int = 0
    id: int = 0
    is_liked: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return dataclasses.asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Track':
        return cls(**data)
