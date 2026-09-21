# roles/common — NTP / DNS / Syslog

Vendor-neutral base settings for every IOS host (phase 1, low risk).

- Input: `netaut_common` (`ntp_servers`, `dns_servers`, `syslog_servers`).
- Null default fails closed via pre-assert (INV-004).
- Modules only, no CLI strings (INV-003): `ios_ntp_global`, `ios_system`,
  `ios_logging_global`, all `state: merged`.
- Test play: `roles/common/tests/test.yml` (syntax-check in CI).
