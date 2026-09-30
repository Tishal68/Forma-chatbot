import { test, expect } from "@playwright/test";
test("local Ollama chat, context, persistence, actions, themes and mobile", async ({
  page,
  context,
}) => {
  const chatTitle = "Cedar verification " + Date.now();
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await context.grantPermissions(["clipboard-read", "clipboard-write"]);
  await page.goto("/");
  await expect(
    page.getByRole("heading", { name: "How can I help you today?" }),
  ).toBeVisible();
  await page
    .getByRole("combobox", { name: "Select model", exact: true })
    .selectOption("llama3.2:latest");
  await page.getByRole("button", { name: "Write some code" }).click();
  await expect(
    page.getByRole("textbox", { name: "Message Forma" }),
  ).toHaveValue(/Help me write/);
  await page
    .getByRole("textbox", { name: "Message Forma" })
    .fill(
      "Remember this: my project codename is Cedar. Reply with one Python fenced code block that prints Cedar.",
    );
  await page.getByRole("button", { name: "Send message", exact: true }).click();
  await expect(
    page.getByRole("button", { name: "Stop generation" }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Regenerate response" }),
  ).toBeVisible({ timeout: 150000 });
  await expect(page.locator(".code-block")).toBeVisible();
  await page.getByRole("button", { name: "Copy code", exact: true }).click();
  await expect
    .poll(() => page.evaluate(() => navigator.clipboard.readText()))
    .toContain("Cedar");
  await page
    .getByRole("textbox", { name: "Message Forma" })
    .fill("What is my project codename? Answer with just the name.");
  await page.getByRole("button", { name: "Send message", exact: true }).click();
  await expect(
    page.getByRole("button", { name: "Regenerate response" }),
  ).toBeVisible({ timeout: 150000 });
  await expect(page.locator("article.assistant").last()).toContainText("Cedar");
  await page.getByRole("button", { name: "Regenerate response" }).click();
  await expect(
    page.getByRole("button", { name: "Regenerate response" }),
  ).toBeVisible({ timeout: 150000 });
  await expect(page.locator("article.user")).toHaveCount(2);
  await page.reload();
  // The last active chat should reopen without a sidebar click.
  await expect(page.locator("article.user")).toHaveCount(2);
  await expect(page.locator("article.assistant").last()).toContainText("Cedar");

  await page.locator(".chat-row").first().hover();
  await page.getByRole("button", { name: /Rename Remember/ }).click();
  await page
    .getByRole("textbox", { name: "Conversation title" })
    .fill(chatTitle);
  await page.getByRole("button", { name: "Save", exact: true }).click();
  await expect(
    page.getByRole("button", { name: chatTitle, exact: true }),
  ).toBeVisible();
  await page
    .getByRole("textbox", { name: "Search conversations" })
    .fill("Cedar");
  await expect(
    page.getByRole("button", { name: chatTitle, exact: true }),
  ).toBeVisible();
  await page.getByRole("textbox", { name: "Search conversations" }).fill("");
  await page.getByRole("button", { name: "Settings", exact: false }).click();
  await page
    .getByRole("combobox", { name: "Theme", exact: true })
    .selectOption("dark");
  await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
  await page.getByRole("button", { name: "Close settings" }).click();
  await page.screenshot({
    path: "test-results/chat-dark.png",
    fullPage: true,
  });
  await page.getByRole("button", { name: "Settings", exact: false }).click();
  await page
    .getByRole("combobox", { name: "Theme", exact: true })
    .selectOption("light");
  await page.getByRole("button", { name: "Close settings" }).click();
  await page.getByRole("button", { name: "Start new chat", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "How can I help you today?" }),
  ).toBeVisible();
  await page.screenshot({
    path: "test-results/welcome-desktop.png",
    fullPage: true,
  });
  await page
    .getByRole("textbox", { name: "Message Forma" })
    .fill(
      "Write a very long detailed tutorial about Python with many examples.",
    );
  await page.getByRole("button", { name: "Send message", exact: true }).click();
  await expect(page.locator("article.assistant .message-body")).toContainText(
    /\w+/,
    { timeout: 150000 },
  );
  await page.getByRole("button", { name: "Stop generation" }).click();
  await expect(page.getByText("Response stopped", { exact: true })).toBeVisible(
    { timeout: 15000 },
  );
  await page.setViewportSize({ width: 390, height: 844 });
  await page.getByRole("button", { name: "Collapse sidebar" }).click();
  await page.screenshot({
    path: "test-results/chat-mobile.png",
    fullPage: true,
  });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  await page.getByRole("button", { name: "Open sidebar" }).click();
  await page
    .getByRole("button", { name: chatTitle, exact: true })
    .click();
  await expect(page.locator("article.user")).toHaveCount(2);
  await page.getByRole("button", { name: "Open sidebar" }).click();

  await page
    .getByRole("button", { name: "Delete " + chatTitle, exact: true })
    .click();
  await page.getByRole("button", { name: "Confirm", exact: true }).click();
  await expect(
    page.getByRole("button", { name: chatTitle, exact: true }),
  ).toHaveCount(0);
  expect(errors).toEqual([]);
});

