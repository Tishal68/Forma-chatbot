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
    path: "../../../work/chat-dark.png",
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
    path: "../../../work/welcome-desktop.png",
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
    path: "../../../work/chat-mobile.png",
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
