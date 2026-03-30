"""
Test suite for Stage 4: Streamlit GUI Backend & Integration.
Tests: backend helpers, history persistence, stream execution, zip download,
       optional image generation, per-blog output directories.
"""

import os
import sys
import json
import shutil
import zipfile
import io

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ============================================================================
# TEST 1: run_agent_stream WITHOUT images (default)
# ============================================================================
def test_run_agent_stream_no_images():
    """Stream with generate_images=False should skip image nodes."""
    print("=" * 70)
    print("TEST 1: run_agent_stream (no images — default)")
    print("=" * 70)

    from backend import run_agent_stream, NODE_LABELS

    events = []
    for node_name, node_output in run_agent_stream("Binary Search Algorithm",
                                                    generate_images=False):
        events.append((node_name, node_output))
        label = NODE_LABELS.get(node_name, node_name)
        print(f"  ✅ {label}")

    node_names = [e[0] for e in events]

    # Core nodes
    assert "router" in node_names, "Missing router"
    assert "orchestrator" in node_names, "Missing orchestrator"
    assert "worker_node" in node_names, "Missing worker_node"
    assert "merge_content" in node_names, "Missing merge_content"

    # Should take finalize path, NOT image path
    assert "finalize_blog" in node_names, "Missing finalize_blog (should skip images)"
    assert "decide_images" not in node_names, "decide_images should NOT appear"
    assert "generate_and_place_images" not in node_names, "generate_and_place_images should NOT appear"

    # Final blog present
    last_name, last_output = events[-1]
    assert "final_blog" in last_output, "Last event missing final_blog"
    assert len(last_output["final_blog"]) > 0, "final_blog is empty"

    print(f"\n  Total events: {len(events)}, Final blog: {len(last_output['final_blog']):,} chars")
    print("\n✅ TEST 1 PASSED")
    return events


# ============================================================================
# TEST 2: Per-blog output directory
# ============================================================================
def test_per_blog_output_dir():
    """Each run should create its own output/<timestamp>/ folder."""
    print("=" * 70)
    print("TEST 2: Per-blog output directory isolation")
    print("=" * 70)

    from backend import run_agent_stream, OUTPUT_DIR

    accumulated = {}
    for node_name, node_output in run_agent_stream("Linked List Basics",
                                                    generate_images=False):
        accumulated.update(node_output)

    out_dir = accumulated.get("output_dir", "")
    assert out_dir, "output_dir not found in result"
    assert out_dir.startswith(OUTPUT_DIR), f"output_dir should be under {OUTPUT_DIR}"
    assert os.path.isdir(out_dir), f"output_dir does not exist: {out_dir}"

    blog_path = os.path.join(out_dir, "blog.md")
    assert os.path.isfile(blog_path), f"blog.md not found in {out_dir}"

    with open(blog_path, "r", encoding="utf-8") as f:
        saved_content = f.read()
    assert len(saved_content) > 100, "Saved blog.md is too short"
    assert saved_content == accumulated["final_blog"], "blog.md content doesn't match final_blog"

    print(f"  ✅ Output dir: {out_dir}")
    print(f"  ✅ blog.md: {len(saved_content):,} chars")
    print("\n✅ TEST 2 PASSED")