test("functional controls: attachments, web search toggle, header rename, and settings", async ({
  page,
}) => {
  await page.goto("/");

  // Test Web Search toggle button
  const webSearchBtn = page.locator('button[aria-label*="Web search"]');
  await expect(webSearchBtn).toBeVisible();
  await expect(webSearchBtn).toHaveAttribute("aria-label", /Disabled/);

  // Toggle ON
  await webSearchBtn.click();
  await expect(webSearchBtn).toHaveAttribute("aria-label", /Enabled/);
  await expect(webSearchBtn).toHaveClass(/active/);

  // Toggle OFF
  await webSearchBtn.click();
  await expect(webSearchBtn).toHaveAttribute("aria-label", /Disabled/);

  // Test File Attachment and Remove action before sending
  const fileInput = page.locator('input[type="file"]');
  await fileInput.setInputFiles({
    name: "test_script.py",
    mimeType: "text/x-python",
    buffer: Buffer.from('def add(a, b):\n    return a + b\n'),
  });

  // Chip should appear in the composer tray
  const chip = page.locator(".attachment-chip");
  await expect(chip).toBeVisible();
  await expect(chip).toContainText("test_script.py");

  // Remove attachment before sending
  const removeBtn = chip.locator(".attachment-remove");
  await removeBtn.click();
  await expect(page.locator(".attachment-chip")).toHaveCount(0);

  // Test Settings / Parameters button in composer
  const paramsBtn = page.getByRole("button", { name: "Adjust parameters & settings" });
  await expect(paramsBtn).toBeVisible();
  await paramsBtn.click();

  // Settings dialog opens
  const settingsModal = page.locator("dialog[open]");
  await expect(settingsModal).toBeVisible();
  await expect(page.getByRole("slider", { name: "Temperature" })).toBeVisible();
  await page.getByRole("button", { name: "Close settings" }).click();
  await expect(page.locator("dialog[open]")).toHaveCount(0);
});

test("send message with attachment and render attachment badge in chat", async ({
  page,
}) => {
  await page.addInitScript(() => {
    localStorage.setItem("forma-provider", "ollama");
    localStorage.setItem("forma-model-ollama", "llama3.2");
    localStorage.setItem("forma-model", "llama3.2");
  });

  await page.goto("/");

  // Upload an attachment
  const fileInput = page.locator('input[type="file"]');
  await fileInput.setInputFiles({
    name: "calculator.py",
    mimeType: "text/x-python",
    buffer: Buffer.from('def divide(a, b):\n    return a / b  # bug: no zero check\n'),
  });

  const chip = page.locator(".attachment-chip");
  await expect(chip).toBeVisible();
  await expect(chip).toContainText("calculator.py");

  // Wait for upload to complete (remove button appears when upload finishes)
  await expect(chip.locator(".attachment-remove")).toBeVisible();

  // Enter prompt
  const input = page.getByRole("textbox", { name: "Message Forma" });
  await input.fill("Explain the bug in this uploaded code");

  // Mock chat stream so test doesn't depend on external model response
  await page.route("/api/chat", async (route) => {
    const sse = [
      'data: {"type": "start", "message_id": 9999}\n\n',
      'data: {"type": "token", "content": "The bug in `calculator.py` is division by zero."}\n\n',
      'data: {"type": "done", "status": "complete"}\n\n',
    ].join("");
    await route.fulfill({
      status: 200,
      contentType: "text/event-stream",
      body: sse,
    });
  });

  await page.route("**/api/conversations/*", async (route) => {
    if (route.request().method() === "GET") {
      const response = await route.fetch();
      const json = await response.json();
      if (!json.messages || json.messages.length === 0) {
        json.messages = [
          {
            id: 1001,
            role: "user",
            content: "Explain the bug in this uploaded code",
            status: "complete",
            created_at: new Date().toISOString(),
            attachments: [
              {
                id: "att-1",
                conversation_id: json.id,
                filename: "calculator.py",
                content_type: "text/x-python",
                size_bytes: 50,
                created_at: new Date().toISOString(),
              },
            ],
          },
          {
            id: 1002,
            role: "assistant",
            content: "The bug in `calculator.py` is division by zero.",
            status: "complete",
            created_at: new Date().toISOString(),
          },
        ];
      }
      await route.fulfill({ json });
    } else {
      await route.continue();
    }
  });

  const sendBtn = page.locator('button[type="submit"].primary-send');
  await expect(sendBtn).toBeEnabled();
  await sendBtn.click();

  // Verify the user message rendered with attachment chip
  const attInMsg = page.locator(".message-attachment-item");
  await expect(attInMsg).toBeVisible();
  await expect(attInMsg).toContainText("calculator.py");

  // Verify assistant response received
  const assistantMsg = page.locator("article.assistant");
  await expect(assistantMsg).toBeVisible();
  await expect(assistantMsg).toContainText("division by zero");
});


