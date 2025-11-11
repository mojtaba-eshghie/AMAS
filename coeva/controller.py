from __future__ import annotations
from typing import Dict, Any, Tuple, List
import json, os, math
from .bandits import UCB1, ThompsonBernoulli, EXP3
from .strategies import get_portfolio
from .llm import LLM
from . import oracles, config
from .logging_utils import get_logger, jsonl_write, preview, new_run_id, now_ts, write_text

def _ucb_scores(means: List[float], counts: List[int]) -> List[float]:
    total = sum(counts)
    scores = []
    for r, c in zip(means, counts):
        if c == 0:
            scores.append(float("inf"))
        else:
            scores.append(r + math.sqrt((2.0 * math.log(max(1, total))) / c))
    return scores

def _ucb_table(names: List[str], means: List[float], counts: List[int]) -> List[str]:
    total = sum(counts) if sum(counts) > 0 else 1
    rows = []
    for i, (n, r, c) in enumerate(zip(names, means, counts)):
        bonus = float("inf") if c == 0 else ((2.0 * math.log(total)) / c) ** 0.5
        score = (r if math.isinf(bonus) else r + bonus)
        rows.append(f"{i:>2} | {n:<22} | pulls={c:<3} mean={r:0.3f} ucb={score if not math.isinf(bonus) else float('inf')}")
    return rows

