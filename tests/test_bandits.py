from coeva.bandits import UCB1, ThompsonBernoulli, EXP3

def test_ucb1_smoke():
    rewards = [0.0, 0.0, 0.0]
    counts = [0, 0, 0]
    pol = UCB1()
    for t in range(10):
        i = pol.select(rewards, counts, t)
        counts[i] += 1
        rewards[i] = 1.0 if i == 1 else 0.0

def test_thompson_smoke():
    pol = ThompsonBernoulli(3)
    rewards = [0.0, 0.0, 0.0]
    counts = [0, 0, 0]
    for t in range(10):
        i = pol.select(rewards, counts, t)
        pol.update(i, 1.0 if i == 2 else 0.0)

def test_exp3_smoke():
    pol = EXP3(3)
    rewards = [0.0, 0.0, 0.0]
    counts = [0, 0, 0]
    for t in range(10):
        i = pol.select(rewards, counts, t)
        pol.update(i, 1.0 if i == 0 else 0.0)
