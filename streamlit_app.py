"""
Stage 4 — Streamlit GUI for the AI Blog Writing Agent.

Run with:
    streamlit run streamlit_app.py
"""

import os
import re
import io
import zipfile
from datetime import datetime

import streamlit as st

from backend import (
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
# Custom CSS — clean, consistent styling
# ---------------------------------------------------------------------------
st.markdown("""
<style>
    /* tighter main padding */
    .block-container { padding-top: 1.5rem; }
    /* plan cards */
    div[data-testid="stExpander"] summary p { font-weight: 600; }
    /* blog prose */
    .blog-prose { line-height: 1.75; font-size: 1.05rem; }
    .blog-prose h1 { margin-top: 0; }
    .blog-prose h2 { margin-top: 2rem; border-bottom: 1px solid rgba(128,128,128,0.2); padding-bottom: .3rem; }
    .blog-prose h3 { margin-top: 1.5rem; }
    .blog-prose pre { background: #f6f8fa; padding: 1rem; border-radius: 6px; overflow-x: auto; }
    .blog-prose code { background: #f0f0f0; padding: .15rem .35rem; border-radius: 4px; font-size: .92em; }
    .blog-prose pre code { background: none; padding: 0; }
    .blog-prose blockquote { border-left: 4px solid #4A90D9; padding-left: 1rem; color: #555; }
    .blog-prose table { border-collapse: collapse; width: 100%; margin: 1rem 0; }
    .blog-prose th, .blog-prose td { border: 1px solid #ddd; padding: .5rem .75rem; text-align: left; }
    .blog-prose th { background: #f6f8fa; }
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
# Helpers
# ---------------------------------------------------------------------------

def build_download_zip(blog_md: str, output_dir: str) -> bytes:
    """Create an in-memory zip with blog.md + images/ from the per-blog output dir."""
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


def _extract_result_data(result: dict, is_history: bool) -> dict:
    """Normalize result into plain dicts regardless of source (live vs history)."""
    if is_history:
        return {
            "plan": result.get("plan"),
            "evidence": result.get("evidence"),
            "image_specs": result.get("image_specs", []),
            "final_blog": result.get("final_blog", ""),
            "needs_research": result.get("needs_research", False),
            "generate_images": result.get("generate_images", False),
            "output_dir": result.get("output_dir", ""),
            "title": result.get("title", "Untitled"),
        }

    plan_obj = result.get("plan")
    plan = plan_obj.model_dump() if plan_obj and hasattr(plan_obj, "model_dump") else plan_obj

    ev_obj = result.get("evidence")
    evidence = ev_obj.model_dump() if ev_obj and hasattr(ev_obj, "model_dump") else ev_obj

    specs = []
    for s in result.get("image_specs", []):
        specs.append(s.model_dump() if hasattr(s, "model_dump") else s)

    return {
        "plan": plan,
        "evidence": evidence,
        "image_specs": specs,
        "final_blog": result.get("final_blog", ""),
        "needs_research": result.get("needs_research", False),
        "generate_images": result.get("generate_images", False),
        "output_dir": result.get("output_dir", ""),
        "title": plan.get("title", "Untitled") if plan else "Untitled",
    }


def _render_blog_markdown(blog_md: str, output_dir: str):
    """Render blog markdown section-by-section, inlining images with st.image."""
    images_dir = os.path.join(output_dir, "images") if output_dir else ""

    # Split on image references: ![alt](images/file.png)
    pattern = r'!\[([^\]]*)\]\(images/([^)]+)\)'
    parts = re.split(pattern, blog_md)

    # parts = [text, alt1, fname1, text, alt2, fname2, ...]
    i = 0
    while i < len(parts):
        if i + 2 < len(parts):
            # Current part is text before image
            text_chunk = parts[i].strip()
            if text_chunk:
                st.markdown(
                    f'<div class="blog-prose">{_md_to_safe(text_chunk)}</div>',
                    unsafe_allow_html=True,
                )
            # Next two parts are alt text + filename
            alt = parts[i + 1]
            fname = parts[i + 2]
            fpath = os.path.join(images_dir, fname) if images_dir else ""
            if fpath and os.path.isfile(fpath):
                st.image(fpath, caption=alt if alt else fname, use_container_width=True)
            elif alt or fname:
                st.info(f"🖼️ Image: {fname}" + (f" — {alt}" if alt else ""))
            i += 3
        else:
            # Remaining text after last image (or entire blog if no images)
            text_chunk = parts[i].strip()
            if text_chunk:
                st.markdown(
                    f'<div class="blog-prose">{_md_to_safe(text_chunk)}</div>',
                    unsafe_allow_html=True,
                )
            i += 1


def _md_to_safe(md: str) -> str:
    """Convert markdown to HTML-safe string for rendering inside a styled div.
    We let Streamlit handle the markdown → HTML conversion via markdown(),
    but we need a wrapper. Return raw markdown and let st.markdown handle it."""
    return md


def load_history_entry(entry: dict):
    """Load a history entry into session state for display."""
    st.session_state.selected_history = entry
    st.session_state.generation_complete = True
    st.session_state.result = entry
    st.session_state.logs = [
        f"📂 Loaded from history: {entry.get('title', 'Untitled')}",
        f"🕐 Generated: {entry.get('timestamp', 'unknown')}",
        f"📊 {entry.get('blog_length', 0):,} chars · {entry.get('num_sections', 0)} sections · {entry.get('num_images', 0)} images",
    ]


# ---------------------------------------------------------------------------
# SIDEBAR
# ---------------------------------------------------------------------------
with st.sidebar:
    st.title("✍️ AI Blog Writer")
    st.caption("LangGraph · GPT · Gemini")

    st.divider()

    # --- Input ---
    st.subheader("New Blog")
    topic = st.text_area(
        "Blog Topic",
        placeholder="e.g. Self Attention in Transformer Architecture",
        height=80,
    )
    instructions = st.text_area(
        "Additional Instructions _(optional)_",
        placeholder="e.g. Target audience: beginners, Tone: casual",
        height=60,
    )
    enable_images = st.toggle(
        "🖼️ Generate Images (Gemini)",
        value=False,
        help="Enable AI image generation using Google Gemini. This costs extra API credits.",
    )

    generate_btn = st.button(
        "🚀 Generate Blog",
        use_container_width=True,
        type="primary",
        disabled=st.session_state.is_generating,
    )

    # --- History ---
    st.divider()
    st.subheader("📚 History")

    history = load_history()
    if not history:
        st.caption("No blogs generated yet.")
    else:
        for i, entry in enumerate(history[:20]):
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
                has_img = "🖼" if entry.get("num_images", 0) > 0 else "📝"
                btn_label = f"{has_img} {title[:28]}{'…' if len(title) > 28 else ''}"
                if st.button(btn_label, key=f"hist_{i}", use_container_width=True):
                    load_history_entry(entry)
                    st.rerun()
                if display_date:
                    st.caption(f"{display_date} · {entry.get('blog_length', 0):,} chars")
            with col2:
                if st.button("🗑️", key=f"del_{i}"):
                    delete_history_entry(entry.get("id", ""))
                    st.rerun()


# ---------------------------------------------------------------------------
# GENERATION LOGIC
# ---------------------------------------------------------------------------
if generate_btn and topic.strip():
    st.session_state.is_generating = True
    st.session_state.generation_complete = False
    st.session_state.result = None
    st.session_state.selected_history = None
    st.session_state.logs = []

    accumulated = {}
    completed_nodes = []

    status_container = st.container()
    progress_bar = status_container.progress(0, text="Starting blog generation…")
    log_area = status_container.empty()

    node_order = list(NODE_LABELS.keys())

    try:
        for node_name, node_output in run_agent_stream(
            topic.strip(),
            instructions.strip(),
            generate_images=enable_images,
        ):
            completed_nodes.append(node_name)
            accumulated.update(node_output)

            label = NODE_LABELS.get(node_name, node_name)
            pct = min(len(completed_nodes) / len(node_order), 1.0)
            progress_bar.progress(pct, text=label)

            # Build detailed log
            log_line = f"✅ {label}"
            if node_name == "router":
                log_line += f"  →  needs_research={node_output.get('needs_research', False)}"
            elif node_name == "orchestrator":
                p = node_output.get("plan")
                if p:
                    log_line += f"  →  '{p.title}' ({len(p.tasks)} sections)"
            elif node_name == "worker_node":
                log_line += f"  →  {len(node_output.get('completed_sections', []))} section(s)"
            elif node_name == "merge_content":
                log_line += f"  →  {len(node_output.get('merged_markdown', '')):,} chars"
            elif node_name == "decide_images":
                log_line += f"  →  {len(node_output.get('image_specs', []))} images planned"
            elif node_name in ("generate_and_place_images", "finalize_blog"):
                log_line += f"  →  {len(node_output.get('final_blog', '')):,} chars"

            st.session_state.logs.append(log_line)
            log_area.code("\n".join(st.session_state.logs), language=None)

        progress_bar.progress(1.0, text="✅ Blog generation complete!")
        st.session_state.result = accumulated
        st.session_state.generation_complete = True
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
# MAIN AREA — Results
# ---------------------------------------------------------------------------
if st.session_state.generation_complete and st.session_state.result:
    is_history = st.session_state.selected_history is not None
    d = _extract_result_data(st.session_state.result, is_history)

    plan_data = d["plan"]
    evidence_data = d["evidence"]
    image_specs_data = d["image_specs"]
    final_blog = d["final_blog"]
    needs_research = d["needs_research"]
    blog_title = d["title"]
    out_dir = d["output_dir"]

    # --- Header ---
    st.title(blog_title)

    col_m1, col_m2, col_m3, col_m4 = st.columns(4)
    num_sections = len(plan_data.get("tasks", [])) if plan_data else 0
    col_m1.metric("Sections", num_sections)
    col_m2.metric("Images", len(image_specs_data))
    col_m3.metric("Characters", f"{len(final_blog):,}")
    col_m4.metric("Research", "Yes" if needs_research else "No")

    # --- Tabs ---
    tab_blog, tab_plan, tab_evidence, tab_logs, tab_images = st.tabs(
        ["📝 Blog", "📋 Plan", "🔍 Evidence", "📊 Logs", "🖼️ Images"]
    )

    # ================================================================
    # TAB: Blog  (first tab — the main output)
    # ================================================================
    with tab_blog:
        if final_blog:
            # Download
            if out_dir:
                zip_bytes = build_download_zip(final_blog, out_dir)
            else:
                zip_bytes = build_download_zip(final_blog, "")
            st.download_button(
                "📥 Download Blog (ZIP)",
                data=zip_bytes,
                file_name=f"blog_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip",
                mime="application/zip",
                use_container_width=True,
            )
            st.divider()

            # Render with proper image handling
            _render_blog_markdown(final_blog, out_dir)
        else:
            st.info("No blog content available.")

    # ================================================================
    # TAB: Plan
    # ================================================================
    with tab_plan:
        if plan_data:
            badge = "🔍 Research enabled" if needs_research else "📖 No research needed"
            img_badge = "🖼️ Images enabled" if d["generate_images"] else "📝 Text only"
            st.info(f"{badge}  ·  {img_badge}")

            for i, task in enumerate(plan_data.get("tasks", []), 1):
                with st.expander(f"**Section {i}:** {task.get('title', '')}",
                                 expanded=(i <= 2)):
                    st.caption(f"ID: `{task.get('id', '')}`")
                    st.write(task.get("description", ""))
        else:
            st.info("No plan data available.")

    # ================================================================
    # TAB: Evidence
    # ================================================================
    with tab_evidence:
        if evidence_data and evidence_data.get("items"):
            items = evidence_data["items"]
            st.subheader(f"Research Evidence ({len(items)} sources)")
            for i, item in enumerate(items, 1):
                with st.expander(f"📎 {item.get('title', f'Source {i}')}"):
                    source = item.get("source", "")
                    if source.startswith("http"):
                        st.markdown(f"🔗 [{source}]({source})")
                    else:
                        st.markdown(f"**Source:** {source}")
                    st.markdown("---")
                    st.write(item.get("content", "No content."))
        else:
            if needs_research:
                st.info("Research was performed but no evidence was collected.")
            else:
                st.info("No research was needed for this topic.")

    # ================================================================
    # TAB: Logs
    # ================================================================
    with tab_logs:
        st.subheader("Agent Execution Log")
        if st.session_state.logs:
            st.code("\n".join(st.session_state.logs), language=None)
        else:
            st.info("No logs available. Generate a blog to see execution logs.")

        # Show output directory info
        if out_dir:
            st.caption(f"Output directory: `{out_dir}`")

    # ================================================================
    # TAB: Images
    # ================================================================
    with tab_images:
        images_dir = os.path.join(out_dir, "images") if out_dir else ""
        if image_specs_data:
            st.subheader(f"Generated Images ({len(image_specs_data)})")
            for i, spec in enumerate(image_specs_data):
                fname = spec.get("file_name", f"image_{i+1}.png")
                fpath = os.path.join(images_dir, fname) if images_dir else ""
                prompt = spec.get("prompt", "")

                with st.expander(f"🖼️ **{fname}**", expanded=True):
                    if fpath and os.path.isfile(fpath):
                        st.image(fpath, use_container_width=True)
                    else:
                        st.warning(f"Image file not found: `{fname}`")
                    st.caption(f"**Prompt:** {prompt}")
        else:
            if not d["generate_images"]:
                st.info("Image generation was disabled for this blog. Enable the toggle in the sidebar to generate images.")
            else:
                st.info("No images were generated for this blog.")

# ---------------------------------------------------------------------------
# WELCOME SCREEN (no results yet)
# ---------------------------------------------------------------------------
else:
    st.title("✍️ AI Blog Writing Agent")
    st.markdown("""
### How it works

| Step | What happens |
|------|-------------|
| **1. Router** | Analyzes your topic — decides if web research is needed |
| **2. Research** | Searches the web via Tavily _(if needed)_ |
| **3. Orchestrator** | Creates a structured blog plan with sections |
| **4. Workers** | Writes each section in parallel |
| **5. Images** | Generates diagrams with Google Gemini _(optional)_ |
| **6. Output** | Produces a polished markdown blog |

### Getting Started

Enter your topic in the sidebar and click **🚀 Generate Blog**.

> **Tip:** Toggle **🖼️ Generate Images** only when you need visuals — it uses extra API credits.
""")

    history = load_history()
    if history:
        st.divider()
        col1, col2, col3 = st.columns(3)
        col1.metric("Blogs Generated", len(history))
        total_chars = sum(e.get("blog_length", 0) for e in history)
        col2.metric("Total Characters", f"{total_chars:,}")
        total_images = sum(e.get("num_images", 0) for e in history)
        col3.metric("Images Created", total_images)
