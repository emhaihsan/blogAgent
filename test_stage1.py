"""
Test script for Stage 1: Basic Blog Writing Agent.

This script tests the complete Stage 1 implementation:
- Orchestrator creates a plan
- Workers write sections in parallel
- Reducer merges sections into final blog
"""

import os
from backend import app


def test_basic_blog_generation():
    """Test 1: Basic blog generation without research or images."""
    
    print("=" * 70)
    print("TEST 1: Basic Blog Generation (Stage 1)")
    print("=" * 70)
    print()
    
    # Test topic
    topic = "Self Attention in Transformer Architecture"
    
    print(f"Topic: {topic}")
    print()
    
    # Run the agent
    result = app.invoke({"topic": topic})
    
    # Verify outputs
    print()
    print("=" * 70)
    print("VERIFICATION")
    print("=" * 70)
    
    # Check 1: Plan was created
    plan = result["plan"]
    print(f"✓ Plan created: '{plan.title}'")
    print(f"✓ Number of sections: {len(plan.tasks)}")
    
    # Check 2: All sections have required fields
    for i, task in enumerate(plan.tasks):
        assert task.id, f"Section {i} missing id"
        assert task.title, f"Section {i} missing title"
        assert task.description, f"Section {i} missing description"
    print(f"✓ All {len(plan.tasks)} sections have valid Task structure")
    
    # Check 3: Sections were completed
    completed = result["completed_sections"]
    print(f"✓ Completed sections: {len(completed)}")
    assert len(completed) == len(plan.tasks), "Mismatch between planned and completed sections"
    
    # Check 4: Final blog was created
    final_blog = result["final_blog"]
    print(f"✓ Final blog length: {len(final_blog)} characters")
    assert len(final_blog) > 0, "Final blog is empty"
    assert plan.title in final_blog, "Blog title not in final blog"
    
    # Check 5: Output file exists
    output_path = "output/blog.md"
    if os.path.exists(output_path):
        file_size = os.path.getsize(output_path)
        print(f"✓ Output file exists: {output_path} ({file_size} bytes)")
    else:
        print(f"✗ Output file NOT found: {output_path}")
    
    print()
    print("=" * 70)
    print("PREVIEW (first 1000 chars)")
    print("=" * 70)
    print(final_blog[:1000])
    print("...")
    print()
    
    return result


def test_plan_structure():
    """Test 2: Verify the Plan structure is valid."""
    
    print("=" * 70)
    print("TEST 2: Plan Structure Validation")
    print("=" * 70)
    print()
    
    topic = "Machine Learning Basics"
    result = app.invoke({"topic": topic})
    
    plan = result["plan"]
    
    # Validate plan has title
    assert plan.title, "Plan missing title"
    print(f"✓ Blog title: {plan.title}")
    
    # Validate tasks list
    assert isinstance(plan.tasks, list), "Tasks should be a list"
    assert len(plan.tasks) >= 5, "Should have at least 5 sections"
    assert len(plan.tasks) <= 8, "Should have at most 8 sections"
    print(f"✓ Section count: {len(plan.tasks)} (within 5-8 range)")
    
    # Validate each task
    for i, task in enumerate(plan.tasks):
        assert task.id.startswith("section_"), f"Task {i} id should start with 'section_'"
        assert len(task.title) > 0, f"Task {i} title is empty"
        assert len(task.description) > 20, f"Task {i} description too short"
    
    print(f"✓ All sections have valid structure")
    print()
    
    # Print section breakdown
    print("Section breakdown:")
    for task in plan.tasks:
        print(f"  - {task.id}: {task.title}")
    print()
    
    return result


def test_worker_parallelization():
    """Test 3: Verify workers run and produce output."""
    
    print("=" * 70)
    print("TEST 3: Worker Parallelization")
    print("=" * 70)
    print()
    
    topic = "Binary Search Algorithm"
    result = app.invoke({"topic": topic})
    
    completed = result["completed_sections"]
    plan = result["plan"]
    
    # Verify all sections were written
    assert len(completed) == len(plan.tasks), "Not all sections were completed"
    print(f"✓ All {len(completed)} sections completed")
    
    # Verify each section has content
    for i, section in enumerate(completed):
        assert len(section) > 100, f"Section {i} is too short (likely empty)"
        # Check for markdown formatting
        assert "##" in section or "#" in section, f"Section {i} missing markdown headers"
    
    print(f"✓ All sections have substantial content with markdown formatting")
    
    # Check total word count
    total_words = sum(len(section.split()) for section in completed)
    print(f"✓ Total word count: ~{total_words} words")
    print()
    
    return result


def main():
    """Run all tests."""
    
    print()
    print("╔" + "═" * 68 + "╗")
    print("║" + " " * 68 + "║")
    print("║" + "    STAGE 1: BASIC BLOG WRITING AGENT - TEST SUITE".center(68) + "║")
    print("║" + " " * 68 + "║")
    print("╚" + "═" * 68 + "╝")
    print()
    
    try:
        # Run tests
        test_basic_blog_generation()
        print("\n")
        test_plan_structure()
        print("\n")
        test_worker_parallelization()
        
        # Final summary
        print()
        print("╔" + "═" * 68 + "╗")
        print("║" + " " * 68 + "║")
        print("║" + "    ALL TESTS PASSED ✓".center(68) + "║")
        print("║" + " " * 68 + "║")
        print("╚" + "═" * 68 + "╝")
        print()
        print("Stage 1 is working correctly!")
        print("Next steps: Implement Stage 2 (Research capability)")
        print()
        
    except Exception as e:
        print()
        print("╔" + "═" * 68 + "╗")
        print("║" + "    TEST FAILED ✗".center(68) + "║")
        print("╚" + "═" * 68 + "╝")
        print()
        print(f"Error: {e}")
        raise


if __name__ == "__main__":
    main()
