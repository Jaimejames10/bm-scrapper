const form = document.querySelector("#search-form");
const input = document.querySelector("#account-code");
const identityInput = document.querySelector("#identity-document");
const button = document.querySelector("#search-button");
const feedback = document.querySelector("#feedback");
const resultsPanel = document.querySelector("#results-panel");
const resultsList = document.querySelector("#results-list");
const resultCount = document.querySelector("#result-count");

const fieldLabels = [
    ["username", "Usuario"],
    ["account_code", "Código de cuenta"],
    ["contract_number", "Número de comprobante"],
    ["contract_date", "Fecha de comprobante"],
];

function showFeedback(message, kind = "info") {
    feedback.hidden = false;
    feedback.className = `feedback feedback-${kind}`;
    feedback.textContent = message;
}

function clearFeedback() {
    feedback.hidden = true;
    feedback.textContent = "";
    feedback.className = "feedback";
}

function setLoading(isLoading) {
    button.disabled = isLoading;
    button.classList.toggle("is-loading", isLoading);
    button.querySelector(".button-label").textContent = isLoading
        ? "Consultando..."
        : "Buscar usuario";
}

function formatApiError(detail) {
    if (typeof detail === "string") {
        return detail;
    }
    if (Array.isArray(detail)) {
        return detail.map((item) => item.msg || item.message || String(item)).join(" ");
    }
    if (detail && typeof detail === "object") {
        return detail.message || JSON.stringify(detail);
    }
    return "No fue posible completar la búsqueda.";
}

function createDetailCard(user, index) {
    const card = document.createElement("details");
    card.className = "result-card";
    card.open = false;

    const summary = document.createElement("summary");
    const summaryText = document.createElement("span");
    summaryText.textContent = user.full_name || user.username || `Resultado ${index + 1}`;
    const summaryHint = document.createElement("span");
    summaryHint.className = "summary-hint";
    summaryHint.textContent = "Ver detalle";
    summary.append(summaryText, summaryHint);
    card.appendChild(summary);

    const definitionList = document.createElement("dl");
    definitionList.className = "details-grid";

    for (const [field, label] of fieldLabels) {
        const term = document.createElement("dt");
        term.textContent = label;
        const value = document.createElement("dd");
        value.className = "detail-value";

        const text = document.createElement("span");
        const fieldValue = user[field] || "";
        text.textContent = fieldValue || "Sin información";

        const copyButton = document.createElement("button");
        copyButton.type = "button";
        copyButton.className = "copy-button";
        copyButton.textContent = "Copiar";
        copyButton.disabled = !fieldValue;
        copyButton.dataset.copyValue = fieldValue;

        value.append(text, copyButton);
        definitionList.append(term, value);
    }

    card.appendChild(definitionList);
    return card;
}

function renderResults(data) {
    resultsList.replaceChildren();
    resultCount.textContent = `${data.results.length} encontrado${data.results.length === 1 ? "" : "s"}`;

    data.results.forEach((user, index) => {
        resultsList.appendChild(createDetailCard(user, index));
    });

    resultsPanel.hidden = false;
    resultsPanel.scrollIntoView({ behavior: "smooth", block: "start" });
}

async function searchUsers(event) {
    event.preventDefault();
    const accountCode = input.value.trim();
    const identityDocument = identityInput.value.trim();

    if (!accountCode && !identityDocument) {
        input.focus();
        showFeedback("Ingresa el código de cuenta, el documento de identidad o ambos.", "error");
        return;
    }

    clearFeedback();
    resultsPanel.hidden = true;
    setLoading(true);

    try {
        const response = await fetch("/api/search", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                account_code: accountCode || null,
                identity_document: identityDocument || null,
            }),
        });
        const data = await response.json();

        if (!response.ok) {
            throw new Error(formatApiError(data.detail));
        }

        renderResults(data);
        showFeedback("Consulta completada correctamente.", "success");
    } catch (error) {
        resultsList.replaceChildren();
        resultsPanel.hidden = true;
        showFeedback(error.message || "Ocurrió un error inesperado.", "error");
    } finally {
        setLoading(false);
    }
}

form.addEventListener("submit", searchUsers);

async function copyText(text) {
    if (navigator.clipboard?.writeText) {
        await navigator.clipboard.writeText(text);
        return;
    }

    const helper = document.createElement("textarea");
    helper.value = text;
    helper.setAttribute("readonly", "");
    helper.style.position = "fixed";
    helper.style.opacity = "0";
    document.body.appendChild(helper);
    helper.select();
    const copied = document.execCommand("copy");
    helper.remove();

    if (!copied) {
        throw new Error("No fue posible copiar el dato.");
    }
}

resultsList.addEventListener("click", async (event) => {
    const copyButton = event.target.closest(".copy-button");
    if (!copyButton || copyButton.disabled) {
        return;
    }

    try {
        await copyText(copyButton.dataset.copyValue);
        copyButton.textContent = "Copiado";
        copyButton.classList.add("is-copied");
        window.setTimeout(() => {
            copyButton.textContent = "Copiar";
            copyButton.classList.remove("is-copied");
        }, 1400);
    } catch {
        showFeedback("No fue posible copiar el dato.", "error");
    }
});
