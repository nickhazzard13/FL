import streamlit as st
import pandas as pd
import numpy as np
from pathlib import Path
import base64


# ----------------------------------
# App config
# ----------------------------------


def get_base64_image(image_path: str) -> str:
    """Return a base64 data URI for an image file."""
    img_path = Path(__file__).resolve().parent / image_path
    if not img_path.exists():
        return ""
    with open(img_path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode("utf-8")
    return f"data:image/png;base64,{b64}"

st.set_page_config(page_title="FantasyLine", page_icon="🏈", layout="wide")

CSV_FILE = "src/fantasyline/bettingpros_week1_2025_final.csv"  # <-- your CSV

# ----------------------------------
# Data loading
# ----------------------------------
@st.cache_data
def load_data(path: str) -> pd.DataFrame:
    df = pd.read_csv(path)

    # Clean strings
    for c in ["Player", "Team", "Pos"]:
        if c in df.columns:
            df[c] = df[c].astype(str).str.strip()

    # Normalize TD column name if needed
    if "Proj TD Pts" in df.columns and "Proj TD PTS" not in df.columns:
        df.rename(columns={"Proj TD Pts": "Proj TD PTS"}, inplace=True)

    # Coerce numerics
    for c in ["Base_Projection", "Proj TD PTS", "Total_Projection"]:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")

    # Keep standard column order if present
    cols = ["Player", "Team", "Pos", "Base_Projection", "Proj TD PTS", "Total_Projection"]
    return df[[c for c in cols if c in df.columns]].copy()

df = load_data(CSV_FILE)

# Init session state for compare
st.session_state.setdefault("compare_list", [])

# ----------------------------------
# Pages
# ----------------------------------

def set_home_background(image_filename: str = "FLlogo.png"):
    """
    Sets a full-page background image using base64 so it works on Streamlit Cloud.
    Looks for the image file next to app.py.
    """
    app_dir = Path(__file__).resolve().parent
    img_path = app_dir / image_filename
    if not img_path.exists():
        # Quietly skip if missing
        return
    b64 = base64.b64encode(img_path.read_bytes()).decode("utf-8")
    st.markdown(
        f"""
        <style>
        .stApp {{
            background: url("data:image/png;base64,{b64}") no-repeat center center fixed;
            background-size: cover;
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )

def clear_background():
    """
    Removes any custom background when not on Home.
    """
    st.markdown(
        """
        <style>
        .stApp { background: var(--background-color) !important; }
        </style>
        """,
        unsafe_allow_html=True,
    )

def page_home():
    clear_background()  # keep background plain

    # Encode your logo
    logo_data = get_base64_image("FLlogo.png")  # logo file next to app.py

    st.markdown(
        f"""
        <div style="text-align:center; padding: 40px;">
            <h1 style="color:black; font-size: 64px; margin-bottom: 10px;">FantasyLine</h1>
            <p style="color:black; font-size:20px; margin-top:0;">
                Weekly projections for <b>RB / WR / TE</b> from your CSV.<br/>
                Filter, sort, and compare up to five players.
            </p>
            <img src="{logo_data}" width="300" style="margin-top:20px;"/>
        </div>
        """,
        unsafe_allow_html=True,
    )




   

def page_projections():
    st.markdown("## Projections")
    st.caption("All positions by default. Use quick filters for RB / WR / TE, search, and sort.")

    # ---- Controls
    with st.container():
        quick = st.segmented_control("Quick position filter", options=["All", "RB", "WR", "TE"], default="All")
        col_a, col_b, col_c, col_d = st.columns([2,2,2,2])
        with col_a:
            search = st.text_input("Search Player", "")
        with col_b:
            team_filter = st.text_input("Team filter (comma-separated)", "")
        with col_c:
            sort_by = st.selectbox(
                "Sort by",
                [c for c in ["Total_Projection", "Base_Projection", "Proj TD PTS", "Player", "Team", "Pos"] if c in df.columns],
                index=0
            )
        with col_d:
            desc = st.toggle("Sort descending", value=True)

    # ---- Filtering
    data = df.copy()
    if quick != "All" and "Pos" in data.columns:
        data = data[data["Pos"] == quick]

    if search and "Player" in data.columns:
        data = data[data["Player"].str.contains(search, case=False, na=False)]

    if team_filter and "Team" in data.columns:
        teams = [t.strip() for t in team_filter.split(",") if t.strip()]
        if teams:
            data = data[data["Team"].isin(teams)]

    # ---- Sorting
    if sort_by in data.columns:
        data = data.sort_values(sort_by, ascending=not desc, na_position="last")

    # ---- Pagination
    page_size = st.selectbox("Rows per page", [10, 25, 50, 100], index=1)
    total_rows = len(data)
    if total_rows == 0:
        st.info("No rows to display with current filters.")
        return
    max_page = (total_rows - 1) // page_size + 1
    page = st.number_input("Page", min_value=1, max_value=max_page, value=1)
    start, end = (page - 1) * page_size, (page - 1) * page_size + page_size

    # ---- Table
    st.write(f"Showing **{min(end, total_rows)}** of **{total_rows}** rows")
    st.dataframe(data.iloc[start:end], use_container_width=True, hide_index=True)

    # ---- Download current view
    st.download_button(
        "Download filtered CSV",
        data=data.to_csv(index=False).encode("utf-8"),
        file_name="fantasyline_filtered.csv",
        mime="text/csv"
    )

def page_compare():
    import numpy as np
    st.markdown("## Compare Players")
    st.caption("Pick up to 5 players. We’ll highlight who has the highest **Total_Projection**.")

    # Build a base list of players
    player_list = df["Player"].dropna().unique().tolist() if "Player" in df.columns else []

    # Let Streamlit manage widget state (no session_state needed)
    picks = st.multiselect(
        "Choose up to 5 players",
        options=player_list,
        help="Start typing a name to search."
    )

    # Enforce at most 5
    if len(picks) > 5:
        st.warning("You selected more than 5. Keeping the first 5.")
        picks = picks[:5]

    if not picks:
        st.info("Select players above to compare.")
        return

    sub = df[df["Player"].isin(picks)].copy()

    # Guard: if Total_Projection missing
    if "Total_Projection" not in sub.columns:
        st.error("Column `Total_Projection` not found in CSV — cannot rank players.")
        st.dataframe(sub, use_container_width=True, hide_index=True)
        return

    # Determine the top player(s)
    sub["TP_sanitized"] = pd.to_numeric(sub["Total_Projection"], errors="coerce")
    top_tp = sub["TP_sanitized"].max()
    top_rows = sub.loc[sub["TP_sanitized"] == top_tp]

    if pd.notna(top_tp):
        if len(top_rows) == 1:
            st.success(f"**{top_rows.iloc[0]['Player']}** has the highest projection ({top_tp:.2f}).")
        else:
            # Handle ties
            names = ", ".join(top_rows["Player"].tolist())
            st.info(f"Tie for highest projection ({top_tp:.2f}) between: **{names}**")

    # Show comparison cards (with a crown on the top player)
    cols = st.columns(min(5, len(sub)))
    ranked = sub.sort_values("TP_sanitized", ascending=False).reset_index(drop=True)
    for i, (_, r) in enumerate(ranked.iterrows()):
        is_top = (i == 0 and pd.notna(r["TP_sanitized"]))
        crown = " 👑" if is_top else ""
        with cols[i % len(cols)]:
            st.markdown(f"""
            <div style="
              background: var(--secondary-background-color);
              border: 1px solid rgba(255,255,255,0.08);
              border-radius: 16px; padding: 16px 18px;
              box-shadow: 0 1px 12px rgba(0,0,0,0.15);
            ">
              <h4 style="margin:0 0 6px 0;">{r.get('Player','—')}{crown}</h4>
              <div style="opacity:.8; margin:-4px 0 8px">{r.get('Team','—')} • {r.get('Pos','—')}</div>
              <div style="display:flex; gap:12px;">
                <div>
                  <div style="font-size:12px;opacity:.7">Total</div>
                  <div style="font-size:22px;font-weight:700">
                    {'—' if pd.isna(r.get('Total_Projection')) else f"{r.get('Total_Projection'):.2f}"}
                  </div>
                </div>
                <div>
                  <div style="font-size:12px;opacity:.7">Base</div>
                  <div style="font-size:22px;font-weight:700">
                    {'—' if pd.isna(r.get('Base_Projection')) else f"{r.get('Base_Projection'):.2f}"}
                  </div>
                </div>
                <div>
                  <div style="font-size:12px;opacity:.7">TD</div>
                  <div style="font-size:22px;font-weight:700">
                    {'—' if pd.isna(r.get('Proj TD PTS')) else f"{r.get('Proj TD PTS'):.2f}"}
                  </div>
                </div>
              </div>
            </div>
            """, unsafe_allow_html=True)

    # Download the compare subset
    dl_cols = [c for c in ["Player","Team","Pos","Base_Projection","Proj TD PTS","Total_Projection"] if c in sub.columns]
    st.download_button(
        "Download this comparison as CSV",
        data=sub[dl_cols].to_csv(index=False).encode("utf-8"),
        file_name="fantasyline_compare.csv",
        mime="text/csv"
    )


# ----------------------------------
# Router (Sidebar)
# ----------------------------------
with st.sidebar:
    st.markdown("## 🏈 FantasyLine")
    page = st.radio("Navigate", ["Home", "Projections", "Compare"], index=0)
    st.caption("CSV: bettingpros_week1_2025_final.csv")

if page == "Home":
    page_home()
elif page == "Projections":
    clear_background()
    page_projections()
else:
    clear_background()
    page_compare()

