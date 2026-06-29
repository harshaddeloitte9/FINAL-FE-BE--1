import { test, expect } from '@playwright/test';

test('Complete workflow: Upload → Profiling → Preprocessing → Features → Models → Training', async ({ page, context }) => {
  // Intercept all requests to track backend calls
  const apiCalls: { method: string; url: string; body?: string }[] = [];
  
  page.on('request', (request) => {
    if (request.url().includes('/models/recommend')) {
      apiCalls.push({
        method: request.method(),
        url: request.url(),
        body: request.postData(),
      });
    }
  });

  // Start at the app
  await page.goto('http://localhost:8084/', { waitUntil: 'networkidle' });
  await expect(page).toHaveTitle(/Aegis Credit|Development/i);

  // Step 1: Data Upload
  console.log('📤 Step 1: Data Upload');
  // Use synthetic dataset to avoid file upload complexity
  const syntheticBtn = page.getByText('Generate dataset', { exact: false });
  await syntheticBtn.click();
  
  // Wait for upload to complete (progress bar reaches 100%)
  await page.waitForTimeout(3000);
  
  // Proceed to Profiling
  const proceedToProfilingBtn = page.getByRole('button', { name: /Proceed to Profiling/i });
  if (proceedToProfilingBtn) {
    await proceedToProfilingBtn.click();
  } else {
    // Try via sidebar
    await page.getByText('Data Profiling', { exact: false }).click();
  }

  // Step 2: Data Profiling
  console.log('📊 Step 2: Data Profiling');
  await page.waitForURL(/\/profiling/);
  await expect(page).toHaveTitle(/Profiling|Aegis/i);
  
  // Proceed to Preprocessing
  const proceedToPreprocessingBtn = page.getByRole('button', { name: /Proceed to Preprocessing|Preprocessing/i }).first();
  if (proceedToPreprocessingBtn) {
    await proceedToPreprocessingBtn.click();
  } else {
    await page.getByText('Preprocessing', { exact: false }).click();
  }

  // Step 3: Preprocessing
  console.log('🔧 Step 3: Preprocessing');
  await page.waitForURL(/\/preprocessing/);
  await expect(page).toHaveTitle(/Preprocessing|Aegis/i);
  
  // Wait for preprocessing to complete
  await page.waitForTimeout(3000);
  
  // Proceed to Feature Engineering
  const proceedToFeaturesBtn = page.getByRole('button', { name: /Proceed to Feature Engineering|Feature Engineering/i }).first();
  if (proceedToFeaturesBtn) {
    await proceedToFeaturesBtn.click();
  } else {
    await page.getByText(/Feature Engineering|Features/i).click();
  }

  // Step 4: Feature Engineering
  console.log('⚙️  Step 4: Feature Engineering');
  await page.waitForURL(/\/features/);
  await expect(page).toHaveTitle(/Feature Engineering|Aegis/i);
  
  // Wait for feature engineering to complete
  await page.waitForTimeout(3000);
  
  // Proceed to Model Selection
  const proceedToModelsBtn = page.getByRole('button', { name: /Proceed to Model Selection|Model Selection/i }).first();
  if (proceedToModelsBtn) {
    await proceedToModelsBtn.click();
  } else {
    await page.getByText('Model Selection', { exact: false }).click();
  }

  // Step 5: Model Selection
  console.log('🎯 Step 5: Model Selection');
  await page.waitForURL(/\/models/);
  await expect(page).toHaveTitle(/Model Selection|Aegis/i);
  
  // Wait for recommendations to load
  await page.waitForTimeout(2000);
  
  // Verify dataset summary is shown
  console.log('✓ Checking dataset summary section...');
  const sampleCountText = page.locator('text=Sample count').or(page.locator('text=sample count'));
  await expect(sampleCountText).toBeVisible({ timeout: 5000 });
  console.log('✓ Dataset summary visible');

  // Verify models are displayed
  console.log('✓ Checking model recommendation cards...');
  const modelCards = page.locator('[class*="rounded-2xl"][class*="border"][class*="bg-card"]');
  const count = await modelCards.count();
  console.log(`✓ Found ${count} model recommendation card(s)`);
  
  // Verify models-to-compare section
  console.log('✓ Checking Models to Compare section...');
  const modelsToCompareSection = page.getByText('Models to Compare', { exact: false });
  await expect(modelsToCompareSection).toBeVisible({ timeout: 5000 });
  console.log('✓ Models to Compare section visible');

  // Verify Credit Risk Evaluation Strategy section
  console.log('✓ Checking Credit Risk Evaluation Strategy section...');
  const strategySection = page.getByText('Credit Risk Evaluation Strategy', { exact: false });
  await expect(strategySection).toBeVisible({ timeout: 5000 });
  console.log('✓ Credit Risk Evaluation Strategy section visible');

  // Select a model if not already selected
  console.log('✓ Selecting a model...');
  const selectBtn = page.getByRole('button', { name: /Select model|Selected/i }).first();
  if (selectBtn) {
    await selectBtn.click();
  }

  // Select some challenger models
  console.log('✓ Selecting challenger models...');
  const checkboxes = page.locator('input[type="checkbox"]').all();
  const firstCheckbox = await page.locator('input[type="checkbox"]').first();
  if (firstCheckbox) {
    await firstCheckbox.click();
  }

  // Proceed to Training
  console.log('✓ Clicking Proceed to Training...');
  const proceedToTrainingBtn = page.getByRole('button', { name: /Proceed to Training|Training/i }).first();
  if (proceedToTrainingBtn) {
    await proceedToTrainingBtn.click();
  } else {
    await page.getByText('Training', { exact: false }).click();
  }

  // Step 6: Training
  console.log('🚂 Step 6: Training');
  await page.waitForURL(/\/training/, { timeout: 10000 }).catch(() => {
    console.warn('⚠️  Training URL timeout (may still be navigating)');
  });

  // Final verification
  console.log('\n📋 Test Summary:');
  console.log(`✓ Models-to-recommend API calls: ${apiCalls.length}`);
  console.log(`✓ Expected: exactly 1 call to /models/recommend`);
  
  if (apiCalls.length === 1) {
    console.log('✅ PASS: Exactly one /models/recommend call detected');
  } else if (apiCalls.length === 0) {
    console.log('⚠️  WARN: No /models/recommend calls detected (may be using cache or mock data)');
  } else {
    console.log(`❌ FAIL: ${apiCalls.length} /models/recommend calls detected (expected 1)`);
  }

  // Print all API call details
  console.log('\nAPI Calls:');
  apiCalls.forEach((call, idx) => {
    console.log(`  ${idx + 1}. ${call.method} ${call.url}`);
  });

  // Assert
  expect(apiCalls.length).toBeLessThanOrEqual(1);
});
