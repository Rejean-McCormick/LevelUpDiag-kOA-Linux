from levels.koali_support import run_validation

def run(cfg, report):
    run_validation(cfg, report, command_key="system", required=False, blocked_marker="system: blocked", include_gate_reports=True,
                   recommendation="Inspect the captured kOA-Linux system gate report to identify failures or unmet prerequisites.")
