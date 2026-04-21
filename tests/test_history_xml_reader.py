from pathlib import Path

from geomacro.history_xml_reader import discover_history_directories, load_history_items_from_xml


def test_load_history_items_from_xml_parses_result_view(tmp_path: Path):
    history_dir = tmp_path / "history"
    history_dir.mkdir(parents=True)

    xml_path = history_dir / "H20260421_000001.xml"
    xml_path.write_text(
        """<?xml version=\"1.0\" encoding=\"utf-8\" ?>
<ResultViews>
  <ResultView Tool='Buffer'>
    <CommandLine>Buffer_analysis roads roads_buf 100 Meters</CommandLine>
    <ToolSource>analysis/Buffer</ToolSource>
    <StartTime>Tue Apr 21 14:22:13 2026</StartTime>
    <Parameters>
      <Inputs>
        <Parameter Label='in_features' Type='Layer'>roads</Parameter>
        <Parameter Label='distance' Type='Scalar'>100 Meters</Parameter>
      </Inputs>
      <Outputs>
        <Parameter Label='out_feature_class' Type='Dataset'>roads_buf</Parameter>
      </Outputs>
      <LayerInfo>
        <Layer Name='roads'>D:\\input\\roads.shp</Layer>
        <Layer Name='roads_buf'>D:\\scratch\\roads_buf.shp</Layer>
      </LayerInfo>
    </Parameters>
    <EndTime>成功 在 Tue Apr 21 14:22:14 2026 (经历的时间: 1.0 秒)</EndTime>
  </ResultView>
</ResultViews>
""",
        encoding="utf-8",
    )

    items = load_history_items_from_xml([history_dir], max_files=10, lookback_hours=0)

    assert len(items) == 1
    item = items[0]
    assert item["ToolName"] == "Buffer"
    assert item["ToolPath"] == "analysis/Buffer"
    assert item["Succeeded"] is True
    assert len(item["Parameters"]) == 3
    assert item["Parameters"][0]["value"] == r"D:\input\roads.shp"
    assert item["Outputs"] == [r"D:\scratch\roads_buf.shp"]


def test_discover_history_directories_keeps_existing_explicit_dir(tmp_path: Path):
    history_dir = tmp_path / "history"
    history_dir.mkdir(parents=True)

    discovered = discover_history_directories([str(history_dir)])

    assert history_dir.resolve() in discovered
