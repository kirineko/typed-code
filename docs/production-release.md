# typed-code 生产发布指南

本文定义 typed-code 面向 macOS、Linux 和 Windows 的生产发布目标、制品结构、签名策略、CI/CD 流程、发布门禁和故障处置。适用于发布负责人、维护者和 CI 管理员。

> **重要：当前状态与目标状态不同。** 当前仓库只具备经过验证的 `darwin-arm64` companion 打包链路，工作流为 `.github/workflows/release-macos.yml`。`darwin-x64`、`linux-arm64`、`linux-x64` 和 `win32-x64` 尚未形成可发布制品；Windows 运行时还存在明确的 POSIX 依赖。因此，在本文列出的对应平台门禁全部通过前，不得宣称该平台已受支持，也不得发布不完整的 stable 版本。

## 1. 发布目标

一次 stable 发布必须交付同版本的：

1. `@typed-code/cli`：Node.js/pi-tui 客户端，公开命令仅为 `typed-code`。
2. `@typed-code/sdk`：TypeScript 协议 SDK。
3. 五个按平台拆分的可选 companion 包：
   - `@typed-code/server-darwin-arm64`
   - `@typed-code/server-darwin-x64`
   - `@typed-code/server-linux-arm64`
   - `@typed-code/server-linux-x64`
   - `@typed-code/server-win32-x64`
4. GitHub Release 中的离线服务制品、校验和、签名、SBOM 和来源证明。
5. 签名的 `service-manifest.v1.json`，供 `typed-code service install/check/upgrade/rollback` 使用。

所有 npm 包、companion、manifest 和协议声明必须使用同一个版本号。不得混发不同版本，也不得用兼容别名掩盖版本不一致。

## 2. 支持矩阵

首个完整跨平台版本采用以下支持边界：

| 目标 | Node.js | 服务运行时 | Shell/工具前提 | 系统信任 | 发布状态 |
|---|---:|---|---|---|---|
| macOS Apple Silicon (`darwin-arm64`) | 22+ | 原生冻结二进制 | 系统 Bash | Developer ID + notarization + stapling | 当前唯一已验证目标 |
| macOS Intel (`darwin-x64`) | 22+ | 原生冻结二进制 | 系统 Bash | Developer ID + notarization + stapling | 待实现、待 clean-host 验证 |
| Linux ARM64 (`linux-arm64`) | 22+ | glibc 原生冻结二进制 | Bash | Ed25519 manifest + SHA-256；可附 Sigstore | 待实现、待 clean-host 验证 |
| Linux x64 (`linux-x64`) | 22+ | glibc 原生冻结二进制 | Bash | Ed25519 manifest + SHA-256；可附 Sigstore | 待实现、待 clean-host 验证 |
| Windows x64 (`win32-x64`) | 22+ | 原生冻结 `.exe` | Git for Windows Bash（启动本地服务前检测） | Authenticode + timestamp + Ed25519 manifest | **当前被运行时兼容性阻塞** |

### 2.1 操作系统基线

建议第一版明确而保守地声明：

- macOS 13 Ventura 及以上。
- Linux 以构建机的 glibc 版本为最低基线；建议在 Ubuntu 22.04 或等价的较老 glibc 环境构建并把实际 `GLIBC_*` 需求写入 release evidence。
- Alpine/musl 不属于首版 Linux 支持范围；如需支持，必须增加独立的 `linux-*-musl` 目标，不能复用 glibc 制品。
- Windows 10 22H2、Windows 11 和 Windows Server 2022 x64。

这些基线必须由 clean-host 测试证明，不能只由编译成功推断。

### 2.2 Windows 发布前置改造

当前 Windows 不能只靠新增 PyInstaller job 获得生产支持。至少存在以下阻塞项：

- `src/typed_code/service/runtime_identity.py` 直接使用 `fcntl.flock`、`os.getuid`、`os.fchmod` 和 POSIX 权限模型。
- workspace 执行后端固定为 `LocalBashExecutionBackend` 并要求可发现 Bash。
- CLI 与服务默认使用 XDG 风格的 `~/.config`、`~/.local/share`，尚未定义 Windows 原生目录迁移与 ACL 规则。
- 服务分离启动、进程树取消、文件替换、路径边界、日志轮转和数据库锁必须在 NTFS/Windows 进程模型上重新验证。
- Windows companion 需要 Authenticode 签名和可信时间戳，否则会产生 SmartScreen/企业策略问题。

