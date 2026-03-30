"""
Stage 4 — Streamlit GUI for the AI Blog Writing Agent.

Run with:
    streamlit run streamlit_app.py
"""

import os
import io
import zipfile
import time
from datetime import datetime

import streamlit as st

from backend import (
    app,
    run_agent_stream,
    save_to_history,
    load_history,
    delete_history_entry,
    NODE_LABELS,
    OUTPUT_DIR,
)

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="AI Blog Writer",
    page_icon="✍️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Custom CSS
# ---------------------------------------------------------------------------
st.markdown("""
<style>
    /* Sidebar history items */
    .history-item {
        padding: 0.5rem 0;
        border-bottom: 1px solid rgba(128,128,128,0.2);
    }
    /* Progress node labels */
    .node-step {
        padding: 0.25rem 0;
        font-size: 0.9rem;
    }
    .node-done { color: #28a745; }
    .node-active { color: #fd7e14; font-weight: bold; }
    .node-pending { color: #6c757d; }
    /* Image grid */
    .image-card {
        border: 1px solid rgba(128,128,128,0.3);
        border-radius: 8px;
        padding: 0.75rem;
        margin-bottom: 1rem;
    }
    /* Plan section cards */
    .plan-section {
        background: rgba(128,128,128,0.05);
        border-radius: 8px;
        padding: 1rem;
        margin-bottom: 0.75rem;
        border-left: 4px solid #4A90D9;
    }
</style>
""", unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Session state defaults
# ---------------------------------------------------------------------------
_DEFAULTS = {
    "generation_complete": False,
    "result": None,
    "logs": [],
    "selected_history": None,
    "is_generating": False,
}
for k, v in _DEFAULTS.items():
    if k not in st.session_state:
        st.session_state[k] = v


# ---------------------------------------------------------------------------
# Helper: build zip of blog.md + images
# ---------------------------------------------------------------------------
def build_download_zip(blog_md: str, images_dir: str) -> bytes:
    """Create an in-memory zip with the blog markdown and all images."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("blog.md", blog_md)
        if os.path.isdir(images_dir):
            for fname in os.listdir(images_dir):
                fpath = os.path.join(images_dir, fname)
                if os.path.isfile(fpath):
                    zf.write(fpath, f"images/{fname}")
    return buf.getvalue()


# ---------------------------------------------------------------------------
# Helper: render a history entry into session state
# ---------------------------------------------------------------------------
def load_history_entry(entry: dict):
    """Load a history entry into session state for display."""
    st.session_state.selected_history = entry
    st.session_state.generation_complete = True
    st.session_state.result = entry
    st.session_state.logs = [
        f"[History] Loaded blog: {entry.get('title', 'Untitled')}",
        f"[History] Generated at: {entry.get('timestamp', 'unknown')}",
    ]


# ---------------------------------------------------------------------------
# SIDEBAR
# ---------------------------------------------------------------------------
with st.sidebar:
    st.title("✍️ AI Blog Writer")
    st.caption("Powered by LangGraph + GPT + Gemini")

    st.divider()

    # --- Input Section ---
    st.subheader("New Blog")
    topic = st.text_area(
        "Blog Topic",
        placeholder="e.g. Self Attention in Transformer Architecture",
        height=80,
    )
    instructions = st.text_area(
        "Additional Instructions (optional)",
        placeholder="e.g. Target audience: beginners, Tone: casual",
        height=60,
    )

    generate_btn = st.button(
        "🚀 Generate Blog",
        use_container_width=True,
        type="primary",
        disabled=st.session_state.is_generating,
    )

    # --- Progress Section ---
    if st.session_state.is_generating:
        st.divider()
        st.subheader("Progress")
        progress_placeholder = st.empty()

    # --- History Section ---
    st.divider()
    st.subheader("📚 Blog History")

    history = load_history()
    if not history:
        st.caption("No blogs generated yet.")
    else:
        for i, entry in enumerate(history):
            col1, col2 = st.columns([5, 1])
            with col1:
                title = entry.get("title", "Untitled")
                ts = entry.get("timestamp", "")
                display_date = ""
                if ts:
                    try:
                        dt = datetime.fromisoformat(ts)
                        display_date = dt.strftime("%b %d, %H:%M")
                    except ValueError:
                        display_date = ts[:10]
                btn_label = f"📄 {title[:30]}{'...' if len(title) > 30 else ''}"
                if st.button(btn_label, key=f"hist_{i}", use_container_width=True):
                    load_history_entry(entry)
                    st.rerun()
                if display_date:
                    st.caption(f"  {display_date} · {entry.get('blog_length', 0):,} chars")
            with col2:
                if st.button("🗑️", key=f"del_{i}"):
                    delete_history_entry(entry.get("id", ""))
                    st.rerun()


# ---------------------------------------------------------------------------
# GENERATION LOGIC (runs when Generate is clicked)
# ---------------------------------------------------------------------------
if generate_btn and topic.strip():
    st.session_state.is_generating = True
    st.session_state.generation_complete = False
    st.session_state.result = None
    st.session_state.selected_history = None
    st.session_state.logs = []

    # Accumulate state from streaming
    accumulated = {}
    completed_nodes = []

    # Progress display in main area
    status_container = st.container()
    progress_bar = status_container.progress(0, text="Starting blog generation...")
    log_expander = status_container.expander("Live Logs", expanded=True)

    node_order = list(NODE_LABELS.keys())

    try:
        for node_name, node_output in run_agent_stream(topic.strip(), instructions.strip()):
            completed_nodes.append(node_name)
            accumulated.update(node_output)

            # Update progress
            label = NODE_LABELS.get(node_name, node_name)
            pct = min(len(completed_nodes) / len(node_order), 1.0)
            progress_bar.progress(pct, text=f"Completed: {label}")

            # Build log entry
            log_line = f"✅ {label}"
            if node_name == "router":
                nr = node_output.get("needs_research", False)
                log_line += f" → needs_research={nr}"
            elif node_name == "orchestrator":
                plan = node_output.get("plan")
                if plan:
                    log_line += f" → '{plan.title}' ({len(plan.tasks)} sections)"
            elif node_name == "worker_node":
                secs = node_output.get("completed_sections", [])
                log_line += f" → {len(secs)} section(s) written"
            elif node_name == "merge_content":
                mm = node_output.get("merged_markdown", "")
                log_line += f" → {len(mm):,} chars"
            elif node_name == "decide_images":
                specs = node_output.get("image_specs", [])
                log_line += f" → {len(specs)} images planned"
            elif node_name == "generate_and_place_images":
                fb = node_output.get("final_blog", "")
                log_line += f" → final blog {len(fb):,} chars"

            st.session_state.logs.append(log_line)
            with log_expander:
                for lg in st.session_state.logs:
                    st.text(lg)

        progress_bar.progress(1.0, text="✅ Blog generation complete!")

        # Build final result from accumulated state
        st.session_state.result = accumulated
        st.session_state.generation_complete = True

        # Save to history
        save_to_history(topic.strip(), accumulated)

    except Exception as e:
        st.error(f"Generation failed: {e}")
        st.session_state.logs.append(f"❌ Error: {e}")
    finally:
        st.session_state.is_generating = False
        st.rerun()

elif generate_btn and not topic.strip():
    st.warning("Please enter a blog topic.")


# ---------------------------------------------------------------------------
# MAIN AREA — Tabs (shown when we have results)
# ---------------------------------------------------------------------------
if st.session_state.generation_complete and st.session_state.result:
    result = st.session_state.result

    # Extract data from result — handle both live result (Pydantic objects) and
    # history entries (dicts serialized to JSON)
    is_history = st.session_state.selected_history is not None

    if is_history:
        plan_data = result.get("plan")
        evidence_data = result.get("evidence")
        image_specs_data = result.get("image_specs", [])
        final_blog = result.get("final_blog", "")
        needs_research = result.get("needs_research", False)
        blog_title = result.get("title", "Untitled")
    else:
        plan_obj = result.get("plan")
        plan_data = plan_obj.model_dump() if plan_obj and hasattr(plan_obj, "model_dump") else plan_obj
        evidence_obj = result.get("evidence")
        evidence_data = evidence_obj.model_dump() if evidence_obj and hasattr(evidence_obj, "model_dump") else evidence_obj
        image_specs_raw = result.get("image_specs", [])
        image_specs_data = []
        for s in image_specs_raw:
            if hasattr(s, "model_dump"):
                image_specs_data.append(s.model_dump())
            elif isinstance(s, dict):
                image_specs_data.append(s)
        final_blog = result.get("final_blog", "")
        needs_research = result.get("needs_research", False)
        blog_title = plan_data.get("title", "Untitled") if plan_data else "Untitled"

    # --- Header ---
    st.title(blog_title)
    col_m1, col_m2, col_m3 = st.columns(3)
    num_sections = len(plan_data.get("tasks", [])) if plan_data else 0
    col_m1.metric("Sections", num_sections)
    col_m2.metric("Images", len(image_specs_data))
    col_m3.metric("Characters", f"{len(final_blog):,}")

    # --- Tabs ---
    tab_plan, tab_blog, tab_evidence, tab_logs, tab_images = st.tabs(
        ["📋 Plan", "📝 Blog", "🔍 Evidence", "📊 Logs", "🖼️ Images"]
    )

    # ---- TAB: Plan ----
    with tab_plan:
        if plan_data:
            st.subheader(f"Blog Plan: {plan_data.get('title', '')}")
            research_badge = "🔍 Research enabled" if needs_research else "📖 No research needed"
            st.info(research_badge)

            tasks = plan_data.get("tasks", [])
            for i, task in enumerate(tasks, 1):
                with st.container():
                    st.markdown(f"""
<div class="plan-section">
    <strong>Section {i}: {task.get('title', '')}</strong><br>
    <em>ID: {task.get('id', '')}</em><br>
    {task.get('description', '')}
</div>
""", unsafe_allow_html=True)
        else:
            st.info("No plan data available.")

    # ---- TAB: Blog ----
    with tab_blog:
        if final_blog:
            # Download button
            images_dir = os.path.join(OUTPUT_DIR, "images")
            zip_bytes = build_download_zip(final_blog, images_dir)
            st.download_button(
                label="📥 Download Blog (ZIP)",
                data=zip_bytes,
                file_name=f"blog_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip",
                mime="application/zip",
                use_container_width=True,
            )

            st.divider()

            # Render blog markdown — replace image paths with actual files
            blog_display = final_blog
            if os.path.isdir(images_dir):
                for fname in os.listdir(images_dir):
                    fpath = os.path.join(images_dir, fname)
                    if os.path.isfile(fpath):
                        blog_display = blog_display.replace(
                            f"images/{fname}",
                            fpath,
                        )
            st.markdown(blog_display, unsafe_allow_html=True)
        else:
            st.info("No blog content available.")

    # ---- TAB: Evidence ----
    with tab_evidence:
        if evidence_data and evidence_data.get("items"):
            items = evidence_data["items"]
            st.subheader(f"Research Evidence ({len(items)} sources)")
            for i, item in enumerate(items, 1):
                with st.expander(f"📎 {item.get('title', f'Source {i}')}"):
                    source = item.get("source", "")
                    if source.startswith("http"):
                        st.markdown(f"**Source:** [{source}]({source})")
                    else:
                        st.markdown(f"**Source:** {source}")
                    st.markdown(item.get("content", "No content."))
        else:
            if needs_research:
                st.info("Research was performed but no evidence was collected.")
            else:
                st.info("No research was needed for this topic. The blog was written from the model's knowledge.")

    # ---- TAB: Logs ----
    with tab_logs:
        st.subheader("Agent Execution Log")
        if st.session_state.logs:
            for log in st.session_state.logs:
                if log.startswith("❌"):
                    st.error(log)
                elif log.startswith("✅"):
                    st.success(log)
                else:
                    st.info(log)
        else:
            st.info("No logs available. Generate a blog to see execution logs.")

    # ---- TAB: Images ----
    with tab_images:
        if image_specs_data:
            st.subheader(f"Generated Images ({len(image_specs_data)})")
            images_dir = os.path.join(OUTPUT_DIR, "images")

            cols = st.columns(min(len(image_specs_data), 3))
            for i, spec in enumerate(image_specs_data):
                with cols[i % 3]:
                    fname = spec.get("file_name", f"image_{i+1}.png")
                    fpath = os.path.join(images_dir, fname)

                    st.markdown(f"**{fname}**")
                    if os.path.isfile(fpath):
                        st.image(fpath, use_container_width=True)
                    else:
                        st.warning(f"Image file not found: {fname}")

                    prompt = spec.get("prompt", "No prompt")
                    st.caption(f"Prompt: {prompt[:150]}{'...' if len(prompt) > 150 else ''}")
        else:
            st.info("No images were generated for this blog.")

else:
    # --- Welcome screen ---
    st.title("✍️ AI Blog Writing Agent")
    st.markdown("""
Welcome to the **AI Blog Writing Agent** — an intelligent system that:

1. **Analyzes** your topic to determine if web research is needed
2. **Researches** the topic using Tavily search (if needed)
3. **Plans** a structured blog outline with multiple sections
4. **Writes** each section in parallel using AI workers
5. **Generates** relevant images using Google Gemini
6. **Produces** a polished markdown blog with inline images

### Getting Started
Enter your blog topic in the sidebar and click **Generate Blog**!

### Features
- **5 Tabs** — View your blog plan, rendered blog, research evidence, execution logs, and generated images
- **Real-time Progress** — Watch the agent work through each stage
- **Blog History** — All generated blogs are saved and can be revisited
- **Download** — Export your blog as a ZIP file with markdown + images
""")

    # Show quick stats
    history = load_history()
    if history:
        st.divider()
        col1, col2 = st.columns(2)
        col1.metric("Total Blogs Generated", len(history))
        total_chars = sum(e.get("blog_length", 0) for e in history)
        col2.metric("Total Characters Written", f"{total_chars:,}")
