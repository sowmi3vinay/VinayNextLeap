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
    initial_sidebar_state="expanded",
)

# Custom CSS for aesthetic UI
st.markdown("""
<style>
    /* Main background with food pattern */
    .stApp {
        background: linear-gradient(135deg, #faf5ff 0%, #f3e8ff 50%, #e9d5ff 100%);
        background-attachment: fixed;
    }
    
    /* Sidebar styling */
    section[data-testid="stSidebar"] {
        background: linear-gradient(180deg, #ffffff 0%, #faf5ff 100%) !important;
        border-right: 2px solid #d8b4fe;
    }
    
    section[data-testid="stSidebar"] .stMarkdown h1,
    section[data-testid="stSidebar"] .stMarkdown h2,
    section[data-testid="stSidebar"] .stMarkdown h3 {
        color: #7c3aed !important;
        font-weight: 700 !important;
    }
    
    /* Title styling */
    .stMarkdown h1 {
        background: linear-gradient(135deg, #7c3aed 0%, #a855f7 50%, #c084fc 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-weight: 800 !important;
        font-size: 2.5rem !important;
        text-align: center;
        margin-bottom: 0.5rem !important;
    }
    
    /* Caption styling */
    .stMarkdown p {
        color: #6b7280;
        text-align: center;
        font-size: 1.1rem;
    }
    
    /* Button styling */
    .stButton > button {
        background: linear-gradient(135deg, #7c3aed 0%, #a855f7 100%) !important;
        color: white !important;
        border: none !important;
        border-radius: 12px !important;
        padding: 0.75rem 2rem !important;
        font-weight: 600 !important;
        font-size: 1.1rem !important;
        box-shadow: 0 4px 14px rgba(124, 58, 237, 0.4) !important;
        transition: all 0.3s ease !important;
    }
    
    .stButton > button:hover {
        transform: translateY(-2px) !important;
        box-shadow: 0 6px 20px rgba(124, 58, 237, 0.5) !important;
    }
    
    /* Card/container styling */
    div[data-testid="stVerticalBlock"] > div[data-testid="stVerticalBlock"] {
        background: rgba(255, 255, 255, 0.9) !important;
        border-radius: 16px !important;
        padding: 1.5rem !important;
        border: 1px solid #e9d5ff !important;
        box-shadow: 0 4px 20px rgba(124, 58, 237, 0.1) !important;
        margin-bottom: 1rem !important;
    }
    
    /* Slider styling */
    .stSlider > div > div > div {
        background: linear-gradient(135deg, #7c3aed 0%, #a855f7 100%) !important;
    }
    
    /* Selectbox and multiselect styling */
    .stSelectbox > div > div,
    .stMultiSelect > div > div {
        border-radius: 10px !important;
        border-color: #d8b4fe !important;
    }
    
    /* Radio button styling */
    .stRadio > div {
        background: rgba(255, 255, 255, 0.7) !important;
        border-radius: 12px !important;
        padding: 0.5rem !important;
    }
    
    /* Metric card styling */
    div[data-testid="stMetric"] {
        background: linear-gradient(135deg, #f3e8ff 0%, #e9d5ff 100%) !important;
        border-radius: 12px !important;
        padding: 1rem !important;
        border: 2px solid #d8b4fe !important;
    }
    
    div[data-testid="stMetric"] > div {
        color: #7c3aed !important;
        font-weight: 700 !important;
    }
    
    /* Info/Alert boxes */
    .stInfo {
        background: linear-gradient(135deg, #dbeafe 0%, #bfdbfe 100%) !important;
        border-left: 4px solid #3b82f6 !important;
        border-radius: 12px !important;
    }
    
    /* Expander styling */
    .stExpander {
        background: rgba(255, 255, 255, 0.8) !important;
        border-radius: 12px !important;
        border: 1px solid #e9d5ff !important;
    }
    
    /* Divider styling */
    hr {
        border-color: #d8b4fe !important;
        border-width: 2px !important;
    }
</style>
""", unsafe_allow_html=True)


@st.cache_data(show_spinner=False)
def get_restaurant_df():
    return load_and_process_data()


@st.cache_data(show_spinner=False)
def get_localities() -> list[str]:
    df = get_restaurant_df()
    series = df["city"].dropna().astype(str).str.strip()
    series = series[(series != "") & (series.str.lower() != "nan")]
    return sorted(series.unique().tolist())


st.title("🍽️ The Appetizing Intelligence")
st.markdown("<p style='text-align: center; color: #6b7280; font-size: 1.2rem; margin-bottom: 2rem;'>AI-powered restaurant recommendations with smart relaxation and what-if suggestions</p>", unsafe_allow_html=True)

