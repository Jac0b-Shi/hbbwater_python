import { test, expect } from '@playwright/test'

test.describe('profile page live flow', () => {
  test('profile loads local admin data from control sqlite', async ({ page }) => {
    const accountFailures = []

    page.on('response', response => {
      if (!response.url().includes('/api/account/')) {
        return
      }
      if (response.status() >= 400) {
        accountFailures.push({
          url: response.url(),
          status: response.status()
        })
      }
    })

    await page.goto('/profile')

    await expect(page.getByText('编辑资料')).toBeVisible()
    await expect(page.getByPlaceholder('请输入用户名')).toHaveValue('admin')
    await expect(page.getByPlaceholder('请输入显示名称')).toHaveValue('管理员')
    await expect(page.getByPlaceholder('请输入邮箱，用于 Gravatar 头像')).toHaveValue('admin@example.com')
    await expect(page.getByText('admin@example.com')).toBeVisible()
    await expect(page.getByText('认证方式：本地账户')).toBeVisible()

    expect(accountFailures).toEqual([])
  })
})
