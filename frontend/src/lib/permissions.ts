import type { Role, UserPublic } from "@/client"

export const roles = ["admin", "manager", "member"] as const
export const roleLabels: Record<Role, string> = {
  admin: "Admin",
  manager: "Manager",
  member: "Member",
}

type Permission = "users:read" | "users:write"
const permissions: Record<Role, readonly Permission[]> = {
  admin: ["users:read", "users:write"],
  manager: ["users:read"],
  member: [],
}

export function can(
  user: UserPublic | null | undefined,
  permission: Permission,
) {
  return !!user && permissions[user.role].includes(permission)
}
