// static/js/validation.js
document.addEventListener("DOMContentLoaded", function () {
    const form = document.getElementById("loginForm");
    const input = document.getElementById("test_code");
    const feedback = document.getElementById("fieldFeedback");

    function setInvalid(message) {
        input.classList.add("is-invalid");
        feedback.textContent = message;
    }

    function clearInvalid() {
        input.classList.remove("is-invalid");
        feedback.textContent = "";
    }

    input.addEventListener("input", function () {
        // remove non-digit characters as typed
        this.value = this.value.replace(/\D/g, "").slice(0, 6);
        clearInvalid();
    });

    form.addEventListener("submit", function (e) {
        const val = input.value.trim();
        if (!val) {
            e.preventDefault();
            setInvalid("Please enter the 6 digit Unique Test ID.");
            return;
        }
        if (!/^\d+$/.test(val)) {
            e.preventDefault();
            setInvalid("Unique Test ID must be numeric.");
            return;
        }
        if (val.length !== 6) {
            e.preventDefault();
            setInvalid("Unique Test ID must be exactly 6 digits.");
            return;
        }
        // Allow submit to proceed to server for DB check
        clearInvalid();
    });
});