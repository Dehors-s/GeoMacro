from datetime import datetime, timedelta

from geomacro.code_generator import CodeGenerator
from geomacro.dependency_analyzer import DependencyAnalyzer
from geomacro.models import Parameter, StandardEvent
from geomacro.script_validator import ScriptValidator
from geomacro.variable_extractor import VariableExtractor


def test_pipeline_e2e_builds_dependency_and_generates_script():
    t0 = datetime(2026, 4, 20, 10, 0, 0)

    buffer_event = StandardEvent(
        event_id="evt_buffer",
        tool_name="Buffer",
        tool_path="analysis/Buffer",
        timestamp=t0,
        is_success=True,
        ordered_params=[
            Parameter(name="in_features", value=r"D:\\input\\roads.shp", direction="input", is_path=True),
            Parameter(
                name="out_feature_class",
                value=r"D:\\scratch\\roads_buf.shp",
                direction="output",
                is_path=True,
            ),
            Parameter(name="buffer_distance_or_field", value="100 Meters", direction="input", is_path=False),
        ],
        outputs=[r"D:\\scratch\\roads_buf.shp"],
    )

    clip_event = StandardEvent(
        event_id="evt_clip",
        tool_name="Clip",
        tool_path="analysis/Clip",
        timestamp=t0 + timedelta(seconds=1),
        is_success=True,
        ordered_params=[
            Parameter(name="in_features", value=r"D:\\scratch\\roads_buf.shp", direction="input", is_path=True),
            Parameter(name="clip_features", value=r"D:\\input\\boundary.shp", direction="input", is_path=True),
            Parameter(name="out_feature_class", value=r"D:\\output\\roads_clip.shp", direction="output", is_path=True),
        ],
        outputs=[r"D:\\output\\roads_clip.shp"],
    )

    events = [buffer_event, clip_event]
    dependencies = DependencyAnalyzer().build(events)

    assert dependencies[1].depends_on == ["evt_buffer"]

    extraction = VariableExtractor().extract(events)
    script_text = CodeGenerator().generate(events, extraction)
    report = ScriptValidator().validate(script_text, extraction)

    assert report.ok
    assert "arcpy.analysis.Buffer" in script_text
    assert "arcpy.analysis.Clip" in script_text
