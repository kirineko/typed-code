## ADDED Requirements

### Requirement: Version-matched Web asset delivery
The user-scoped service SHALL serve immutable fingerprinted Web assets and a non-cacheable application shell from its loopback origin. Asset metadata SHALL declare the supported public protocol range and service release used to build the bundle.

#### Scenario: Request a fingerprinted asset
- **WHEN** a browser requests an asset referenced by the current application shell
- **THEN** the service returns the exact packaged bytes with an immutable cache policy and a restrictive content type

#### Scenario: Request the application shell
- **WHEN** a browser opens a supported client route
- **THEN** the service returns the current shell with no-store semantics, security headers, and no credential material embedded in markup

### Requirement: One-time browser bootstrap exchange
The service SHALL let an authenticated local CLI mint a cryptographically random, single-use browser bootstrap with a short bounded expiry and optional canonical launch workspace. Redemption SHALL be accepted only at the service's allowed loopback origin and SHALL create an opaque revocable browser session without disclosing the long-lived bearer token.

#### Scenario: Mint and redeem a bootstrap
- **WHEN** an authenticated CLI mints a bootstrap and the same-origin page redeems it before expiry
- **THEN** the bootstrap is atomically consumed and an HttpOnly SameSite=Strict browser-session cookie is issued with the narrowest applicable path and lifetime

#### Scenario: Concurrent redemption
- **WHEN** two requests race to redeem the same bootstrap
- **THEN** exactly one succeeds and the other receives an unauthorized response

#### Scenario: Restart invalidates volatile bootstraps
- **WHEN** the service restarts before an outstanding bootstrap is redeemed
- **THEN** the bootstrap is no longer accepted and the user can safely mint another through `typed-code web`

### Requirement: Browser request protection
Every browser-authenticated state-changing route SHALL require an allowed loopback Host, exact same Origin, valid unguessable anti-forgery proof bound to the browser session, and a current session cookie. Responses SHALL apply a restrictive Content Security Policy and SHALL not enable broad production CORS.

#### Scenario: DNS rebinding attempt
- **WHEN** an authenticated browser sends a request with a non-loopback or unrecognized Host authority
- **THEN** the service rejects it before authentication-sensitive routing

#### Scenario: Cross-site form or fetch
- **WHEN** a foreign origin attempts a protected command with ambient browser cookies
- **THEN** Origin and anti-forgery validation reject the request without changing authoritative state

### Requirement: Browser session administration
The service SHALL store only hashed opaque browser-session identifiers with creation, idle-expiry, absolute-expiry, and revocation metadata. It SHALL support current-session inspection, renewal within policy, and explicit revocation while keeping CLI bearer authentication behavior separate.

#### Scenario: Revoke current browser session
- **WHEN** the authenticated browser signs out
- **THEN** the server revokes that session, expires its cookie, closes or rejects its subsequent subscriptions, and leaves other browser and CLI clients unaffected

#### Scenario: Expired session uses an event stream
- **WHEN** a browser session expires while its stream reconnects
- **THEN** reconnection is rejected with an authentication outcome suitable for the page to request a fresh `typed-code web` bootstrap

### Requirement: Redacted transactional configuration API
The service SHALL expose authenticated endpoints to read a redacted configuration schema/state, validate candidate provider credentials and shared defaults, and atomically commit an accepted transaction. Stored secrets SHALL never appear in a response, event, URL, or diagnostic payload.

#### Scenario: Read configuration state
- **WHEN** an authenticated client requests configuration
- **THEN** the response identifies supported fields, provider configured/available/validation state, current shared defaults, constraints, and revision without any secret values

#### Scenario: Commit against a stale revision
- **WHEN** two clients edit the same configuration revision and the first commits
- **THEN** the second receives a structured conflict with current redacted state and its stale transaction is not applied

#### Scenario: Validate without committing
- **WHEN** a client asks to validate a candidate credential or model default
- **THEN** the service reports a bounded secret-safe validation result and leaves durable and live settings unchanged

### Requirement: Manual context compaction command
The service SHALL expose an authenticated idempotency-aware command that requests context compaction for an idle session at a caller-supplied revision. It SHALL reject compaction while a run or approval is active, preserve durable conversation meaning required for subsequent turns, and emit a normalized compaction event on success.

#### Scenario: Compact an idle session
- **WHEN** an authorized client requests compaction for the current idle revision
- **THEN** the service performs one compaction, advances authoritative revision, persists the result, and emits its reason and removed item count

#### Scenario: Compaction conflicts with active work
- **WHEN** a compaction request races with a newly accepted turn or pending approval
- **THEN** one authoritative transition wins and the other receives a structured conflict without partial transcript mutation

### Requirement: Service-level client invalidation stream
The service SHALL provide an authenticated service-instance event stream for lightweight invalidations of session summaries, redacted configuration, model catalog, service lifecycle identity, and browser-session expiry. The stream SHALL not duplicate transcript deltas or establish cross-session ordering; clients SHALL refetch the named authoritative resource after an invalidation or gap.

#### Scenario: Another client creates a session
- **WHEN** one client creates a session
- **THEN** other subscribed clients receive a session-list invalidation and can refetch the authoritative workspace-grouped summaries without polling continuously

#### Scenario: Service event gap occurs
- **WHEN** a client reconnects after service-instance invalidations are no longer retained
- **THEN** the stream signals reset and the client refetches all affected catalog resources before reporting live state

### Requirement: Browser workspace boundary
Browser-authenticated clients SHALL only create sessions for canonical local directories accepted by the same workspace policy as CLI clients. Browser APIs SHALL not enumerate arbitrary filesystem trees, return directory contents for navigation, or expose paths other than explicit input and previously authorized session workspace metadata.

#### Scenario: Browser proposes a recent workspace
- **WHEN** a browser reads session summaries
- **THEN** it may reuse those canonical workspace paths for session creation but receives no broader directory listing capability

#### Scenario: Browser supplies a traversal or missing path
- **WHEN** session creation contains an invalid workspace path
- **THEN** the service rejects it before creating durable session state and returns a bounded path-safe error
