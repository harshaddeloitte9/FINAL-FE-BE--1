/**
 * Thin HTTP client for the FastAPI backend (see `backend/api/`).
 *
 * The Aegis UI now renders from FastAPI endpoints only.
 */
const BASE_URL = import.meta.env.VITE_API_URL ?? "";
// Default to local backend during development when VITE_API_URL is not set
const EFFECTIVE_BASE = BASE_URL || "http://localhost:8000";

export class ApiError extends Error {
  constructor(public status: number, message: string, public body?: unknown) {
    super(message);
  }
}

export async function api<T = unknown>(
  path: string,
  init: RequestInit = {},
): Promise<T> {
  const res = await fetch(`${EFFECTIVE_BASE}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init.headers ?? {}),
    },
  });
  const text = await res.text();
  const body = text ? safeJson(text) : undefined;
  if (!res.ok) {
    throw new ApiError(res.status, `${res.status} ${res.statusText}`, body);
  }
  return body as T;
}

/**
 * Upload a FormData payload. Does not override Content-Type so the browser
 * can set multipart boundaries correctly.
 */
export async function formUpload<T = unknown>(path: string, form: FormData): Promise<T> {
  const url = `${EFFECTIVE_BASE}${path}`;
  console.log("formUpload: POST", url);
  console.log("VITE_API_URL =", import.meta.env.VITE_API_URL);
  console.log("EFFECTIVE_BASE =", EFFECTIVE_BASE);
  try {
    const res = await fetch(url, {
      method: "POST",
      body: form,
    });
    console.log("formUpload: response status", res.status);
    const text = await res.text();
    const body = text ? safeJson(text) : undefined;
    if (!res.ok) {
      console.error("formUpload: response error", res.status, body);
      throw new ApiError(res.status, `${res.status} ${res.statusText}`, body);
    }
    return body as T;
  } catch (err) {
    console.error("formUpload: fetch error", err);
    throw err;
  }
}

export const apiUrl = (path: string) => `${EFFECTIVE_BASE}${path}`;

function safeJson(text: string): unknown {
  try {
    return JSON.parse(text);
  } catch {
    return text;
  }
}