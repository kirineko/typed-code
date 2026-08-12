## MODIFIED Requirements

### Requirement: Automatic local service lifecycle
The default interactive entry SHALL ensure that exactly one compatible authenticated loopback agent service owns a given canonical user data directory before opening the main chat UI. Production startup SHALL resolve the active verified managed installation; development startup MAY use only an explicit absolute project or executable override. Concurrent clients SHALL coordinate process startup atomically, but ordinary TUI startup SHALL NOT perform an implicit network download, service upgrade, or destructive installation repair.

#### Scenario: No local service is running
- **WHEN** the default entry cannot reach a compatible owner for the configured canonical data directory
- **THEN** it starts only the resolved active verified managed service or an explicit development override, waits for authenticated health and protocol negotiation, and does not download or upgrade an artifact implicitly

#### Scenario: Compatible service already running
- **WHEN** a compatible authenticated service already owns the canonical data directory
- **THEN** the entry reuses that service without spawning a duplicate process or changing the active managed installation

#### Scenario: Exit after spawning service
- **WHEN** the CLI caused the persistent user-scoped service to start and the user exits cleanly
- **THEN** the CLI releases its subscriptions and restores the terminal without stopping the service or cancelling server-owned work

#### Scenario: Compatible managed service is installed but not running
- **WHEN** the default production entry finds a compatible active managed installation and no service owns the data directory
- **THEN** one startup contender starts that installed service, waits for authenticated health, and allows all waiting clients to attach

#### Scenario: No managed service is installed
- **WHEN** production startup cannot resolve a compatible verified managed installation
- **THEN** it displays a focused recovery screen with the exact install command, target platform, expected release/channel, and an option to exit without creating a session

#### Scenario: Installed service is outdated
- **WHEN** the active managed service is incompatible with the CLI or configured channel policy
- **THEN** startup identifies whether the service or CLI must be upgraded and does not automatically replace binaries while opening the TUI

#### Scenario: Development source path is configured
- **WHEN** an explicit development project or executable is valid
- **THEN** startup uses it without consulting or changing the production active-version record

### Requirement: First-run setup orders service and provider prerequisites safely
First-run guidance SHALL distinguish service installation from provider credential onboarding. It SHALL establish a compatible service before attempting authenticated service configuration reload, and SHALL preserve already valid credentials when installation is cancelled or fails.

#### Scenario: Fresh production install has no service or provider key
- **WHEN** the user starts the CLI with neither prerequisite
- **THEN** the UI first explains and invokes the explicit service-install flow, then collects a provider credential only after the service passes health and compatibility checks

#### Scenario: Service installation fails after credentials already exist
- **WHEN** valid XDG credentials exist but service acquisition or activation fails
- **THEN** the credentials remain unchanged and the UI offers retry, offline artifact selection, diagnostics, or exit without asking the user to re-enter secrets

#### Scenario: Upgrade is blocked by active work
- **WHEN** startup detects an available service update while another client owns an active run or approval
- **THEN** the current compatible service remains usable and the UI defers upgrade with the affected-session state rather than forcing interruption