首个 Windows 版本确定复用现有 Bash tool contract，并将 **Git for Windows Bash 作为显式运行前提**，不在第一版引入 PowerShell 执行后端，也不把 MSYS2/Git Bash 捆绑进 companion。CLI 仅在准备启动本地 Windows 服务时执行检测；`--help`、不启动服务的诊断命令和连接外部服务的模式不应被本机 Bash 前提阻塞。

检测顺序为显式 `TYPED_CODE_BASH_EXECUTABLE`、`config.toml` 的 `[bash].executable`、`PATH`、Git for Windows 安装信息和标准安装目录。候选文件存在并不足以通过检测：CLI 或服务必须以参数数组执行 `bash.exe --noprofile --norc -c <probe>`，确认工作目录、UTF-8 输出和基本文件操作可用，并接受 Git for Windows 的 `MINGW*`/`MSYS*` 环境。Native Windows 进程不得把 WSL `bash.exe` 当作兼容候选；在 WSL 内运行的 typed-code 应使用 Linux companion。

如果没有可用 Bash，CLI 不自动安装第三方软件，而是在启动 TUI 或创建 session 前退出并给出：

```powershell
winget install --id Git.Git -e --source winget
```

提示还必须包含 [Git for Windows 官方下载地址](https://git-scm.com/install/windows)、重新打开终端后重试的说明，以及配置现有 `bash.exe` 绝对路径的方法。安装 Bash 后无需重新安装 typed-code。

该决定只解决 Shell 前提，不消除前述 Windows runtime 阻塞项。文件锁/ACL、Windows 数据目录、进程树取消、NTFS 路径边界、`.exe` 生命周期、签名和 clean-host 场景仍须分别实现和验证。在这些门禁关闭前，CLI 必须以“unsupported target”提前失败，不能在启动 TUI 后才暴露 Python import 或进程错误。

## 3. 制品模型

### 3.1 npm 包

`@typed-code/cli` 的 `optionalDependencies` 必须精确固定五个 companion 版本：

```json
{
  "optionalDependencies": {
    "@typed-code/server-darwin-arm64": "X.Y.Z",
    "@typed-code/server-darwin-x64": "X.Y.Z",
    "@typed-code/server-linux-arm64": "X.Y.Z",
    "@typed-code/server-linux-x64": "X.Y.Z",
    "@typed-code/server-win32-x64": "X.Y.Z"
  }
}
```

每个 companion `package.json` 必须声明精确的 `os`、`cpu` 和 `files`：

```json
{
  "name": "@typed-code/server-linux-x64",
  "version": "X.Y.Z",
  "os": ["linux"],
  "cpu": ["x64"],
  "files": ["bin/typed-code-server"]
}
```

Windows 使用 `bin/typed-code-server.exe`。包内只放该平台运行所需文件、许可证和最小元数据，不放源码、密钥、测试缓存或构建机路径。

### 3.2 GitHub Release 制品

建议固定命名，禁止发布后原地替换：

```text
typed-code-server-X.Y.Z-darwin-arm64.dmg
typed-code-server-X.Y.Z-darwin-x64.dmg
typed-code-server-X.Y.Z-linux-arm64.tar.gz
typed-code-server-X.Y.Z-linux-x64.tar.gz
typed-code-server-X.Y.Z-win32-x64.zip
service-manifest.v1.json
service-manifest.v1.json.sig
SHA256SUMS
SHA256SUMS.sig
sbom-X.Y.Z.spdx.json
provenance-X.Y.Z.intoto.jsonl
```

macOS DMG 保存已签名、已 notarize、已 staple 的精确二进制。Linux tarball 和 Windows zip 保留可执行位或平台等价元数据。npm companion 包和离线制品可使用不同容器格式，但其中服务可执行文件的 digest 必须能追溯到同一次构建输出。

### 3.3 签名 release manifest

`service-manifest.v1.json` 至少包含：

- manifest schema 版本、release 版本、channel、生成时间和过期时间；
- CLI、SDK、协议和事件 schema 的兼容范围；
- 每个目标的 URL、长度、SHA-256、归档格式、内部可执行文件路径；
- macOS notarization、Windows Authenticode 和 Linux 签名状态；
- Ed25519 key id；
- 可选的最低操作系统/glibc 约束和撤销信息。

manifest 使用 canonical JSON 后由离线或受保护的 Ed25519 密钥签名。客户端内置公钥信任根，只在签名、目标、版本、长度、digest 和兼容性全部通过后解压。密钥轮换采用重叠信任期；不得只从 manifest 自己读取新的可信公钥。

## 4. 构建策略

### 4.1 原生构建，不交叉编译

冻结的 Python 服务包含解释器、原生依赖和平台加载器，五个目标必须在相同 OS/CPU 的 runner 上构建：

| Job | Runner 示例 | 输出 |
|---|---|---|
| `build-darwin-arm64` | Apple Silicon macOS runner | arm64 Mach-O、DMG、npm tgz |
| `build-darwin-x64` | Intel macOS runner | x86_64 Mach-O、DMG、npm tgz |
| `build-linux-arm64` | 原生 ARM64 Linux runner | aarch64 ELF、tar.gz、npm tgz |
| `build-linux-x64` | x64 Linux runner | x86-64 ELF、tar.gz、npm tgz |
| `build-win32-x64` | x64 Windows runner | PE32+ `.exe`、zip、npm tgz |

Runner label 会随 GitHub Actions 供应变化；workflow 必须固定经过验证的 image，而不是假设示例 label 永久可用。若托管 runner 不满足架构或系统基线，使用受控的 ephemeral self-hosted runner。

### 4.2 构建输入固定

所有 job 必须固定并记录：

- 仓库 commit 和签名 tag；
- Python、uv、Node、npm、PyInstaller 及 hooks 版本；
- `uv.lock` 和 npm lockfile；
- runner image 标识、OS、CPU、glibc 或 SDK 版本；
- `SOURCE_DATE_EPOCH`；
- OpenAPI 和 SSE event schema digest。

构建前必须从干净 checkout 安装锁定依赖。不得从维护者本地 venv、全局 site-packages 或未记录的缓存收集模块。

### 4.3 可复现性边界

至少连续构建两份未签名制品并比较文件清单和 digest。Mach-O/PE 签名、notarization ticket、timestamp 和归档元数据可能引入预期差异，因此：

1. 先验证未签名构建的可复现部分。
2. 只对被接受的可执行文件签名一次。
3. 签名、notarize、staple 后不再重新打包或修改该可执行文件。
4. 记录签名前后 digest 和转换步骤。

## 5. 平台签名与验证

### 5.1 macOS

每个架构独立执行：

1. 用 Developer ID Application 证书签名所有收集的 Mach-O，最后签名主可执行文件。
2. `codesign --verify --deep --strict`。
3. 对精确的发布归档提交 Apple notarization。
4. 等待成功结果，将 ticket staple 到 DMG 或可验证载体。
5. 在没有源码、Python、uv 和 npm companion 缓存的 clean host 上执行：

```bash
codesign --verify --deep --strict /path/to/typed-code-server
spctl --assess --type execute --verbose /path/to/typed-code-server
xcrun stapler validate /path/to/typed-code-server-X.Y.Z-darwin-ARCH.dmg
```

不得通过关闭 Gatekeeper、移除 quarantine 或要求用户执行 `xattr -dr` 来“修复”发布。

### 5.2 Linux

Linux 没有统一的系统代码签名信任链。强制要求：

- release manifest Ed25519 签名有效；
- tarball 与内部 ELF 的 SHA-256 匹配；
- ELF 架构和动态依赖符合目标基线；
- 可选附加 Sigstore/cosign 签名和 GitHub OIDC provenance，但不能替代客户端内置的 manifest 信任根。

验证至少包括：

```bash
file typed-code-server
ldd typed-code-server
readelf -h typed-code-server
```

并在最低支持 glibc 的 clean container/VM 上实际启动、认证、创建 session 和执行 Bash workspace tool。

### 5.3 Windows

1. 使用 Azure Trusted Signing、EV 证书或组织批准的 HSM-backed 证书对 `.exe` 签名。
2. 使用可信 RFC 3161 timestamp server；证书私钥不得作为普通仓库 secret 导出。
3. 在 clean host 验证：

```powershell
Get-AuthenticodeSignature .\typed-code-server.exe
signtool verify /pa /all /v .\typed-code-server.exe
```

4. 验证 Defender/SmartScreen、非管理员用户安装、长路径、空格/非 ASCII workspace、Ctrl+C、服务停止和升级回滚。

## 6. CI/CD 工作流

建议拆为三个 workflow，避免一个 job 同时拥有全部供应链权限：

```text
release-prepare.yml
  └─ 版本/协议/变更日志/契约/质量门禁

release-build.yml
  ├─ darwin-arm64 ─┐
  ├─ darwin-x64   ─┤
  ├─ linux-arm64  ─┼─> attest + upload immutable workflow artifacts
  ├─ linux-x64    ─┤
  └─ win32-x64   ─┘

release-publish.yml (protected environment)
  ├─ verify every target and digest
  ├─ create draft GitHub Release
  ├─ sign canonical manifest/checksums
  ├─ publish platform npm packages
  ├─ publish SDK
  ├─ publish GitHub Release + manifest
  ├─ publish CLI last
  └─ clean-install smoke on every target
```

### 6.1 触发与权限

- 只允许签名的 `vX.Y.Z` tag 或受保护的手动 promotion 触发 stable 发布。
- build jobs 默认 `contents: read`，无 npm、Apple、Windows 或 manifest signing 权限。
- publish job 使用 GitHub protected environment、审批和最小权限 OIDC。
- npm 使用 trusted publishing/短期 OIDC 和 `npm publish --provenance --access public`，不使用长期 automation token；若 npm 目标尚不支持 trusted publishing，则将受限 token 作为临时例外并记录轮换策略。
- Apple 和 Windows 签名权限拆分，任何一个 build runner 泄露都不能签另一个平台或 release manifest。

### 6.2 发布顺序

1. 验证 tag、所有 lockstep version、clean worktree、生成契约和 changelog。
2. 运行仓库完整质量门禁。
3. 并行完成五个平台 build、平台签名和平台 smoke。
4. 汇总制品；校验架构、版本、协议、schema、包内容和 digest。
5. 创建 draft GitHub Release，上传不可变平台制品。
6. 生成并签名 canonical manifest、`SHA256SUMS`、SBOM 和 provenance。
7. 发布五个 companion npm 包。
8. 发布 `@typed-code/sdk`。
9. 发布 GitHub Release，使签名 manifest 和离线制品可访问。
10. **最后发布 `@typed-code/cli`**，确保用户安装 CLI 时 companion 和 manifest 已经存在。
11. 从公开 registry 和公开 release URL 执行全平台 clean-install smoke。
12. promotion 成功后更新 stable channel 指针；失败时保持旧版本，不自动部分发布。

npm 包一旦发布不得覆盖同版本。GitHub Release asset 也不得原地替换；任何位变化都必须发布新 patch 版本。

## 7. 发布门禁

### 7.1 仓库质量门禁

当前基础命令：

```bash
uv run ruff check src tests packaging
uv run ty check src tests packaging
uv run pytest -q
npm run check
npm run test:unit
uv run typed-code export-contracts
```

CI 还必须确认导出契约后仓库没有未提交差异，并严格验证相关 OpenSpec change。

### 7.2 包与协议门禁

每个目标必须验证：

- CLI、SDK、Python 项目、companion 包和二进制报告相同的 `X.Y.Z`；
- CLI 只暴露 `typed-code` bin；
- companion 包只匹配自己的 `os`/`cpu`；
- npm tarball 无密钥、绝对构建路径、venv、缓存和多余二进制；
- companion 可执行文件权限正确；
- OpenAPI、event schema、SDK protocol constant 和 server protocol 一致；
- 安装器拒绝错误架构、错误版本、错误 digest、错误签名、过期 manifest 和路径穿越归档。

### 7.3 Clean-install smoke

每个平台必须从全新 VM 或 ephemeral runner 执行，不能复用 build workspace：

1. 只安装受支持 Node.js；不预装 Python、uv 或 typed-code 源码。
2. 从公开 npm registry 安装 `@typed-code/cli@X.Y.Z`。
3. 验证解析到正确平台 companion。
4. 执行 `typed-code service status/start/check`。
5. 使用受控 fake provider 或专用 smoke provider：创建 session、接收 text/thinking streaming、执行只读工具、执行需审批工具、完成响应。
6. 第二个 CLI attach 同一 session；第一个退出后服务和 run 继续；第二个能重连并收到 authoritative replay。
7. 升级上一 stable 版本，确认配置、credentials、数据库、session 和 workspace 不丢失。
8. 注入候选启动失败，验证事务回滚到旧版本。
9. 执行 uninstall，确认程序文件移除且默认保留用户数据。
10. macOS 额外验证离线 stapled-DMG；Linux 验证最低 glibc；Windows 分别验证 Bash 缺失时的可执行安装指引、Git for Windows Bash capability probe、WSL Bash 拒绝、显式 Bash 路径、Authenticode、ACL 和进程树取消。

真实 Provider smoke 可作为受保护的附加门禁，但不得输出 API key，也不能替代 deterministic fake-provider 流程。

### 7.4 验收结论

只有以下条件全部成立才可标记 stable：

- 五个目标均构建、签名并在 clean host 通过；
- release manifest 和 checksum 签名有效；
- npm 与 GitHub Release 公网下载可用；
- upgrade/rollback/uninstall 通过；
- 无未决的高危安全问题或平台阻塞项；
- 发布 evidence 记录了 runner、工具链、版本、digest、签名、notarization、测试结果和已知限制。

如任一必需目标失败，本次 stable release 整体失败。需要允许部分平台发布时，必须预先定义不同 channel 或产品版本策略，不能在发布途中临时缩小范围。

## 8. 发布负责人操作清单

### 发布前

- [ ] 合并并验证对应 OpenSpec change。
- [ ] 更新 changelog 和升级/迁移说明。
- [ ] 将 Python、SDK、CLI 和五个 companion 版本统一为 `X.Y.Z`。
- [ ] 更新 CLI 的五个精确 optional dependency 版本。
- [ ] 重新导出 OpenAPI 和 event schema。
- [ ] 确认 manifest key、Apple notarization 和 Windows signing 服务可用。
- [ ] 确认 Windows clean host 可通过官方 Git for Windows 安装包或 `winget install --id Git.Git -e --source winget` 满足 Bash 前提，且缺失/无效/WSL-only 场景会在本地服务启动前给出诊断。
- [ ] 确认上一 stable 版本可用于 upgrade/rollback 测试。

### 构建与发布

- [ ] 创建签名的 `vX.Y.Z` tag。
- [ ] 确认 prepare 与五个平台 build job 全绿。
- [ ] 审核每个平台的架构、包内容、签名和 smoke evidence。
- [ ] 批准 protected publish environment。
- [ ] 确认 companion → SDK → GitHub Release/manifest → CLI 的发布顺序完成。
- [ ] 从公开源执行五个平台 clean-install smoke。

### 发布后

- [ ] 验证 `npm view @typed-code/cli@X.Y.Z` 及五个 optional dependency。
- [ ] 验证 GitHub Release 的所有 URL、digest 和签名。
- [ ] 从上一 stable 版本执行一次真实 upgrade/rollback 演练。
- [ ] 观察安装失败率、启动失败、签名拒绝和协议不兼容告警。
- [ ] 保存 release evidence，宣布 stable。

## 9. 故障、撤销与回滚

- **build 阶段失败：** 不发布任何包，修复后重新创建构建；同一 tag 不指向不同 commit。
- **部分 npm 包已发布：** 不 unpublish、不覆盖。暂停 CLI 发布，标记已发平台包为 deprecated，修复后升 patch 版本完整重发。
- **CLI 已发布但发现严重问题：** 从 stable manifest/channel 移除有问题版本，发布修复 patch；对 npm 旧版本执行 `npm deprecate` 并给出明确升级信息。
- **签名密钥疑似泄露：** 立即冻结发布，发布撤销信息，轮换到预先信任的 key；不能靠更新同一远程 manifest 自证新 key。
- **迁移失败：** 保留旧 active pointer、恢复迁移前数据库备份并重新启动旧服务。候选版本在健康检查前不得成为 active。
- **平台单独故障：** stable 默认是原子多平台发布；除非事先存在平台独立 channel，否则按整个版本处理，不临时隐藏失败目标。

## 10. 当前仓库到目标状态的实施顺序

1. 完成现有 `add-service-install-upgrade-commands` 变更，建立签名 manifest、事务式 install/upgrade/rollback/uninstall 和 active pointer。
2. 将现有 `release-macos.yml` 拆分为无发布权限的多平台 build 与受保护 publish；保留 Darwin ARM64 已验证逻辑。
3. 增加四个 companion workspace 包和 CLI 精确 optional dependencies。
4. 增加 macOS x64 和 Linux 双架构原生冻结、归档、签名/校验与 clean-host job。
5. 解决 2.2 的 Windows 运行时、路径、权限、锁、进程和 Shell 设计，再增加 Windows x64 build/sign/smoke。
6. 增加 manifest 聚合、SBOM、provenance、npm trusted publishing 和原子 promotion。
7. 用全平台 clean-install、upgrade、rollback、offline 和安全测试关闭发布门禁后，才更新 README 的生产支持声明。

在这七步完成前，维护者可以继续发布当前 Darwin ARM64 preview，但不能把本文的目标矩阵描述为已经交付。