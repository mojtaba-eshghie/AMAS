from __future__ import annotations
import math
import random
from typing import List

class BanditPolicy:
    # Base class
    def select(self, rewards: List[float], counts: List[int], t: int) -> int:
        raise NotImplementedError
    def update(self, idx: int, reward: float):
        pass

class UCB1(BanditPolicy):
    # UCB1 for bounded rewards in [0,1].
    def __init__(self):
        self.t = 0

    def select(self, rewards: List[float], counts: List[int], t: int) -> int:
        self.t += 1
        # Pull each arm at least once
        for i, c in enumerate(counts):
            if c == 0:
                return i
        total = sum(counts)
        ucb_scores = []
        for i, (r, c) in enumerate(zip(rewards, counts)):
            bonus = math.sqrt((2.0 * math.log(total)) / c)
            ucb_scores.append(r + bonus)
        return int(max(range(len(ucb_scores)), key=lambda i: ucb_scores[i]))

class ThompsonBernoulli(BanditPolicy):
    # Thompson sampling with Beta priors (treat fractional reward as fractional success)
    def __init__(self, n_arms: int, alpha0: float = 1.0, beta0: float = 1.0):
        self.alpha = [alpha0] * n_arms
        self.beta = [beta0] * n_arms

    def select(self, rewards: List[float], counts: List[int], t: int) -> int:
        samples = []
        for i in range(len(self.alpha)):
            a = random.gammavariate(self.alpha[i], 1.0)
            b = random.gammavariate(self.beta[i], 1.0)
            samples.append(a / (a + b))
        return int(max(range(len(samples)), key=lambda i: samples[i]))

    def update(self, idx: int, reward: float):
        r = max(0.0, min(1.0, reward))
        self.alpha[idx] += r
        self.beta[idx] += 1.0 - r

class EXP3(BanditPolicy):
    # EXP3 for adversarial rewards in [0,1].
    def __init__(self, n_arms: int, gamma: float = 0.07):
        self.n = n_arms
        self.gamma = gamma
        self.weights = [1.0] * n_arms

    def _probs(self):
        total = sum(self.weights)
        return [(1 - self.gamma) * (w / total) + (self.gamma / self.n) for w in self.weights]

    def select(self, rewards: List[float], counts: List[int], t: int) -> int:
        probs = self._probs()
        r = random.random()
        cum = 0.0
        for i, p in enumerate(probs):
            cum += p
            if r <= cum:
                return i
        return self.n - 1

    def update(self, idx: int, reward: float):
        probs = self._probs()
        xhat = reward / max(1e-9, probs[idx])
        self.weights[idx] *= math.exp((self.gamma * xhat) / self.n)
