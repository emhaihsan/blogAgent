"""
Test suite for Stage 1: Basic Blog Writing Agent.
Tests: Orchestrator -> Workers (parallel) -> Reducer
"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from graph.builder import build_graph

app = build_graph()


def test_basic_blog_generation():
    """Test 1: Basic blog generation without research or images."""

    print("=" * 70)
    print("TEST 1: Basic Blog Generation (Stage 1)")
    print("=" * 70)

    topic = "Self Attention in Transformer Architecture"
    result = app.invoke({"topic": topic})

    print()
    print("=" * 70)
    print("VERIFICATION")
    print("=" * 70)

    plan = result["plan"]
    print(f"✓ Plan created: '{plan.title}'")
    print(f"✓ Number of sections: {len(plan.tasks)}")

    for i, task in enumerate(plan.tasks):
        assert task.id, f"Section {i} missing id"
        assert task.title, f"Section {i} missing title"
        assert task.description, f"Section {i} missing description"
    print(f"✓ All {len(plan.tasks)} sections have valid Task structure")

    completed = result["completed_sections"]
    assert len(completed) == len(plan.tasks), "Mismatch between planned and completed sections"
    print(f"✓ Completed sections: {len(completed)}")

    final_blog = result["final_blog"]
    assert len(final_blog) > 0, "Final blog is empty"
    assert plan.title in final_blog, "Blog title not in final blog"
    print(f"✓ Final blog length: {len(final_blog)} characters")

    output_path = "output/blog.md"
    if os.path.exists(output_path):
        print(f"✓ Output file: {output_path} ({os.path.getsize(output_path)} bytes)")
    else:
        print(f"✗ Output file NOT found: {output_path}")

    print()
    print("PREVIEW (first 500 chars)")
    print("=" * 70)
    print(final_blog[:500])
    print("...")

    return result


def test_plan_structure():
    """Test 2: Verify the Plan structure is valid."""

    print("=" * 70)
    print("TEST 2: Plan Structure Validation")
    print("=" * 70)

    result = app.invoke({"topic": "Machine Learning Basics"})
    plan = result["plan"]

    assert plan.title, "Plan missing title"
    print(f"✓ Blog title: {plan.title}")

    assert isinstance(plan.tasks, list), "Tasks should be a list"
    assert 5 <= len(plan.tasks) <= 8, f"Expected 5-8 sections, got {len(plan.tasks)}"
    print(f"✓ Section count: {len(plan.tasks)} (within 5-8 range)")

    for i, task in enumerate(plan.tasks):
        assert task.id.startswith("section_"), f"Task {i} id should start with 'section_'"
        assert len(task.title) > 0, f"Task {i} title is empty"
        assert len(task.description) > 20, f"Task {i} description too short"
    print("✓ All sections have valid structure")

    print()
    for task in plan.tasks:
        print(f"  - {task.id}: {task.title}")

    return result


def test_worker_parallelization():
    """Test 3: Verify workers run in parallel and produce content."""

    print("=" * 70)
    print("TEST 3: Worker Parallelization")
    print("=" * 70)

    result = app.invoke({"topic": "Binary Search Algorithm"})
    completed = result["completed_sections"]
    plan = result["plan"]

    assert len(completed) == len(plan.tasks), "Not all sections were completed"
    print(f"✓ All {len(completed)} sections completed")

    for i, section in enumerate(completed):
        assert len(section) > 100, f"Section {i} is too short"
        assert "##" in section or "#" in section, f"Section {i} missing markdown headers"
    print("✓ All sections have substantial content with markdown formatting")

    total_words = sum(len(s.split()) for s in completed)
    print(f"✓ Total word count: ~{total_words} words")

    return result


def main():
    print()
    print("╔" + "═" * 68 + "╗")
    print("║" + "    STAGE 1: BASIC BLOG WRITING AGENT - TEST SUITE".center(68) + "║")
    print("╚" + "═" * 68 + "╝")
    print()

    try:
        test_basic_blog_generation()
        print()
        test_plan_structure()
        print()
        test_worker_parallelization()

        print()
        print("╔" + "═" * 68 + "╗")
        print("║" + "    ALL STAGE 1 TESTS PASSED ✓".center(68) + "║")
        print("╚" + "═" * 68 + "╝")
        print()

    except Exception as e:
        print()
        print("╔" + "═" * 68 + "╗")
        print("║" + "    TEST FAILED ✗".center(68) + "║")
        print("╚" + "═" * 68 + "╝")
        print(f"\nError: {e}")
        raise


if __name__ == "__main__":
    main()
