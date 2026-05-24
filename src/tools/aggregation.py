"""Aggregation tool for parallel search results.

This module provides the aggregate_search_results tool that combines and
deduplicates results from multiple search paths, calculating diversity scores.
"""

from langchain_core.tools import tool


@tool
def aggregate_search_results(path_results: list[dict]) -> str:
    """Aggregate and deduplicate results from multiple search paths.
    
    Call this AFTER collecting results from all path SubAgents
    (keyword-precision-searcher, semantic-recall-searcher, structural-combo-searcher).
    
    Args:
        path_results: List of results from each path, each containing:
            - path_id: The path identifier (e.g., "keyword_precision", "semantic_recall", "structural_combination")
            - references_found: List of references from that path, each with ref_id, title, source, abstract
            
    Returns:
        Summary of aggregated results with diversity scores and metrics
        
    Example:
        >>> results = [
        ...     {"path_id": "keyword_precision", "references_found": [{"ref_id": "US1234567", "title": "..."}]},
        ...     {"path_id": "semantic_recall", "references_found": [{"ref_id": "US1234567", "title": "..."}]},
        ...     {"path_id": "structural_combination", "references_found": [{"ref_id": "EP9876543", "title": "..."}]}
        ... ]
        >>> aggregate_search_results(results)
    """
    if not path_results:
        return "No path results provided. Execute search paths first."
    
    unique_refs: dict[str, dict] = {}
    path_stats: dict[str, int] = {}
    
    for pr in path_results:
        path_id = pr.get("path_id", "unknown")
        refs = pr.get("references_found", [])
        path_stats[path_id] = len(refs)
        
        for ref in refs:
            # Normalize reference ID for deduplication
            ref_id = str(ref.get("ref_id", "")).upper().replace(" ", "").replace("-", "")
            if not ref_id:
                continue
                
            if ref_id in unique_refs:
                # Reference found by multiple paths - boost score
                unique_refs[ref_id]["found_by_paths"].append(path_id)
                unique_refs[ref_id]["discovery_count"] += 1
            else:
                unique_refs[ref_id] = {
                    **ref,
                    "ref_id": ref_id,
                    "found_by_paths": [path_id],
                    "discovery_count": 1,
                }
    
    # Calculate diversity scores
    for ref in unique_refs.values():
        # Base score
        base = 1.0
        
        # Multi-path discovery bonus (+0.5 per additional path)
        multi_path_bonus = (ref["discovery_count"] - 1) * 0.5
        
        # Semantic discovery bonus (found different vocabulary)
        semantic_bonus = 0.2 if "semantic_recall" in ref["found_by_paths"] else 0.0
        
        # Combination discovery bonus (covers multiple features)
        combo_bonus = 0.3 if "structural_combination" in ref["found_by_paths"] else 0.0
        
        ref["diversity_score"] = round(base + multi_path_bonus + semantic_bonus + combo_bonus, 2)
    
    # Sort by diversity score (highest first)
    sorted_refs = sorted(unique_refs.values(), key=lambda x: x["diversity_score"], reverse=True)
    
    # Calculate metrics
    total_before = sum(len(pr.get("references_found", [])) for pr in path_results)
    total_after = len(sorted_refs)
    dedup_rate = round((1 - total_after / total_before) * 100, 1) if total_before > 0 else 0
    multi_path_count = len([r for r in sorted_refs if r["discovery_count"] > 1])
    
    # Build summary
    summary = f"""## Aggregation Complete

### Metrics
| Metric | Value |
|--------|-------|
| Paths executed | {len(path_results)} |
| Total refs before dedup | {total_before} |
| Total refs after dedup | {total_after} |
| Deduplication rate | {dedup_rate}% |
| Multi-path discoveries | {multi_path_count} |

### Path Contributions
"""
    
    for path_id, count in path_stats.items():
        summary += f"- **{path_id}**: {count} references\n"
    
    summary += "\n### Top 10 by Diversity Score\n"
    summary += "| Rank | Ref ID | Title | Score | Paths |\n"
    summary += "|------|--------|-------|-------|-------|\n"
    
    for i, ref in enumerate(sorted_refs[:10], 1):
        paths = ", ".join(ref["found_by_paths"])
        title = ref.get("title", "N/A")[:40] + "..." if len(ref.get("title", "")) > 40 else ref.get("title", "N/A")
        summary += f"| {i} | {ref['ref_id']} | {title} | {ref['diversity_score']} | {paths} |\n"
    
    if len(sorted_refs) > 10:
        summary += f"\n*...and {len(sorted_refs) - 10} more references*\n"
    
    summary += """
### Diversity Score Formula
- Base: 1.0
- +0.5 per additional path finding the same reference
- +0.2 if found by semantic path (vocabulary diversity)
- +0.3 if found by combination path (multi-feature coverage)
"""
    
    return summary
