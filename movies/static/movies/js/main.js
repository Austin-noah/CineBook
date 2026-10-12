document.querySelectorAll("[data-image-fallback]").forEach((image) => {
    function showFallback() {
        const placeholder = image.parentElement.querySelector(
            ".poster-placeholder, .image-text-fallback"
        );
        image.hidden = true;
        if (placeholder) {
            placeholder.hidden = false;
        }
        const hero = image.closest(".featured-hero, .detail-hero");
        if (hero) {
            hero.classList.add(
                hero.classList.contains("featured-hero")
                    ? "featured-hero-fallback"
                    : "detail-hero-fallback"
            );
        }
    }

    image.addEventListener("error", showFallback, { once: true });
    if (image.complete && image.naturalWidth === 0) {
        showFallback();
    }
});

document.querySelectorAll(".star-display").forEach((rating) => {
    const value = Number(rating.dataset.rating);
    rating.querySelectorAll("span").forEach((star, index) => {
        const fill = Math.max(0, Math.min(1, value - index));
        star.classList.toggle("is-full", fill >= 1);
        star.classList.toggle("is-half", fill > 0 && fill < 1);
    });
});

document.querySelectorAll("[data-movie-carousel]").forEach((carousel) => {
    carousel.addEventListener("wheel", (event) => {
        if (
            carousel.scrollWidth <= carousel.clientWidth ||
            Math.abs(event.deltaY) <= Math.abs(event.deltaX)
        ) {
            return;
        }
        event.preventDefault();
        carousel.scrollLeft += event.deltaY;
    }, { passive: false });
});

document.querySelectorAll("[data-print-ticket]").forEach((button) => {
    button.addEventListener("click", () => window.print());
});

const cityDialog = document.getElementById("city-picker-dialog");
const cityTrigger = document.querySelector("[data-open-city-picker]");
const citySearch = document.getElementById("city-picker-search");
const popularCities = document.getElementById("popular-cities");
const allCities = document.getElementById("all-cities");
const viewAllCities = document.querySelector("[data-view-all-cities]");

if (cityDialog && cityTrigger && citySearch && popularCities && allCities) {
    cityTrigger.addEventListener("click", () => {
        cityDialog.showModal();
        citySearch.value = "";
        popularCities.hidden = false;
        allCities.hidden = true;
        citySearch.focus();
    });

    cityDialog.querySelector("[data-close-city-picker]")
        ?.addEventListener("click", () => cityDialog.close());

    viewAllCities?.addEventListener("click", () => {
        popularCities.hidden = true;
        allCities.hidden = false;
        viewAllCities.dataset.expanded = "true";
        citySearch.focus();
    });

    citySearch.addEventListener("input", () => {
        const query = citySearch.value.trim().toLocaleLowerCase();
        const showAll = Boolean(query);
        popularCities.hidden = showAll;
        allCities.hidden = !showAll && !viewAllCities?.dataset.expanded;
        allCities.querySelectorAll("[data-city-choice]").forEach((button) => {
            button.hidden = Boolean(query) &&
                !button.dataset.cityChoice.toLocaleLowerCase().includes(query);
        });
    });
    cityDialog.querySelectorAll("[data-city-choice]").forEach((button) => {
        button.addEventListener("click", () => {
            const destination = new URL(window.location.href);
            destination.searchParams.set("city", button.dataset.cityChoice);
            window.location.assign(destination);
        });
    });
}

const themeToggle = document.querySelector("[data-theme-toggle]");
if (themeToggle) {
    function updateThemeButton() {
        const isLight = document.documentElement.dataset.theme === "light";
        themeToggle.setAttribute("aria-pressed", String(isLight));
        themeToggle.setAttribute(
            "aria-label",
            `Switch to ${isLight ? "dark" : "light"} theme`
        );
        themeToggle.querySelector("[data-theme-icon]").textContent =
            isLight ? "☾" : "☀";
        themeToggle.querySelector("[data-theme-label]").textContent =
            isLight ? "Light" : "Dark";
    }

    themeToggle.addEventListener("click", () => {
        const theme = document.documentElement.dataset.theme === "light"
            ? "dark"
            : "light";
        document.documentElement.dataset.theme = theme;
        try {
            localStorage.setItem("cinebook-theme", theme);
        } catch (error) {
            console.warn("Could not save the CineBook theme preference.", error);
        }
        updateThemeButton();
    });
    updateThemeButton();
    window.matchMedia("(prefers-color-scheme: light)")
        .addEventListener("change", (event) => {
            let hasSavedPreference = false;
            try {
                hasSavedPreference = localStorage.getItem("cinebook-theme") !== null;
            } catch (error) {
                console.warn("Could not read the CineBook theme preference.", error);
            }
            if (!hasSavedPreference) {
                document.documentElement.dataset.theme =
                    event.matches ? "light" : "dark";
                updateThemeButton();
            }
        });
}

