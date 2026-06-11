// Inject tagline below the app name on the welcome screen
(function () {
  const TAGLINE = "Verken (open) onderwijsdata — zie waar jouw instelling staat t.o.v. regio en Nederland";
  const TAGLINE_ID = "cl-tagline";

  function injectTagline() {
    if (document.getElementById(TAGLINE_ID)) return;
    const heading = document.querySelector("h1, h2");
    if (!heading) return;
    const el = document.createElement("p");
    el.id = TAGLINE_ID;
    el.textContent = TAGLINE;
    el.style.cssText = "margin:4px 0 0;font-size:0.95rem;opacity:0.65;text-align:center;";
    heading.insertAdjacentElement("afterend", el);
  }

  const observer = new MutationObserver(injectTagline);
  observer.observe(document.body, { childList: true, subtree: true });
  injectTagline();
})();

window.addEventListener("message", function (event) {
  const data = event.data;
  if (!data || data.type !== "set_input" || !data.value) return;

  const textarea = document.querySelector("textarea");
  if (!textarea) return;

  // React tracks the internal value via a native property descriptor;
  // a plain assignment to .value won't trigger a React state update.
  const nativeSetter = Object.getOwnPropertyDescriptor(
    HTMLTextAreaElement.prototype,
    "value"
  ).set;
  nativeSetter.call(textarea, data.value);
  textarea.dispatchEvent(new Event("input", { bubbles: true }));
  textarea.focus();
});
