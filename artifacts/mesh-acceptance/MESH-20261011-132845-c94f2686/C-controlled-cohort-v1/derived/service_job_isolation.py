"""Read-only proof of separation from the supervisor's existing Windows Job.

C derived copy for round MESH-20261011-132845-c94f2686 (reference v7, sha256
57a2a1ff9cf808954bee83ce20d1cd5db12732110d2eaaf5004bfd5b5c1c4ade). Logic is
unchanged from the A reference: no privilege enablement, process termination,
job assignment or config change.
Native handle layout: winsiderss/phnt ntexapi.h SYSTEM_HANDLE_INFORMATION_EX.
Membership API: Microsoft's IsProcessInJob / QueryInformationJobObject.
"""
import ctypes
import os
from ctypes import wintypes as w

class HandleEntry(ctypes.Structure):
    _fields_ = [('object',ctypes.c_void_p),('owner',ctypes.c_size_t),
                ('handle',ctypes.c_size_t),('access',w.ULONG),
                ('backtrace',w.USHORT),('type',w.USHORT),
                ('attributes',w.ULONG),('reserved',w.ULONG)]

def verify_service_job_isolation(supervisor_pid, worker_pid):
    if type(supervisor_pid) is not int or type(worker_pid) is not int or min(supervisor_pid,worker_pid)<=0:
        raise ValueError('real original supervisor and worker PID required')
    k=ctypes.WinDLL('kernel32',use_last_error=True)
    signatures={
      'GetCurrentProcess':([],w.HANDLE), 'OpenProcess':([w.DWORD,w.BOOL,w.DWORD],w.HANDLE),
      'DuplicateHandle':([w.HANDLE,w.HANDLE,w.HANDLE,ctypes.POINTER(w.HANDLE),w.DWORD,w.BOOL,w.DWORD],w.BOOL),
      'QueryInformationJobObject':([w.HANDLE,ctypes.c_int,ctypes.c_void_p,w.DWORD,ctypes.POINTER(w.DWORD)],w.BOOL),
      'IsProcessInJob':([w.HANDLE,w.HANDLE,ctypes.POINTER(w.BOOL)],w.BOOL),
      'CloseHandle':([w.HANDLE],w.BOOL)}
    for name,(args,result) in signatures.items():
        f=getattr(k,name);f.argtypes=args;f.restype=result
    nt=ctypes.WinDLL('ntdll').NtQuerySystemInformation
    nt.argtypes=[w.ULONG,ctypes.c_void_p,w.ULONG,ctypes.POINTER(w.ULONG)];nt.restype=ctypes.c_long
    size=1024*1024
    while size<=64*1024*1024:
        data=ctypes.create_string_buffer(size);required=w.ULONG()
        status=nt(64,data,size,ctypes.byref(required))
        if status==0:break
        if status & 0xffffffff not in (0xc0000004,0xc0000023):
            raise OSError('read-only system handle query failed: '+hex(status & 0xffffffff))
        size=max(size*2,required.value+65536)
    else:raise OSError('system handle snapshot exceeds bounded capacity')
    count=ctypes.c_size_t.from_buffer(data).value
    offset=2*ctypes.sizeof(ctypes.c_size_t)
    if count>(size-offset)//ctypes.sizeof(HandleEntry):raise ValueError('handle snapshot malformed')
    source=k.OpenProcess(0x0040,False,supervisor_pid)  # duplicate only existing handles
    if not source:raise ctypes.WinError(ctypes.get_last_error())
    current=k.GetCurrentProcess();proof=[]
    try:
        entries=(HandleEntry*count).from_buffer(data,offset)
        for entry in entries:
            if entry.owner!=supervisor_pid or not entry.access & 4:continue
            duplicate=w.HANDLE()
            if not k.DuplicateHandle(source,w.HANDLE(entry.handle),current,ctypes.byref(duplicate),0,False,2):
                continue
            try:
                jobs=ctypes.create_string_buffer(65536);returned=w.DWORD()
                if not k.QueryInformationJobObject(duplicate,3,jobs,len(jobs),ctypes.byref(returned)):
                    continue
                members=w.ULONG.from_buffer(jobs,4).value
                if members>(len(jobs)-8)//ctypes.sizeof(ctypes.c_size_t):raise ValueError('job snapshot malformed')
                pids=list((ctypes.c_size_t*members).from_buffer(jobs,8))
                if worker_pid not in pids:continue
                inside=w.BOOL()
                if not k.IsProcessInJob(current,duplicate,ctypes.byref(inside)):
                    raise ctypes.WinError(ctypes.get_last_error())
                proof.append({'supervisor_job_handle':entry.handle,'job_member_pids':pids,
                              'current_process_in_service_job':bool(inside.value)})
            finally:k.CloseHandle(duplicate)
    finally:k.CloseHandle(source)
    if not proof:raise RuntimeError('original worker Job could not be identified; no isolation proof')
    if any(p['current_process_in_service_job'] for p in proof):
        raise RuntimeError('watcher is in original service Job; no stop allowed')
    return {'pid':os.getpid(),'supervisor_pid':supervisor_pid,'worker_pid':worker_pid,
            'isolation_verified':True,'read_only':True,'jobs':proof}
