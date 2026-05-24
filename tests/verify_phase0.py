"""Verify Phase 0 integration of get_patent_details."""

from src.tools.search import get_patent_details
print("✅ get_patent_details imported from search.py")
print(f"   Tool name: {get_patent_details.name}")
print(f"   Description: {get_patent_details.description[:80]}...")
print()

from src.tools.registry import get_content_tools, get_all_tools, CONTENT_TOOLS
print("✅ CONTENT_TOOLS registered in registry.py")
print(f"   CONTENT_TOOLS: {[t.name for t in CONTENT_TOOLS]}")
print()

all_tools = get_all_tools()
tool_names = [t.name for t in all_tools]
print(f"✅ get_all_tools() returns {len(all_tools)} tools")
assert "get_patent_details" in tool_names, "get_patent_details NOT in get_all_tools()!"
print("   get_patent_details in get_all_tools(): YES")
print()

content_tools = get_content_tools()
print(f"✅ get_content_tools(): {[t.name for t in content_tools]}")
print()

from src.tools import get_patent_details as gpd, get_content_tools as gct
print("✅ Exported from src.tools.__init__.py")
print()

from src.novelty_checker.deep_agent import load_subagents
subagents = load_subagents()
subagent_names = [s["name"] for s in subagents]
print(f"✅ load_subagents() returned {len(subagents)} subagents:")
for s in subagents:
    tools = [t.name for t in s.get("tools", [])]
    has_details = "get_patent_details" in tools
    marker = " ← has get_patent_details" if has_details else ""
    print(f"   - {s['name']}: {len(tools)} tools{marker}")

assert "citation-researcher" in subagent_names, "citation-researcher NOT in subagents!"
print()
print("✅ citation-researcher subagent exists")

cit = next(s for s in subagents if s["name"] == "citation-researcher")
cit_tools = [t.name for t in cit.get("tools", [])]
print(f"   Tools: {cit_tools}")
assert "get_patent_details" in cit_tools
assert "get_patent_citations" in cit_tools
print("   ✅ Has both get_patent_details and get_patent_citations")

rw = next(s for s in subagents if s["name"] == "report-writer")
rw_tools = [t.name for t in rw.get("tools", [])]
print(f"   report-writer tools: {rw_tools}")
assert "get_patent_details" in rw_tools
print("   ✅ report-writer has get_patent_details")

ca = next(s for s in subagents if s["name"] == "coverage-analyst")
ca_tools = [t.name for t in ca.get("tools", [])]
print(f"   coverage-analyst tools: {ca_tools}")
assert "get_patent_details" in ca_tools
print("   ✅ coverage-analyst has get_patent_details")

print()
print("🎉 ALL PHASE 0 CHECKS PASSED!")
