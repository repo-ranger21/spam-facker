export async function onRequestPost(context) {
  const apiKey = context.env.ANTHROPIC_API_KEY;
  if (!apiKey) return new Response("Missing API key", { status: 500 });
  const body = await context.request.json();
  const allowed = ["claude-sonnet-4-5","claude-3-5-sonnet-20241022","claude-3-5-haiku-20241022"];
  if (!allowed.includes(body.model)) return new Response("Model not allowed", { status: 400 });
  if ((body.max_tokens || 0) > 1024) body.max_tokens = 1024;
  const resp = await fetch("https://api.anthropic.com/v1/messages", {
    method: "POST",
    headers: { "Content-Type": "application/json", "x-api-key": apiKey, "anthropic-version": "2023-06-01" },
    body: JSON.stringify(body)
  });
  const data = await resp.json();
  return new Response(JSON.stringify(data), {
    status: resp.status,
    headers: { "Content-Type": "application/json", "Access-Control-Allow-Origin": "*" }
  });
}
