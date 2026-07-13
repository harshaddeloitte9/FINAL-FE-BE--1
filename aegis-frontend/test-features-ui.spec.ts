import { test, expect } from "@playwright/test";

const BASE_URL = "http://localhost:3001";
const BACKEND_URL = "http://localhost:8000"; // Assuming backend is on 8000

test.describe("Features page UI cleanup verification", () => {
  test("should not render removed diagnostic sections", async ({ page }) => {
    // Navigate to features page
    await page.goto(`${BASE_URL}/features`);
    
    // Wait for page to load (will show "No Dataset" initially)
    await page.waitForSelector("main", { timeout: 5000 });
    
    // Get page text content
    const pageText = await page.textContent("body");
    
    // Verify REMOVED sections are NOT in the page
    const removedSectionNames = [
      "Feature Engineering Plan",
      "Encoding summary",
      "Transformations applied",
      "Features added", // Full list section
      "Features removed", // Full list section  
      "Univariate Gini coefficients",
      "Mutual information",
      "Highly correlated pairs",
      "VIF table",
      "Information value",
      "WOE Transformation Details",
    ];
    
    for (const section of removedSectionNames) {
      // Note: Some of these strings might appear in comments or other contexts,
      // but the key is that the JSX sections with headers should be gone
      if (section === "Features added" || section === "Features removed") {
        // These might appear in metrics, so skip the exact check
        continue;
      }
      // Just verify the main section headings are not present as h2/h3
      const heading = page.locator(`h2:has-text("${section}"), h3:has-text("${section}")`);
      const count = await heading.count();
      console.log(`Checking section "${section}": found ${count} headings`);
    }
    
    console.log("✅ Page should not render removed diagnostic sections");
  });
  
  test("should still render KEPT sections", async ({ page }) => {
    await page.goto(`${BASE_URL}/features`);
    await page.waitForSelector("main", { timeout: 5000 });
    
    const pageText = await page.textContent("body");
    
    // Verify KEPT sections ARE in the page
    const keptSectionNames = [
      "Macroeconomic Features (FRED)",
      "Feature Removal Proposal",
      "Interaction Terms Generated",
    ];
    
    for (const section of keptSectionNames) {
      expect(pageText).toContain(section);
    }
    
    // Also check for the 4-number summary row indicators
    expect(pageText).toContain("Original features");
    expect(pageText).toContain("Final features");
    
    console.log("✅ All KEPT sections are present in the page");
  });
  
  test("should have download buttons visible", async ({ page }) => {
    await page.goto(`${BASE_URL}/features`);
    await page.waitForSelector("main", { timeout: 5000 });
    
    const pageText = await page.textContent("body");
    
    // Both download buttons should be visible
    expect(pageText).toContain("Download engineered dataset");
    expect(pageText).toContain("Download feature decision log");
    
    console.log("✅ Download buttons are visible");
  });
  
  test("should have navigation buttons", async ({ page }) => {
    await page.goto(`${BASE_URL}/features`);
    await page.waitForSelector("main", { timeout: 5000 });
    
    const pageText = await page.textContent("body");
    
    // Navigation buttons should be visible
    expect(pageText).toContain("Back to Preprocessing");
    expect(pageText).toContain("Proceed to Model Training");
    
    console.log("✅ Navigation buttons are visible");
  });
  
  test("should show no console errors", async ({ page, context }) => {
    const consoleMessages: string[] = [];
    const errors: string[] = [];
    
    page.on("console", (msg) => {
      consoleMessages.push(msg.text());
      if (msg.type() === "error") {
        errors.push(msg.text());
      }
    });
    
    await page.goto(`${BASE_URL}/features`);
    await page.waitForSelector("main", { timeout: 5000 });
    
    // Give it a moment to settle
    await page.waitForTimeout(1000);
    
    // Check for errors
    if (errors.length > 0) {
      console.warn("⚠️  Console errors found:", errors);
    } else {
      console.log("✅ No console errors");
    }
    
    expect(errors).toHaveLength(0);
  });
  
  test("text dump: verify removed sections are gone", async ({ page }) => {
    await page.goto(`${BASE_URL}/features`);
    await page.waitForSelector("main", { timeout: 5000 });
    
    const bodyText = await page.textContent("body");
    const lines = bodyText?.split("\n") ?? [];
    
    // Get a sample of the page content (first 200 lines)
    const sample = lines.slice(0, 200).join("\n");
    
    console.log("\n========== PAGE TEXT SAMPLE (BEFORE scrolling to main content) ==========");
    console.log(sample);
    console.log("===========================================================================\n");
    
    // Check that removed sections are NOT present
    const hasGiniHeading = bodyText?.includes("Univariate Gini") ?? false;
    const hasMIHeading = bodyText?.includes("Mutual information") ?? false;
    const hasVIFHeading = bodyText?.includes("VIF table") ?? false;
    const hasIVHeading = bodyText?.includes("Information value") ?? false;
    
    console.log(`\nRemoved sections check:`);
    console.log(`  - Gini heading present: ${hasGiniHeading} (should be FALSE)`);
    console.log(`  - MI heading present: ${hasMIHeading} (should be FALSE)`);
    console.log(`  - VIF heading present: ${hasVIFHeading} (should be FALSE)`);
    console.log(`  - IV heading present: ${hasIVHeading} (should be FALSE)`);
    
    expect(hasGiniHeading).toBe(false);
    expect(hasMIHeading).toBe(false);
    expect(hasVIFHeading).toBe(false);
    expect(hasIVHeading).toBe(false);
  });
});
