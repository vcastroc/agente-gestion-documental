document.querySelectorAll(".alert").forEach((alert) => {
  setTimeout(() => alert.remove(), 5000);
});

(() => {
  const bot = document.querySelector(".recruitbot");
  if (!bot) return;

  const toggle = bot.querySelector(".recruitbot-toggle");
  const close = bot.querySelector(".recruitbot-close");
  const messages = bot.querySelector(".recruitbot-messages");
  const form = bot.querySelector(".recruitbot-form");
  const input = form.querySelector("input[name='message']");
  const quickButtons = bot.querySelectorAll(".recruitbot-quick button");
  const csrf = bot.dataset.csrf;
  const storageKey = "recruitbot-history";
  const initial = "Hola, soy RecruitBot. Puedo ayudarte a consultar candidatos, vacantes, rankings, entrevistas y decisiones del agente.";
  const history = JSON.parse(sessionStorage.getItem(storageKey) || "[]");

  if (!history.length) {
    history.push({ role: "bot", content: initial });
  }

  function render() {
    messages.innerHTML = "";
    history.forEach((item) => {
      const bubble = document.createElement("div");
      bubble.className = `recruitbot-msg ${item.role === "user" ? "user" : "bot"}`;
      bubble.textContent = item.content;
      messages.appendChild(bubble);
    });
    messages.scrollTop = messages.scrollHeight;
    sessionStorage.setItem(storageKey, JSON.stringify(history.slice(-20)));
  }

  async function sendMessage(text) {
    const message = text.trim();
    if (!message) return;
    history.push({ role: "user", content: message });
    render();
    input.value = "";
    bot.classList.add("typing");
    try {
      const response = await fetch("/chatbot", {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-CSRFToken": csrf },
        body: JSON.stringify({ message, _csrf_token: csrf }),
      });
      const data = await response.json();
      history.push({ role: "bot", content: data.answer || data.message || "No pude generar una respuesta." });
    } catch (error) {
      history.push({ role: "bot", content: "No pude conectar con RecruitBot. Intenta nuevamente." });
    } finally {
      bot.classList.remove("typing");
      render();
    }
  }

  toggle.addEventListener("click", () => bot.classList.toggle("open"));
  close.addEventListener("click", () => bot.classList.remove("open"));
  form.addEventListener("submit", (event) => {
    event.preventDefault();
    sendMessage(input.value);
  });
  quickButtons.forEach((button) => {
    button.addEventListener("click", () => sendMessage(button.dataset.message || button.textContent));
  });
  render();
})();