# ============================================================================
# TEST 3: History persistence — save, load, delete
# ============================================================================
def test_history_persistence():
    """Verify save_to_history, load_history, delete_history_entry."""
    print("=" * 70)
    print("TEST 3: History persistence (save / load / delete)")
    print("=" * 70)

    import backend as _backend

    original_dir = _backend.HISTORY_DIR
    original_file = _backend.HISTORY_FILE

    test_dir = "history_test"
    test_file = os.path.join(test_dir, "blogs.json")
    _backend.HISTORY_DIR = test_dir
    _backend.HISTORY_FILE = test_file

    try:
        if os.path.exists(test_dir):
            shutil.rmtree(test_dir)

        from schemas import Plan, Task, EvidencePack, ImageSpec

        mock_plan = Plan(
            title="Test Blog Title",
            tasks=[
                Task(id="s1", title="Intro", description="Introduction"),
                Task(id="s2", title="Body", description="Main body"),
            ],
        )
        mock_result = {
            "plan": mock_plan,
            "needs_research": False,
            "generate_images": False,
            "output_dir": "output/test_20260101",
            "evidence": EvidencePack(items=[]),
            "image_specs": [],
            "final_blog": "# Test Blog\n\nThis is a test blog.",
        }

        entry = _backend.save_to_history("Test Topic", mock_result)
        assert entry["title"] == "Test Blog Title"
        assert entry["num_sections"] == 2
        assert entry["num_images"] == 0
        assert entry["output_dir"] == "output/test_20260101"
        assert entry["generate_images"] is False
        print("  ✅ save_to_history works (incl. output_dir, generate_images)")

        history = _backend.load_history()
        assert len(history) == 1
        assert history[0]["output_dir"] == "output/test_20260101"
        print("  ✅ load_history works")

        # Save another
        mock_result2 = dict(mock_result)
        mock_result2["final_blog"] = "# Second Blog\n\nAnother test."
        mock_plan2 = Plan(title="Second Title", tasks=[Task(id="s1", title="Only", description="Only")])
        mock_result2["plan"] = mock_plan2
        mock_result2["output_dir"] = "output/test_20260102"
        entry2 = _backend.save_to_history("Second Topic", mock_result2)
        history = _backend.load_history()
        assert len(history) == 2
        assert history[0]["title"] == "Second Title"
        print("  ✅ Multiple entries (newest first)")

        # Delete
        _backend.delete_history_entry(entry["id"])
        history = _backend.load_history()
        assert len(history) == 1
        assert history[0]["title"] == "Second Title"
        print("  ✅ delete_history_entry works")

        _backend.delete_history_entry(entry2["id"])
        assert len(_backend.load_history()) == 0
        print("  ✅ All entries deleted")

    finally:
        _backend.HISTORY_DIR = original_dir
        _backend.HISTORY_FILE = original_file
        if os.path.exists(test_dir):
            shutil.rmtree(test_dir)

    print("\n✅ TEST 3 PASSED")


# ============================================================================
# TEST 4: ZIP download builder
# ============================================================================
def test_zip_download():
    """Verify ZIP contains blog.md + images/ from per-blog output dir."""
    print("=" * 70)
    print("TEST 4: ZIP download builder")
    print("=" * 70)

    # Replicate build_download_zip logic (can't import streamlit_app directly)
    def build_download_zip(blog_md, output_dir):
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("blog.md", blog_md)
            images_dir = os.path.join(output_dir, "images")
            if os.path.isdir(images_dir):
                for fname in os.listdir(images_dir):
                    fpath = os.path.join(images_dir, fname)
                    if os.path.isfile(fpath):
                        zf.write(fpath, f"images/{fname}")
        return buf.getvalue()

    test_dir = "test_zip_output_tmp"
    test_images = os.path.join(test_dir, "images")
    os.makedirs(test_images, exist_ok=True)

    try:
        with open(os.path.join(test_images, "test.png"), "wb") as f:
            f.write(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)

        blog = "# Test\n\nHello\n\n![img](images/test.png)"
        zip_bytes = build_download_zip(blog, test_dir)

        buf = io.BytesIO(zip_bytes)
        with zipfile.ZipFile(buf, "r") as zf:
            names = zf.namelist()
            assert "blog.md" in names
            assert "images/test.png" in names
            print(f"  ✅ ZIP: {len(zip_bytes)} bytes, files: {names}")

    finally:
        shutil.rmtree(test_dir, ignore_errors=True)

    print("\n✅ TEST 4 PASSED")


# ============================================================================
# TEST 5: NODE_LABELS covers all graph nodes
# ============================================================================
def test_node_labels_coverage():
    """Verify NODE_LABELS has entries for all nodes in the graph."""
    print("=" * 70)
    print("TEST 5: NODE_LABELS covers all graph nodes")
    print("=" * 70)

    from backend import NODE_LABELS, app

    graph_nodes = set(app.get_graph().nodes.keys())
    graph_nodes.discard("__start__")
    graph_nodes.discard("__end__")

    labeled = set(NODE_LABELS.keys())

    print(f"  Graph nodes:   {sorted(graph_nodes)}")
    print(f"  Labeled nodes: {sorted(labeled)}")

    missing = graph_nodes - labeled
    assert len(missing) == 0, f"Missing labels: {missing}"
    print("  ✅ All graph nodes have display labels")

    print("\n✅ TEST 5 PASSED")


