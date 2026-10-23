"""Own one training child and its workers, with a two-hour hard deadline."""
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

run = Path(sys.argv[1]).resolve()
status = run.with_suffix('.job.json')
log = run.with_suffix('.log')
if run.exists() or status.exists() or log.exists():
    raise SystemExit('Refusing to overwrite an existing run/job/log')

def save(data):
    temp = status.with_suffix('.tmp')
    temp.write_text(json.dumps(data, indent=2)+'\n')
    temp.replace(status)

env = os.environ.copy()
for key in list(env):
    if key.startswith(('HSA_', 'HIP_', 'AMD_SERIALIZE')):
        env.pop(key)
env.update(HF_HUB_OFFLINE='1', OPENBLAS_NUM_THREADS='4', OMP_NUM_THREADS='4')
command = [str(Path.home()/'.venvs/rocm/bin/python'), '-u',
           str(Path(__file__).with_name('train_local_pilot.py')),
           '--run-dir', str(run), '--batch-size', '16', '--workers', '2',
           *sys.argv[2:]]
with log.open('x') as output:
    child = subprocess.Popen(command, env=env, stdout=output,
                             stderr=subprocess.STDOUT, start_new_session=True)
    state = {'state': 'running', 'runner_pid': os.getpid(), 'pid': child.pid,
             'started_at': time.time(), 'timeout_seconds': 7200,
             'run_dir': str(run), 'log': str(log), 'command': command,
             'boot_id': Path('/proc/sys/kernel/random/boot_id').read_text().strip()}
    save(state)
    try:
        rc = child.wait(timeout=7200)
        state.update(state='finished' if rc == 0 else 'failed', exit_code=rc)
    except subprocess.TimeoutExpired:
        os.killpg(child.pid, signal.SIGKILL)
        state.update(state='timed_out', exit_code=child.wait(timeout=15))
    finally:
        # Clean up only descendants in this task-owned process group.
        try:
            os.killpg(child.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        state['finished_at'] = time.time()
        state['kernel_taint_after'] = int(Path('/proc/sys/kernel/tainted').read_text())
        save(state)
