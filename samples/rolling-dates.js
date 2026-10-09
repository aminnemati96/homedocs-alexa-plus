// Fills in every <span data-days="N" data-format="..."> with the date N days from
// today, so the sample documents always have dates in the near future. Make PDFs or
// screenshots from these pages on the day you use them.
//   data-format: "long" (October 28, 2026, the default), "short" (Oct 28, 2026),
//                "iso" (2026-10-28), "month" (September 2026)
(function () {
  const today = new Date();
  today.setHours(12, 0, 0, 0);
  const pad = (n) => String(n).padStart(2, "0");
  document.querySelectorAll("[data-days]").forEach((el) => {
    const d = new Date(today);
    d.setDate(d.getDate() + Number(el.dataset.days));
    const format = el.dataset.format || "long";
    if (format === "iso") {
      el.textContent = `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
    } else if (format === "month") {
      el.textContent = d.toLocaleString("en-US", { month: "long", year: "numeric" });
    } else {
      const month = d.toLocaleString("en-US", { month: format === "short" ? "short" : "long" });
      el.textContent = `${month} ${d.getDate()}, ${d.getFullYear()}`;
    }
  });
})();
