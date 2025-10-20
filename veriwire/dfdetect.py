import random


class DeepfakeDetector:
    def __init__(self, threshold: float = 0.78):
        self.threshold = threshold

    def current_risk(self) -> float:
        base = random.uniform(0.05, 0.25)
        if random.random() < 0.07:
            base += random.uniform(0.5, 0.9)
        return min(1.0, base)

    def is_suspicious(self):
        risk = self.current_risk()
        return risk >= self.threshold, risk


