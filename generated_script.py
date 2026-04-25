"""GeoMacro generated batch pipeline."""
from pathlib import Path
import os
import sys
import arcpy

arcpy.env.overwriteOutput = True

def _copy_features_for_inplace(src, dst):
    if Path(src).suffix.lower() == '.shp':
        Path(dst).parent.mkdir(parents=True, exist_ok=True)
        arcpy.management.CopyFeatures(str(src), str(dst))
        return str(dst)
    Path(dst).parent.mkdir(parents=True, exist_ok=True)
    arcpy.management.Copy(str(src), str(dst))
    return str(dst)

FIXED_PAR_0 = 'D:\\Work space\\DeepLearning\\farm\\results\\he015009_vectorized\\test\\HE015009_2024_1_repairgeometry.shp'

OUTPUT_DIR = './geomacro_output'
INPUT_GLOB = '*.shp'


def run_pipeline(input_file, output_dir=None):
    """Run the toolchain on a single input file."""
    output_dir = Path(output_dir or OUTPUT_DIR)
    output_dir.mkdir(parents=True, exist_ok=True)
    stem = Path(input_file).stem
    working = str(Path(input_file).resolve())

    stg_repairgeometry = str(output_dir / f'{stem}_repairgeometry{Path(working).suffix}')
    working = _copy_features_for_inplace(working, stg_repairgeometry)
    arcpy.management.RepairGeometry(working, 'true', 'ESRI')

    stg_repairgeometry2 = str(output_dir / f'{stem}_repairgeometry2{Path(working).suffix}')
    working = _copy_features_for_inplace(working, stg_repairgeometry2)
    arcpy.management.RepairGeometry(working, 'true', 'ESRI')

    stg_repairgeometry3 = str(output_dir / f'{stem}_repairgeometry3{Path(working).suffix}')
    working = _copy_features_for_inplace(working, stg_repairgeometry3)
    arcpy.management.RepairGeometry(working, 'true', 'ESRI')

    stg_repairgeometry4 = str(output_dir / f'{stem}_repairgeometry4{Path(working).suffix}')
    working = _copy_features_for_inplace(working, stg_repairgeometry4)
    arcpy.management.RepairGeometry(working, 'true', 'ESRI')

    stg_repairgeometry5 = str(output_dir / f'{stem}_repairgeometry5{Path(working).suffix}')
    working = _copy_features_for_inplace(working, stg_repairgeometry5)
    arcpy.management.RepairGeometry(working, 'true', 'ESRI')

    return working


def main(input_dir=None, output_dir=None):
    input_dir = Path(input_dir or '.')
    if output_dir is not None:
        odir = output_dir
    else:
        odir = OUTPUT_DIR
    Path(odir).mkdir(parents=True, exist_ok=True)

    candidates = sorted(input_dir.glob(INPUT_GLOB))
    if not candidates:
        print('[GeoMacro] No files matching ' + repr(INPUT_GLOB) + ' found in ' + str(input_dir))
        return

    print('[GeoMacro] Found', len(candidates), 'input file(s)')
    for candidate in candidates:
        print('  Processing', candidate.name, '...')
        try:
            result = run_pipeline(
                input_file=str(candidate),
                output_dir=odir,
            )
            label = Path(result).name if result else 'done'
            print('    -> ok:', label)
        except Exception as exc:
            print('    ERROR:', exc, file=sys.stderr)


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='GeoMacro batch pipeline')
    parser.add_argument('--input', '-i', default=None, help='Input directory (default: current dir)')
    parser.add_argument('--output', '-o', default=None, help='Output directory (default: ./geomacro_output)')
    args = parser.parse_args()
    main(input_dir=args.input, output_dir=args.output)
