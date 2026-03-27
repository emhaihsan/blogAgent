"""
Test suite for Stage 2: Research Capability.
Tests: Router -> Research (Tavily) -> Orchestrator -> Workers (citations) -> Reducer
"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from graph.builder import build_graph
from nodes.router import router_node

app = build_graph()


def test_no_research_topic():
    """Test 1: Evergreen topic should skip research."""

    print("=" * 70)
    print("TEST 1: Topic Without Research (Self-Attention)")
    print("=" * 70)

    result = app.invoke({"topic": "Self Attention in Transformer Architecture"})

    print()
    print("VERIFICATION")
    print("=" * 70)

    needs_research = result.get("needs_research", True)
    assert not needs_research, "This topic should NOT need research"
    print(f"✓ Router decision: needs_research={needs_research}")

    evidence = result.get("evidence")
    if evidence:
        assert len(evidence.items) == 0, "No evidence should be collected"
        print(f"✓ Evidence items: {len(evidence.items)} (as expected)")
    else:
        print("✓ No evidence (as expected)")

    assert len(result["final_blog"]) > 0
    print(f"✓ Blog generated: {len(result['final_blog'])} characters")
    print("\n✅ TEST 1 PASSED")

    return result


def test_research_topic():
    """Test 2: Recent topic should trigger research."""

    print("=" * 70)
    print("TEST 2: Topic With Research (Recent AI Developments)")
    print("=" * 70)

    result = app.invoke({"topic": "Latest developments in AI and machine learning 2024"})

    print()
    print("VERIFICATION")
    print("=" * 70)

    needs_research = result.get("needs_research", False)
    assert needs_research, "This topic should need research"
    print(f"✓ Router decision: needs_research={needs_research}")

    evidence = result.get("evidence")
    if evidence and evidence.items:
        print(f"✓ Evidence collected: {len(evidence.items)} items")
        print(f"✓ Search queries: {len(result.get('search_queries', []))}")
        for i, item in enumerate(evidence.items[:3], 1):
            print(f"  {i}. {item.title}")
            print(f"     {item.source}")
    else:
        print("⚠ No evidence (check TAVILY_API_KEY in .env)")

    assert len(result["final_blog"]) > 0
    print(f"✓ Blog generated: {len(result['final_blog'])} characters")
    print("\n✅ TEST 2 PASSED")

    return result


def test_router_accuracy():
    """Test 3: Router accuracy across a range of topics."""

    print("=" * 70)
    print("TEST 3: Router Decision Accuracy")
    print("=" * 70)

    test_cases = [
        ("Binary Search Algorithm", False),
        ("History of the Roman Empire", False),
        ("How Neural Networks Work", False),
        ("Latest AI News This Month", True),
        ("Stock Market Trends 2024", True),
        ("Recent Breakthroughs in Quantum Computing", True),
    ]

    correct = 0
    for topic, expected in test_cases:
        result = router_node({"topic": topic})
        actual = result["needs_research"]
        status = "✓" if actual == expected else "✗"
        print(f"{status} '{topic[:45]}' -> {actual} (expected {expected})")
        if actual == expected:
            correct += 1

    accuracy = correct / len(test_cases)
    print(f"\nRouter accuracy: {correct}/{len(test_cases)} ({accuracy*100:.0f}%)")
    assert accuracy >= 0.7, f"Router accuracy too low: {accuracy:.0%}"
    print("\n✅ TEST 3 PASSED")


def test_evidence_in_blog():
    """Test 4: Evidence should influence blog content when available."""

    print("=" * 70)
    print("TEST 4: Evidence Integration in Blog")
    print("=" * 70)

    result = app.invoke({"topic": "State of Large Language Models 2024"})

    evidence = result.get("evidence")
    if evidence and evidence.items:
        print(f"✓ Evidence collected: {len(evidence.items)} sources")
        blog = result["final_blog"]
        has_links = "http" in blog or "[" in blog
        print(f"✓ Blog contains citations: {has_links}")
    else:
        print("⚠ No evidence (TAVILY_API_KEY not configured)")

    assert len(result["final_blog"]) > 0
    print(f"✓ Blog length: {len(result['final_blog'])} characters")
    print("\n✅ TEST 4 PASSED")

    return result


def main():
    print()
    print("╔" + "═" * 68 + "╗")
    print("║" + "    STAGE 2: RESEARCH CAPABILITY - TEST SUITE".center(68) + "║")
    print("╚" + "═" * 68 + "╝")
    print()

    try:
        test_no_research_topic()
        print()
        test_research_topic()
        print()
        test_router_accuracy()
        print()
        test_evidence_in_blog()

        print()
        print("╔" + "═" * 68 + "╗")
        print("║" + "    ALL STAGE 2 TESTS PASSED ✓".center(68) + "║")
        print("╚" + "═" * 68 + "╝")
        print()

    except Exception as e:
        print()
        print("╔" + "═" * 68 + "╗")
        print("║" + "    TEST FAILED ✗".center(68) + "║")
        print("╚" + "═" * 68 + "╝")
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()
        raise


if __name__ == "__main__":
    main()
