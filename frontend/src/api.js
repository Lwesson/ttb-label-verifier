export async function verifyLabel(imageFiles, expected) {
  const form = new FormData();
  for (const f of imageFiles) form.append("images", f);
  for (const [key, value] of Object.entries(expected)) {
    if (value !== null && value !== undefined && value !== "") {
      form.append(key, value);
    }
  }
  let res;
  try {
    res = await fetch("/api/verify", { method: "POST", body: form });
  } catch {
    throw new Error("Could not reach the server. Check your connection and try again.");
  }
  const body = await res.json().catch(() => null);
  if (!res.ok) {
    throw new Error(
      body && body.detail ? body.detail : "Something went wrong. Please try again."
    );
  }
  return body;
}
