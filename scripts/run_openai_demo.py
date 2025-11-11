from __future__ import annotations
import random
import sys
from pathlib import Path

# Ensure project root is on sys.path so absolute imports like `from coeva...` work
# when running this script directly (python3 scripts/run_demo.py).
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from coeva.controller import AgentRunner
from coeva.config import PROVIDER

CTX = {
    'property': 'amountOut >= minOut',
    'summary': 'Router swap requires minimum output; users can manipulate path.',
    'file_text': 'pragma solidity ^0.8.20; contract Example { function swap(uint amount) public { require(amount > 0); } }',
    'target': 'Router',
    'sink_fn': 'swap',
    'args': '["1000"]',
    'token': 'Token',
    'pool': 'Pool',
    'liq_args': '["500","500"]',
    'spec_type': 'Slippage',
    'loc': 'Router.sol:212',
    'inv': 'amountOut >= minOut',
    'exploit': 'Swap path allows output below minOut under crafted reserves',
}

def run_role(role: str, steps: int = 2, policy: str = 'ucb1'):
    print(f"\n== {role.upper()} (policy={policy}, provider={PROVIDER}) ==")
    runner = AgentRunner(role=role, policy=policy)
    for t in range(steps):
        out = runner.step(CTX)
        means = out.get('post_means') or out.get('means') or []
        means = [round(m, 3) for m in means]
        print(f"[t{out['t']}] strategy={out['selected_name']:<22} reward={out['reward']:.3f} means={means}")

if __name__ == '__main__':
    random.seed(0)
    for role in ['injector','exploiter','detector','patcher']:
        run_role(role, steps=2)
