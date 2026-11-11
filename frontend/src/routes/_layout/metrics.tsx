import { useSuspenseQuery } from "@tanstack/react-query"
import { createFileRoute } from "@tanstack/react-router"
import { Suspense } from "react"

import { MetricsService, UsersService } from "@/client"
import {
  AccessDenied,
  ProtectedPageError,
} from "@/components/Common/AccessDenied"
import { can } from "@/lib/permissions"

export const Route = createFileRoute("/_layout/metrics")({
  component: MetricsPage,
  errorComponent: ProtectedPageError,
  beforeLoad: async () => {
    const { data: user } = await UsersService.readUserMe()
    return { canReadMetrics: can(user, "metrics:read") }
  },
})

function MetricsContent() {
  const { data } = useSuspenseQuery({
    queryKey: ["metrics"],
    queryFn: async () => (await MetricsService.readMetrics()).data,
  })
  return (
    <dl className="grid gap-4 sm:grid-cols-2">
      <div className="rounded-lg border p-6">
        <dt className="text-muted-foreground">Total users</dt>
        <dd className="text-3xl font-bold" data-testid="metrics-users">
          {data.users}
        </dd>
      </div>
      <div className="rounded-lg border p-6">
        <dt className="text-muted-foreground">Total items</dt>
        <dd className="text-3xl font-bold" data-testid="metrics-items">
          {data.items}
        </dd>
      </div>
    </dl>
  )
}

function MetricsPage() {
  const { canReadMetrics } = Route.useRouteContext()
  if (!canReadMetrics) return <AccessDenied />
  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold tracking-tight">Metrics</h1>
      <Suspense fallback={<p role="status">Loading metrics…</p>}>
        <MetricsContent />
      </Suspense>
    </div>
  )
}
