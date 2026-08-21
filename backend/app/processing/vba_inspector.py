import hashlib
from pathlib import Path
from typing import Any


def inspect_vba(path: Path) -> dict[str, Any]:
    report: dict[str, Any] = {
        "contains_macros": False,
        "modules": [],
        "indicators": [],
        "inspection_status": "not_present",
    }
    try:
        from oletools.olevba import VBA_Parser

        parser = VBA_Parser(str(path))
        try:
            report["contains_macros"] = bool(parser.detect_vba_macros())
            if not report["contains_macros"]:
                return report
            report["inspection_status"] = "completed"
            for _filename, stream_path, module_name, code in parser.extract_macros():
                binary = code if isinstance(code, bytes) else str(code).encode("utf-8", "replace")
                report["modules"].append(
                    {
                        "module_name": module_name,
                        "stream_path": stream_path,
                        "line_count": binary.count(b"\n") + 1,
                        "sha256": hashlib.sha256(binary).hexdigest(),
                    }
                )
            for indicator_type, keyword, description in parser.analyze_macros():
                report["indicators"].append(
                    {
                        "type": indicator_type,
                        "keyword": keyword,
                        "description": description,
                        "severity": "high"
                        if indicator_type in {"AutoExec", "Suspicious", "IOC"}
                        else "medium",
                    }
                )
        finally:
            parser.close()
    except Exception as error:
        report["inspection_status"] = "failed"
        report["error"] = str(error)
    return report
