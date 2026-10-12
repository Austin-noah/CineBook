(() => {
    const bookingForm = document.getElementById("booking-form");
    const quantityDialog = document.getElementById("quantity-dialog");
    const seatMap = document.querySelector("[data-seat-map]");

    if (!bookingForm || !seatMap) {
        return;
    }

    const quantityField = document.getElementById("ticket-quantity");
    const quantityOptions = quantityDialog ? [...quantityDialog.querySelectorAll("[data-quantity]")] : [];
    const confirmQuantity = quantityDialog ? quantityDialog.querySelector("[data-confirm-quantity]") : null;
    const quantityError = quantityDialog ? quantityDialog.querySelector("[data-quantity-error]") : null;
    const seatQuantityError = document.getElementById("seat-quantity-error");
    const checkboxes = [...bookingForm.querySelectorAll(".seat-checkbox")];
    const selectedDisplay = document.getElementById("selected-seats");
    const totalDisplay = document.getElementById("total-price");
    const countDisplay = document.getElementById("ticket-count");
    const sectionDisplay = document.getElementById("section-totals");
    const submitButton = document.getElementById("continue-booking");
    const requiredQuantityDisplay = document.querySelector("[data-required-quantity]");
    const inlineQtyButtons = [...document.querySelectorAll("[data-set-qty]")];

    let selectedQuantity = Number(quantityField.value) || 0;
    let isSubmitting = false;

    function setQuantity(newQty) {
        if (newQty < 1 || newQty > 6) return;
        selectedQuantity = newQty;
        quantityField.value = String(newQty);
        if (requiredQuantityDisplay) {
            requiredQuantityDisplay.textContent = String(newQty);
        }

        quantityOptions.forEach((option) => {
            const isMatch = Number(option.dataset.quantity) === newQty;
            option.classList.toggle("is-selected", isMatch);
            option.setAttribute("aria-pressed", String(isMatch));
        });

        inlineQtyButtons.forEach((btn) => {
            const isMatch = Number(btn.dataset.setQty) === newQty;
            btn.classList.toggle("active", isMatch);
            btn.setAttribute("aria-pressed", String(isMatch));
        });

        if (confirmQuantity) {
            confirmQuantity.disabled = false;
        }
        if (quantityError) {
            quantityError.hidden = true;
        }

        // If currently selected seats exceed new quantity, trim excess
        const checkedBoxes = checkboxes.filter((b) => b.checked);
        if (checkedBoxes.length > selectedQuantity) {
            checkedBoxes.slice(selectedQuantity).forEach((b) => {
                b.checked = false;
            });
        }

        updateBooking();
    }

    // Modal quantity selection
    quantityOptions.forEach((option) => {
        option.addEventListener("click", () => {
            setQuantity(Number(option.dataset.quantity));
        });
    });

    if (confirmQuantity && quantityDialog) {
        confirmQuantity.addEventListener("click", () => {
            if (selectedQuantity < 1 || selectedQuantity > 6) {
                if (quantityError) {
                    quantityError.textContent = "Choose between 1 and 6 tickets.";
                    quantityError.hidden = false;
                }
                return;
            }
            quantityDialog.hidden = true;
            seatMap.hidden = false;
            checkboxes.find((b) => !b.disabled)?.focus();
            updateBooking();
        });

        quantityDialog.querySelector("[data-close-quantity]")?.addEventListener("click", () => {
            window.location.assign(bookingForm.dataset.showtimesUrl || "/");
        });

        quantityDialog.addEventListener("keydown", (event) => {
            if (event.key === "Escape") {
                event.preventDefault();
                window.location.assign(bookingForm.dataset.showtimesUrl || "/");
            }
        });
    }

    // Inline quantity switcher
    inlineQtyButtons.forEach((btn) => {
        btn.addEventListener("click", () => {
            setQuantity(Number(btn.dataset.setQty));
        });
    });

    if (selectedQuantity) {
        setQuantity(selectedQuantity);
    } else if (quantityOptions.length > 0) {
        if (confirmQuantity) confirmQuantity.disabled = true;
    }

    /**
     * Intelligent adjacent seat selection algorithm.
     * Given a clicked seat checkbox, select requested contiguous seats in the same row.
     */
    function autoSelectAdjacentSeats(clickedCheckbox) {
        const rowElement = clickedCheckbox.closest(".seat-row");
        if (!rowElement) return;

        const rowBoxes = [...rowElement.querySelectorAll(".seat-checkbox")];
        const clickedIdx = rowBoxes.indexOf(clickedCheckbox);
        if (clickedIdx === -1) return;

        const targetCount = selectedQuantity;
        if (targetCount <= 1) {
            // Uncheck other seats and check only this one
            checkboxes.forEach((b) => {
                if (b !== clickedCheckbox) b.checked = false;
            });
            clickedCheckbox.checked = true;
            return;
        }

        // Try primary contiguous block to the right: [clickedIdx ... clickedIdx + targetCount - 1]
        let bestBlock = null;
        const totalInRow = rowBoxes.length;

        if (clickedIdx + targetCount <= totalInRow) {
            const candidate = rowBoxes.slice(clickedIdx, clickedIdx + targetCount);
            if (!candidate.some((b) => b.disabled)) {
                bestBlock = candidate;
            }
        }

        // If rightward block unavailable (boundary or booked seat), search in the same row:
        if (!bestBlock) {
            // First check blocks that still contain the clicked seat (shifted left)
            for (let shift = 1; shift < targetCount; shift++) {
                const start = clickedIdx - shift;
                if (start >= 0 && start + targetCount <= totalInRow) {
                    const block = rowBoxes.slice(start, start + targetCount);
                    if (!block.some((b) => b.disabled)) {
                        bestBlock = block;
                        break;
                    }
                }
            }
        }

        // Check any other contiguous block in the same row
        if (!bestBlock) {
            for (let start = 0; start <= totalInRow - targetCount; start++) {
                const block = rowBoxes.slice(start, start + targetCount);
                if (!block.some((b) => b.disabled)) {
                    bestBlock = block;
                    break;
                }
            }
        }

        if (bestBlock) {
            // Uncheck all other seats across all rows
            checkboxes.forEach((b) => {
                b.checked = false;
            });
            // Check the intelligent adjacent block
            bestBlock.forEach((b) => {
                b.checked = true;
            });
            if (seatQuantityError) {
                seatQuantityError.textContent = "";
            }
        } else {
            // No full contiguous block in this row; keep this seat selected and advise user
            const currentSelectedCount = checkboxes.filter((b) => b.checked).length;
            if (currentSelectedCount > targetCount) {
                clickedCheckbox.checked = false;
            }
            if (seatQuantityError) {
                seatQuantityError.textContent =
                    `Could not find ${targetCount} adjacent seats in this row. You can select another row or pick available seats individually.`;
            }
        }
    }

    checkboxes.forEach((checkbox) => {
        checkbox.addEventListener("click", (event) => {
            if (checkbox.disabled) return;

            if (checkbox.checked) {
                // If user clicks an unselected seat, trigger intelligent adjacent selection
                autoSelectAdjacentSeats(checkbox);
            } else {
                // Seat was deselected manually
                if (seatQuantityError) {
                    seatQuantityError.textContent = "";
                }
            }
            updateBooking();
        });
    });

    function updateBooking() {
        const selected = checkboxes.filter((box) => box.checked);
        const sectionTotals = new Map();
        let total = 0;

        selected.forEach((checkbox) => {
            const price = Number(checkbox.dataset.price) || 0;
            const section = checkbox.dataset.section || "General";
            total += price;
            sectionTotals.set(section, (sectionTotals.get(section) || 0) + price);
        });

        if (selectedDisplay) {
            selectedDisplay.textContent = selected.map((b) => b.value).join(", ") || "None";
        }
        if (countDisplay) {
            countDisplay.textContent = String(selected.length);
        }
        if (totalDisplay) {
            totalDisplay.textContent = total.toFixed(2);
        }
        if (sectionDisplay) {
            sectionDisplay.textContent = [...sectionTotals.entries()]
                .map(([section, amount]) => `${section}: ₹${amount.toFixed(2)}`)
                .join(" · ") || "None";
        }

        const exactCount = selected.length === selectedQuantity;
        if (submitButton && !isSubmitting) {
            submitButton.disabled = !exactCount;
        }

        if (seatQuantityError && !seatQuantityError.textContent) {
            if (selected.length > 0 && selected.length < selectedQuantity) {
                const diff = selectedQuantity - selected.length;
                seatQuantityError.textContent = `Select ${diff} more seat${diff === 1 ? "" : "s"}.`;
            } else if (selected.length > selectedQuantity) {
                seatQuantityError.textContent = `You selected ${selected.length} seats. Choose exactly ${selectedQuantity}.`;
            }
        }
    }

    // Double-click prevention and submission validation
    bookingForm.addEventListener("submit", (event) => {
        const selected = checkboxes.filter((box) => box.checked);
        if (selected.length !== selectedQuantity) {
            event.preventDefault();
            if (seatQuantityError) {
                seatQuantityError.textContent = `Please choose exactly ${selectedQuantity} seat${selectedQuantity === 1 ? "" : "s"} before continuing.`;
            }
            submitButton?.focus();
            return;
        }

        if (isSubmitting) {
            event.preventDefault();
            return;
        }

        isSubmitting = true;
        if (submitButton) {
            submitButton.disabled = true;
            const textSpan = submitButton.querySelector(".btn-text");
            const spinnerSpan = submitButton.querySelector(".btn-spinner");
            if (textSpan) textSpan.textContent = "Reserving tickets...";
            if (spinnerSpan) spinnerSpan.hidden = false;
        }
    });

    updateBooking();
})();
