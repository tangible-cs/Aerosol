from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]


def test_http_only_vm_keeps_ubuntu_dns_resolver_running():
    tasks = yaml.safe_load((ROOT / "ansible/tasks/pixi.yml").read_text())
    dns_tasks = [task for task in tasks if "resolved" in task["name"]]
    assert len(dns_tasks) == 3
    for task in dns_tasks:
        conditions = task.get("when", [])
        if isinstance(conditions, str):
            conditions = [conditions]
        assert "not (local_http_only | default(false) | bool)" in conditions, task["name"]


def test_local_install_provides_the_service_startup_reclaim_helper():
    plays = yaml.safe_load((ROOT / "ansible/local_setup.yml").read_text())
    imports = [task["import_tasks"] for play in plays for task in play["tasks"] if "import_tasks" in task]
    assert imports.index("tasks/reclaim_pixi.yml") < imports.index("tasks/pixi.yml")
