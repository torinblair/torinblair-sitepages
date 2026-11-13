// Keyboard navigation and present mode for /talks/<deck>/<n> slide pages.
(function () {
  var deck = document.querySelector("[data-deck]");
  if (!deck) return;

  var root = document.documentElement;
  var button = deck.querySelector("[data-present]");

  function store(on) {
    try {
      if (on) sessionStorage.setItem("deck-present", "1");
      else sessionStorage.removeItem("deck-present");
    } catch (e) {}
  }

  function setPresenting(on) {
    root.classList.toggle("presenting", on);
    if (button) {
      button.setAttribute("aria-pressed", on ? "true" : "false");
      button.textContent = on ? "Exit" : "Present";
    }
    store(on);
  }

  function go(rel) {
    var link = deck.querySelector('a[rel="' + rel + '"]');
    if (link) window.location.href = link.href;
  }

  setPresenting(root.classList.contains("presenting"));
  if (button) {
    button.addEventListener("click", function () {
      setPresenting(!root.classList.contains("presenting"));
    });
  }

  document.addEventListener("keydown", function (e) {
    if (e.altKey || e.ctrlKey || e.metaKey) return;
    var t = e.target;
    if (t && (t.isContentEditable || /^(INPUT|TEXTAREA|SELECT)$/.test(t.tagName))) return;

    switch (e.key) {
      case "ArrowRight":
      case "PageDown":
      case " ":
        if (e.key === " " && e.shiftKey) go("prev");
        else go("next");
        break;
      case "ArrowLeft":
      case "PageUp":
        go("prev");
        break;
      case "Home":
        window.location.href = deck.dataset.first;
        break;
      case "End":
        window.location.href = deck.dataset.last;
        break;
      case "p":
      case "P":
        setPresenting(!root.classList.contains("presenting"));
        break;
      case "Escape":
        if (root.classList.contains("presenting")) setPresenting(false);
        else window.location.href = deck.dataset.overview;
        break;
      default:
        return;
    }
    e.preventDefault();
  });
})();
