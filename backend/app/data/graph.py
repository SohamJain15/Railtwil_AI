import networkx as nx
from dataclasses import dataclass

@dataclass(frozen=True)
class TrackSegment:
    edge_id: str; from_node: str; to_node: str; length_m: float; nominal_speed_kmph: float; direction: str; track_type: str; capacity: int

class RailwayGraph:
    def __init__(self, nodes: list[dict], edges: list[dict]):
        self.graph = nx.DiGraph()
        for node in nodes: self.graph.add_node(node["node_id"], **node)
        for edge in edges:
            travel_time = edge["length_m"] / max(edge["nominal_speed_kmph"], 1) * 3.6
            self.graph.add_edge(edge["from_node"], edge["to_node"], **edge, travel_time=travel_time, occupancy=0)
    def get_route(self, origin: str, destination: str) -> list[str]: return nx.shortest_path(self.graph, origin, destination, weight="travel_time")
    def get_shortest_route(self, origin: str, destination: str) -> list[str]: return self.get_route(origin, destination)
    def get_route_travel_time(self, route: list[str]) -> float: return sum(self.graph[a][b]["travel_time"] for a, b in zip(route, route[1:]))
    def get_downstream_nodes(self, node: str) -> list[str]: return list(self.graph.successors(node))
    def get_upstream_nodes(self, node: str) -> list[str]: return list(self.graph.predecessors(node))
    def get_conflicting_routes(self, route_a: list[str], route_b: list[str]) -> list[str]: return sorted(set(route_a) & set(route_b))
