/**
 * SkillSwap — Client-side JavaScript
 *
 * Features:
 *  1. AJAX bid submission (submit bid without full page reload)
 *  2. Live marketplace search/filter
 *  3. AJAX message send
 *  4. Character counters for textarea inputs
 *  5. Toast notifications (accessible ARIA role="status")
 *  6. Form validation feedback
 *  7. Confirm dialogs for destructive actions
 */

"use strict";

// ─── Utility: get CSRF token from cookie ────────────────────────────────────
function getCsrfToken() {
  const name = "csrftoken";
  const cookies = document.cookie.split(";");
  for (const cookie of cookies) {
    const [key, val] = cookie.trim().split("=");
    if (key === name) return decodeURIComponent(val);
  }
  return "";
}

// ─── Utility: show an accessible toast ──────────────────────────────────────
function showToast(message, type = "success") {
  const container = document.getElementById("toast-container");
  if (!container) return;

  const colourMap = {
    success: "text-bg-success",
    error:   "text-bg-danger",
    warning: "text-bg-warning",
    info:    "text-bg-info",
  };
  const role = (type === "error" || type === "warning") ? "alert" : "status";

  const el = document.createElement("div");
  el.className = `toast align-items-center ${colourMap[type] || "text-bg-secondary"} border-0 show`;
  el.setAttribute("role", role);
  el.setAttribute("aria-live", role === "alert" ? "assertive" : "polite");
  el.setAttribute("aria-atomic", "true");
  el.innerHTML = `
    <div class="d-flex">
      <div class="toast-body">${message}</div>
      <button type="button" class="btn-close btn-close-white me-2 m-auto" aria-label="Close toast"></button>
    </div>`;

  el.querySelector(".btn-close").addEventListener("click", () => el.remove());
  container.appendChild(el);
  setTimeout(() => el.remove(), 5000);
}

// ─── Character counters ──────────────────────────────────────────────────────
function initCharCounters() {
  document.querySelectorAll("textarea[maxlength], input[maxlength]").forEach((el) => {
    const max = parseInt(el.getAttribute("maxlength"), 10);
    if (!max) return;

    const counter = document.createElement("div");
    counter.className = "char-count";
    counter.setAttribute("aria-live", "polite");
    counter.setAttribute("aria-atomic", "true");
    el.parentNode.insertBefore(counter, el.nextSibling);

    const update = () => {
      const remaining = max - el.value.length;
      counter.textContent = `${el.value.length} / ${max}`;
      counter.className = "char-count" + (remaining < 20 ? " warning" : "") + (remaining < 0 ? " over" : "");
    };

    el.addEventListener("input", update);
    update();
  });
}

// ─── AJAX bid submission ─────────────────────────────────────────────────────
function initBidForm() {
  const form = document.getElementById("bid-form");
  if (!form) return;

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const btn = form.querySelector("[type=submit]");
    const spinner = btn.querySelector(".ajax-spinner");
    const url = form.action;

    // Clear previous errors
    form.querySelectorAll(".invalid-feedback").forEach((el) => (el.textContent = ""));
    form.querySelectorAll(".is-invalid").forEach((el) => el.classList.remove("is-invalid"));

    btn.disabled = true;
    if (spinner) spinner.style.display = "inline-block";

    try {
      const resp = await fetch(url, {
        method: "POST",
        headers: {
          "X-CSRFToken": getCsrfToken(),
          "X-Requested-With": "XMLHttpRequest",
        },
        body: new FormData(form),
      });
      const data = await resp.json();

      if (data.success) {
        showToast(data.is_update ? "Bid updated!" : "Bid submitted!", "success");
        // Update bid list if element exists
        const bidList = document.getElementById("bid-list");
        if (bidList) {
          appendBidRow(bidList, data);
        }
        form.reset();
        // Update bid count badge
        const bidCountEl = document.getElementById("bid-count");
        if (bidCountEl) {
          const count = parseInt(bidCountEl.textContent, 10) || 0;
          bidCountEl.textContent = data.is_update ? count : count + 1;
        }
      } else if (data.errors) {
        // Show field-level errors
        for (const [field, errs] of Object.entries(data.errors)) {
          const input = form.querySelector(`[name=${field}]`);
          if (input) {
            input.classList.add("is-invalid");
            let fb = input.nextElementSibling;
            if (!fb || !fb.classList.contains("invalid-feedback")) {
              fb = document.createElement("div");
              fb.className = "invalid-feedback";
              input.parentNode.insertBefore(fb, input.nextSibling);
            }
            fb.textContent = errs.join(" ");
          }
        }
        showToast("Please fix the errors above.", "error");
      } else if (data.error) {
        showToast(data.error, "error");
      }
    } catch (err) {
      showToast("Network error. Please try again.", "error");
    } finally {
      btn.disabled = false;
      if (spinner) spinner.style.display = "none";
    }
  });
}

function appendBidRow(container, data) {
  // Prevent duplicate row if updating
  const existing = container.querySelector(`[data-bid-id="${data.bid_id}"]`);
  if (existing) {
    existing.querySelector(".bid-hours").textContent = data.proposed_hours + "h";
    existing.querySelector(".bid-message").textContent = data.message_text;
    return;
  }
  const row = document.createElement("div");
  row.className = "d-flex justify-content-between align-items-start p-2 border-bottom";
  row.setAttribute("data-bid-id", data.bid_id);
  row.innerHTML = `
    <div>
      <strong>${escapeHtml(data.provider)}</strong>
      <p class="mb-0 text-muted small bid-message">${escapeHtml(data.message_text)}</p>
    </div>
    <span class="badge bg-warning text-dark bid-hours">${escapeHtml(data.proposed_hours)}h</span>`;
  container.appendChild(row);
}

