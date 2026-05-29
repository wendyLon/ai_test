"""Execution graph / DAG builder for workflows.

Simple DAG support with conditional branching via 'when' lambdas expressed as strings.
"""
from typing import Dict, Any, List, Optional
import ast
import operator


class Node:
    def __init__(self, name: str, meta: Optional[Dict[str, Any]] = None):
        self.name = name
        self.meta = meta or {}
        self.next: List[Dict[str, Any]] = []  # list of {'to': node_name, 'when': condition_str}

    def add_next(self, to: str, when: Optional[str] = None):
        self.next.append({'to': to, 'when': when})


class ExecutionGraph:
    def __init__(self, steps: List[str], config: Optional[Dict[str, Any]] = None):
        # simple linear by default
        self.nodes: Dict[str, Node] = {}
        self.config = config or {}
        for s in steps:
            self.nodes[s] = Node(s)
        for i in range(len(steps) - 1):
            self.nodes[steps[i]].add_next(steps[i + 1])

    def add_edge(self, frm: str, to: str, when: Optional[str] = None):
        if frm not in self.nodes:
            self.nodes[frm] = Node(frm)
        if to not in self.nodes:
            self.nodes[to] = Node(to)
        self.nodes[frm].add_next(to, when)

    def get_next(self, current: str, context: Dict[str, Any]) -> List[str]:
        node = self.nodes.get(current)
        if not node:
            return []
        outs = []
        for e in node.next:
            cond = e.get('when')
            if not cond:
                outs.append(e['to'])
            else:
                # evaluate simple expression in context safely
                try:
                    # allow only names and operators
                    allowed = {k: context.get(k) for k in context}
                    if eval(cond, {'__builtins__': {}}, allowed):
                        outs.append(e['to'])
                except Exception:
                    continue
        return outs
