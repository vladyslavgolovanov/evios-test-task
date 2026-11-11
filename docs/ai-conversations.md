# Development discussion

## Scope and compatibility

**Developer**

Keep the implementation focused on the assignment. By code quality, I mean clear code, targeted tests, and review. Preserve the existing template and restore the development endpoint; I will explain its limitation when presenting the solution. Avoid unrelated changes to CI, Docker, dependencies, and documentation.

**AI**

Restored the endpoint, its client, and its tests. All excessive reworking has also been reverted: CI, Docker, dependencies, documentation, and email templates are back to their original state.

`git status` is clean. No commits or pushes were made. The repository structure check passed; I am not attributing earlier runtime test results to the restored version.

Next: only the required functionality, targeted tests, and review, without restructuring the template.

## Implementation quality

**Developer**

Review the current implementation and identify focused improvements to code quality and verification. Keep the changes within the agreed scope.

**AI**

The improvements have already been implemented in the first RBAC task:

- One source of permissions: `role`, with a shared server-side access check.
- Registration and profile updates cannot elevate privileges.
- Managers can view the user list without editing actions.
- Denied access displays `Access Denied` while preserving authentication.

**69 backend tests and 63 browser scenarios** passed, along with type checks, the build, migration, and data restoration checks.

Application: [localhost:8092](http://localhost:8092). Accounts: `admin@example.com`, `manager@example.com`, and `member@example.com`; passwords are stored in the private local configuration.

**No commits or pushes.** The private endpoint is retained. The next task is metrics and a short README; Ghost remains a separate stage.

## Requirements and verification

**Developer**

Confirm that the remaining work is explicitly required by the assignment. Keep the implementation limited to those requirements.

**AI**

Yes, the [requirements](https://github.com/evios/Fullstack-Dev-Test-Task#requirements) explicitly include:

- Metrics for admin/manager; a placeholder is allowed.
- Creation of test users.
- A README covering setup, tests, and migrations.
- Hiding unavailable actions and displaying Access Denied.

These are implemented. Verification: **74 backend tests and 67 browser tests**, with successful build and type checks.

Available at the [metrics page](http://localhost:8092/metrics). **The changes have not been committed or pushed.**

## Deployment and persistence

**Developer**

Provision the infrastructure once and reuse it for subsequent application updates. Preserve the database and uploaded files across redeployments. For this demo, leave email disabled and keep password-based login.

**AI**

**Ghost is running on Railway:**

- [Open the blog](https://ghost-production-3cf8ea87.up.railway.app)
- [Open the admin login](https://ghost-production-3cf8ea87.up.railway.app/ghost/)
- The email and password are stored in a private local file excluded from Git.

Verified login and preservation of a post with an image after redeployment. MySQL is not publicly accessible.

Email remains disabled. The deployment is running on $5 of trial credit. No commits or pushes were made.
