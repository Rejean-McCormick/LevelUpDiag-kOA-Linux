from levels.koali_support import run_validation

def run(cfg, report):
    run_validation(cfg, report, command_key="contracts", required=True, include_gate_reports=True,
                   recommendation="Inspect the kOA-Linux contracts gate output and gate report.")
