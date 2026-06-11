const TAGLINE = "Verken (open) onderwijsdata — zie waar jouw instelling staat t.o.v. regio en Nederland";
const TAGLINE_ID = "cl-tagline";

function injectTagline() {
  if (document.getElementById(TAGLINE_ID)) return;
  const logo = document.querySelector("img[src*='logo']");
  if (!logo) return;
  const el = document.createElement("p");
  el.id = TAGLINE_ID;
  el.textContent = TAGLINE;
  el.style.cssText = "margin:8px auto 0;font-size:1.1rem;color:#6b7280;text-align:center;max-width:600px;line-height:1.4;";
  logo.parentNode.insertBefore(el, logo.nextSibling);
}

const observer = new MutationObserver(injectTagline);
observer.observe(document.body, { childList: true, subtree: true });
injectTagline();

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
