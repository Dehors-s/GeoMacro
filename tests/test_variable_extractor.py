from datetime import datetime

from geomacro.models import Parameter, StandardEvent
from geomacro.variable_extractor import VariableExtractor


def test_variable_extractor_marks_path_params_as_variables():
    event = StandardEvent(
        event_id="evt_1",
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

    extractor = VariableExtractor()
    result = extractor.extract([event])

    assert ("evt_1", "in_features") in result.variable_slots
    assert ("evt_1", "out_feature_class") in result.variable_slots
    assert result.variable_slots[("evt_1", "in_features")].name == "input_path_1"
    assert result.variable_slots[("evt_1", "out_feature_class")].name == "output_path_1"
    assert result.constants[("evt_1", "buffer_distance_or_field")] == "100 Meters"
