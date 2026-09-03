from levels.koali_support import run_validation

DEFAULT_PROFILE_COMMAND = ["uv", "run", "--frozen", "pytest", "-q", "tests/profiles"]

def run(cfg, report):
    command = cfg.get("profiles_command") or DEFAULT_PROFILE_COMMAND
    run_validation(cfg, report, command_key="profiles", command_override=command, required=False, include_gate_reports=False,
                   recommendation="Inspect the kOA-Linux tests/profiles pytest output and uv environment.")
