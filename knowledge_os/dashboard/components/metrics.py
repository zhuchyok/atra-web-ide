import streamlit as st

def render_metric_card(label, value, delta=None, delta_color="normal", help=None):
    """Render a styled metric card following Singularity design system."""
    with st.container():
        st.markdown(f"""
            <div class="premium-card">
                <div class="premium-meta">{label}</div>
                <div class="premium-value">{value}</div>
                {f'<div class="premium-meta" style="color: {"#a6e3a1" if delta_color == "normal" else "#f38ba8"};">{"↑" if delta_color == "normal" else "↓"} {delta}</div>' if delta else ''}
            </div>
        """, unsafe_allow_html=True)

def render_stat_row(metrics_dict):
    """Render a row of metrics."""
    cols = st.columns(len(metrics_dict))
    for i, (label, val) in enumerate(metrics_dict.items()):
        with cols[i]:
            render_metric_card(label, val)
