// JSON that goes inside an inline <script>: a '<' in a label must not close the element
// ('</script') or open a comment ('<!--'). Inside a JSON string the escape is the same
// character, so the parsed value does not change.
export const scriptSafe = json => json.replace(/</g, '\\u003c')
