import edward_exact_worker as worker
worker.owned()
def stop_at_boundary(stage, **values):
    worker.write('controlled_timing_stop.json',{'stage':stage,'values':values,
        'reason':'Post-edit exact-zero influence variants regressed strongly. Preserve completed diagnostic runs and switch to native-reopened comparison before acceptance.'})
    raise RuntimeError('Controlled stop at timing boundary; switch to native-reopened scene comparisons.')
worker.progress=stop_at_boundary
result={'stop_requested':True}
