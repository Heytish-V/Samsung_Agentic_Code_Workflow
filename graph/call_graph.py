"""Directed call graph builder using NetworkX.

Constructs a DiGraph where:
- Nodes are canonical chunk_ids (e.g., 'auth/service.py::AuthService::login')
- Edges point from Caller -> Callee with CallType metadata
- Symbol disambiguation prefers same-file, then import-matched, then all candidates
- External (third-party / stdlib) calls get stub nodes marked is_external=True
"""

import networkx as nx
from typing import Dict, Any, List

from graph.types import NodeAttrs


def build_call_graph(dna_store: Dict[str, Any]) -> nx.DiGraph:
    """Build a directed call graph from a CodeDNA store.

    Args:
        dna_store: Mapping of chunk_id -> CodeDNA objects produced by
                   Nived's parser pipeline.

    Returns:
        NetworkX DiGraph with internal and external nodes wired by
        caller -> callee edges.
    """
    G = nx.DiGraph()

    # 1. Build Symbol Lookup Table: symbol_name -> List[chunk_id]
    symbol_table: Dict[str, List[str]] = {}
    for chunk_id, dna in dna_store.items():
        node_attrs: NodeAttrs = {
            "file": dna.file,
            "symbol": dna.symbol,
            "is_external": False,
            "parent_class": dna.parent_class,
        }
        G.add_node(chunk_id, **node_attrs)
        symbol_table.setdefault(dna.symbol, []).append(chunk_id)

    # 2. Wire Caller -> Callee Edges with Smart Disambiguation
    for chunk_id, dna in dna_store.items():
        caller_file = dna.file
        caller_imports = getattr(dna, "imports", [])

        for callee_symbol in dna.functions_called:
            if callee_symbol in symbol_table:
                candidates = symbol_table[callee_symbol]

                # Rule A: Disambiguate by same-file match (OS-normalized)
                caller_norm = caller_file.replace("\\", "/").lstrip("./")
                same_file_matches = [
                    cid
                    for cid in candidates
                    if dna_store[cid].file.replace("\\", "/").lstrip("./") == caller_norm
                ]
                if same_file_matches:
                    for target_id in same_file_matches:
                        G.add_edge(chunk_id, target_id, call_type="same_file")
                    continue

                # Rule B: Disambiguate by import statement matching
                def _file_matches_import(file_str: str, imp_str: str) -> bool:
                    norm = file_str.replace("\\", "/").lstrip("./").rstrip(".py")
                    dot_path = norm.replace("/", ".")
                    base_mod = norm.split("/")[-1]
                    return dot_path in imp_str or base_mod in imp_str

                imported_matches = [
                    cid
                    for cid in candidates
                    if any(
                        _file_matches_import(dna_store[cid].file, imp)
                        or callee_symbol in imp
                        for imp in caller_imports
                    )
                ]
                if imported_matches:
                    for target_id in imported_matches:
                        G.add_edge(
                            chunk_id, target_id, call_type="imported"
                        )
                    continue

                # Rule C: General internal resolution (all potential targets)
                for target_id in candidates:
                    G.add_edge(chunk_id, target_id, call_type="internal")
            else:
                # Track external third-party or stdlib calls
                ext_id = f"external::{callee_symbol}"
                if ext_id not in G:
                    ext_attrs: NodeAttrs = {
                        "file": "external",
                        "symbol": callee_symbol,
                        "is_external": True,
                        "parent_class": None,
                    }
                    G.add_node(ext_id, **ext_attrs)
                G.add_edge(chunk_id, ext_id, call_type="external")

    return G