document.querySelectorAll("[data-share-page]").forEach((button) => {
    button.addEventListener("click", async () => {
        const status = button.parentElement.querySelector(".share-status");
        try {
            if (navigator.share) {
                await navigator.share({
                    title: document.title,
                    url: window.location.href,
                });
                if (status) status.textContent = "Shared.";
            } else if (navigator.clipboard) {
                await navigator.clipboard.writeText(window.location.href);
                if (status) status.textContent = "Link copied.";
            } else {
                window.prompt("Copy this movie link:", window.location.href);
            }
        } catch (error) {
            if (error.name !== "AbortError" && status) {
                status.textContent = "Sharing is unavailable in this browser.";
            }
        }
    });
});

document.querySelectorAll("[data-review-copy]").forEach((copy) => {
    const readMore = copy.parentElement.querySelector("[data-read-more]");
    if (!readMore || copy.scrollHeight <= copy.clientHeight + 2) return;
    readMore.hidden = false;
    readMore.addEventListener("click", () => {
        const expanded = copy.classList.toggle("is-expanded");
        readMore.textContent = expanded ? "Read less" : "Read more";
    });
});

// Nav search clear button and live autocomplete suggestions
const navSearchInput = document.getElementById("nav-search");
const navSearchClear = document.getElementById("nav-search-clear");
const suggestionsBox = document.getElementById("search-suggestions-box");

if (navSearchInput) {
    function toggleClearBtn() {
        if (navSearchClear) {
            navSearchClear.hidden = !navSearchInput.value.trim();
        }
    }
    navSearchInput.addEventListener("input", toggleClearBtn);
    if (navSearchClear) {
        navSearchClear.addEventListener("click", () => {
            navSearchInput.value = "";
            toggleClearBtn();
            if (suggestionsBox) suggestionsBox.hidden = true;
            navSearchInput.focus();
        });
    }

    let debounceTimer = null;
    navSearchInput.addEventListener("input", () => {
        clearTimeout(debounceTimer);
        const query = navSearchInput.value.trim();
        if (query.length < 2) {
            if (suggestionsBox) suggestionsBox.hidden = true;
            return;
        }

        debounceTimer = setTimeout(async () => {
            try {
                const res = await fetch(`/api/search-suggestions/?q=${encodeURIComponent(query)}`);
                if (!res.ok) return;
                const data = await res.json();
                if (!data.results || data.results.length === 0) {
                    if (suggestionsBox) suggestionsBox.hidden = true;
                    return;
                }

                if (suggestionsBox) {
                    suggestionsBox.innerHTML = data.results.map((movie) => `
                        <a href="${movie.detail_url}" class="suggestion-item">
                            ${movie.poster_url ? `<img src="${movie.poster_url}" alt="" class="suggestion-thumb">` : `<div class="suggestion-thumb-placeholder">🎬</div>`}
                            <div class="suggestion-text">
                                <div class="suggestion-title">${movie.title}</div>
                                <div class="suggestion-meta">${movie.genre} · ${movie.language} (${movie.year})</div>
                            </div>
                        </a>
                    `).join("");
                    suggestionsBox.hidden = false;
                }
            } catch (err) {
                console.warn("Could not fetch search suggestions:", err);
            }
        }, 220);
    });

    document.addEventListener("click", (e) => {
        if (suggestionsBox && !suggestionsBox.contains(e.target) && e.target !== navSearchInput) {
            suggestionsBox.hidden = true;
        }
    });

    navSearchInput.addEventListener("keydown", (e) => {
        if (e.key === "Escape" && suggestionsBox) {
            suggestionsBox.hidden = true;
        }
    });
}

