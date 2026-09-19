import importlib.machinery
import importlib.util
from pathlib import Path
from types import SimpleNamespace
import unittest
from levelupdiag_core.manifest import load_manifest

ROOT=Path(__file__).resolve().parents[1]
loader=importlib.machinery.SourceFileLoader('console_test',str(ROOT/'LEVELUPDIAG_CONSOLE.pyw'))
spec=importlib.util.spec_from_loader(loader.name,loader)
module=importlib.util.module_from_spec(spec);loader.exec_module(module)

class ConsolePresetTests(unittest.TestCase):
    def test_qemu_preset_keeps_identity_despite_matching_stabilization_levels(self):
        manifest=load_manifest(ROOT)
        stub=SimpleNamespace(manifest=manifest, selected_campaign='audit-qemu')
        selected=manifest['campaigns']['audit-qemu']['levels']
        self.assertEqual(module.LevelUpDiagConsole._campaign_for_selected(stub,selected,'debug'),'audit-qemu')
