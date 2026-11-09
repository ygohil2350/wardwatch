"""Fake bedside monitors. Each patient drifts around a personal baseline; now and then one goes
through an "episode" (a fever, a desaturation...) that pulls a few vitals out of range for a minute
or so and then recovers. Nothing here is real patient data."""

import random
from dataclasses import dataclass, field

# Fictional ward. Names are invented.
PATIENTS = [
    {"bed": "4B-01", "name": "Asha Kulkarni", "age": 67, "reason": "Community-acquired pneumonia",
     "base": {"hr": 88, "spo2": 96, "sys": 128, "dia": 78, "rr": 17, "temp": 37.6}},
    {"bed": "4B-02", "name": "Ravi Deshmukh", "age": 54, "reason": "Post-op day 2, bowel resection",
     "base": {"hr": 82, "spo2": 97, "sys": 122, "dia": 76, "rr": 16, "temp": 37.1}},
    {"bed": "4B-03", "name": "Meera Iyer", "age": 72, "reason": "Heart failure, fluid overload",
     "base": {"hr": 92, "spo2": 96, "sys": 114, "dia": 68, "rr": 17, "temp": 36.8}},
    {"bed": "4B-04", "name": "Joseph D'Souza", "age": 45, "reason": "Cellulitis, IV antibiotics",
     "base": {"hr": 78, "spo2": 98, "sys": 130, "dia": 84, "rr": 15, "temp": 37.9}},
    {"bed": "4B-05", "name": "Farah Shaikh", "age": 81, "reason": "Fall, hip fracture awaiting surgery",
     "base": {"hr": 74, "spo2": 96, "sys": 142, "dia": 80, "rr": 16, "temp": 36.7}},
    {"bed": "4B-06", "name": "Vikram Patil", "age": 59, "reason": "COPD exacerbation",
     "base": {"hr": 90, "spo2": 95, "sys": 134, "dia": 82, "rr": 18, "temp": 37.2}},
    {"bed": "4B-07", "name": "Lata Menon", "age": 38, "reason": "Diabetic ketoacidosis, recovering",
     "base": {"hr": 90, "spo2": 98, "sys": 116, "dia": 72, "rr": 18, "temp": 36.9}},
    {"bed": "4B-08", "name": "Imran Qureshi", "age": 63, "reason": "Upper GI bleed, transfused",
     "base": {"hr": 94, "spo2": 97, "sys": 112, "dia": 66, "rr": 17, "temp": 36.9}},
]

NOISE = {"hr": 2.2, "spo2": 0.45, "sys": 2.6, "dia": 1.8, "rr": 0.7, "temp": 0.04}
EPISODES = {
    "tachycardia": {"hr": 42},
    "desaturation": {"spo2": -9, "rr": 9, "hr": 18},
    "hypotension": {"sys": -38, "dia": -20, "hr": 24},
    "fever": {"temp": 2.4, "hr": 20, "rr": 4},
}
EPISODE_CHANCE = 0.006  # per patient per tick: roughly one episode somewhere on the ward each 1–2 minutes


@dataclass
class Monitor:
    base: dict[str, float]
    value: dict[str, float] = field(default_factory=dict)
    episode: dict[str, float] = field(default_factory=dict)
    ticks_left: int = 0

    def __post_init__(self) -> None:
        self.value = dict(self.base)

    def step(self, rng: random.Random) -> dict[str, float]:
        if self.ticks_left == 0 and rng.random() < EPISODE_CHANCE:
            self.episode = dict(rng.choice(list(EPISODES.values())))
            self.ticks_left = rng.randint(25, 50)
        elif self.ticks_left > 0:
            self.ticks_left -= 1
            if self.ticks_left == 0:
                self.episode = {}

        for k, base in self.base.items():
            target = base + self.episode.get(k, 0)
            v = self.value[k]
            v += (target - v) * 0.12 + rng.gauss(0, NOISE[k])
            self.value[k] = v

        return {
            "hr": round(self.value["hr"]),
            "spo2": min(100, round(self.value["spo2"])),
            "sys": round(self.value["sys"]),
            "dia": round(self.value["dia"]),
            "rr": max(4, round(self.value["rr"])),
            "temp": round(self.value["temp"], 1),
        }
