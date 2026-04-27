"""
Core data classes for the ASCAL action-model learner.

Defines the immutable value types used throughout the system:
    Literal       — a single grounded or lifted fluent with a truth value
    State         — a frozenset of Literals representing a world state
    Action        — an action name + argument tuple
    Demonstration — a (pre_state, action, post_state) triple; post_state is
                    None for negative (failed-action) demonstrations

Also provides helpers for version-space effect enumeration:
    has_contradiction             — detect contradictory literal pairs
    get_subsets                   — powerset of a frozenset
    generate_version_space_effects — all consistent effect hypotheses between bounds
"""
from dataclasses import dataclass
from itertools import combinations

@dataclass(frozen=True)
class Literal:
    fluent: str
    arguments: tuple
    value: bool

    def negated(self) -> "Literal":
        """Return a copy of this literal with the truth value flipped."""
        return Literal(self.fluent, self.arguments, not self.value)
    
    def __repr__(self) -> str:
        prefix = "" if self.value else "¬"
        return f"{prefix}{self.fluent}({', '.join(self.arguments)})"
    
@dataclass(frozen=True)
class State:
    literals: frozenset #frozenset of Literal

    def has_contradictions(self) -> bool:
        """Return True if this state contains a literal and its negation."""
        return any(literal.negated() in self.literals for literal in self.literals)
    
    def intersection(self, other: "State") -> "State":
        """Return a new State with only literals present in both states."""
        return State(self.literals & other.literals)
    
    def difference(self, other: "State") -> "State":
        """Return a new State with literals in self but not in other."""
        return State(self.literals - other.literals) 

    def issubset(self, other: "State") -> bool:
        """Return True if every literal in self is also in other."""
        return (self.literals <= other.literals)

    def __repr__(self) -> str:
        return f"State({{{', '.join(repr(l) for l in sorted(self.literals, key=str))}}})"
    
@dataclass(frozen=True)
class Action: # similar to Unified Planning ActionInstance but hashable. Better for efficiency
    name: str
    args: tuple

    def __repr__(self) -> str:
        return f"{self.name}({', '.join(str(a) for a in self.args)})"
    
@dataclass(frozen=True)
class Demonstration:
    pre_state: State
    action: Action
    post_state: State | None

    @property
    def is_positive(self) -> bool:
        """True if this is a positive (successful-action) demonstration."""
        return self.post_state is not None

    @property
    def is_negative(self) -> bool:
        """True if this is a negative (failed-action) demonstration."""
        return self.post_state is None

    def __repr__(self) -> str:
        demo_type = "+" if self.is_positive else "-"
        return (
            f"Demonstration({demo_type} "
            f"{self.action} | "
            f"pre={self.pre_state} → "
            f"post={self.post_state if self.is_positive else '⊥'})"
        )

def has_contradiction(h: frozenset) -> bool:
    """
    Return True if h contains both a literal and its negation.
    e.g. {("on",("x","y"),True), ("on",("x","y"),False)} → True
    
    Used to guard against building actions with unsatisfiable preconditions
    """

    return any(literal.negated() in h for literal in h)

def get_subsets(fullset: frozenset) -> list[frozenset]:

    """
    Return all subsets of fullset as a list of frozensets.

    Example:
        get_subsets(frozenset({a, b}))
        → [frozenset(), frozenset({a}), frozenset({b}), frozenset({a,b})]
    """

    elements = tuple(fullset)
    n = len(elements)
    indices = range(n)

    return [
        frozenset(elements[k] for k in indices if i & (1 << k))
        for i in range(1 << n)  # 1 << n is faster than 2**n
    ]
def generate_version_space_effects(heL: frozenset, heU:frozenset) -> set[frozenset]:

    """
    Generate all consistent effect hypotheses h where heL ⊆ h ⊆ heU.
    Filters out hypotheses with contradictions.
    
    Args:
        heL: mandatory effects (lower bound)
        heU: possible effects   (upper bound)
    Returns:
        set of valid non-contradictory effect hypotheses
    """

    diff = heU - heL

    return {
        heL | extension
        for extension in get_subsets(diff)
        if not has_contradiction(heL | extension)
    }
