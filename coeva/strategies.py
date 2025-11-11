# coeva/strategies.py

from dataclasses import dataclass
from typing import List

@dataclass
class Strategy:
    name: str
    system_prompt: str
    user_template: str

def get_portfolio(role: str) -> List[Strategy]:
    role = role.lower()

    if role == "injector":
        injector_one_shot = r'''Example unified diff:
        *** Begin Patch
        *** Update File: contracts/Example.sol
        @@
        - require(amountOut >= minOut, "slippage");
        + require(amountOut >  minOut, "slippage"); // weakened bound
        *** End Patch
        '''
        base_sys = (
            'You edit Solidity contracts. Return only a unified diff. '
            'Avoid dead code; touch paths affecting the target property. '
            'Your reply MUST include "*** Begin Patch" and "*** End Patch" with at least one changed line.\n\n'
            + injector_one_shot  # <— one-shot example lives in the system prompt
            + 'Follow the format above exactly. Do not add prose.'
        )

        return [
            Strategy(
                name="bounds-relax",
                system_prompt=base_sys,
                user_template=(
                    "Target property: {property}\n"
                    "Short summary: {summary}\n"
                    "Make a minimal diff that relaxes bounds on inputs affecting {property}. "
                    "Return only diff.\n"
                    "File:\n{file_text}"
                ),
            ),
            Strategy(
                name="access-slip",
                system_prompt=base_sys,
                user_template=(
                    "Target property: {property}\n"
                    "Summary: {summary}\n"
                    "Loosen access control minimally (e.g., remove or weaken onlyOwner) on a path influencing {property}. "
                    "Return only diff.\n"
                    "File:\n{file_text}"
                ),
            ),
            Strategy(
                name="init-bypass",
                system_prompt=base_sys,
                user_template=(
                    "Target property: {property}\n"
                    "Summary: {summary}\n"
                    "Introduce a subtle initialization/setup bypass that can affect {property}. "
                    "Return only diff.\n"
                    "File:\n{file_text}"
                ),
            ),
            Strategy(
                name="reentrancy-window",
                system_prompt=base_sys,
                user_template=(
                    "Target property: {property}\n"
                    "Summary: {summary}\n"
                    "Create a small reentrancy window or ordering issue that may influence {property}. "
                    "Return only diff.\n"
                    "File:\n{file_text}"
                ),
            ),
        ]

    if role == "patcher":
        patcher_one_shot = r'''Example unified diff:
*** Begin Patch
*** Update File: contracts/Example.sol
@@
- require(amountOut >  minOut, "slippage");
+ require(amountOut >= minOut, "slippage"); // strengthened bound
*** End Patch
'''
        base_sys = (
            'You produce minimal, non-vacuous unified diffs that fix the exploit. '
            'Avoid always-false requires; reference tainted vars where applicable. '
            'Your reply MUST include "*** Begin Patch" and "*** End Patch".\n\n'
            + patcher_one_shot  # <— one-shot example lives in the system prompt
            + 'Follow the format above exactly. Do not add prose.'
        )

        return [
            Strategy(
                name="precondition-strengthen",
                system_prompt=base_sys,
                user_template=(
                    "Exploit summary: {exploit}\n"
                    "Insert/strengthen requires around {sink_fn} to enforce {property}. "
                    "Return only diff.\n"
                    "{file_text}"
                ),
            ),
            Strategy(
                name="cei-refactor",
                system_prompt=base_sys,
                user_template=(
                    "Exploit: {exploit}\n"
                    "Refactor to Checks-Effects-Interactions; move external calls after state changes, ensuring {property}. "
                    "Return only diff.\n"
                    "{file_text}"
                ),
            ),
            Strategy(
                name="role-gating",
                system_prompt=base_sys,
                user_template=(
                    "Exploit: {exploit}\n"
                    "Gate risky paths with minimal role checks or circuit-breakers to ensure {property}. "
                    "Return only diff.\n"
                    "{file_text}"
                ),
            ),
        ]

    if role == "exploiter":
        base_sys = "You propose EVM transaction sequences as JSON. Do not explain; output valid JSON only."
        return [
            Strategy(
                name="direct-call",
                system_prompt=base_sys,
                user_template='{"sequence":[{"to":"{target}","function":"{sink_fn}","args":{args},"value":"0"}], "rationale":"direct path"}',
            ),
            Strategy(
                name="approve-then-call",
                system_prompt=base_sys,
                user_template='{"sequence":[{"to":"{token}","function":"approve","args":["{target}","MAX"],"value":"0"},{"to":"{target}","function":"{sink_fn}","args":{args},"value":"0"}], "rationale":"allowance then sink"}',
            ),
            Strategy(
                name="multi-tx-liquidity",
                system_prompt=base_sys,
                user_template='{"sequence":[{"to":"{pool}","function":"addLiquidity","args":{liq_args},"value":"0"},{"to":"{target}","function":"{sink_fn}","args":{args},"value":"0"}], "rationale":"liquidity manipulation then sink"}',
            ),
        ]

    if role == "detector":
        base_sys = "Given a trace snippet and code context, output a JSON finding. No prose."
        return [
            Strategy(
                name="spec-phrase",
                system_prompt=base_sys,
                user_template='{"type":"{spec_type}","location":"{loc}","invariant":"{inv}","confidence":0.72}',
            ),
            Strategy(
                name="flow-anomaly",
                system_prompt=base_sys,
                user_template='{"type":"Flow anomaly","location":"{loc}","invariant":"{inv}","confidence":0.65}',
            ),
            Strategy(
                name="swc-template",
                system_prompt=base_sys,
                user_template='{"type":"SWC template","location":"{loc}","invariant":"{inv}","confidence":0.58}',
            ),
        ]

    raise ValueError(f"unknown role: {role}")
