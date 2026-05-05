"""Pure routing function (spec §5.2-5.6).

route(task, agents, policy) -> RunSpec
First matching rule wins. Falls back to default.
"""

from __future__ import annotations

from .models import AgentProfile, RunSpec, Task


def route(
    task: Task,
    agents: list[AgentProfile],
    policy: dict,
    identity: str = "",
) -> RunSpec:
    """Route a task to an agent. Returns a RunSpec."""
    agent = select_agent(task, agents, policy)
    fallback = _get_fallback(task, policy)
    return RunSpec(
        task_id=task.id,
        agent=agent.name,
        identity=identity,
        workspace="",
        image="",
        fallback=fallback,
    )


def select_agent(
    task: Task,
    agents: list[AgentProfile],
    policy: dict,
) -> AgentProfile:
    """Select agent by first matching rule, or default."""
    agent_map = {a.name: a for a in agents}
    for rule in policy.get("rules", []):
        if match_rule(task, rule):
            name = rule["agent"]
            if name in agent_map:
                return agent_map[name]
    default_name = policy["default"]["agent"]
    return agent_map[default_name]


def match_rule(task: Task, rule: dict) -> bool:
    """Check if a task matches a rule's predicates."""
    match = rule.get("match", {})
    for field, expected in match.items():
        actual = getattr(task, field, None)
        if isinstance(expected, list):
            if actual not in expected:
                return False
        elif actual != expected:
            return False
    return True


def _get_fallback(task: Task, policy: dict) -> list[str]:
    """Get fallback chain for a task's route."""
    for rule in policy.get("rules", []):
        if match_rule(task, rule):
            return rule.get("fallback", [])
    return policy["default"].get("fallback", [])
