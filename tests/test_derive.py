import unittest

from oosc.schema import DomainDef, ParamDef, TableDef, ToolDef
from oosc.world.derive import EffectKind, WorldSpec


def devops_domain() -> DomainDef:
    return DomainDef(
        name="devops",
        policy="Confirm irreversible actions.",
        tools=[
            ToolDef(name="list_snapshots"),
            ToolDef(name="restart_instance", params=[ParamDef(name="instance_id", required=True)]),
            ToolDef(
                name="delete_snapshot",
                short_desc="Delete a snapshot after explicit confirmation.",
                params=[ParamDef(name="snapshot_id", required=True)],
            ),
        ],
        tables=[
            TableDef(name="instances", records=[{"instance_id": "inst_1", "status": "running"}]),
            TableDef(name="snapshots", records=[{"snapshot_id": "snap_1", "status": "ready"}]),
        ],
    )


class DeriveTests(unittest.TestCase):
    def test_effects_are_derived_for_unseen_domain(self):
        effects = WorldSpec(devops_domain()).effects
        self.assertEqual(effects["list_snapshots"].kind, EffectKind.READ)
        self.assertEqual(effects["restart_instance"].kind, EffectKind.WRITE)
        self.assertEqual(effects["delete_snapshot"].bindings[0].table_hint, "snapshots")


if __name__ == "__main__":
    unittest.main()