class AgentRunner:
    def __init__(self, role: str, policy: str = 'ucb1'):
        self.role = role.lower()
        self.portfolio = get_portfolio(self.role)
        self.n = len(self.portfolio)
        if policy == 'ucb1':
            self.policy = UCB1()
        elif policy == 'thompson':
            self.policy = ThompsonBernoulli(self.n)
        elif policy == 'exp3':
            self.policy = EXP3(self.n)
        else:
            raise ValueError("policy must be 'ucb1' | 'thompson' | 'exp3'")
        self.rewards = [0.0] * self.n
        self.counts = [0] * self.n
        self.t = 0
        self.llm = LLM()
        self.logger = get_logger(f"coeva.{self.role}", config.LOG_LEVEL)
        if getattr(config, 'LOG_JSONL', False):
            os.makedirs(config.LOG_DIR, exist_ok=True)
        self.run_id = new_run_id()

    def _score(self, artifact) -> Tuple[float, str]:
        if self.role == 'injector':
            return oracles.evaluate_injector(artifact)
        if self.role == 'exploiter':
            return oracles.evaluate_exploiter(artifact)
        if self.role == 'detector':
            return oracles.evaluate_detector(artifact)
        if self.role == 'patcher':
            return oracles.evaluate_patcher(artifact)
        raise ValueError('unknown role')

    def _fill_template(self, template: str, ctx: Dict[str, Any]) -> str:
        # Leave unknown placeholders intact instead of failing hard.
        class _SafeDict(dict):
            def __missing__(self, key):
                return '{' + key + '}'
        try:
            return template.format_map(_SafeDict(**ctx))
        except Exception:
            return template

    def step(self, ctx: Dict[str, Any]) -> Dict[str, Any]:
        ts0 = now_ts()
        prior_counts = list(self.counts)
        prior_means  = list(self.rewards)
        approx_ucb = _ucb_scores(prior_means, [c if c > 0 else 1 for c in prior_counts]) if isinstance(self.policy, UCB1) else None

        names = [s.name for s in self.portfolio]
        for row in _ucb_table(names, prior_means, prior_counts):
            self.logger.debug(f"UCB  {row}")

        idx = self.policy.select(self.rewards, self.counts, self.t)
        self.t += 1
        strat = self.portfolio[idx]
        decision = "explore" if prior_counts[idx] == 0 else "exploit"

        user_prompt = self._fill_template(strat.user_template, ctx)

        # Console logging: decision & strategy
        self.logger.info(f"[t{self.t-1}] select={strat.name} idx={idx} decision={decision}")

        if getattr(config, 'LOG_PROMPTS', False):
            self.logger.debug(f"system_prompt: {preview(strat.system_prompt, getattr(config, 'LOG_PREVIEW_CHARS', 240))}")
            self.logger.debug(f"user_prompt:   {preview(user_prompt, getattr(config, 'LOG_PREVIEW_CHARS', 240))}")

        artifact = self.llm.generate(self.role, strat.name, strat.system_prompt, user_prompt)

        # Artifact preview
        if getattr(config, 'LOG_ARTIFACTS', False):
            if hasattr(artifact, "diff_text"):
                self.logger.debug(f"artifact.diff preview:\n{preview(artifact.diff_text, getattr(config, 'LOG_PREVIEW_CHARS', 240))}")
            elif hasattr(artifact, "sequence"):
                try:
                    seq_json = json.dumps([c.__dict__ for c in artifact.sequence])
                except Exception:
                    seq_json = str(artifact.sequence)
                self.logger.debug(f"artifact.txplan preview: {preview(seq_json, getattr(config, 'LOG_PREVIEW_CHARS', 240))}")
            elif hasattr(artifact, "invariant"):
                self.logger.debug(f"artifact.finding preview: type={getattr(artifact,'type','')} "
                                  f"loc={getattr(artifact,'location','')} inv={getattr(artifact,'invariant','')} "
                                  f"conf={getattr(artifact,'confidence',0)}")

        # Save artifacts to disk (optional)
        artifacts_dir = getattr(config, 'ARTIFACTS_DIR', 'artifacts')
        if artifacts_dir:
            stepdir = os.path.join(artifacts_dir, self.role, f"t{self.t-1:04d}_{strat.name}")
            try:
                if hasattr(artifact, "diff_text"):
                    write_text(os.path.join(stepdir, "patch.diff"), artifact.diff_text)
                elif hasattr(artifact, "sequence"):
                    seq_json = json.dumps([c.__dict__ for c in artifact.sequence], ensure_ascii=False, indent=2)
                    write_text(os.path.join(stepdir, "txplan.json"), seq_json)
                    write_text(os.path.join(stepdir, "rationale.txt"), getattr(artifact, "rationale", ""))
                elif hasattr(artifact, "invariant"):
                    finding = {
                        "type": getattr(artifact, "type", ""),
                        "location": getattr(artifact, "location", ""),
                        "invariant": getattr(artifact, "invariant", ""),
                        "confidence": getattr(artifact, "confidence", 0),
                    }
                    write_text(os.path.join(stepdir, "finding.json"), json.dumps(finding, ensure_ascii=False, indent=2))
            except Exception as e:
                self.logger.debug(f"artifact save skipped: {e}")

        reward, feedback = self._score(artifact)
        self.counts[idx] += 1
        self.rewards[idx] = ((self.rewards[idx] * (self.counts[idx] - 1)) + reward) / self.counts[idx]

        out = {
            'time': ts0,
            'run_id': self.run_id,
            't': self.t - 1,
            'role': self.role,
            'policy': type(self.policy).__name__,
            'selected_idx': idx,
            'selected_name': strat.name,
            'decision': decision,
            'prior_counts': prior_counts,
            'prior_means': prior_means,
            'approx_ucb': approx_ucb,
            'reward': reward,
            'feedback': feedback,
            'post_counts': list(self.counts),
            'post_means': list(self.rewards),
        }

        if getattr(config, 'LOG_PROMPTS', False):
            out['system_prompt'] = strat.system_prompt
            out['user_prompt'] = user_prompt

        if getattr(config, 'LOG_ARTIFACTS', False):
            if hasattr(artifact, "diff_text"):
                out['artifact'] = {'type': 'diff', 'text': artifact.diff_text}
            elif hasattr(artifact, "sequence"):
                try:
                    out['artifact'] = {'type': 'txplan', 'sequence': [c.__dict__ for c in artifact.sequence],
                                       'rationale': getattr(artifact, 'rationale', '')}
                except Exception:
                    out['artifact'] = {'type': 'txplan', 'sequence': str(getattr(artifact, 'sequence', ''))}
            elif hasattr(artifact, "invariant"):
                out['artifact'] = {'type': 'finding',
                                   'finding': {
                                       'type': getattr(artifact, 'type', ''),
                                       'location': getattr(artifact, 'location', ''),
                                       'invariant': getattr(artifact, 'invariant', ''),
                                       'confidence': getattr(artifact, 'confidence', 0),
                                   }}

        # Back-compat keys for earlier scripts
        out['means']  = list(self.rewards)
        out['counts'] = list(self.counts)

        if getattr(config, 'LOG_JSONL', False):
            path = os.path.join(config.LOG_DIR, f'{self.role}.jsonl')
            jsonl_write(path, out)

        # Short console summary
        self.logger.info(f"[t{self.t-1}] reward={reward:.3f} feedback={feedback} means={[round(m,3) for m in self.rewards]}")

        return out
