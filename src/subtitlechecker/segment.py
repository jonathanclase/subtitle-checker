from dataclasses import dataclass, field
from .fileobject import fileobject

@dataclass
class segment:
    clip_start: str
    audio_clip: fileobject | None = field(default=None)

    def __str__(self):
        return f"{self.clip_start} : {self.audio_clip}"
