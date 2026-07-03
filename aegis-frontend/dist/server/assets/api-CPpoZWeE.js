//#region src/lib/api.ts
var EFFECTIVE_BASE = "http://localhost:8000";
var ApiError = class extends Error {
	status;
	body;
	constructor(status, message, body) {
		super(message);
		this.status = status;
		this.body = body;
	}
};
async function api(path, init = {}) {
	const res = await fetch(`${EFFECTIVE_BASE}${path}`, {
		...init,
		headers: {
			"Content-Type": "application/json",
			...init.headers ?? {}
		}
	});
	const text = await res.text();
	const body = text ? safeJson(text) : void 0;
	if (!res.ok) throw new ApiError(res.status, `${res.status} ${res.statusText}`, body);
	return body;
}
/**
* Upload a FormData payload. Does not override Content-Type so the browser
* can set multipart boundaries correctly.
*/
async function formUpload(path, form) {
	const url = `${EFFECTIVE_BASE}${path}`;
	console.log("formUpload: POST", url);
	try {
		const res = await fetch(url, {
			method: "POST",
			body: form
		});
		console.log("formUpload: response status", res.status);
		const text = await res.text();
		const body = text ? safeJson(text) : void 0;
		if (!res.ok) {
			console.error("formUpload: response error", res.status, body);
			throw new ApiError(res.status, `${res.status} ${res.statusText}`, body);
		}
		return body;
	} catch (err) {
		console.error("formUpload: fetch error", err);
		throw err;
	}
}
var apiUrl = (path) => `${EFFECTIVE_BASE}${path}`;
function safeJson(text) {
	try {
		return JSON.parse(text);
	} catch {
		return text;
	}
}
//#endregion
export { apiUrl as n, formUpload as r, api as t };
