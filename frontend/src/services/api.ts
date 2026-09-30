export type Message = {
  id: number;
  role: "user" | "assistant";
  content: string;
  status: string;
  model?: string;
};
export type Conversation = {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
  messages?: Message[];
};
export async function api<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  let response: Response;
  try {
    response = await fetch("/api" + path, {
      ...options,
      headers: { "Content-Type": "application/json", ...options.headers },
    });
  } catch {
    throw new Error(
      "Cannot reach the backend. Make sure the application server is running.",
    );
  }
  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    throw new Error(
      typeof data.detail === "string"
        ? data.detail
        : "The request could not be completed. Please try again.",
    );
  }
  return response.json();
}
export async function streamChat(
  body: unknown,
  signal: AbortSignal,
  receive: (event: any) => void,
) {
  const response = await fetch("/api/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    signal,
  });
  if (!response.ok) {
    const data = await response.json();
    throw new Error(
      typeof data.detail === "string" ? data.detail : "Unable to send message.",
    );
  }
  if (!response.body)
    throw new Error("Streaming is unavailable in this browser.");
  const reader = response.body.getReader(),
    decoder = new TextDecoder();
  let buffer = "",
    doneEvent = false;
  try {
    while (true) {
      const { value, done } = await reader.read();
      buffer += decoder.decode(value, { stream: !done });
      const frames = buffer.split("\n\n");
      buffer = frames.pop()!;
      for (const frame of frames) {
        if (frame.startsWith("data: ")) {
          const event = JSON.parse(frame.slice(6));
          if (event.type === "done") doneEvent = true;
          receive(event);
        }
      }
      if (done) break;
    }
    if (!doneEvent)
      throw new Error(
        "Connection interrupted. Your saved response is available; try regenerating.",
      );
  } finally {
    reader.releaseLock();
  }
}
