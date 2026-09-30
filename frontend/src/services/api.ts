export type Attachment = {
  id: string;
  conversation_id: string;
  message_id?: number | null;
  filename: string;
  content_type: string;
  size_bytes: number;
  page_count?: number;
  is_image?: boolean;
  created_at: string;
  progress?: number;
  uploading?: boolean;
  error?: string;
};

export type WebSearchResult = {
  title: string;
  url: string;
  snippet: string;
};

export type Message = {
  id: number;
  role: "user" | "assistant";
  content: string;
  status: string;
  model?: string;
  attachments?: Attachment[];
  sources?: WebSearchResult[];
  web_search?: boolean;
  created_at?: string;
};

export type Conversation = {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
  messages?: Message[];
  pending_attachments?: Attachment[];
};

export async function uploadAttachment(
  cid: string,
  file: File,
  onProgress?: (percent: number) => void,
): Promise<Attachment> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    const formData = new FormData();
    formData.append("file", file);

    xhr.open("POST", `/api/conversations/${cid}/attachments`);

    if (xhr.upload && onProgress) {
      xhr.upload.onprogress = (e) => {
        if (e.lengthComputable) {
          onProgress(Math.round((e.loaded / e.total) * 100));
        }
      };
    }

    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        try {
          resolve(JSON.parse(xhr.responseText));
        } catch {
          reject(new Error("Invalid server response format."));
        }
      } else {
        try {
          const err = JSON.parse(xhr.responseText);
          reject(new Error(err.detail || "Upload failed."));
        } catch {
          reject(new Error(`Upload failed with status ${xhr.status}.`));
        }
      }
    };

    xhr.onerror = () => reject(new Error("Network error during file upload."));
    xhr.send(formData);
  });
}

export async function deleteAttachment(
  cid: string,
  attachmentId: string,
): Promise<void> {
  await api(`/conversations/${cid}/attachments/${attachmentId}`, {
    method: "DELETE",
  });
}

export async function api<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  let response: Response;
  try {
    const isFormData = options.body instanceof FormData;
    response = await fetch("/api" + path, {
      ...options,
      headers: isFormData
        ? options.headers
        : { "Content-Type": "application/json", ...options.headers },
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
    const data = await response.json().catch(() => ({}));
    throw new Error(
      typeof data.detail === "string" ? data.detail : "Unable to send message.",
    );
  }

  if (!response.body) {
    throw new Error("Streaming is unavailable in this browser.");
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let doneEvent = false;

  try {
    while (true) {
      const { value, done } = await reader.read();
      if (value) {
        buffer += decoder.decode(value, { stream: !done });
      }
      if (done) {
        buffer += decoder.decode();
      }

      const frames = buffer.split(/\r?\n\r?\n/);
      buffer = frames.pop() || "";

      for (const frame of frames) {
        const trimmed = frame.trim();
        if (trimmed.startsWith("data: ")) {
          try {
            const event = JSON.parse(trimmed.slice(6));
            if (event.type === "done") {
              doneEvent = true;
            }
            receive(event);
          } catch {
            // Ignore incomplete frames or heartbeat comments
          }
        }
      }

      if (done) break;
    }

    // Do not throw an interruption error if the user deliberately aborted
    if (!doneEvent && !signal.aborted) {
      throw new Error(
        "Connection interrupted. Your saved response is available; try regenerating.",
      );
    }
  } finally {
    reader.releaseLock();
  }
}
