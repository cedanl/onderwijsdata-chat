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
