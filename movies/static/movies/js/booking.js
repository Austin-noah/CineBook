const priceElement = document.getElementById("ticket-price");
const bookingForm = document.getElementById("booking-form");
const quantityDialog = document.getElementById("quantity-dialog");
const seatMap = document.querySelector("[data-seat-map]");

if (bookingForm && quantityDialog && seatMap) {
    const quantityField = document.getElementById("ticket-quantity");
    const quantityOptions = [...quantityDialog.querySelectorAll("[data-quantity]")];
    const confirmQuantity = quantityDialog.querySelector("[data-confirm-quantity]");
    const quantityError = quantityDialog.querySelector("[data-quantity-error]");
    const seatQuantityError = document.getElementById("seat-quantity-error");
    const checkboxes = [...bookingForm.querySelectorAll(".seat-checkbox")];
    const selectedDisplay = document.getElementById("selected-seats");
    const totalDisplay = document.getElementById("total-price");
    const countDisplay = document.getElementById("ticket-count");
    const sectionDisplay = document.getElementById("section-totals");
    const submitButton = document.getElementById("continue-booking");
    const requiredQuantityDisplay = document.querySelector("[data-required-quantity]");
    let selectedQuantity = Number(quantityField.value) || 0;

    function updateQuantityChoice(quantity) {
        selectedQuantity = quantity;
        quantityField.value = String(quantity);
        requiredQuantityDisplay.textContent = String(quantity);
        quantityOptions.forEach((option) => {
            const isSelected = Number(option.dataset.quantity) === quantity;
            option.classList.toggle("is-selected", isSelected);
            option.setAttribute("aria-pressed", String(isSelected));
        });
        confirmQuantity.disabled = false;
        quantityError.hidden = true;
    }

    quantityOptions.forEach((option) => {
        option.addEventListener("click", () => {
            updateQuantityChoice(Number(option.dataset.quantity));
        });
    });

    confirmQuantity.addEventListener("click", () => {
        if (selectedQuantity < 1 || selectedQuantity > 6) {
            quantityError.textContent = "Choose between 1 and 6 tickets.";
            quantityError.hidden = false;
            return;
        }
        quantityDialog.hidden = true;
        seatMap.hidden = false;
        checkboxes.find((checkbox) => !checkbox.disabled)?.focus();
        updateBooking();
    });

    quantityDialog.querySelector("[data-close-quantity]")
        ?.addEventListener("click", () => {
            window.location.assign(
                bookingForm.dataset.showtimesUrl || "/"
            );
        });

    if (selectedQuantity) {
        quantityOptions.find(
            (option) => Number(option.dataset.quantity) === selectedQuantity
        )?.click();
    } else {
        confirmQuantity.disabled = true;
        const firstOption = quantityOptions.find((option) => !option.disabled);
        firstOption?.focus();
    }

    quantityDialog.addEventListener("keydown", (event) => {
        if (event.key === "Escape") {
            event.preventDefault();
            window.location.assign(bookingForm.dataset.showtimesUrl || "/");
        }
        if (event.key !== "Tab") return;
        const focusable = [...quantityDialog.querySelectorAll(
            "button:not(:disabled):not([hidden])"
        )];
        if (!focusable.length) return;
        const first = focusable[0];
        const last = focusable[focusable.length - 1];
        if (event.shiftKey && document.activeElement === first) {
            event.preventDefault();
            last.focus();
        } else if (!event.shiftKey && document.activeElement === last) {
            event.preventDefault();
            first.focus();
        }
    });

    function updateBooking() {
        const selected = checkboxes.filter((box) => box.checked);
        const sectionTotals = new Map();
        let total = 0;

        selected.forEach((checkbox) => {
            const price = Number(checkbox.dataset.price);
            const section = checkbox.dataset.section;
            total += price;
            sectionTotals.set(
                section,
                (sectionTotals.get(section) || 0) + price
            );
        });

        selectedDisplay.textContent = selected.map((box) => box.value).join(", ") || "None";
        countDisplay.textContent = String(selected.length);
        totalDisplay.textContent = total.toFixed(2);
        sectionDisplay.textContent = [...sectionTotals.entries()]
            .map(([section, amount]) => `${section}: ₹${amount.toFixed(2)}`)
            .join(" · ") || "None";

        const exactQuantitySelected = selected.length === selectedQuantity;
        submitButton.disabled = !exactQuantitySelected;
        seatQuantityError.textContent = selected.length > selectedQuantity
            ? `You selected ${selected.length} seats. Choose exactly ${selectedQuantity}.`
            : selected.length > 0 && !exactQuantitySelected
                ? `Choose ${selectedQuantity - selected.length} more seat${selectedQuantity - selected.length === 1 ? "" : "s"}.`
                : "";
    }

    checkboxes.forEach((checkbox) => {
        checkbox.addEventListener("change", () => {
            const selectedCount = checkboxes.filter((box) => box.checked).length;
            if (checkbox.checked && selectedCount > selectedQuantity) {
                checkbox.checked = false;
                seatQuantityError.textContent =
                    `You can select only ${selectedQuantity} seat${selectedQuantity === 1 ? "" : "s"}.`;
            }
            updateBooking();
        });
    });

    bookingForm.addEventListener("submit", (event) => {
        const selectedCount = checkboxes.filter((box) => box.checked).length;
        if (selectedCount !== selectedQuantity) {
            event.preventDefault();
            seatQuantityError.textContent =
                `Choose exactly ${selectedQuantity} seats before continuing.`;
            submitButton.focus();
        }
    });

    updateBooking();
} else if (priceElement) {
    const checkboxes = document.querySelectorAll(".seat-checkbox");
    const selectedDisplay = document.getElementById("selected-seats");
    const totalDisplay = document.getElementById("total-price");
    const countDisplay = document.getElementById("ticket-count");
    const sectionDisplay = document.getElementById("section-totals");

    function updateBooking() {
        const selected = [...checkboxes].filter((box) => box.checked);
        const sectionTotals = new Map();
        let total = 0;
        selected.forEach((checkbox) => {
            const price = Number(checkbox.dataset.price);
            const section = checkbox.dataset.section;
            total += price;
            sectionTotals.set(section, (sectionTotals.get(section) || 0) + price);
        });
        selectedDisplay.textContent = selected.map((box) => box.value).join(", ") || "None";
        countDisplay.textContent = String(selected.length);
        totalDisplay.textContent = total.toFixed(2);
        sectionDisplay.textContent = [...sectionTotals.entries()]
            .map(([section, amount]) => `${section}: ₹${amount.toFixed(2)}`)
            .join(" · ") || "None";
    }

    checkboxes.forEach((checkbox) => {
        checkbox.addEventListener("change", updateBooking);
    });
    updateBooking();
}
