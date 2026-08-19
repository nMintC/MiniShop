async function login(event) {
    event.preventDefault();
    const form = event.currentTarget;
    const button = document.getElementById("login-button");
    const message = document.getElementById("message");

    button.disabled = true;
    message.textContent = "";

    const payload = {
        username: form.username.value.trim(),
        password: form.password.value,
    };

    try {
        const response = await fetch("/api/auth/login", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload),
        });

        if (!response.ok) {
            const data = await response.json().catch(() => ({}));
            throw new Error(data.detail || "Login failed");
        }

        window.location.href = "/dashboard";
    } catch (error) {
        message.textContent = error.message;
    } finally {
        button.disabled = false;
    }
}

document.getElementById("login-form").addEventListener("submit", login);