function escapeHtml(str) {
  const d = document.createElement("div");
  d.appendChild(document.createTextNode(str));
  return d.innerHTML;
}

// ─── Live marketplace search ─────────────────────────────────────────────────
function initMarketplaceSearch() {
  const searchForm = document.getElementById("marketplace-filter");
  if (!searchForm) return;

  const resultsContainer = document.getElementById("request-list");
  const countEl = document.getElementById("result-count");
  if (!resultsContainer) return;

  let debounceTimer;

  const doSearch = async () => {
    const params = new URLSearchParams(new FormData(searchForm));
    try {
      const resp = await fetch(`?${params.toString()}`, {
        headers: { "X-Requested-With": "XMLHttpRequest" },
      });
      const data = await resp.json();
      renderResults(data.results);
      if (countEl) countEl.textContent = `${data.count} request${data.count !== 1 ? "s" : ""}`;
    } catch (err) {
      // fall back to full page reload on error
    }
  };

  searchForm.querySelectorAll("input, select").forEach((el) => {
    el.addEventListener("input", () => {
      clearTimeout(debounceTimer);
      debounceTimer = setTimeout(doSearch, 350);
    });
  });
}

function renderResults(results) {
  const container = document.getElementById("request-list");
  if (!container) return;
  if (results.length === 0) {
    container.innerHTML = '<p class="text-muted py-4 text-center">No requests match your search.</p>';
    return;
  }
  container.innerHTML = results
    .map(
      (r) => `
    <div class="ss-card request-card p-3 mb-3">
      <div class="d-flex justify-content-between align-items-start flex-wrap gap-2">
        <div>
          <h5 class="mb-1">
            <a href="${r.url}" class="text-decoration-none stretched-link">${escapeHtml(r.title)}</a>
          </h5>
          <span class="skill-tag me-2">${escapeHtml(r.skill_category)}</span>
          <small class="text-muted">by ${escapeHtml(r.requester)} · ${escapeHtml(r.created_at)}</small>
        </div>
        <div class="text-end">
          <span class="hours-badge me-2">${escapeHtml(r.hours_required)}h</span>
          <span class="bid-count">${r.bid_count} bid${r.bid_count !== 1 ? "s" : ""}</span>
        </div>
      </div>
    </div>`
    )
    .join("");
}

// ─── AJAX message send ───────────────────────────────────────────────────────
function initMessageForm() {
  const form = document.getElementById("message-form");
  if (!form) return;

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const btn = form.querySelector("[type=submit]");
    btn.disabled = true;

    try {
      const resp = await fetch(form.action, {
        method: "POST",
        headers: {
          "X-CSRFToken": getCsrfToken(),
          "X-Requested-With": "XMLHttpRequest",
        },
        body: new FormData(form),
      });
      const data = await resp.json();
      if (data.id) {
        const thread = document.getElementById("message-thread");
        if (thread) {
          const bubble = document.createElement("div");
          bubble.className = "message-bubble own";
          bubble.innerHTML = `
            <div class="d-flex justify-content-between">
              <span class="sender">${escapeHtml(data.sender)}</span>
              <span class="timestamp">${escapeHtml(data.created_at)}</span>
            </div>
            <p class="mb-0 mt-1">${escapeHtml(data.content)}</p>`;
          thread.appendChild(bubble);
          thread.scrollTop = thread.scrollHeight;
        }
        form.reset();
      }
    } catch (err) {
      showToast("Message could not be sent.", "error");
    } finally {
      btn.disabled = false;
    }
  });
}

// ─── Confirm dialogs for destructive actions ─────────────────────────────────
function initConfirmForms() {
  document.querySelectorAll("[data-confirm]").forEach((el) => {
    el.addEventListener("submit", (e) => {
      const msg = el.getAttribute("data-confirm");
      if (!confirm(msg)) e.preventDefault();
    });
    // Also handle buttons that aren't forms
    el.addEventListener("click", (e) => {
      if (el.tagName !== "FORM") {
        const msg = el.getAttribute("data-confirm");
        if (!confirm(msg)) e.preventDefault();
      }
    });
  });
}

// ─── Balance live update ─────────────────────────────────────────────────────
function initBalanceHighlight() {
  const balEl = document.querySelectorAll(".live-balance");
  if (!balEl.length) return;
  // Highlight balance when it changes (after successful exchange)
  balEl.forEach((el) => {
    el.classList.add("fw-bold");
  });
}

// ─── Bootstrap tooltips ──────────────────────────────────────────────────────
function initTooltips() {
  if (typeof bootstrap !== "undefined" && bootstrap.Tooltip) {
    document.querySelectorAll('[data-bs-toggle="tooltip"]').forEach((el) => {
      new bootstrap.Tooltip(el);
    });
  }
}

// ─── Entry point ─────────────────────────────────────────────────────────────
document.addEventListener("DOMContentLoaded", () => {
  initCharCounters();
  initBidForm();
  initMarketplaceSearch();
  initMessageForm();
  initConfirmForms();
  initBalanceHighlight();
  initTooltips();
});
