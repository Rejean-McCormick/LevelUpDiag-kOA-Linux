from levels.koali_support import run_validation

def run(cfg, report):
    run_validation(cfg, report, command_key="offline", required=False, blocked_marker="offline: blocked", include_gate_reports=True,
                   recommendation="Inspect the captured kOA-Linux offline gate report to identify failures or unmet prerequisites.")
