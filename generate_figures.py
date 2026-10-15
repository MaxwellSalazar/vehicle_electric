from pathlib import Path
import os
import runpy


project_dir = Path(__file__).resolve().parent
os.chdir(project_dir)
runpy.run_path(
    str(project_dir / 'process_real_data_and_generate_figures.py'),
    run_name='__main__',
)
