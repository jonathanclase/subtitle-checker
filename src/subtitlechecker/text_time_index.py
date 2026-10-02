from dataclasses import dataclass

@dataclass
class text_time_index():
    secs_timestamp:float
    text:str

    def __str__(self):
        return f"{self.secs_timestamp}: {self.text}"
