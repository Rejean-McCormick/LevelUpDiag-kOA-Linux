from levels.koali_support import run_validation

def run(cfg, report):
    run_validation(cfg, report, command_key="security", required=False, blocked_marker="security: blocked", include_gate_reports=True,
                   recommendation="Inspect the captured kOA-Linux security gate report to identify failures or unmet prerequisites.")
