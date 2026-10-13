// dashboard.js - Client-side table search, filtering, and sorting
document.addEventListener("DOMContentLoaded", () => {
  const searchInput = document.getElementById("searchInput");
  const categoryFilter = document.getElementById("categoryFilter");
  const statusFilter = document.getElementById("statusFilter");
  const flaggedToggle = document.getElementById("flaggedToggle");
  const table = document.getElementById("matchesTable");

  if (!table) return;

  const rows = Array.from(table.querySelectorAll("tbody tr"));

  function filterTable() {
    const query = (searchInput ? searchInput.value : "").toLowerCase().trim();
    const category = categoryFilter ? categoryFilter.value : "all";
    const status = statusFilter ? statusFilter.value : "all";
    const flaggedOnly = flaggedToggle ? flaggedToggle.checked : false;

    let visibleCount = 0;

    rows.forEach(row => {
      const rowText = row.textContent.toLowerCase();
      const rowCategory = row.getAttribute("data-category") || "";
      const rowStatus = row.getAttribute("data-status") || "";
      const isFlagged = row.getAttribute("data-flagged") === "true";

      const matchesQuery = !query || rowText.includes(query);
      const matchesCategory = category === "all" || rowCategory === category;
      const matchesStatus = status === "all" || rowStatus === status;
      const matchesFlagged = !flaggedOnly || isFlagged;

      if (matchesQuery && matchesCategory && matchesStatus && matchesFlagged) {
        row.style.display = "";
        visibleCount++;
      } else {
        row.style.display = "none";
      }
    });

    const counter = document.getElementById("matchCounter");
    if (counter) {
      counter.textContent = `Showing ${visibleCount} of ${rows.length} matches`;
    }
  }

  if (searchInput) searchInput.addEventListener("input", filterTable);
  if (categoryFilter) categoryFilter.addEventListener("change", filterTable);
  if (statusFilter) statusFilter.addEventListener("change", filterTable);
  if (flaggedToggle) flaggedToggle.addEventListener("change", filterTable);

  filterTable();
});