# ============================================================================
# TEST 6: Streamlit app structure
# ============================================================================
def test_streamlit_app_structure():
    """Verify streamlit_app.py has all required UI components."""
    print("=" * 70)
    print("TEST 6: Streamlit app file structure")
    print("=" * 70)

    app_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "streamlit_app.py",
    )
    assert os.path.exists(app_path)
    print("  ✅ streamlit_app.py exists")

    with open(app_path, "r", encoding="utf-8") as f:
        content = f.read()

    checks = {
        "Page config": "set_page_config" in content,
        "Sidebar": "st.sidebar" in content,
        "Tab: Plan": "📋 Plan" in content,
        "Tab: Blog": "📝 Blog" in content,
        "Tab: Evidence": "🔍 Evidence" in content,
        "Tab: Logs": "📊 Logs" in content,
        "Tab: Images": "🖼️ Images" in content,
        "Topic input": "text_area" in content,
        "Image toggle": "toggle" in content and "Generate Images" in content,
        "Generate button": "Generate Blog" in content,
        "Progress bar": "progress" in content,
        "Download button": "download_button" in content,
        "Blog history": "load_history" in content,
        "Stream execution": "run_agent_stream" in content,
        "ZIP builder": "build_download_zip" in content,
        "Per-blog output_dir": "output_dir" in content,
        "Blog prose CSS": "blog-prose" in content,
    }

    all_pass = True
    for name, found in checks.items():
        status = "✅" if found else "❌"
        print(f"  {status} {name}")
        if not found:
            all_pass = False

    assert all_pass, "Some required UI components are missing"
    print(f"\n  File size: {len(content):,} chars")
    print("\n✅ TEST 6 PASSED")


# ============================================================================
# TEST 7: Full integration — stream → save → load round-trip
# ============================================================================
def test_full_integration():
    """Full integration: stream (no images) → save → load → verify."""
    print("=" * 70)
    print("TEST 7: Full integration round-trip")
    print("=" * 70)

    import backend as _backend

    original_dir = _backend.HISTORY_DIR
    original_file = _backend.HISTORY_FILE
    test_dir = "history_integ_test"
    test_file = os.path.join(test_dir, "blogs.json")
    _backend.HISTORY_DIR = test_dir
    _backend.HISTORY_FILE = test_file

    try:
        if os.path.exists(test_dir):
            shutil.rmtree(test_dir)

        accumulated = {}
        node_count = 0
        for node_name, node_output in _backend.run_agent_stream(
            "Bubble Sort Algorithm", generate_images=False
        ):
            accumulated.update(node_output)
            node_count += 1
            print(f"  ✅ {_backend.NODE_LABELS.get(node_name, node_name)}")

        assert node_count >= 5
        assert accumulated.get("final_blog")
        assert accumulated.get("output_dir")
        print(f"  ✅ Streamed {node_count} nodes, blog={len(accumulated['final_blog']):,} chars")
        print(f"  ✅ Output dir: {accumulated['output_dir']}")

        # Save
        entry = _backend.save_to_history("Bubble Sort Algorithm", accumulated)
        assert entry["id"]
        assert entry["output_dir"] == accumulated["output_dir"]
        print(f"  ✅ Saved to history: id={entry['id']}")

        # Load and verify
        history = _backend.load_history()
        assert len(history) == 1
        loaded = history[0]
        assert loaded["title"] == entry["title"]
        assert loaded["final_blog"] == accumulated["final_blog"]
        assert loaded["output_dir"] == accumulated["output_dir"]
        assert loaded["generate_images"] is False
        print(f"  ✅ Round-trip verified: '{loaded['title']}'")
        print(f"  ✅ Plan: {len(loaded['plan']['tasks'])} tasks")

    finally:
        _backend.HISTORY_DIR = original_dir
        _backend.HISTORY_FILE = original_file
        if os.path.exists(test_dir):
            shutil.rmtree(test_dir)

    print("\n✅ TEST 7 PASSED")


# ============================================================================
# MAIN
# ============================================================================
def main():
    print()
    print("╔" + "═" * 68 + "╗")
    print("║" + "    STAGE 4: STREAMLIT GUI - TEST SUITE".center(68) + "║")
    print("╚" + "═" * 68 + "╝")
    print()

    try:
        # Fast tests
        test_node_labels_coverage()
        print()
        test_streamlit_app_structure()
        print()
        test_history_persistence()
        print()
        test_zip_download()
        print()

        # LLM tests
        test_run_agent_stream_no_images()
        print()
        test_per_blog_output_dir()
        print()
        test_full_integration()

        print()
        print("╔" + "═" * 68 + "╗")
        print("║" + "    ALL STAGE 4 TESTS PASSED ✓".center(68) + "║")
        print("╚" + "═" * 68 + "╝")
        print()
        print("Features validated:")
        print("  - Image generation is optional (toggle)")
        print("  - Per-blog output directories (output/<timestamp>/)")
        print("  - History persistence with output_dir + generate_images")
        print("  - ZIP download builder (per-blog dir)")
        print("  - NODE_LABELS covers all graph nodes (incl. finalize_blog)")
        print("  - Streamlit app has all required UI components + image toggle")
        print("  - Full integration round-trip (stream → save → load)")
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
