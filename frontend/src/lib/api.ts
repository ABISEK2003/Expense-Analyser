function getApiBase(): string {
  if (process.env.NEXT_PUBLIC_API_URL) return process.env.NEXT_PUBLIC_API_URL;
  if (typeof window === "undefined") return "http://localhost:8000";
  return `${window.location.protocol}//${window.location.hostname}:8000`;
}
const API_BASE = getApiBase();

export async function analyzeStatement(file: File): Promise<Blob> {
  const form = new FormData();
  form.append("file", file);

  const res = await fetch(`${API_BASE}/api/analyze`, { method: "POST", body: form });

  if (!res.ok) {
    let msg = `Server error ${res.status}`;
    try {
      const json = await res.json();
      msg = json.detail ?? msg;
    } catch {
      // ignore parse error
    }
    throw new Error(msg);
  }

  return res.blob();
}
