`seccomp_profile.json` is based on Microsoft Playwright v1.64.1:
https://github.com/microsoft/playwright/blob/v1.64.1/utils/docker/seccomp_profile.json

Playwright is licensed under Apache-2.0:
https://github.com/microsoft/playwright/blob/v1.64.1/LICENSE
The full license is included in `LICENSE.playwright`.

Local modification: allow `chroot` alongside the namespace syscalls. Chromium uses
it inside its user namespace. The usual capability-conditioned Docker rule would
otherwise block sandbox startup when all outer container capabilities are dropped.
This does not add CAP_SYS_CHROOT or SYS_ADMIN to the container.

It retains a deny-by-default syscall policy while permitting the user namespaces
needed by Chromium's sandbox. Keep it under review when updating browser versions.
The container never adds SYS_ADMIN, privileged mode, host networking, a Docker socket,
or `--no-sandbox`. If the host cannot support sandboxed Chromium, startup must fail.
