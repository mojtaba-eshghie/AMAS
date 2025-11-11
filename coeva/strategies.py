from __future__ import annotations
from typing import List

Role = str

class Strategy:
    def __init__(self, name: str, system_prompt: str, user_template: str, notes: str = ''):
        self.name = name
        self.system_prompt = system_prompt
        self.user_template = user_template
        self.notes = notes

def _injector_portfolio() -> List[Strategy]:
    sys = 'You edit Solidity contracts. Return only a unified diff. Avoid dead code; touch paths affecting target property. Your reply MUST include "*** Begin Patch" and "*** End Patch" with at least one changed line.'
    return [
        Strategy('bounds-relax', sys,
                 'Target property: {property}\nShort summary: {summary}\nMake a minimal diff that relaxes bounds on inputs affecting {property}. Return only diff.\nFile:\n{file_text}'),
        Strategy('access-slip', sys,
                 'Target property: {property}\nSummary: {summary}\nLoosen access control minimally (e.g., missing onlyOwner) on path to {property}. Return diff.\nFile:\n{file_text}'),
        Strategy('init-bypass', sys,
                 'Target: {property}\nSummary: {summary}\nIntroduce an initialization flag / bypass that weakens preconditions for {property}. Minimal diff.\nFile:\n{file_text}'),
        Strategy('reentrancy-window', sys,
                 'Target: {property}\nSummary: {summary}\nReorder effects/interactions to open a reentrancy window on the path.\nReturn only a unified diff.\nFile:\n{file_text}'),
    ]

def _exploiter_portfolio() -> List[Strategy]:
    sys = 'You propose EVM transaction sequences as JSON. Do not explain; output valid JSON only.'
    return [
        Strategy('direct-call', sys,
                '{{"sequence":[{{"to":"{target}","function":"{sink_fn}","args":{args},"value":"0"}}], "rationale":"direct path"}}'),
        Strategy('approve-then-call', sys,
                '{{"sequence":[{{"to":"{token}","function":"approve","args":["{target}","MAX"],"value":"0"}},{{"to":"{target}","function":"{sink_fn}","args":{args},"value":"0"}}], "rationale":"allowance then sink"}}'),
        Strategy('multi-tx-liquidity', sys,
                '{{"sequence":[{{"to":"{pool}","function":"addLiquidity","args":{liq_args},"value":"0"}},{{"to":"{target}","function":"{sink_fn}","args":{args},"value":"0"}}], "rationale":"state prep then sink"}}'),
    ]

def _detector_portfolio() -> List[Strategy]:
    sys = 'Given a trace snippet and code context, output a JSON finding. No prose.'
    return [
        Strategy('spec-phrase', sys,
                '{{"type":"{spec_type}","location":"{loc}","invariant":"{inv}","confidence":0.72}}'),
        Strategy('flow-anomaly', sys,
                '{{"type":"Flow anomaly","location":"{loc}","invariant":"{inv}","confidence":0.65}}'),
        Strategy('swc-template', sys,
                '{{"type":"SWC template match","location":"{loc}","invariant":"{inv}","confidence":0.61}}'),
    ]

def _patcher_portfolio() -> List[Strategy]:
    sys = 'You produce minimal non-vacuous unified diffs that fix the exploit. Avoid always-false requires; reference tainted vars. Your reply MUST include "*** Begin Patch" and "*** End Patch".'
    return [
        Strategy('precondition-strengthen', sys,
                'Exploit summary: {exploit}\nInsert/strengthen requires around {sink_fn} to enforce {inv}. Return only diff.\n{file_text}'),
        Strategy('cei-refactor', sys,
                'Exploit: {exploit}\nRefactor to Checks-Effects-Interactions; move external calls after state changes. Return only diff.\n{file_text}'),
        Strategy('role-gating', sys,
                'Exploit: {exploit}\nGate sensitive function {sink_fn} by role; ensure legitimate flows remain. Return only diff.\n{file_text}'),
    ]

def get_portfolio(role: Role) -> List[Strategy]:
    role = role.lower()
    if role == 'injector':
        return _injector_portfolio()
    if role == 'exploiter':
        return _exploiter_portfolio()
    if role == 'detector':
        return _detector_portfolio()
    if role == 'patcher':
        return _patcher_portfolio()
    raise ValueError(f'Unknown role: {role}')
