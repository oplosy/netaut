# roles/vlan_interface — VLANs + access interfaces

VLAN and L2 interface state (phase 2).

- Inputs: `netaut_vlans` (`id`, `name`), `netaut_interfaces`
  (`name`, `description`, `access_vlan`). Null defaults fail closed.
- Modules only (INV-003): `ios_vlans`, `ios_l2_interfaces`, merged per entry.
- Raw twin: `templates/ios/vlan_interface.j2` must render the same config.
- Tests: `pytest roles/vlan_interface/tests/ -q` (rerender + IOS content).
