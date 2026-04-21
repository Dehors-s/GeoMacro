from datetime import datetime

from geomacro.code_generator import CodeGenerator
from geomacro.models import Parameter, StandardEvent
from geomacro.variable_extractor import VariableExtractor


def test_code_generator_produces_valid_python_script_for_buffer():
    event = StandardEvent(
        event_id="evt_buffer",
        tool_name="Buffer",
        tool_path="analysis/Buffer",
        timestamp=datetime(2026, 4, 20, 10, 0, 0),
        is_success=True,
        ordered_params=[
            Parameter(name="in_features", value=r"D:\\input\\roads.shp", direction="input", is_path=True),
            Parameter(
                name="out_feature_class",
                value=r"D:\\output\\roads_buffer.shp",
                direction="output",
                is_path=True,
            ),
            Parameter(name="buffer_distance_or_field", value="100 Meters", direction="input", is_path=False),
        ],
    )

    extraction = VariableExtractor().extract([event])
    script_text = CodeGenerator().generate([event], extraction)

    assert "arcpy.analysis.Buffer" in script_text
    assert "context['input_path_1']" in script_text
    assert "context['output_path_1']" in script_text

    compile(script_text, "generated.py", "exec")
