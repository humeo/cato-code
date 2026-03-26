# GitHub App SaaS Auth Boundary Design

**Goal**

Move CatoCode to a true multi-user SaaS auth model built around a single platform-managed GitHub App. Users log in with GitHub, install the same App into personal accounts or organizations, and CatoCode runs repository actions with short-lived installation tokens. Personal access tokens are not part of the product path.

## Product Decisions

- CatoCode is a multi-user SaaS.
- The platform owns exactly one GitHub App.
- The same GitHub App handles login, installation, and runtime execution.
- Users can install the App into personal accounts or organizations.
- Dashboard repo visibility only includes repos where:
  - the platform App is installed, and
  - the logged-in user has at least GitHub `write` permission.
- `watch` is a repo-global state, not per-user.
- GitHub writebacks always appear as the GitHub App bot identity.
- `/approve` is accepted from GitHub-native collaborators with `write` permission; SaaS login is not required for that action.

## Token Model

There are two distinct token classes.

### User Access Token

Purpose:

- GitHub login session bootstrap
- read the current user's accessible installations and repositories
- verify the current user's effective repo permissions for control-plane actions

Rules:

- stored encrypted in the database
- never injected into worker containers
- only used by the API/control plane

### Installation Access Token

Purpose:

- clone/fetch/push repository contents
- post issue comments, review replies, and pull requests
- all runtime GitHub API and `gh` CLI actions

Rules:

- minted dynamically per installation
- short-lived and cached only in memory with expiry awareness
- injected into the selected worker container only for the activity being executed

## Boundary Changes

The current global auth factory is not compatible with SaaS because it assumes either:

- one global `GITHUB_TOKEN`, or
- one global `GITHUB_APP_INSTALLATION_ID`

The correct boundary is:

- app credentials are global server config
- installation selection is per repo
- user token selection is per logged-in user
- runtime GitHub token resolution happens per activity

## Required Data Model

Existing tables already provide most of the shape. The missing contract is operational:

- `users.access_token` stores the encrypted user access token
- `installations.installation_id` identifies a GitHub App installation
- repos must be linked to the installation that grants runtime access
- repo visibility is computed as the intersection of:
  - repos known to an installation
  - repos the logged-in user can administer at `write` level

Each repo must therefore have a durable installation binding. Runtime execution must resolve:

`activity -> repo -> installation_id -> installation token`

## Control Plane Flow

1. User opens landing page.
2. User clicks `Connect GitHub`.
3. GitHub App OAuth flow returns a user access token.
4. CatoCode creates or updates the platform user session.
5. If the user has no linked installations, CTA is `Install App`.
6. User installs the platform App into a personal account or organization.
7. Installation callback links the installation to the user.
8. Dashboard lists only installed repos that the user can manage with `write` permission.
9. User clicks `Watch`.
10. Repo enters `setting_up`, then `ready`.

## Runtime Flow

1. Scheduler/dispatcher receives an activity for a repo.
2. Control plane resolves the repo's installation.
3. Control plane mints or refreshes an installation token for that installation.
4. Worker container receives only that installation token plus Anthropic config.
5. Claude Agent SDK session runs as the GitHub App bot identity.

## Security Properties

- no PAT-based product path
- no user token in worker containers
- no global installation token shared across repos
- repo actions are auditable as the App bot
- user control-plane access and bot execution permissions remain separate

## V1 Scope

This design changes auth/token boundaries only. It does not change:

- session/worktree lifecycle
- resolution-memory behavior
- issue/fix activity semantics

## Open Edge Cases

- app installations that include repos the logged-in user cannot manage
- organizations with changing membership after installation
- revoked/expired user access tokens
- installations deleted outside the normal callback path
