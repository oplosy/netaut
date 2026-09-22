# templates/ — vendor render layer

Raw per-vendor Jinja2. Business logic lives in roles; templates carry only
syntax (INV-003). Both paths consume the same intended-state shape, so role
and template converge on one effective config.

- `ios/vlan_interface.j2` — VLANs + access interfaces.
- `ios/routing/static.j2` — statics + prefix-lists + route-maps.
- `eos/vlan_interface.j2`, `eos/routing/static.j2` — EOS twins (T-008):
  same context, EOS 3-space indentation.
- New vendor = new directory + tests. Never fork role logic per vendor.
- `scripts/render_idempotency.py --vendor <v>` renders every template of
  that vendor for every device with `platform: <v>`; zero devices fails.
