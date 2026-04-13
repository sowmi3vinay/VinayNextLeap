/**
 * Restaurant Recommendation UI - The Appetizing Intelligence
 * Handles form interactions, API calls, and card rendering.
 * 
 * For deployment: Set API_BASE_URL environment variable or window.API_BASE_URL
 * Default: same-origin (works with local development and Streamlit)
 */

(function () {
  // API Configuration - change this for production deployment
  const API_BASE_URL = window.API_BASE_URL || 
                       (typeof process !== 'undefined' && process.env && process.env.API_URL) || 
                       ''; // Empty string = same-origin (default for local dev)
  
  const form = document.getElementById("prefs-form");
  const statusEl = document.getElementById("status");
  const metaEl = document.getElementById("meta");
  const listEl = document.getElementById("results-list");
  const submitBtn = document.getElementById("submit-btn");
  const locationSelect = document.getElementById("location-select");
  const resultsSubtitle = document.getElementById("results-subtitle");

  // Form elements
  const budgetSlider = document.getElementById("budget-slider");
  const budgetDisplay = document.getElementById("budget-display");
  const cuisinePills = document.querySelectorAll("#cuisine-pills .pill");
  const cuisinesInput = document.getElementById("cuisines-input");
  const clearCuisinesBtn = document.getElementById("clear-cuisines");
  const ratingBtns = document.querySelectorAll(".rating-btn");
  const ratingInput = document.getElementById("rating-input");
  const topkSlider = document.getElementById("topk-slider");
  const topkDisplay = document.getElementById("topk-display");

  // Selected cuisines tracking
  let selectedCuisines = [];

  function titleCaseLocality(s) {
    return String(s)
      .split(/\s+/)
      .filter(Boolean)
      .map(function (w) {
        return w.charAt(0).toUpperCase() + w.slice(1);
      })
      .join(" ");
  }

  function formatCurrency(value) {
    return "₹" + parseInt(value).toLocaleString("en-IN");
  }

  // Budget slider handler
  budgetSlider.addEventListener("input", function () {
    budgetDisplay.textContent = formatCurrency(this.value);
  });

  // Top K slider handler
  topkSlider.addEventListener("input", function () {
    topkDisplay.textContent = this.value;
  });

  // Clear cuisines handler
  clearCuisinesBtn.addEventListener("click", function () {
    selectedCuisines = [];
    cuisinesInput.value = "";
    cuisinePills.forEach(function (pill) {
      pill.classList.remove("active");
    });
  });

  // Cuisine pills handler
  cuisinePills.forEach(function (pill) {
    pill.addEventListener("click", function () {
      const cuisine = this.dataset.cuisine;
      if (this.classList.contains("active")) {
        this.classList.remove("active");
        selectedCuisines = selectedCuisines.filter(function (c) {
          return c !== cuisine;
        });
      } else {
        this.classList.add("active");
        selectedCuisines.push(cuisine);
      }
      cuisinesInput.value = selectedCuisines.join(",");
    });
  });

  // Rating buttons handler
  ratingBtns.forEach(function (btn) {
    btn.addEventListener("click", function () {
      ratingBtns.forEach(function (b) {
        b.classList.remove("active");
      });
      this.classList.add("active");
      ratingInput.value = this.dataset.rating;
    });
  });

  async function loadLocalities() {
    if (!locationSelect) return;
    try {
      const res = await fetch(API_BASE_URL + "/localities");
      const text = await res.text();
      var data = null;
      try {
        data = text ? JSON.parse(text) : null;
      } catch (e) {
        data = null;
      }
      if (!res.ok || !data || !Array.isArray(data.localities)) {
        locationSelect.replaceChildren();
        var errOpt = document.createElement("option");
        errOpt.value = "";
        errOpt.textContent = "Could not load localities — refresh the page";
        locationSelect.appendChild(errOpt);
        locationSelect.disabled = true;
        return;
      }
      locationSelect.replaceChildren();
      var ph = document.createElement("option");
      ph.value = "";
      ph.disabled = true;
      ph.selected = true;
      ph.textContent = "Select a locality...";
      locationSelect.appendChild(ph);
      data.localities.forEach(function (loc) {
        var opt = document.createElement("option");
        opt.value = loc;
        opt.textContent = titleCaseLocality(loc);
        locationSelect.appendChild(opt);
      });
      locationSelect.disabled = false;
    } catch (err) {
      locationSelect.replaceChildren();
      var netOpt = document.createElement("option");
      netOpt.value = "";
      netOpt.textContent = "Network error loading localities";
      locationSelect.appendChild(netOpt);
      locationSelect.disabled = true;
    }
  }

  function setStatus(message, variant) {
    statusEl.textContent = message || "";
    statusEl.className = "status" + (variant ? " " + variant : "");
  }

  function buildPayload(formData) {
    const location = (formData.get("location") || "").trim().toLowerCase();
    const budget = parseFloat(String(formData.get("budget") || "").trim());
    const minRating = parseFloat(formData.get("min_rating") || "0", 10);
    const topK = parseInt(formData.get("top_k") || "5", 10);
    const cuisines = formData.get("cuisines");
    const cuisineList = cuisines
      ? cuisines.split(",").map(function (x) {
          return x.trim().toLowerCase();
        }).filter(Boolean)
      : null;

    const body = {
      location,
      budget: Number.isFinite(budget) ? budget : 0,
      min_rating: Number.isFinite(minRating) ? minRating : 0,
      top_k: Number.isFinite(topK) ? topK : 5,
    };
    if (cuisineList && cuisineList.length) body.cuisines = cuisineList;
    return body;
  }

  function clearResults() {
    listEl.replaceChildren();
    metaEl.classList.add("hidden");
    metaEl.replaceChildren();
    // Clear any existing what-if or relaxation messages
    const existingWhatIf = document.getElementById("what-if-section");
    if (existingWhatIf) existingWhatIf.remove();
    const existingRelaxation = document.getElementById("relaxation-banner");
    if (existingRelaxation) existingRelaxation.remove();
  }

  function renderWhatIfSuggestions(suggestions) {
    if (!suggestions || suggestions.length === 0) return;
    
    const section = document.createElement("div");
    section.id = "what-if-section";
    section.style.cssText = "margin-bottom: 1.5rem; padding: 1.25rem; background: linear-gradient(135deg, #fef3c7 0%, #fde68a 100%); border-radius: 16px; border: 2px solid #f59e0b; box-shadow: 0 4px 12px rgba(245, 158, 11, 0.2);";
    
    const header = document.createElement("div");
    header.style.cssText = "font-weight: 800; color: #92400e; margin-bottom: 1rem; font-size: 1.1rem; display: flex; align-items: center; gap: 0.5rem;";
    header.innerHTML = "💡 <span>What If You Changed Your Preferences?</span>";
    section.appendChild(header);
    
    suggestions.forEach(function (suggestion) {
      const item = document.createElement("div");
      item.style.cssText = "margin-bottom: 0.75rem; padding: 0.75rem; background: rgba(255,255,255,0.8); border-radius: 10px; border-left: 4px solid #f59e0b;";
      
      const message = document.createElement("div");
      message.style.cssText = "font-size: 0.95rem; color: #78350f; font-weight: 500;";
      message.textContent = suggestion.message;
      item.appendChild(message);
      
      if (suggestion.example_restaurants && suggestion.example_restaurants.length > 0) {
        const examples = document.createElement("div");
        examples.style.cssText = "font-size: 0.85rem; color: #92400e; margin-top: 0.5rem; padding-top: 0.5rem; border-top: 1px dashed #fbbf24;";
        examples.innerHTML = "<strong>Examples:</strong> " + suggestion.example_restaurants.join(", ");
        item.appendChild(examples);
      }
      
      section.appendChild(item);
    });
    
    // Insert at the top of results section
    const resultsSection = document.querySelector(".results-section");
    if (resultsSection) {
      resultsSection.insertBefore(section, resultsSection.firstChild);
    }
  }

  function renderRelaxationBanner(relaxation) {
    if (!relaxation || !relaxation.was_relaxed) return;
    
    const banner = document.createElement("div");
    banner.id = "relaxation-banner";
    banner.style.cssText = "margin-bottom: 1.5rem; padding: 1rem; background: linear-gradient(135deg, #dbeafe 0%, #bfdbfe 100%); border-radius: 12px; border: 1px solid #3b82f6; display: flex; align-items: center; gap: 0.75rem;";
    
    const icon = document.createElement("span");
    icon.textContent = "🔍";
    icon.style.fontSize = "1.25rem";
    banner.appendChild(icon);
    
    const content = document.createElement("div");
    
    const message = document.createElement("div");
    message.style.cssText = "font-weight: 600; color: #1e40af; font-size: 0.9rem;";
    message.textContent = relaxation.message;
    content.appendChild(message);
    
    if (relaxation.relaxed_filters) {
      const details = document.createElement("div");
      details.style.cssText = "font-size: 0.8rem; color: #3b82f6; margin-top: 0.25rem;";
      const changes = [];
      if (relaxation.relaxed_filters.min_rating !== relaxation.original_filters.min_rating) {
        changes.push("rating relaxed");
      }
      if (relaxation.relaxed_filters.budget !== relaxation.original_filters.budget) {
        changes.push("budget increased");
      }
      if (changes.length > 0) {
        details.textContent = "Adjusted: " + changes.join(", ");
        content.appendChild(details);
      }
    }
    
    banner.appendChild(content);
    
    // Insert before results grid
    listEl.parentNode.insertBefore(banner, listEl);
  }

  function calculateMatchScore(item, budget) {
    // Simple match score based on rating and budget fit
    let score = 0;
    if (item.rating) {
      score += item.rating * 15; // Rating contributes up to 75%
    }
    if (item.cost && budget) {
      const budgetFit = Math.max(0, 1 - (item.cost / budget));
      score += budgetFit * 25; // Budget fit contributes up to 25%
    }
    return Math.min(98, Math.round(score));
  }

  function getGradientForIndex(index) {
    const gradients = [
      "linear-gradient(135deg, #667eea 0%, #764ba2 100%)",
      "linear-gradient(135deg, #f093fb 0%, #f5576c 100%)",
      "linear-gradient(135deg, #4facfe 0%, #00f2fe 100%)",
      "linear-gradient(135deg, #43e97b 0%, #38f9d7 100%)",
      "linear-gradient(135deg, #fa709a 0%, #fee140 100%)",
      "linear-gradient(135deg, #a8edea 0%, #fed6e3 100%)",
    ];
    return gradients[index % gradients.length];
  }

  function renderCard(item, index, budget) {
    const card = document.createElement("div");
    card.className = "card";

    const matchScore = calculateMatchScore(item, budget);
    const gradient = getGradientForIndex(index);

    // Card image section
    const imageSection = document.createElement("div");
    imageSection.className = "card-image";
    imageSection.style.background = gradient;

    // Rating badge
    if (item.rating) {
      const ratingBadge = document.createElement("span");
      ratingBadge.className = "card-rating";
      ratingBadge.textContent = item.rating.toFixed(1);
      imageSection.appendChild(ratingBadge);
    }

    // Match percentage
    const matchBadge = document.createElement("span");
    matchBadge.className = "card-match";
    matchBadge.textContent = matchScore + "% MATCH";
    imageSection.appendChild(matchBadge);

    card.appendChild(imageSection);

    // Card content
    const content = document.createElement("div");
    content.className = "card-content";

    // Header with name and cost
    const header = document.createElement("div");
    header.className = "card-header";

    const title = document.createElement("h3");
    title.className = "card-title";
    title.textContent = item.name || "(unnamed)";
    header.appendChild(title);

    if (item.cost) {
      const cost = document.createElement("span");
      cost.className = "card-cost";
      cost.textContent = "₹" + Math.round(item.cost).toLocaleString("en-IN") + " for two";
      header.appendChild(cost);
    }

    content.appendChild(header);

    // Cuisine tags
    if (Array.isArray(item.cuisines) && item.cuisines.length) {
      const cuisinesDiv = document.createElement("div");
      cuisinesDiv.className = "card-cuisines";
      item.cuisines.slice(0, 3).forEach(function (cuisine) {
        const tag = document.createElement("span");
        tag.className = "cuisine-tag";
        tag.textContent = cuisine;
        cuisinesDiv.appendChild(tag);
      });
      content.appendChild(cuisinesDiv);
    }

    // AI Insight
    if (item.explanation) {
      const insight = document.createElement("div");
      insight.className = "card-insight";

      const insightHeader = document.createElement("div");
      insightHeader.className = "insight-header";
      insightHeader.textContent = "AI INSIGHT";
      insight.appendChild(insightHeader);

      const insightText = document.createElement("p");
      insightText.className = "insight-text";
      insightText.textContent = item.explanation;
      insight.appendChild(insightText);

      content.appendChild(insight);
    }

    // Maps link
    if (item.maps_url) {
      const mapsLink = document.createElement("a");
      mapsLink.href = item.maps_url;
      mapsLink.target = "_blank";
      mapsLink.rel = "noopener noreferrer";
      mapsLink.className = "card-maps-link";
      mapsLink.textContent = "View on Google Maps";
      content.appendChild(mapsLink);
    }

    card.appendChild(content);

    return card;
  }

  form.addEventListener("submit", async function (e) {
    e.preventDefault();
    clearResults();
    const fd = new FormData(form);
    const body = buildPayload(fd);

    submitBtn.disabled = true;
    setStatus("Loading...", "loading");

    // Update subtitle with location
    const location = fd.get("location");
    if (location) {
      resultsSubtitle.textContent =
        "Based on your preferences in " +
        titleCaseLocality(location) +
        ". Here are your top matches for today.";
    }

    try {
      const res = await fetch(API_BASE_URL + "/recommend", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });

      const text = await res.text();
      let data = null;
      try {
        data = text ? JSON.parse(text) : null;
      } catch {
        data = null;
      }

      if (!res.ok) {
        const detail =
          data && data.detail ? JSON.stringify(data.detail) : text.slice(0, 400);
        setStatus("Error " + res.status + ": " + detail, "error");
        return;
      }

      if (!data || !Array.isArray(data.recommendations)) {
        setStatus("Unexpected response shape from server.", "error");
        return;
      }

      setStatus(
        data.recommendations.length
          ? "Showing " + data.recommendations.length + " recommendation(s)."
          : "No restaurants matched your filters."
      );

      // Show filter relaxation banner if applicable
      if (data.filter_relaxation) {
        renderRelaxationBanner(data.filter_relaxation);
      }

      // Show what-if suggestions
      if (data.what_if_suggestions && data.what_if_suggestions.length > 0) {
        renderWhatIfSuggestions(data.what_if_suggestions);
      }

      data.recommendations.forEach(function (item, index) {
        listEl.appendChild(renderCard(item, index, body.budget));
      });
    } catch (err) {
      setStatus(
        "Network error: " + (err && err.message ? err.message : err),
        "error"
      );
    } finally {
      submitBtn.disabled = false;
    }
  });

  document.addEventListener("DOMContentLoaded", loadLocalities);
})();
