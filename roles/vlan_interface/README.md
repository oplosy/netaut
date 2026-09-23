# roles/vlan_interface — VLANs + access interfaces

VLAN and L2 interface state (phase 2).

- Inputs: `netaut_vlans` (`id`, `name`), `netaut_interfaces`
  (`name`, `description`, `access_vlan`). Null defaults fail closed.
- `main.yml` asserts inputs and vendor, then dispatches to `tasks/<vendor>.yml`.
  Modules only (INV-003):
  - `ios.yml` / `eos.yml`: `*_vlans`, `*_l2_interfaces` (mode access), merged per entry.
  - `srlinux.yml`: VLAN = mac-vrf `vlan-<id>` (description = name); access port =
    `vlan-tagging` + bridged, untagged subinterface 0 in that mac-vrf.
    Moving a port between VLANs fails the commit (ADR-007 known gap).
- Raw twins: `templates/<vendor>/vlan_interface.j2` must render the same config.
- Tests: `pytest roles/vlan_interface/tests/ -q` (rerender + content per vendor).
