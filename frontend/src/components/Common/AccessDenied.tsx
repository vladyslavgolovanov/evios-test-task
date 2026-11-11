import {
  ErrorComponent,
  type ErrorComponentProps,
  Link,
} from "@tanstack/react-router"
import { AxiosError } from "axios"

export function AccessDenied() {
  return (
    <section className="space-y-3" role="alert">
      <h1 className="text-2xl font-bold">Access Denied</h1>
      <p>You don't have permission to view this page.</p>
      <Link to="/" className="underline">
        Return to dashboard
      </Link>
    </section>
  )
}

export function ProtectedPageError(props: ErrorComponentProps) {
  if (
    props.error instanceof AxiosError &&
    props.error.response?.status === 403
  ) {
    return <AccessDenied />
  }
  return <ErrorComponent {...props} />
}
