"""Static story graph validation utilities."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping, MutableMapping, Sequence

from tbg.domain.defs import StoryChoiceDef, StoryEffectDef, StoryNodeDef


Severity = str

_KNOWN_EFFECT_TYPES = {
    "set_class",
    "start_battle",
    "add_party_member",
    "give_gold",
    "give_exp",
    "give_party_exp",
    "enter_game_menu",
    "set_flag",
    "remove_item",
    "branch_on_flag",
    "quest",
}

_HALTING_EFFECT_TYPES = {"start_battle", "enter_game_menu", "branch_on_flag"}


@dataclass(frozen=True, slots=True)
class Issue:
    severity: Severity
    code: str
    message: str
    context: dict[str, str]


@dataclass(frozen=True, slots=True)
class EntryRoot:
    node_id: str
    source_type: str
    source_id: str
    source_field: str


@dataclass(frozen=True, slots=True)
class EffectView:
    effect_type: str
    data: Mapping[str, object]
    path: str


@dataclass(frozen=True, slots=True)
class NodeInfo:
    node_id: str
    next_node_id: str | None
    choice_next_ids: list[str]
    effects: list[EffectView]
    has_choices: bool


def format_issue(issue: Issue) -> str:
    context = " ".join(f"{key}={value}" for key, value in issue.context.items())
    suffix = f" ({context})" if context else ""
    return f"[{issue.severity}] {issue.code}: {issue.message}{suffix}"


def validate_story_graph(
    story_nodes: Mapping[str, StoryNodeDef] | Sequence[tuple[str, object]],
    entry_roots: Sequence[EntryRoot] | Sequence[str],
    *,
    error_on_autoadvance_cycle: bool = True,
) -> list[Issue]:
    issues: list[Issue] = []
    nodes, duplicate_ids = _coerce_story_nodes(story_nodes)
    for node_id in duplicate_ids:
        issues.append(
            Issue(
                severity="ERROR",
                code="DUPLICATE_NODE_ID",
                message="Duplicate story node id detected.",
                context={"node_id": node_id},
            )
        )
    node_infos: dict[str, NodeInfo] = {}
    for node_id, node in nodes.items():
        node_infos[node_id] = _build_node_info(node_id, node, issues)

    node_ids = set(node_infos.keys())
    entry_root_list = _coerce_entry_roots(entry_roots)

    for entry in entry_root_list:
        if entry.node_id not in node_ids:
            issues.append(
                Issue(
                    severity="ERROR",
                    code="MISSING_ENTRY_ROOT",
                    message="Entry root references missing story node.",
                    context={
                        "source_type": entry.source_type,
                        "source_id": entry.source_id,
                        "field_path": entry.source_field,
                        "referenced_id": entry.node_id,
                    },
                )
            )

    for node_info in node_infos.values():
        _validate_node_references(node_info, node_ids, issues)

    _validate_reachability(node_infos, entry_root_list, issues)
    _validate_auto_advance_cycles(
        node_infos, issues, error_on_autoadvance_cycle=error_on_autoadvance_cycle
    )
    return issues


def _coerce_story_nodes(
    story_nodes: Mapping[str, StoryNodeDef] | Sequence[tuple[str, object]],
) -> tuple[dict[str, object], list[str]]:
    if isinstance(story_nodes, Mapping):
        return dict(story_nodes), []
    nodes: dict[str, object] = {}
    duplicates: list[str] = []
    for node_id, node in story_nodes:
        if node_id in nodes:
            duplicates.append(node_id)
            continue
        nodes[node_id] = node
    return nodes, duplicates


def _coerce_entry_roots(entry_roots: Sequence[EntryRoot] | Sequence[str]) -> list[EntryRoot]:
    roots: list[EntryRoot] = []
    for entry in entry_roots:
        if isinstance(entry, EntryRoot):
            roots.append(entry)
        else:
            roots.append(
                EntryRoot(
                    node_id=str(entry),
                    source_type="unknown",
                    source_id="unknown",
                    source_field="entry_roots",
                )
            )
    return roots


def _build_node_info(node_id: str, node: object, issues: list[Issue]) -> NodeInfo:
    if isinstance(node, StoryNodeDef):
        effects = _effects_from_typed(node.effects, f"story node '{node_id}' effects")
        _warn_on_unknown_effects(node_id, effects, issues)
        for choice_index, choice in enumerate(node.choices):
            _warn_on_unknown_choice_effects(node_id, choice, choice_index, issues)
        choice_next_ids = [choice.next_node_id for choice in node.choices]
        return NodeInfo(
            node_id=node_id,
            next_node_id=node.next_node_id,
            choice_next_ids=choice_next_ids,
            effects=effects,
            has_choices=bool(node.choices),
        )
    if not isinstance(node, dict):
        issues.append(
            Issue(
                severity="ERROR",
                code="INVALID_NODE_TYPE",
                message="Story node payload must be a mapping.",
                context={"node_id": node_id},
            )
        )
        return NodeInfo(
            node_id=node_id,
            next_node_id=None,
            choice_next_ids=[],
            effects=[],
            has_choices=False,
        )
    next_node_id = node.get("next") if isinstance(node.get("next"), str) else None
    choices, choice_next_ids = _parse_choices(node_id, node.get("choices"), issues)
    effects = _parse_effects(node_id, node.get("effects"), issues, context="effects")
    _warn_on_unknown_effects(node_id, effects, issues)
    return NodeInfo(
        node_id=node_id,
        next_node_id=next_node_id,
        choice_next_ids=choice_next_ids,
        effects=effects,
        has_choices=bool(choices),
    )


def _effects_from_typed(effects: Sequence[StoryEffectDef], context: str) -> list[EffectView]:
    return [
        EffectView(effect_type=effect.type, data=effect.data, path=f"{context}[{index}]")
        for index, effect in enumerate(effects)
    ]


def _parse_effects(
    node_id: str,
    raw_effects: object,
    issues: list[Issue],
    *,
    context: str,
) -> list[EffectView]:
    if raw_effects is None:
        return []
    if not isinstance(raw_effects, list):
        issues.append(
            Issue(
                severity="ERROR",
                code="INVALID_EFFECTS",
                message="Effects must be a list if provided.",
                context={"node_id": node_id, "field_path": context},
            )
        )
        return []
    effects: list[EffectView] = []
    for index, entry in enumerate(raw_effects):
        effect_path = f"{context}[{index}]"
        if not isinstance(entry, dict):
            issues.append(
                Issue(
                    severity="ERROR",
                    code="INVALID_EFFECT",
                    message="Effect entry must be an object.",
                    context={"node_id": node_id, "field_path": effect_path},
                )
            )
            continue
        effect_type = entry.get("type")
        if not isinstance(effect_type, str):
            issues.append(
                Issue(
                    severity="ERROR",
                    code="INVALID_EFFECT_TYPE",
                    message="Effect type must be a string.",
                    context={"node_id": node_id, "field_path": effect_path},
                )
            )
            continue
        payload = {key: value for key, value in entry.items() if key != "type"}
        effects.append(EffectView(effect_type=effect_type, data=payload, path=effect_path))
    return effects


def _parse_choices(
    node_id: str, raw_choices: object, issues: list[Issue]
) -> tuple[list[StoryChoiceDef], list[str]]:
    if raw_choices is None:
        return [], []
    if not isinstance(raw_choices, list):
        issues.append(
            Issue(
                severity="ERROR",
                code="INVALID_CHOICES",
                message="Choices must be a list if provided.",
                context={"node_id": node_id, "field_path": "choices"},
            )
        )
        return [], []
    choices: list[StoryChoiceDef] = []
    next_ids: list[str] = []
    for index, entry in enumerate(raw_choices):
        choice_path = f"choices[{index}]"
        if not isinstance(entry, dict):
            issues.append(
                Issue(
                    severity="ERROR",
                    code="INVALID_CHOICE",
                    message="Choice entry must be an object.",
                    context={"node_id": node_id, "field_path": choice_path},
                )
            )
            continue
        label = entry.get("label")
        next_node = entry.get("next")
        if not isinstance(label, str):
            issues.append(
                Issue(
                    severity="ERROR",
                    code="INVALID_CHOICE_LABEL",
                    message="Choice label must be a string.",
                    context={"node_id": node_id, "field_path": f"{choice_path}.label"},
                )
            )
        if not isinstance(next_node, str):
            issues.append(
                Issue(
                    severity="ERROR",
                    code="INVALID_CHOICE_NEXT",
                    message="Choice next must be a string.",
                    context={"node_id": node_id, "field_path": f"{choice_path}.next"},
                )
            )
        if isinstance(label, str) and isinstance(next_node, str):
            next_ids.append(next_node)
            effects = _parse_effects(
                node_id, entry.get("effects"), issues, context=f"{choice_path}.effects"
            )
            _warn_on_unknown_effects(node_id, effects, issues)
            choices.append(StoryChoiceDef(label=label, next_node_id=next_node, effects=[]))
            for effect in effects:
                choices[-1].effects.append(
                    StoryEffectDef(type=effect.effect_type, data=dict(effect.data))
                )
    return choices, next_ids


def _validate_node_references(
    node_info: NodeInfo, node_ids: set[str], issues: list[Issue]
) -> None:
    if node_info.next_node_id and node_info.next_node_id not in node_ids:
        issues.append(
            Issue(
                severity="ERROR",
                code="MISSING_NODE_REF",
                message="Node references missing next node.",
                context={
                    "node_id": node_info.node_id,
                    "field_path": "next",
                    "referenced_id": node_info.next_node_id,
                },
            )
        )
    for index, next_id in enumerate(node_info.choice_next_ids):
        if next_id not in node_ids:
            issues.append(
                Issue(
                    severity="ERROR",
                    code="MISSING_NODE_REF",
                    message="Choice references missing node.",
                    context={
                        "node_id": node_info.node_id,
                        "field_path": f"choices[{index}].next",
                        "referenced_id": next_id,
                    },
                )
            )
    for effect in node_info.effects:
        if effect.effect_type != "branch_on_flag":
            continue
        _validate_branch_effect(node_info.node_id, effect, node_ids, issues)


def _validate_branch_effect(
    node_id: str,
    effect: EffectView,
    node_ids: set[str],
    issues: list[Issue],
) -> None:
    flag_id = effect.data.get("flag_id")
    if not isinstance(flag_id, str):
        issues.append(
            Issue(
                severity="ERROR",
                code="INVALID_BRANCH_ON_FLAG",
                message="branch_on_flag.flag_id must be a string.",
                context={"node_id": node_id, "field_path": f"{effect.path}.flag_id"},
            )
        )
    next_on_true = effect.data.get("next_on_true")
    next_on_false = effect.data.get("next_on_false")
    if not isinstance(next_on_true, str):
        issues.append(
            Issue(
                severity="ERROR",
                code="INVALID_BRANCH_ON_FLAG",
                message="branch_on_flag.next_on_true must be a string.",
                context={"node_id": node_id, "field_path": f"{effect.path}.next_on_true"},
            )
        )
    if not isinstance(next_on_false, str):
        issues.append(
            Issue(
                severity="ERROR",
                code="INVALID_BRANCH_ON_FLAG",
                message="branch_on_flag.next_on_false must be a string.",
                context={"node_id": node_id, "field_path": f"{effect.path}.next_on_false"},
            )
        )
    if isinstance(next_on_true, str) and next_on_true not in node_ids:
        issues.append(
            Issue(
                severity="ERROR",
                code="MISSING_NODE_REF",
                message="branch_on_flag references missing node.",
                context={
                    "node_id": node_id,
                    "field_path": f"{effect.path}.next_on_true",
                    "referenced_id": next_on_true,
                },
            )
        )
    if isinstance(next_on_false, str) and next_on_false not in node_ids:
        issues.append(
            Issue(
                severity="ERROR",
                code="MISSING_NODE_REF",
                message="branch_on_flag references missing node.",
                context={
                    "node_id": node_id,
                    "field_path": f"{effect.path}.next_on_false",
                    "referenced_id": next_on_false,
                },
            )
        )


def _validate_reachability(
    node_infos: Mapping[str, NodeInfo],
    entry_roots: Sequence[EntryRoot],
    issues: list[Issue],
) -> None:
    node_ids = set(node_infos.keys())
    reachable: set[str] = set()
    stack: list[str] = []
    for entry in entry_roots:
        if entry.node_id in node_ids:
            stack.append(entry.node_id)
    while stack:
        node_id = stack.pop()
        if node_id in reachable:
            continue
        reachable.add(node_id)
        node_info = node_infos[node_id]
        if node_info.next_node_id and node_info.next_node_id in node_ids:
            stack.append(node_info.next_node_id)
        for next_id in node_info.choice_next_ids:
            if next_id in node_ids:
                stack.append(next_id)
        for effect in node_info.effects:
            if effect.effect_type != "branch_on_flag":
                continue
            next_on_true = effect.data.get("next_on_true")
            next_on_false = effect.data.get("next_on_false")
            if isinstance(next_on_true, str) and next_on_true in node_ids:
                stack.append(next_on_true)
            if isinstance(next_on_false, str) and next_on_false in node_ids:
                stack.append(next_on_false)
    for node_id in sorted(node_ids - reachable):
        issues.append(
            Issue(
                severity="WARN",
                code="UNREACHABLE_NODE",
                message="Node is unreachable from story roots.",
                context={"node_id": node_id},
            )
        )


def _validate_auto_advance_cycles(
    node_infos: Mapping[str, NodeInfo],
    issues: list[Issue],
    *,
    error_on_autoadvance_cycle: bool,
) -> None:
    candidate_ids = {
        node_id
        for node_id, node_info in node_infos.items()
        if node_info.next_node_id
        and not node_info.has_choices
        and not _has_halting_effect(node_info.effects)
    }
    adjacency: MutableMapping[str, str] = {}
    for node_id in candidate_ids:
        next_node_id = node_infos[node_id].next_node_id
        if next_node_id in candidate_ids:
            adjacency[node_id] = next_node_id

    visited: set[str] = set()
    stack: list[str] = []
    stack_set: set[str] = set()
    cycles: list[list[str]] = []

    def dfs(current: str) -> None:
        visited.add(current)
        stack.append(current)
        stack_set.add(current)
        next_node = adjacency.get(current)
        if next_node:
            if next_node not in visited:
                dfs(next_node)
            elif next_node in stack_set:
                cycle = stack[stack.index(next_node) :]
                cycles.append(cycle)
        stack.pop()
        stack_set.remove(current)

    for node_id in sorted(candidate_ids):
        if node_id not in visited:
            dfs(node_id)

    if not cycles:
        return
    severity = "ERROR" if error_on_autoadvance_cycle else "WARN"
    for cycle in cycles:
        cycle_path = " -> ".join(cycle + [cycle[0]])
        issues.append(
            Issue(
                severity=severity,
                code="AUTOADVANCE_CYCLE",
                message="Auto-advance cycle detected.",
                context={"cycle": cycle_path},
            )
        )


def _has_halting_effect(effects: Sequence[EffectView]) -> bool:
    return any(effect.effect_type in _HALTING_EFFECT_TYPES for effect in effects)


def _warn_on_unknown_effects(
    node_id: str, effects: Sequence[EffectView], issues: list[Issue]
) -> None:
    for effect in effects:
        if effect.effect_type in _KNOWN_EFFECT_TYPES:
            continue
        issues.append(
            Issue(
                severity="WARN",
                code="UNKNOWN_EFFECT_TYPE",
                message="Effect type is not recognized by runtime and will be ignored.",
                context={"node_id": node_id, "field_path": effect.path},
            )
        )


def _warn_on_unknown_choice_effects(
    node_id: str, choice: StoryChoiceDef, choice_index: int, issues: list[Issue]
) -> None:
    for effect_index, effect in enumerate(choice.effects):
        if effect.type in _KNOWN_EFFECT_TYPES:
            continue
        issues.append(
            Issue(
                severity="WARN",
                code="UNKNOWN_EFFECT_TYPE",
                message="Effect type is not recognized by runtime and will be ignored.",
                context={
                    "node_id": node_id,
                    "field_path": f"choices[{choice_index}].effects[{effect_index}]",
                },
            )
        )