with st.sidebar:
    st.markdown("<h2 style='color: #7c3aed; text-align: center; margin-bottom: 1rem;'>🍴 Your Preferences</h2>", unsafe_allow_html=True)
    st.markdown("<p style='color: #6b7280; text-align: center; font-size: 0.9rem; margin-bottom: 2rem;'>Fine-tune your culinary discovery</p>", unsafe_allow_html=True)
    
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

        st.markdown(f"""
        <h2 style='color: #7c3aed; margin: 2rem 0 1rem 0;'>✨ AI Curated Results</h2>
        <p style='color: #6b7280; margin-bottom: 1.5rem;'>Showing {len(response.recommendations)} recommendation(s) based on your preferences</p>
        """, unsafe_allow_html=True)

        if response.filter_relaxation.was_relaxed and response.filter_relaxation.message:
            st.markdown(f"""
            <div style='background: linear-gradient(135deg, #dbeafe 0%, #bfdbfe 100%); padding: 1rem 1.5rem; border-radius: 12px; border-left: 4px solid #3b82f6; margin: 1rem 0;'>
                <div style='color: #1e40af; font-weight: 600;'>🔍 {response.filter_relaxation.message}</div>
            </div>
            """, unsafe_allow_html=True)

        if response.what_if_suggestions:
            st.markdown("<h3 style='color: #92400e; margin: 2rem 0 1rem 0;'>💡 What If?</h3>", unsafe_allow_html=True)
            for suggestion in response.what_if_suggestions:
                with st.container():
                    example_text = f"<div style='color: #92400e; font-size: 0.9rem; margin-top: 0.5rem;'><strong>Examples:</strong> {', '.join(suggestion.example_restaurants)}</div>" if suggestion.example_restaurants else ""
                    st.markdown(f"""
                    <div style='background: linear-gradient(135deg, #fef3c7 0%, #fde68a 100%); padding: 1rem 1.5rem; border-radius: 12px; border-left: 4px solid #f59e0b; margin-bottom: 1rem;'>
                        <div style='color: #78350f; font-weight: 500; font-size: 1rem;'>{suggestion.message}</div>
                        {example_text}
                    </div>
                    """, unsafe_allow_html=True)

        columns = st.columns(2)
        for index, item in enumerate(response.recommendations):
            with columns[index % 2]:
                # Create a card-like container
                with st.container():
                    st.markdown("---")
                    
                    # Header with name and rating
                    header_cols = st.columns([3, 1])
                    with header_cols[0]:
                        st.markdown(f"### 🍴 {item.name}")
                    with header_cols[1]:
                        if item.rating is not None:
                            st.markdown(f"<div style='background: linear-gradient(135deg, #7c3aed, #a855f7); color: white; padding: 0.5rem 1rem; border-radius: 20px; text-align: center; font-weight: bold;'>⭐ {item.rating:.1f}</div>", unsafe_allow_html=True)
                    
                    # Cost
                    if item.cost is not None:
                        st.markdown(f"<div style='font-size: 1.2rem; color: #7c3aed; font-weight: 600; margin: 0.5rem 0;'>💰 ₹{item.cost:.0f} for two</div>", unsafe_allow_html=True)
                    
                    # Cuisines as pills
                    if item.cuisines:
                        cuisine_pills = " ".join([f"<span style='background: linear-gradient(135deg, #f3e8ff, #e9d5ff); color: #7c3aed; padding: 0.3rem 0.8rem; border-radius: 15px; font-size: 0.85rem; margin-right: 0.5rem; border: 1px solid #d8b4fe;'>{cuisine.title()}</span>" for cuisine in item.cuisines[:4]])
                        st.markdown(f"<div style='margin: 0.5rem 0;'>{cuisine_pills}</div>", unsafe_allow_html=True)
                    
                    # AI Insight box
                    if item.explanation:
                        st.markdown("<div style='background: linear-gradient(135deg, #fef3c7, #fde68a); padding: 1rem; border-radius: 12px; border-left: 4px solid #f59e0b; margin: 1rem 0;'>", unsafe_allow_html=True)
                        st.markdown(f"<div style='color: #92400e; font-weight: 600; margin-bottom: 0.5rem;'>✨ AI Insight</div>", unsafe_allow_html=True)
                        st.markdown(f"<div style='color: #78350f;'>{item.explanation}</div>", unsafe_allow_html=True)
                        st.markdown("</div>", unsafe_allow_html=True)
                    
                    # Google Maps link
                    if item.maps_url:
                        st.markdown(f"<a href='{item.maps_url}' target='_blank' style='display: inline-block; background: linear-gradient(135deg, #10b981, #34d399); color: white; padding: 0.5rem 1rem; border-radius: 8px; text-decoration: none; font-weight: 500;'>📍 View on Google Maps</a>", unsafe_allow_html=True)
                    
                    st.markdown("<br>", unsafe_allow_html=True)
else:
    # Initial state with welcome message
    st.markdown("""
    <div style='background: linear-gradient(135deg, #f3e8ff 0%, #e9d5ff 100%); padding: 3rem; border-radius: 20px; text-align: center; border: 2px solid #d8b4fe; margin: 2rem 0;'>
        <h2 style='color: #7c3aed; margin-bottom: 1rem;'>🍽️ Welcome to The Appetizing Intelligence!</h2>
        <p style='color: #6b7280; font-size: 1.1rem; margin-bottom: 1.5rem;'>
            Discover the perfect dining experience with AI-powered recommendations.
        </p>
        <div style='text-align: left; max-width: 500px; margin: 0 auto; color: #6b7280;'>
            <p><strong>How it works:</strong></p>
            <ol style='line-height: 2;'>
                <li>Select your preferred <strong>locality</strong></li>
                <li>Set your <strong>budget</strong> (₹ for two people)</li>
                <li>Choose <strong>cuisines</strong> (optional)</li>
                <li>Set minimum <strong>rating</strong> preference</li>
                <li>Click <strong>"Get Recommendations"</strong></li>
            </ol>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    # Show some stats
    df = get_restaurant_df()
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("🍴 Total Restaurants", f"{len(df):,}")
    with col2:
        st.metric("📍 Localities", f"{df['city'].nunique()}")
    with col3:
        st.metric("⭐ Avg Rating", f"{df['rating'].mean():.1f}")
