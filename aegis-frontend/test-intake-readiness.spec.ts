import { test, expect } from '@playwright/test';

const LOGIN_URL = '/login';
const INTAKE_URL = '/validation/intake';

async function signIn(page: any) {
  await page.goto(LOGIN_URL);
  await page.getByPlaceholder('Username').fill('demo');
  await page.getByPlaceholder('Password').fill('demo');
  await page.getByRole('button', { name: 'Sign in' }).click();
  await page.waitForURL(/\/validation(?:\/intake)?$/);
}

async function fillRequiredMetadata(page: any) {
  await page.getByLabel('Model Name').locator('input').fill('Demo Model');
  await page.getByLabel('Model Version').locator('input').fill('1.0');
  await page.getByLabel('Owning Team / Business Unit').locator('input').fill('Credit Risk');
  await page.getByLabel('Model Owner').locator('input').fill('Owner One');
  await page.getByLabel('Lead Validator').locator('input').fill('Validator One');
  await page.getByLabel('Model Purpose').locator('textarea, input').fill('Retail credit risk monitoring');
}

test.describe('Intake readiness gate', () => {
  test('fresh demo intake starts with governance and final confirmation unchecked', async ({ page }) => {
    await signIn(page);
    await page.goto(INTAKE_URL);

    const finalConfirmation = page.getByText('I confirm the above information is accurate and complete').locator('..').locator('input');
    const governanceInputs = page.locator('input[type="checkbox"]').filter({ has: page.locator('..') });

    await expect(page.getByRole('button', { name: /Proceed to Stage 2/i })).toBeDisabled();
    await expect(finalConfirmation).not.toBeChecked();
    await expect(page.locator('input[type="checkbox"]').nth(0)).not.toBeChecked();
    await expect(governanceInputs.first()).not.toBeChecked();
  });

  test('incomplete artifacts + checked confirmation keeps the proceed button disabled', async ({ page }) => {
    await signIn(page);
    await page.goto(INTAKE_URL);

    await fillRequiredMetadata(page);
    await page.getByText('I confirm the above information is accurate and complete').click();

    await expect(page.getByRole('button', { name: /Proceed to Stage 2/i })).toBeDisabled();
    await expect(page.getByText(/Upload the required dataset, MDD, and training code\./i)).toBeVisible();
  });

  test('complete artifacts + incomplete governance keeps the proceed button disabled', async ({ page }) => {
    await signIn(page);
    await page.goto(INTAKE_URL);

    await fillRequiredMetadata(page);
    await page.locator('input[type="file"]').nth(0).setInputFiles({
      name: 'dataset.csv',
      mimeType: 'text/csv',
      buffer: Buffer.from('default\n0\n1\n'),
    });
    await page.locator('input[type="file"]').nth(1).setInputFiles({
      name: 'mdd.txt',
      mimeType: 'text/plain',
      buffer: Buffer.from('Purpose and intended use are documented. Validation independence is managed separately.'),
    });
    await page.locator('input[type="file"]').nth(2).setInputFiles({
      name: 'training.py',
      mimeType: 'text/x-python',
      buffer: Buffer.from('print("ok")\n'),
    });
    await page.getByText('I confirm the above information is accurate and complete').click();

    await expect(page.getByRole('button', { name: /Proceed to Stage 2/i })).toBeDisabled();
    await expect(page.getByText(/Complete all governance controls\./i)).toBeVisible();
  });

  test('complete requirements enables the proceed button', async ({ page }) => {
    await signIn(page);
    await page.goto(INTAKE_URL);

    await fillRequiredMetadata(page);
    await page.locator('input[type="file"]').nth(0).setInputFiles({
      name: 'dataset.csv',
      mimeType: 'text/csv',
      buffer: Buffer.from('default\n0\n1\n'),
    });
    await page.locator('input[type="file"]').nth(1).setInputFiles({
      name: 'mdd.txt',
      mimeType: 'text/plain',
      buffer: Buffer.from('Purpose and intended use are documented. Validation independence is managed separately.'),
    });
    await page.locator('input[type="file"]').nth(2).setInputFiles({
      name: 'training.py',
      mimeType: 'text/x-python',
      buffer: Buffer.from('print("ok")\n'),
    });

    const governanceCheckboxes = page.locator('input[type="checkbox"]').filter({ has: page.locator('..') });
    for (let i = 0; i < 7; i++) {
      await governanceCheckboxes.nth(i).check();
    }
    await page.getByText('I confirm the above information is accurate and complete').click();

    await expect(page.getByRole('button', { name: /Proceed to Stage 2/i })).toBeEnabled();
    await expect(page.getByText(/All required conditions satisfied/i)).toBeVisible();
  });
});
