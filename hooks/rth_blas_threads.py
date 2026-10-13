# PyInstaller runtime hook: runs before main.py in the frozen app.
# numpy's OpenBLAS on ONE thread before numpy loads, or a fork
# while another thread is inside OpenBLAS hangs the app for good
# (Knut, #182 6144104040, 4.3.5-beta.2). See core/blas_threads.py.
import os

os.environ["OPENBLAS_NUM_THREADS"] = "1"
os.environ["GOTO_NUM_THREADS"] = "1"
