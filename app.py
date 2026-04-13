from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

REPO_ROOT = Path(__file__).resolve().parent
APP_ROOT = REPO_ROOT / "app"
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

from phase_1.data_loader import load_and_process_data
from phase_3.filter import filter_with_relaxation
from phase_4.llm import recommend_with_llm
from phase_5.api import _generate_what_if_suggestions
from phase_5.merge import merge_llm_with_candidates
from phase_5.schemas import FilterRelaxation, RecommendRequest


st.set_page_config(
    page_title="The Appetizing Intelligence",
    page_icon="🍽️",
    layout="wide",
)


@st.cache_data(show_spinner=False)
def get_restaurant_df():
    return load_and_process_data()


@st.cache_data(show_spinner=False)
def get_localities() -> list[str]:
    df = get_restaurant_df()
    series = df["city"].dropna().astype(str).str.strip()
    series = series[(series != "") & (series.str.lower() != "nan")]
    return sorted(series.unique().tolist())


st.title("The Appetizing Intelligence")
st.caption("AI-powered restaurant recommendations with smart relaxation and what-if suggestions.")

with st.sidebar:
    st.header("Your Preferences")
    localities = get_localities()
    location = st.selectbox(
        "Locality",
        options=localities,
        index=0 if localities else None,
        format_func=lambda value: value.title(),
    )
    budget = st.slider("Max Budget (for two)", min_value=100, max_value=10000, value=1200, step=100)
    cuisine_options = ["mexican", "italian", "asian", "continental", "indian", "chinese"]
    cuisines = st.multiselect(
        "Cuisines (optional)",
        options=cuisine_options,
        default=[],
        format_func=lambda value: value.title(),
    )
    min_rating = st.radio("Minimum Rating", options=[3.0, 4.0, 4.5], format_func=lambda value: f"{value}+")
    top_k = st.slider("Top Results", min_value=1, max_value=10, value=5, step=1)
    submit = st.button("Get Recommendations", type="primary", use_container_width=True)

if submit:
    if not location:
        st.error("No localities are available in the dataset.")
    else:
        prefs = RecommendRequest(
            location=location,
            budget=float(budget),
            cuisines=cuisines or None,
            min_rating=float(min_rating),
            top_k=int(top_k),
        )

        with st.spinner("Finding your best matches..."):
            df = get_restaurant_df()
            filter_result = filter_with_relaxation(df, prefs)
            candidates = filter_result.candidates
            llm_out = recommend_with_llm(candidates, prefs)
            response = merge_llm_with_candidates(candidates, llm_out)
            response.what_if_suggestions = _generate_what_if_suggestions(
                df,
                prefs,
                candidates,
                filter_result.was_relaxed,
            )
            if filter_result.was_relaxed:
                response.filter_relaxation = FilterRelaxation(
                    was_relaxed=True,
                    original_filters=filter_result.original_filters or {},
                    relaxed_filters=filter_result.relaxed_filters or {},
                    message=filter_result.relaxation_message,
                )

        st.subheader("AI Curated Results")
        st.write(f"Showing {len(response.recommendations)} recommendation(s).")

        if response.filter_relaxation.was_relaxed and response.filter_relaxation.message:
            st.info(response.filter_relaxation.message)

        if response.what_if_suggestions:
            st.markdown("### What If?")
            for suggestion in response.what_if_suggestions:
                with st.container(border=True):
                    st.write(suggestion.message)
                    if suggestion.example_restaurants:
                        st.caption("Examples: " + ", ".join(suggestion.example_restaurants))

        columns = st.columns(2)
        for index, item in enumerate(response.recommendations):
            with columns[index % 2]:
                with st.container(border=True):
                    title_cols = st.columns([4, 1])
                    with title_cols[0]:
                        st.markdown(f"### {item.name}")
                    with title_cols[1]:
                        if item.rating is not None:
                            st.metric("Rating", f"{item.rating:.1f}")
                    if item.cost is not None:
                        st.write(f"**₹{item.cost:.0f} for two**")
                    if item.cuisines:
                        st.caption(" • ".join(cuisine.title() for cuisine in item.cuisines[:4]))
                    st.write(item.explanation)
                    if item.maps_url:
                        st.markdown(f"[View on Google Maps]({item.maps_url})")
else:
    st.markdown("### Ready to explore?")
    st.write("Choose your preferences from the left sidebar and click **Get Recommendations**.")
    st.write("This Streamlit app is the correct entry file for Streamlit Cloud deployment.")
