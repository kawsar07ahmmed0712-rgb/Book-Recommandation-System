(() => {
    const input = document.querySelector("#book-input");
    const suggestionsList = document.querySelector("#suggestions");

    if (!input || !suggestionsList) {
        return;
    }

    const escapeHtml = (value) =>
        value
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/\"/g, "&quot;")
            .replace(/'/g, "&#039;");

    let activeIndex = -1;
    let debounceTimer = null;
    let controller = null;

    const clearSuggestions = () => {
        suggestionsList.innerHTML = "";
        suggestionsList.classList.remove("show");
        activeIndex = -1;
    };

    const renderSuggestions = (books) => {
        if (!Array.isArray(books) || books.length === 0) {
            clearSuggestions();
            return;
        }

        suggestionsList.innerHTML = books
            .map((book, index) => `<li data-index="${index}" role="option">${escapeHtml(book)}</li>`)
            .join("");

        suggestionsList.classList.add("show");
        activeIndex = -1;
    };

    const setActiveSuggestion = (items) => {
        items.forEach((item, index) => {
            item.classList.toggle("active", index === activeIndex);
        });

        if (activeIndex >= 0 && items[activeIndex]) {
            items[activeIndex].scrollIntoView({ block: "nearest" });
        }
    };

    const fetchSuggestions = async (query) => {
        if (controller) {
            controller.abort();
        }

        controller = new AbortController();

        const endpoint = input.dataset.suggestionsUrl;
        const url = new URL(endpoint, window.location.origin);
        url.searchParams.set("q", query);
        url.searchParams.set("limit", "10");

        const response = await fetch(url.toString(), { signal: controller.signal });
        if (!response.ok) {
            return [];
        }

        const payload = await response.json();
        return payload.books || [];
    };

    input.addEventListener("input", () => {
        const query = input.value.trim();

        if (query.length < 2) {
            clearSuggestions();
            return;
        }

        window.clearTimeout(debounceTimer);
        debounceTimer = window.setTimeout(async () => {
            try {
                const books = await fetchSuggestions(query);
                renderSuggestions(books);
            } catch (error) {
                if (error.name !== "AbortError") {
                    clearSuggestions();
                }
            }
        }, 180);
    });

    suggestionsList.addEventListener("mousedown", (event) => {
        const item = event.target.closest("li");
        if (!item) {
            return;
        }

        input.value = item.textContent || "";
        clearSuggestions();
    });

    input.addEventListener("keydown", (event) => {
        const items = Array.from(suggestionsList.querySelectorAll("li"));
        if (items.length === 0) {
            return;
        }

        if (event.key === "ArrowDown") {
            event.preventDefault();
            activeIndex = (activeIndex + 1) % items.length;
            setActiveSuggestion(items);
            return;
        }

        if (event.key === "ArrowUp") {
            event.preventDefault();
            activeIndex = (activeIndex - 1 + items.length) % items.length;
            setActiveSuggestion(items);
            return;
        }

        if (event.key === "Enter" && activeIndex >= 0) {
            event.preventDefault();
            input.value = items[activeIndex].textContent || "";
            clearSuggestions();
            return;
        }

        if (event.key === "Escape") {
            clearSuggestions();
        }
    });

    document.addEventListener("click", (event) => {
        if (!event.target.closest(".recommend-form")) {
            clearSuggestions();
        }
    });
})();
