# roles/common — NTP / DNS / Syslog

Vendor-neutral base settings for every lab host (phase 1, low risk).

- Input: `netaut_common` (`ntp_servers`, `dns_servers`, `syslog_servers`).
- Null default fails closed via pre-assert (INV-004); so does an unsupported vendor.
- `main.yml` holds the asserts and dispatches to `tasks/<vendor>.yml`
  (vendor from `ansible_network_os`). Modules only, no CLI strings (INV-003):
  - `ios.yml`: `ios_ntp_global`, `ios_system`, `ios_logging_global`.
  - `eos.yml`: `eos_ntp_global`, `eos_system`, `eos_logging_global`.
  - `srlinux.yml`: `nokia.srlinux.config` on `/system/ntp`, the containerlab
    `dns-instance` server-list (replaced), `/system/logging`; `save_when: never`.
    Instances come from `netaut_srlinux_mgmt_instance` / `netaut_srlinux_dns_instance`.
- Test play: `roles/common/tests/test.yml` (syntax-check in CI).
