async function login(event) {
    event.preventDefault();
    const form = event.currentTarget;
    const button = document.getElementById("login-button");
    const message = document.getElementById("message");

    button.disabled = true;
    message.textContent = "";

    try {
        const response = await fetch("/api/auth/login", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ username: form.username.value.trim(), password: form.password.value }),
        });

        const data = await response.json().catch(() => ({}));
        if (!response.ok) {
            throw new Error(data.detail || "Login failed");
        }

        window.location.href = data.user.role === "admin" ? "/admin/dashboard" : "/";
    } catch (error) {
        message.textContent = error.message;
    } finally {
        button.disabled = false;
    }
}

document.getElementById("login-form").addEventListener("submit", login);