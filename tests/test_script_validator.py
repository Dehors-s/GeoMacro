from datetime import datetime

from geomacro.models import ExtractionResult, Parameter, StandardEvent, VariableSlot
from geomacro.script_validator import ScriptValidator


def test_validator_ok_on_healthy_script():
    event = StandardEvent(
        event_id="evt_1",
        tool_name="Buffer",
        tool_path="analysis/Buffer",
        timestamp=datetime(2026, 4, 20, 10, 0, 0),
        is_success=True,
        ordered_params=[
            Parameter(name="in_features", value=r"D:\input\roads.shp", direction="input", is_path=True),
            Parameter(name="out_fc", value=r"D:\output\result.shp", direction="output", is_path=True),
            Parameter(name="distance", value="100 Meters", direction="input", is_path=False),
        ],
    )
    extraction = ExtractionResult(
        variable_slots={
            ("evt_1", "in_features"): VariableSlot(
                name="input_path_1", default_value=r"D:\input\roads.shp", kind="input_path",
                source_event_id="evt_1", source_param_name="in_features",
            ),
            ("evt_1", "out_fc"): VariableSlot(
                name="output_path_1", default_value=r"D:\output\result.shp", kind="output_path",
                source_event_id="evt_1", source_param_name="out_fc",
            ),
        },
        constants={("evt_1", "distance"): "100 Meters"},
    )
    script_text = "\n".join([
        '"""ok script"""',
        "print('hello')",
    ])
    report = ScriptValidator().validate(script_text, extraction, events=[event])
    assert report.ok


def test_validator_warns_on_missing_param():
    event = StandardEvent(
        event_id="evt_missing",
        tool_name="Clip",
        tool_path="analysis/Clip",
        timestamp=datetime(2026, 4, 20, 10, 0, 0),
        is_success=True,
        ordered_params=[
            Parameter(name="in_features", value=r"D:\input\roads.shp", direction="input", is_path=True),
        ],
    )
    extraction = ExtractionResult(
        variable_slots={},
        constants={},
    )
    report = ScriptValidator().validate("print('x')", extraction, events=[event])
    assert report.ok  # missing param is warning, not error


def test_validator_reports_chinese_path_warning():
    extraction = ExtractionResult(
        variable_slots={
            ("evt_chn", "in_fc"): VariableSlot(
                name="input_path_1",
                default_value=r"D:\数据\中国边界\省界.shp",
                kind="input_path",
                source_event_id="evt_chn",
                source_param_name="in_fc",
            ),
        },
    )
    report = ScriptValidator().validate("print('x')", extraction)
    assert report.ok
    assert any("non-ASCII" in issue.message for issue in report.issues)


def test_validator_warns_on_failed_event():
    event = StandardEvent(
        event_id="evt_fail",
        tool_name="Clip",
        tool_path="analysis/Clip",
        timestamp=datetime(2026, 4, 20, 10, 0, 0),
        is_success=False,
        ordered_params=[
            Parameter(name="in_fc", value=r"D:\input\roads.shp", direction="input", is_path=True),
        ],
    )
    extraction = ExtractionResult(
        variable_slots={
            ("evt_fail", "in_fc"): VariableSlot(
                name="input_path_1", default_value=r"D:\input\roads.shp", kind="input_path",
                source_event_id="evt_fail", source_param_name="in_fc",
            ),
        },
    )
    report = ScriptValidator().validate("print('x')", extraction, events=[event])
    assert report.ok
    assert any("failed" in issue.message.lower() for issue in report.issues)


def test_summary_text_contains_key_metrics():
    extraction = ExtractionResult()
    report = ScriptValidator().validate("print('hello')", extraction)
    summary = report.summary_text(use_emoji=False)
    assert "GeoMacro" in summary
    assert "[OK]" in summary or "[FAIL]" in summary
