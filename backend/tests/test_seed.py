from app.data.seed import load_and_validate
from app.data.graph import RailwayGraph

def test_seed_is_valid_and_has_expected_scale():
    data = load_and_validate()
    assert len(data["trains"]) == 20
    assert len(data["platforms"]) == 7

def test_graph_pathfinding_and_junction():
    data = load_and_validate(); graph = RailwayGraph(data["nodes"], data["edges"])
    path = graph.get_shortest_route("churchgate", "virar")
    assert path[0] == "churchgate" and path[-1] == "virar"
    assert "vasai_road" in path
