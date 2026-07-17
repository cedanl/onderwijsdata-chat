export async function login(page) {
  const resp = await page.request.post('http://localhost:8000/api/auth/login', {
    data: { username: 'admin', password: 'admin' },
  })
  const { token } = await resp.json()

  await page.goto('/')
  await page.evaluate(t => localStorage.setItem('token', t), token)
  await page.reload()
  await page.waitForTimeout(1000)

  const skipBtn = page.locator('button', { hasText: 'Overslaan' })
  if (await skipBtn.isVisible({ timeout: 2000 }).catch(() => false)) {
    await skipBtn.click()
    await page.waitForTimeout(500)
  }
}

export async function handleLoginIfNeeded(page) {
  const passwordField = page.locator('input[type="password"]')
  if (await passwordField.isVisible({ timeout: 3000 }).catch(() => false)) {
    await page.fill('input[type="text"]', 'admin')
    await page.fill('input[type="password"]', 'admin')
    await page.click('button[type="submit"]')
    await page.waitForTimeout(3000)
  }

  const skipBtn = page.locator('button', { hasText: 'Overslaan' })
  if (await skipBtn.isVisible({ timeout: 2000 }).catch(() => false)) {
    await skipBtn.click()
    await page.waitForTimeout(500)
  }
}
