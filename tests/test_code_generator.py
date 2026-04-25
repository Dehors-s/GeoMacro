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
    assert "in_features=working" in script_text
    assert "out_buffer" in script_text
    assert "buffer_distance_or_field='100 Meters'" in script_text

    compile(script_text, "generated.py", "exec")


def test_code_generator_single_non_inplace_can_compile():
    event = StandardEvent(
        event_id="evt_clip",
        tool_name="Clip",
        tool_path="analysis/Clip",
        timestamp=datetime(2026, 4, 20, 10, 0, 0),
        is_success=True,
        ordered_params=[
            Parameter(name="in_features", value=r"D:\\input\\roads.shp", direction="input", is_path=True),
            Parameter(name="clip_features", value=r"D:\\data\\boundary.shp", direction="input", is_path=True),
            Parameter(
                name="out_feature_class",
                value=r"D:\\output\\roads_clip.shp",
                direction="output",
                is_path=True,
            ),
        ],
    )

    extraction = VariableExtractor().extract([event])
    script_text = CodeGenerator().generate([event], extraction)

    assert "arcpy.analysis.Clip" in script_text
    assert "in_features=working" in script_text
    assert "FIXED_CLIP_FEATURES" in script_text
    assert "out_clip" in script_text

    compile(script_text, "generated.py", "exec")


def test_code_generator_inplace_tool_emits_copy():
    event = StandardEvent(
        event_id="evt_calcfield",
        tool_name="CalculateField",
        tool_path="management/CalculateField",
        timestamp=datetime(2026, 4, 20, 10, 0, 0),
        is_success=True,
        ordered_params=[
            Parameter(name="in_table", value=r"D:\\data\\county.shp", direction="input", is_path=True),
            Parameter(name="field", value="Y", direction="input", is_path=False),
            Parameter(name="expression", value="[Y] *300*300/1000000", direction="input", is_path=False),
            Parameter(name="expression_type", value="VB", direction="input", is_path=False),
            Parameter(name="out_table", value=r"D:\\data\\county.shp", direction="output", is_path=True),
        ],
    )

    extraction = VariableExtractor().extract([event])
    script_text = CodeGenerator().generate([event], extraction)

    assert "_copy_features_for_inplace" in script_text
    assert "stg_calculatefield" in script_text
    assert "in_table=working" in script_text
    assert "expression='[Y] *300*300/1000000'" in script_text or "expression=\"[Y] *300*300/1000000\"" in script_text

    compile(script_text, "generated.py", "exec")
