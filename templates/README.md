# templates/ — vendor render layer

Raw per-vendor Jinja2. Business logic lives in roles; templates carry only
syntax (INV-003). Both paths consume the same intended-state shape, so role
and template converge on one effective config.

- `ios/vlan_interface.j2` — VLANs + access interfaces.
- `ios/routing/static.j2` — statics + prefix-lists + route-maps.
- New vendor = new directory + tests. Never fork role logic per vendor.
