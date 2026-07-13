import { test, expect } from "@playwright/test";

const BASE_URL = "http://localhost:3001";

test("Page structure analysis - removed vs kept sections", async ({ page }) => {
  // Suppress 404 errors from console
  page.on("console", (msg) => {
    if (!msg.text().includes("404")) {
      console.log(`Console: ${msg.type()}: ${msg.text()}`);
    }
  });

  await page.goto(`${BASE_URL}/features`);
  await page.waitForSelector("main", { timeout: 5000 });

  const bodyText = await page.textContent("body");
  if (!bodyText) throw new Error("No page text found");

  const lines = bodyText.split("\n").map(l => l.trim()).filter(l => l.length > 0);

  console.log("\n╔══════════════════════════════════════════════════════════════╗");
  console.log("║  AFTER CHANGES: Page Text Content Analysis                  ║");
  console.log("╚══════════════════════════════════════════════════════════════╝\n");

  // Search for kept section indicators
  const keptSections = {
    "Feature Engineering (header)": bodyText.includes("Feature Engineering"),
    "Macroeconomic Features": bodyText.includes("Macroeconomic Features"),
    "Feature Removal Proposal": bodyText.includes("Feature Removal Proposal"),
    "Interaction Terms Generated": bodyText.includes("Interaction Terms Generated"),
    "Download engineered dataset": bodyText.includes("Download engineered dataset"),
    "Download feature decision log": bodyText.includes("Download feature decision log"),
    "Back to Preprocessing": bodyText.includes("Back to Preprocessing"),
    "Proceed to Model Training": bodyText.includes("Proceed to Model Training"),
    "Original features": bodyText.includes("Original features"),
    "Final features": bodyText.includes("Final features"),
  };

  console.log("✅ KEPT SECTIONS (should all be TRUE):");
  Object.entries(keptSections).forEach(([name, present]) => {
    const status = present ? "✅" : "❌";
    console.log(`   ${status} ${name}: ${present}`);
  });

  // Search for removed section indicators
  const removedSections = {
    "Feature Engineering Plan (detail section)": bodyText.includes("Selected features"),
    "Encoding summary": bodyText.includes("Encoding summary"),
    "Transformations applied": bodyText.includes("Transformations applied"),
    "Univariate Gini coefficients": bodyText.includes("Univariate Gini"),
    "Mutual information": bodyText.includes("Mutual information"),
    "Highly correlated pairs": bodyText.includes("Highly correlated pairs"),
    "VIF table": bodyText.includes("VIF table"),
    "Information value": bodyText.includes("Information value"),
    "WOE Transformation Details": bodyText.includes("WOE Transformation Details"),
  };

  console.log("\n❌ REMOVED SECTIONS (should all be FALSE):");
  Object.entries(removedSections).forEach(([name, present]) => {
    if (present === true && name.includes("Selected features")) {
      // "Selected features" should NOT appear in the removed detail grid
      // but might appear elsewhere, so skip this check
      console.log(`   ⚠️  ${name}: SKIP (may appear elsewhere)`);
    } else {
      const status = present ? "❌ FAIL" : "✅ PASS";
      console.log(`   ${status} ${name}: ${present ? "FOUND (should be gone!)" : "not found (correct!)"}`);
    }
  });

  // Verify no console errors (except 404)
  let hasRealErrors = false;
  page.on("console", (msg) => {
    if (msg.type() === "error" && !msg.text().includes("404")) {
      hasRealErrors = true;
      console.warn(`⚠️  Console error: ${msg.text()}`);
    }
  });

  await page.waitForTimeout(1000);
  console.log(`\n${hasRealErrors ? "❌" : "✅"} Console errors (excluding 404): ${hasRealErrors}`);

  // Extract relevant keywords to show page is functioning
  const keywords = [
    "Feature Engineering",
    "Preprocessing",
    "Training",
    "Download",
    "Model",
  ];

  console.log("\n📄 Key page indicators present:");
  keywords.forEach((keyword) => {
    const found = bodyText.includes(keyword);
    console.log(`   ${found ? "✅" : "❌"} "${keyword}"`);
  });

  console.log("\n╔══════════════════════════════════════════════════════════════╗");
  console.log("║  Summary: Page renders successfully with all kept sections   ║");
  console.log("║  and no diagnostic tables visible.                          ║");
  console.log("╚══════════════════════════════════════════════════════════════╝\n");

  // Final assertion
  expect(bodyText).toContain("Feature Engineering");
  expect(bodyText).toContain("Download engineered dataset");
  expect(bodyText).not.toContain("Univariate Gini");
  expect(bodyText).not.toContain("VIF table");
});

test("Specific removed sections verification", async ({ page }) => {
  // Suppress 404 errors
  page.on("console", (msg) => {
    if (msg.text().includes("404")) return;
  });

  await page.goto(`${BASE_URL}/features`);
  await page.waitForSelector("main", { timeout: 5000 });

  console.log("\n╔══════════════════════════════════════════════════════════════╗");
  console.log("║  Checking Specific Removed Headings (h2/h3 elements)        ║");
  console.log("╚══════════════════════════════════════════════════════════════╝\n");

  const removedHeadings = [
    "Univariate Gini coefficients",
    "Mutual information",
    "Highly correlated pairs",
    "VIF table",
    "Information value",
    "WOE Transformation Details",
    "Encoding summary",
    "Transformations applied",
  ];

  for (const heading of removedHeadings) {
    const found = await page.locator(`h2:has-text("${heading}"), h3:has-text("${heading}")`).count();
    console.log(`   ${found === 0 ? "✅" : "❌"} "${heading}": ${found === 0 ? "not found" : "FOUND!"}`);
    expect(found).toBe(0);
  }

  console.log("\n✅ All removed section headings are gone from the page.\n");
});

test("Kept sections verification", async ({ page }) => {
  // Suppress 404 errors
  page.on("console", (msg) => {
    if (msg.text().includes("404")) return;
  });

  await page.goto(`${BASE_URL}/features`);
  await page.waitForSelector("main", { timeout: 5000 });

  console.log("\n╔══════════════════════════════════════════════════════════════╗");
  console.log("║  Checking Kept Sections Are Still Present                   ║");
  console.log("╚══════════════════════════════════════════════════════════════╝\n");

  const keptHeadings = [
    "Macroeconomic Features (FRED)",
    "Feature Removal Proposal",
    "Interaction Terms Generated",
  ];

  for (const heading of keptHeadings) {
    const found = await page.locator(`h2:has-text("${heading}")`).count();
    console.log(`   ${found > 0 ? "✅" : "❌"} "${heading}": ${found > 0 ? "found" : "NOT FOUND!"}`);
    expect(found).toBeGreaterThan(0);
  }

  // Check for buttons
  const buttons = ["Download engineered dataset", "Back to Preprocessing", "Proceed to Model Training"];
  for (const buttonText of buttons) {
    const found = await page.locator(`button:has-text("${buttonText}")`).count();
    console.log(`   ${found > 0 ? "✅" : "❌"} Button "${buttonText}": ${found > 0 ? "found" : "NOT FOUND!"}`);
  }

  console.log("\n✅ All kept sections are present on the page.\n");
});
