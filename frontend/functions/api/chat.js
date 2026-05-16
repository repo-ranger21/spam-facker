const CORS_HEADERS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Methods": "POST, OPTIONS",
  "Access-Control-Allow-Headers": "Content-Type",
};

export async function onRequestOptions() {
  return new Response(null, { status: 204, headers: CORS_HEADERS });
}

export async function onRequestPost(context) {
  try {
    const apiKey = context.env.ANTHROPIC_API_KEY;
    if (!apiKey) return new Response(
      JSON.stringify({ error: "Missing API key" }),
      { status: 500, headers: { "Content-Type": "application/json", ...CORS_HEADERS } }
    );

    let body;
    try {
      body = await context.request.json();
    } catch {
      return new Response(
        JSON.stringify({ error: "Request body must be valid JSON." }),
        { status: 400, headers: { "Content-Type": "application/json", ...CORS_HEADERS } }
      );
    }

    const allowed = ["claude-sonnet-4-5-20251001", "claude-3-5-sonnet-20241022", "claude-3-5-haiku-20241022"];
    if (!allowed.includes(body.model)) return new Response(
      JSON.stringify({ error: "Model not allowed" }),
      { status: 400, headers: { "Content-Type": "application/json", ...CORS_HEADERS } }
    );

    if ((body.max_tokens || 0) > 1024) body.max_tokens = 1024;

    const resp = await fetch("https://api.anthropic.com/v1/messages", {
      method: "POST",
      headers: { "Content-Type": "application/json", "x-api-key": apiKey, "anthropic-version": "2023-06-01" },
      body: JSON.stringify(body)
    });

    const data = await resp.json();
    return new Response(JSON.stringify(data), {
      status: resp.status,
      headers: { "Content-Type": "application/json", ...CORS_HEADERS }
    });
  } catch (err) {
    return new Response(
      JSON.stringify({ error: "Internal server error", detail: err.message }),
      { status: 500, headers: { "Content-Type": "application/json", ...CORS_HEADERS } }
    );
  }
}
