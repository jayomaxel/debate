import { expect, test } from '@playwright/test';

test('production gateway renders an interactive login page', async ({ page }) => {
  const pageErrors: string[] = [];
  page.on('pageerror', (error) => pageErrors.push(error.message));

  const response = await page.goto('/login', { waitUntil: 'networkidle' });
  expect(response?.ok()).toBe(true);
  await expect(page.getByRole('heading', { name: '欢迎登录' })).toBeVisible();

  const studentAccount = page.locator('#student-account');
  const studentPassword = page.locator('#student-password');
  await expect(studentAccount).toBeVisible();
  await expect(studentPassword).toBeVisible();
  await studentAccount.fill('browser-smoke-student');
  await studentPassword.fill('browser-smoke-password');

  await page.getByRole('tab', { name: '我是老师' }).click();
  await expect(page.locator('#teacher-id')).toBeVisible();
  await page.getByRole('tab', { name: '我是学生' }).click();
  await expect(studentAccount).toHaveValue('browser-smoke-student');
  expect(pageErrors).toEqual([]);
});

test('anonymous entry reaches the public debate home', async ({ page }) => {
  const response = await page.goto('/login', { waitUntil: 'networkidle' });
  expect(response?.ok()).toBe(true);

  await page.getByRole('button', { name: '暂不登录' }).click();
  await expect(page).toHaveURL(/\/$/);
  await expect(page.getByRole('heading', { name: '碳硅之辩' })).toBeVisible();
  await expect(page.getByRole('button', { name: '开始辩论' })).toBeVisible();
});
