"use strict";

// Keep select values as the form's data model; all visible interaction is custom.
(() => {
  const refreshers = [];
  let dismiss = null;
  document.querySelectorAll("select").forEach(select => {
    const label = document.querySelector(`label[for="${select.id}"]`);
    const button = document.createElement("button");
    button.type = "button";
    button.id = `${select.id}-trigger`;
    button.className = "select-trigger";
    button.setAttribute("role", "combobox");
    button.setAttribute("aria-haspopup", "listbox");
    button.setAttribute("aria-expanded", "false");
    const value = document.createElement("span");
    const chevron = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    chevron.setAttribute("class", "select-chevron");
    chevron.setAttribute("viewBox", "0 0 24 24");
    chevron.setAttribute("aria-hidden", "true");
    chevron.setAttribute("focusable", "false");
    const glyph = document.createElementNS("http://www.w3.org/2000/svg", "use");
    glyph.setAttribute("href", "/icons.svg#chevrondown");
    chevron.append(glyph);
    button.append(value, chevron);
    if (label) {
      label.htmlFor = button.id;
      label.id ||= `${select.id}-label`;
      button.setAttribute("aria-labelledby", `${label.id} ${button.id}-value`);
    }
    value.id = `${button.id}-value`;
    select.hidden = true;
    select.after(button);

    const menu = document.createElement("div");
    menu.className = "select-menu";
    menu.id = `${select.id}-options`;
    menu.setAttribute("role", "listbox");
    menu.setAttribute("aria-label", label?.textContent.trim() || "Pilihan");
    menu.hidden = true;
    document.body.append(menu);
    button.setAttribute("aria-controls", menu.id);
    let active = 0;
    const options = [...select.options].map((option, index) => {
      const row = document.createElement("div");
      row.id = `${menu.id}-${index}`;
      row.className = "select-option";
      row.setAttribute("role", "option");
      const text = document.createElement("span");
      text.textContent = option.text;
      const tick = document.createElement("span");
      tick.className = "select-tick";
      tick.textContent = "✓";
      tick.setAttribute("aria-hidden", "true");
      row.append(text, tick);
      row.addEventListener("pointerdown", event => event.preventDefault());
      row.addEventListener("click", () => choose(index));
      menu.append(row);
      return row;
    });
    function refresh() {
      value.textContent = select.selectedOptions[0]?.text || "";
      options.forEach((row, index) => row.setAttribute("aria-selected", String(index === select.selectedIndex)));
    }
    function highlight(index) {
      active = Math.max(0, Math.min(index, options.length - 1));
      options.forEach((row, i) => row.classList.toggle("is-active", i === active));
      button.setAttribute("aria-activedescendant", options[active].id);
      options[active].scrollIntoView({block: "nearest"});
    }
    function close() {
      menu.hidden = true;
      button.setAttribute("aria-expanded", "false");
      button.removeAttribute("aria-activedescendant");
      if (dismiss === close) dismiss = null;
    }
    function open() {
      dismiss?.();
      refresh();
      menu.hidden = false;
      const rect = button.getBoundingClientRect();
      const width = Math.min(Math.max(rect.width, select.id === "speed" ? 116 : 180), innerWidth - 16);
      menu.style.width = `${width}px`;
      menu.style.left = `${Math.max(8, Math.min(rect.left, innerWidth - width - 8))}px`;
      const height = menu.offsetHeight;
      menu.style.top = `${rect.bottom + height + 6 <= innerHeight ? rect.bottom + 6 : Math.max(8, rect.top - height - 6)}px`;
      button.setAttribute("aria-expanded", "true");
      dismiss = close;
      highlight(select.selectedIndex);
    }
    function choose(index) {
      select.selectedIndex = index;
      refresh();
      close();
      select.dispatchEvent(new Event("input", {bubbles: true}));
      select.dispatchEvent(new Event("change", {bubbles: true}));
      button.focus({preventScroll: true});
    }
    button.addEventListener("click", () => menu.hidden ? open() : close());
    button.addEventListener("keydown", event => {
      if (event.key === "Tab") { close(); return; }
      if (event.key === "Escape") {
        if (!menu.hidden) { event.preventDefault(); event.stopPropagation(); close(); }
        return;
      }
      if (["ArrowDown", "ArrowUp", "Home", "End", "Enter", " "].includes(event.key)) {
        event.preventDefault();
        if (menu.hidden) { open(); return; }
        if (event.key === "Enter" || event.key === " ") choose(active);
        else highlight(event.key === "Home" ? 0 : event.key === "End" ? options.length - 1 : active + (event.key === "ArrowDown" ? 1 : -1));
      } else if (event.key.length === 1 && !event.ctrlKey && !event.metaKey) {
        const index = [...select.options].findIndex(option => option.text.toLowerCase().startsWith(event.key.toLowerCase()));
        if (index >= 0) { event.preventDefault(); if (menu.hidden) open(); highlight(index); }
      }
    });
    button.addEventListener("blur", close);
    document.addEventListener("pointerdown", event => {
      if (!button.contains(event.target) && !menu.contains(event.target)) close();
    });
    select.addEventListener("change", refresh);
    refreshers.push(refresh);
    refresh();
  });
  window.refreshDropdowns = () => refreshers.forEach(refresh => refresh());
  window.addEventListener("resize", () => dismiss?.());
  document.addEventListener("scroll", event => {
    if (!event.target.closest?.(".select-menu")) dismiss?.();
  }, true);
})();
