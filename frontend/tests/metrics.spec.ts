import { expect, test } from "@playwright/test"

import { firstSuperuser, firstSuperuserPassword } from "./config"
import { randomEmail, randomPassword } from "./utils/random"
import { logInUser } from "./utils/user"

test("Admin can open metrics from navigation", async ({ page }) => {
  await page.goto("/")
  await page.getByRole("link", { name: "Metrics" }).click()
  await expect(page.getByRole("heading", { name: "Metrics" })).toBeVisible()
  await expect(page.getByTestId("metrics-users")).toHaveText(/^\d+$/)
  await expect(page.getByTestId("metrics-items")).toHaveText(/^\d+$/)
})

test.describe("Metrics access", () => {
  test.use({ storageState: { cookies: [], origins: [] } })

  for (const role of ["manager", "member"] as const) {
    test(`${role} navigation and direct metrics access`, async ({
      page,
      request,
    }) => {
      const base = process.env.VITE_API_URL
      const login = await request.post(`${base}/api/v1/login/access-token`, {
        form: { username: firstSuperuser, password: firstSuperuserPassword },
      })
      expect(login.ok()).toBeTruthy()
      const headers = {
        Authorization: `Bearer ${(await login.json()).access_token}`,
      }
      const email = randomEmail()
      const password = randomPassword()
      const created = await request.post(`${base}/api/v1/users/`, {
        headers,
        data: { email, password, role },
      })
      expect(created.ok()).toBeTruthy()
      const user = await created.json()
      try {
        await logInUser(page, email, password)
        const link = page.getByRole("link", { name: "Metrics" })
        if (role === "member") await expect(link).toHaveCount(0)
        else await expect(link).toBeVisible()
        await page.goto("/metrics")
        if (role === "member") {
          await expect(
            page.getByRole("heading", { name: "Access Denied" }),
          ).toBeVisible()
          await expect(page.getByTestId("metrics-users")).toHaveCount(0)
        } else {
          await expect(
            page.getByRole("heading", { name: "Metrics" }),
          ).toBeVisible()
          await expect(page.getByTestId("metrics-users")).toHaveText(/^\d+$/)
        }
      } finally {
        await request.delete(`${base}/api/v1/users/${user.id}`, { headers })
      }
    })
  }

  test("Anonymous navigation requires login", async ({ page }) => {
    await page.goto("/metrics")
    await expect(page).toHaveURL(/\/login/)
  })
})
