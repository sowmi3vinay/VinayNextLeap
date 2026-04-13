"""
Streamlit Cloud Deployment Entry Point
Wraps the FastAPI app for deployment on Streamlit Cloud.
Also provides a native Streamlit UI as an alternative interface.
"""

from __future__ import annotations

import os
import sys

import streamlit as st

# Add Source to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "Source"))

from phase_1.data_loader import load_and_process_data
from phase_2.models import UserPreferences
from phase_3.filter import filter_with_relaxation
from phase_4.llm import recommend_with_llm
from phase_5.merge import merge_llm_with_candidates
from phase_5.schemas import RecommendRequest

# Page config
st.set_page_config(
    page_title="The Appetizing Intelligence",
    page_icon="🍽️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Load CSS
with open("web/styles.css", "r") as f:
    css = f.read()
st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)

# Initialize session state
if "df" not in st.session_state:
    with st.spinner("Loading restaurant data..."):
        st.session_state.df = load_and_process_data()

if "recommendations" not in st.session_state:
    st.session_state.recommendations = None

# Sidebar - Preferences
st.sidebar.title("🍽️ Your Preferences")
st.sidebar.markdown("Fine-tune your culinary discovery")

df = st.session_state.df
localities = sorted(df["city"].unique())

# Locality selection
location = st.sidebar.selectbox(
    "Locality",
    options=localities,
    format_func=lambda x: x.title(),
)

# Budget slider
budget = st.sidebar.slider(
    "Max Budget (₹ for two)",
    min_value=100,
    max_value=10000,
    value=1200,
    step=100,
)
st.sidebar.markdown(f"**Selected: ₹{budget:,}**")

# Cuisine pills (multiselect)
available_cuisines = ["mexican", "italian", "asian", "continental", "indian", "chinese"]
cuisines = st.sidebar.multiselect(
    "Cuisines (Optional)",
    options=available_cuisines,
    format_func=lambda x: x.title(),
)

# Rating selection
min_rating = st.sidebar.radio(
    "Minimum Rating",
    options=[3.0, 4.0, 4.5],
    format_func=lambda x: f"{x}+",
    index=1,
)

# Top K slider
top_k = st.sidebar.slider(
    "Top Results (K)",
    min_value=1,
    max_value=10,
    value=5,
)

# Get recommendations button
if st.sidebar.button("🎯 Get Recommendations", type="primary"):
    with st.spinner("Finding the best restaurants for you..."):
        # Build request
        prefs = RecommendRequest(
            location=location,
            budget=float(budget),
            cuisines=cuisines if cuisines else None,
            min_rating=float(min_rating),
            top_k=int(top_k),
        )
        
        # Filter with relaxation
        filter_result = filter_with_relaxation(df, prefs)
        candidates = filter_result.candidates
        
        # Get LLM recommendations
        llm_out = recommend_with_llm(candidates, prefs)
        response = merge_llm_with_candidates(candidates, llm_out)
        
        st.session_state.recommendations = response
        st.session_state.filter_result = filter_result

# Main content area
st.title("AI Curated Results")

if st.session_state.recommendations:
    response = st.session_state.recommendations
    filter_result = st.session_state.filter_result
    
    # Show filter relaxation banner if applicable
    if filter_result.was_relaxed:
        st.info(f"🔍 {filter_result.relaxation_message}")
    
    # Show recommendations count
    st.markdown(f"Showing {len(response.recommendations)} recommendation(s).")
    
    # Display recommendations in columns
    cols = st.columns(3)
    
    for idx, item in enumerate(response.recommendations):
        with cols[idx % 3]:
            # Card container
            with st.container():
                st.markdown("---")
                
                # Header with rating badge
                col1, col2 = st.columns([3, 1])
                with col1:
                    st.subheader(item.name)
                with col2:
                    if item.rating:
                        st.markdown(f"⭐ {item.rating}")
                
                # Cost
                if item.cost:
                    st.markdown(f"**₹{item.cost:,.0f} for two**")
                
                # Cuisines
                if item.cuisines:
                    st.markdown(
                        " ".join([f"<span style='background:#f3e8ff;padding:4px 8px;border-radius:12px;font-size:0.8em;'>{c.title()}</span>" for c in item.cuisines[:3]]),
                        unsafe_allow_html=True
                    )
                
                # AI Insight
                if item.explanation:
                    st.markdown("---")
                    st.markdown("✨ **AI Insight**")
                    st.markdown(f"<div style='background:linear-gradient(135deg,#f3e8ff 0%,#e9d5ff 100%);padding:12px;border-radius:8px;'>{item.explanation}</div>", unsafe_allow_html=True)
                
                # Google Maps link
                if item.maps_url:
                    st.markdown(f"[📍 View on Google Maps]({item.maps_url})")
    
    # Show what-if suggestions
    if response.what_if_suggestions:
        st.markdown("---")
        st.markdown("### 💡 What If?")
        for suggestion in response.what_if_suggestions:
            with st.expander(suggestion.message):
                if suggestion.example_restaurants:
                    st.markdown("**Examples:** " + ", ".join(suggestion.example_restaurants))

else:
    # Initial state
    st.markdown("""
    ### Welcome to The Appetizing Intelligence! 🍽️
    
    This AI-powered restaurant recommendation system helps you discover the perfect dining experience.
    
    **How it works:**
    1. Select your preferred **locality**
    2. Set your **budget** (₹ for two people)
    3. Choose **cuisines** (optional)
    4. Set minimum **rating** preference
    5. Click **"Get Recommendations"**
    
    The AI will analyze thousands of restaurants and curate personalized recommendations just for you!
    """)
    
    # Show some stats
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total Restaurants", f"{len(df):,}")
    with col2:
        st.metric("Localities", f"{df['city'].nunique()}")
    with col3:
        st.metric("Avg Rating", f"{df['rating'].mean():.1f}")

# Footer
st.markdown("---")
st.markdown("<div style='text-align:center;color:#6b7280;'>Powered by AI • Built with Streamlit</div>", unsafe_allow_html=True)
