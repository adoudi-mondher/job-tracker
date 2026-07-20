from langgraph.graph import StateGraph, END

from nodes.analyste import analyste_node
from nodes.redacteur import redacteur_node
from nodes.verificateur import verificateur_node
from state import LMState

_MAX_ITERATIONS = 2


def _route_apres_verification(state: LMState) -> str:
    if state["verification"]["conforme"]:
        return "end"
    if state["nb_iterations"] >= _MAX_ITERATIONS:
        return "end"
    return "redacteur"


def build_graph():
    graph = StateGraph(LMState)

    graph.add_node("analyste", analyste_node)
    graph.add_node("redacteur", redacteur_node)
    graph.add_node("verificateur", verificateur_node)

    graph.set_entry_point("analyste")
    graph.add_edge("analyste", "redacteur")
    graph.add_edge("redacteur", "verificateur")
    graph.add_conditional_edges(
        "verificateur",
        _route_apres_verification,
        {"end": END, "redacteur": "redacteur"},
    )

    return graph.compile()


lm_graph = build_graph()
