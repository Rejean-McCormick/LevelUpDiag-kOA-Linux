from levels.koali_support import run_validation

def run(cfg, report):
    run_validation(cfg, report, command_key="integrations", required=False, include_gate_reports=False,
                   recommendation="Inspect the configured public kOA-Linux integration validation.")
