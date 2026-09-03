from levels.koali_support import run_validation

def run(cfg, report):
    run_validation(cfg, report, command_key="docs", required=True, include_gate_reports=False,
                   recommendation="Inspect the public kOA-Linux documentation validator output.")
